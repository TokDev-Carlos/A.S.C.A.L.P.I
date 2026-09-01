from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PATCHABLE=("App/","Host/Bridge/","Dev/Host/","Dev/Tools/","Docs/","Updates/Apply-Master.ps1","Updates/Apply-Worker.ps1")
PROTECTED=("Runtime/","Data/","Shared/","Repo/","Logs/","Temp/","Export/","Host/Bin/")
GENERATED={"App/Config/app.integrity.json","App/Config/master.id","App/Config/provenance.json","App/Config/repository.anchor.json","Updates/State/atual.json","Host/launcher-build.json","CJL.exe","CJL.root.json","CJL.branch.json"}
MAX_MEMBERS=20000;MAX_TOTAL=2*1024**3;MAX_MEMBER=512*1024**2

def now_sp():
    try:return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:return datetime.now(timezone(timedelta(hours=-3)))

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def read(p):
    try:v=json.loads(Path(p).read_text(encoding="utf-8"));return v if isinstance(v,dict) else {}
    except Exception:return {}

def writej(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(t,p)

def identity(cfg):
    v=cfg.get("versioning") or {};x=(int(v["business"]),int(v["structural"]),int(v["incremental"]),int(v["security"]),int(v["compat_sequence"]));core=f"{x[1]}.{x[2]:02d}.{x[3]:03d}";public=f"{x[0]}.{x[1]:02d}.{x[2]:02d}.{x[3]:03d}"
    if cfg.get("version")!=core or str(cfg.get("version_full") or "")!=public:raise RuntimeError("Identidade CJL divergiu.")
    return x,core,public

def safe_rel(v):
    t=str(v or "").replace("\\","/").strip("/");p=Path(t)
    if not t or p.is_absolute() or ".." in p.parts:raise RuntimeError("Path de patch invalido.")
    if t in GENERATED or any(t==x.rstrip("/") or t.startswith(x) for x in PROTECTED):raise RuntimeError("Patch tentou alterar gerado/protegido: "+t)
    if not any(t==x or t.startswith(x) for x in PATCHABLE):raise RuntimeError("Path fora do contrato patchable: "+t)
    return t

def run(cmd,cwd):
    p=subprocess.run([str(x) for x in cmd],cwd=str(cwd),capture_output=True,text=True,encoding="utf-8",errors="replace")
    if p.returncode!=0:raise RuntimeError("Comando falhou: "+" ".join(map(str,cmd))+"\n"+(p.stdout or "")+"\n"+(p.stderr or ""))
    return p.stdout

def extract(z,d):
    with zipfile.ZipFile(z) as a:
        ms=a.infolist();total=0;seen=set();base=d.resolve();bad=a.testzip()
        if bad:raise RuntimeError("ZIP corrompido: "+bad)
        if not ms or len(ms)>MAX_MEMBERS:raise RuntimeError("ZIP invalido.")
        for m in ms:
            n=str(m.filename or "").replace("\\","/");p=Path(n);total+=int(m.file_size or 0)
            if not n or "\x00" in n or n.startswith("/") or (m.flag_bits&1) or p.is_absolute() or ".." in p.parts or n.casefold() in seen or int(m.file_size or 0)>MAX_MEMBER or total>MAX_TOTAL:raise RuntimeError("Membro ZIP invalido.")
            seen.add(n.casefold());(d/n).resolve().relative_to(base)
        a.extractall(d)
    if (d/"patch.json").is_file():return d
    hits=list(d.glob("*/patch.json"))
    if len(hits)!=1:raise RuntimeError("patch.json ambiguo/ausente.")
    return hits[0].parent

def promotion_gate(root,patch,manifest,branch):
    if branch!="MAIN":return
    sm=root.parent/"SM_Repo";digest=sha(patch);receipt=sm/"Promotions"/"Approved"/(digest+".json");value=read(receipt)
    if not receipt.is_file() or int(value.get("format") or 0)!=1 or value.get("status")!="APPROVED" or value.get("patch_sha256")!=digest or value.get("patch_id")!=manifest.get("patch_id"):
        raise RuntimeError("MAIN exige aprovacao previa do MESMO ZIP na Branch DEV por SHA-256.")

def validate_patch(root,pr,patch,branch):
    cfg=read(root/"App/Config/sistema.json");cur,core,public=identity(cfg);m=read(pr/"patch.json")
    if int(m.get("format") or 0)!=7 or m.get("root_contract")!="RELATIVE_TO_SELECTED_CJL_ROOT" or m.get("branch_contract")!="SAME_PACKAGE_DEV_THEN_MAIN":raise RuntimeError("Patch nao usa contrato Branch Format 7.")
    src=m.get("source") or {};dst=m.get("target") or {};s=(int(src["business"]),int(src["structural"]),int(src["incremental"]),int(src["security"]),int(src["compat_sequence"]))
    if s!=cur or src.get("version")!=core or src.get("version_full")!=public or int(src.get("build") or -1)!=int(cfg.get("build") or -2):raise RuntimeError("Patch construido para outra baseline.")
    promotion_gate(root,patch,m,branch)
    ops=[];seen=set()
    for x in m.get("operations") or []:
        a=str(x.get("action") or "").upper();rel=safe_rel(x.get("path"));curp=root/rel;before=str(x.get("sha256_before") or "").lower();after=str(x.get("sha256_after") or "").lower()
        if a not in {"ADD","REPLACE","REMOVE"} or rel.casefold() in seen:raise RuntimeError("Operacao invalida/duplicada.")
        seen.add(rel.casefold())
        if a in {"REPLACE","REMOVE"} and (not curp.is_file() or sha(curp)!=before):raise RuntimeError("Baseline divergiu em "+rel)
        if a=="ADD" and curp.exists():raise RuntimeError("ADD colide: "+rel)
        pp=pr/"Payload"/rel
        if a in {"ADD","REPLACE"} and (not pp.is_file() or sha(pp)!=after):raise RuntimeError("Payload divergiu: "+rel)
        ops.append({"action":a,"path":rel,"before":before,"after":after})
    if not ops:raise RuntimeError("Patch sem operacoes.")
    if bool(m.get("host_rebuild"))!=any(x["path"].startswith(("Dev/Host/","Host/Bridge/")) for x in ops):raise RuntimeError("host_rebuild diverge das operacoes.")
    rules=m.get("rules")
    if not isinstance(rules,dict):raise RuntimeError("Patch sem metadados da Regra Mestra.")
    sys.path.insert(0,str(root/"App"))
    from Core.cumulativity import metadata as rules_metadata, parse_volume, logical_sha256, semantic_changes
    current_rules=rules_metadata(root);source_rules=rules.get("source") or {}
    for key in ("count","last_rule","logical_sha256"):
        if str(current_rules.get(key))!=str(source_rules.get(key)):raise RuntimeError("Baseline da Regra Mestra divergiu em "+key)
    target_rules=rules.get("target") or {};declared=[str(x).strip().upper() for x in (rules.get("declared_rules") or []) if str(x).strip()]
    recomputed=[]
    for x in ops:
        if x["action"]=="REPLACE":
            items=semantic_changes(root/x["path"],pr/"Payload"/x["path"])
            if items:recomputed.append({"path":x["path"],"classification":"SEMANTIC_CHANGE","items":items})
        elif x["action"]=="REMOVE":recomputed.append({"path":x["path"],"classification":"FILE_REMOVAL","items":[x["path"]]})
    if recomputed and not declared:raise RuntimeError("Patch possui alteracao/remocao semantica sem regra declarada.")
    if json.dumps(recomputed,ensure_ascii=False,sort_keys=True)!=json.dumps(rules.get("semantic_findings") or [],ensure_ascii=False,sort_keys=True):raise RuntimeError("Achados semanticos divergem da recomputacao local.")
    rule_rel=str(target_rules.get("volume") or current_rules.get("volume") or "");payload_rule=pr/"Payload"/rule_rel
    if payload_rule.is_file():
        parsed=parse_volume(payload_rule);base_parsed=parse_volume(root/rule_rel)
        if str(len(parsed))!=str(target_rules.get("count")) or parsed[-1].rule_id!=target_rules.get("last_rule") or logical_sha256(parsed)!=target_rules.get("logical_sha256"):raise RuntimeError("Volume de Regras alvo diverge do manifesto.")
        if len(parsed)<len(base_parsed) or any(a.line!=b.line for a,b in zip(base_parsed,parsed[:len(base_parsed)])):raise RuntimeError("Patch tentou reescrever/reordenar regra historica.")
        ids={r.rule_id for r in parsed};invalid=[x for x in declared if x not in ids]
        if invalid:raise RuntimeError("Regra declarada ausente no Volume alvo: "+", ".join(invalid))
    elif str(current_rules.get("logical_sha256"))!=str(target_rules.get("logical_sha256")):
        raise RuntimeError("Manifesto declara Regra Mestra alvo diferente sem transportar o Volume.")
    return m,ops

def state_payload(root,m,branch):
    d=m["target"];mid=(root/"App/Config/master.id").read_text(encoding="utf-8").strip().upper()
    return {"format":4,"product":"CJL System","product_code":"CJL","business":int(d["business"]),"business_id":f"BA-{int(d['business']):02d}","version":d["version"],"version_full":d["version_full"],"structural":int(d["structural"]),"incremental":int(d["incremental"]),"security":int(d["security"]),"patches":{"business":f"BA-{int(d['business']):02d}","structural":f"ES-{int(d['structural']):02d}","incremental":f"IN-{int(d['incremental']):02d}","security":f"SE-{int(d['security']):03d}"},"compat_sequence":int(d["compat_sequence"]),"schema":int(d["schema"]),"runtime":int(d["runtime"]),"build":int(d["build"]),"master_id":mid,"channel":"STABLE","branch":branch,"branch_role":"PRODUCTION" if branch=="MAIN" else "DEVELOPMENT","minimum_station_version":d["version"],"minimum_station_compat":int(d["compat_sequence"]),"last_update_mode":"CRITICAL","last_update_type":m["primary_type"],"timezone":"America/Sao_Paulo","last_patch_id":m["patch_id"],"patch_sha256":""}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--patch");ap.add_argument("--validate-only",action="store_true");ns=ap.parse_args();root=Path(ns.root).resolve();python=root/"Runtime/Python/python.exe"
    sys.path.insert(0,str(root/"Runtime/Python/Lib/site-packages"));sys.path.insert(0,str(root/"App"));from Core.branch import read_branch;from Core.sm_repo import ensure_structure,copy_file_verified,append_index;from Core.system_history import append_event
    branch=read_branch(root)["branch"];run([python,"-B","-I","-S",root/"App/Validacao/validar_sistema.py",root],root)
    patch=Path(ns.patch).resolve() if ns.patch else None
    if patch is None:
        cs=list((root/"Updates/In").glob("*.zip"))
        if len(cs)!=1:raise RuntimeError(f"Esperado 1 patch em Updates/In; encontrados {len(cs)}.")
        patch=cs[0]
    patch_digest=sha(patch);td=root/"Temp"/("CJL_Patch7_"+now_sp().strftime("%Y%m%d_%H%M%S")+"_"+os.urandom(3).hex());td.mkdir(parents=True,exist_ok=False)
    try:
        pr=extract(patch,td);m,ops=validate_patch(root,pr,patch,branch)
        if ns.validate_only:print(json.dumps({"ok":True,"branch":branch,"patch_id":m["patch_id"],"patch_sha256":patch_digest,"operations":len(ops),"host_rebuild":bool(m.get("host_rebuild"))},indent=2));return 0
        sm=ensure_structure(root);runid=now_sp().strftime("%Y%m%dT%H%M%S")+"_"+os.urandom(3).hex().upper();backup=sm["patch_backups"]/runid;backup.mkdir(parents=True);backed=[]
        for rel in sorted({x["path"] for x in ops}|{"App/Config/app.integrity.json","App/Config/provenance.json","Updates/State/atual.json","CJL.root.json","Host/launcher-build.json","CJL.exe"},key=str.casefold):
            s=root/rel
            if s.is_file():d=backup/rel;res=copy_file_verified(s,d);backed.append({"path":rel,"sha256":res["sha256"]})
        if bool(m.get("host_rebuild")) and (root/"Host/Bin").is_dir():shutil.copytree(root/"Host/Bin",backup/"Host/Bin")
        (backup/"backup.json").write_text(json.dumps({"format":2,"patch_id":m["patch_id"],"patch_sha256":patch_digest,"branch":branch,"files":backed,"host_bin_backed_up":(backup/"Host/Bin").is_dir()},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        applied=[]
        try:
            append_event(root,"PATCH_BEGIN",branch=branch,patch_id=m["patch_id"],patch_sha256=patch_digest,target_version=m["target"]["version_full"])
            for x in ops:
                dest=root/x["path"]
                if x["action"]=="REMOVE":dest.unlink()
                else:
                    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_name(dest.name+".cjl.tmp");shutil.copy2(pr/"Payload"/x["path"],tmp)
                    if sha(tmp)!=x["after"]:raise RuntimeError("SHA temporario divergiu: "+x["path"])
                    os.replace(tmp,dest)
                applied.append(x)
            state=state_payload(root,m,branch);state["patch_sha256"]=patch_digest;writej(root/"Updates/State/atual.json",state)
            marker=read(root/"CJL.root.json");marker.update({"version":m["target"]["version"],"version_full":m["target"]["version_full"],"incremental_id":f"IN-{int(m['target']['incremental']):02d}","security_id":f"SE-{int(m['target']['security']):03d}","branch":branch,"branch_contract":1});writej(root/"CJL.root.json",marker)
            prov=read(root/"App/Config/provenance.json");prov.update({"current_version":m["target"]["version"],"current_version_full":m["target"]["version_full"],"current_incremental":f"IN-{int(m['target']['incremental']):02d}","current_security":f"SE-{int(m['target']['security']):03d}","current_build":int(m["target"]["build"]),"branch_contract":1});writej(root/"App/Config/provenance.json",prov)
            run([python,"-B","-I","-S",root/"Dev/Tools/build_integrity.py","--root",root],root)
            if bool(m.get("host_rebuild")):run(["powershell.exe","-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",root/"Dev/Host/Bootstrap/Prepare-Host.ps1","-Root",root],root)
            run([python,"-B","-I","-S",root/"App/Validacao/validar_sistema.py",root],root)
            archive=sm["patch_archive"]/patch.name;copy_file_verified(patch,archive);append_event(root,"PATCH_SUCCEEDED",branch=branch,patch_id=m["patch_id"],patch_sha256=patch_digest,target_version=m["target"]["version_full"]);append_index(root,{"type":"PATCH_APPLIED","branch":branch,"patch_id":m["patch_id"],"patch_sha256":patch_digest,"archive":str(archive),"backup":str(backup),"version_full":m["target"]["version_full"]});patch.unlink(missing_ok=True)
            print(json.dumps({"ok":True,"branch":branch,"patch_id":m["patch_id"],"patch_sha256":patch_digest,"version_full":m["target"]["version_full"]},indent=2));return 0
        except Exception as exc:
            for x in reversed(applied):
                dest=root/x["path"];src=backup/x["path"]
                if src.is_file():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
                else:dest.unlink(missing_ok=True)
            for rel in ["App/Config/app.integrity.json","App/Config/provenance.json","Updates/State/atual.json","CJL.root.json","Host/launcher-build.json","CJL.exe"]:
                src=backup/rel;dest=root/rel
                if src.is_file():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
            if (backup/"Host/Bin").is_dir():shutil.rmtree(root/"Host/Bin",ignore_errors=True);shutil.copytree(backup/"Host/Bin",root/"Host/Bin")
            append_index(root,{"type":"PATCH_FAILED_ROLLBACK","branch":branch,"patch_id":m["patch_id"],"patch_sha256":patch_digest,"backup":str(backup),"error":str(exc)});raise
    finally:shutil.rmtree(td,ignore_errors=True)
if __name__=="__main__":
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:print("FALHA: "+str(exc),file=sys.stderr);raise SystemExit(1)
