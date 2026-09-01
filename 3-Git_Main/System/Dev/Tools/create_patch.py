from __future__ import annotations
import argparse, hashlib, json, shutil, sys, tempfile, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PATCHABLE=("App/","Host/Bridge/","Dev/Host/","Dev/Tools/","Docs/","Updates/Apply-Master.ps1","Updates/Apply-Worker.ps1")
PROTECTED=("Runtime/","Data/","Shared/","Repo/","Logs/","Temp/","Export/","Host/Bin/")
GENERATED={"App/Config/app.integrity.json","App/Config/master.id","App/Config/provenance.json","App/Config/repository.anchor.json","Updates/State/atual.json","Host/launcher-build.json","CJL.exe","CJL.root.json","CJL.branch.json"}
IGNORED_PARTS={"__pycache__","bin","obj",".git",".pytest_cache"}
IGNORED_SUFFIX={".pyc",".pyo",".tmp"}

def now_sp():
    try:return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:return datetime.now(timezone(timedelta(hours=-3)))

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def read(p):
    v=json.loads(Path(p).read_text(encoding="utf-8"))
    if not isinstance(v,dict):raise RuntimeError(f"JSON invalido: {p}")
    return v

def identity(cfg):
    v=cfg.get("versioning")
    if not isinstance(v,dict):raise RuntimeError("versioning ausente.")
    x=(int(v["business"]),int(v["structural"]),int(v["incremental"]),int(v["security"]),int(v["compat_sequence"]))
    core=f"{x[1]}.{x[2]:02d}.{x[3]:03d}";public=f"{x[0]}.{x[1]:02d}.{x[2]:02d}.{x[3]:03d}"
    if cfg.get("project_name")!="CJL System" or int(cfg.get("layout_version") or 0)!=5 or str(cfg.get("version"))!=core or str(cfg.get("version_full"))!=public:
        raise RuntimeError("Identidade CJL invalida.")
    return x,core,public

def transition(kind,s,t):
    sb,se,si,ss,sc=s;tb,te,ti,ts,tc=t
    if tc!=sc+1 or ts!=ss+1:raise RuntimeError("Toda release fisica incrementa compat_sequence e SE em 1.")
    ok=(kind=="IN" and (tb,te,ti)==(sb,se,si+1)) or (kind=="ES" and (tb,te,ti)==(sb,se+1,0)) or (kind=="SE" and (tb,te,ti)==(sb,se,si)) or (kind=="BA" and tb==sb+1 and ((te,ti)==(se,si+1) or (te,ti)==(se+1,0)))
    if not ok:raise RuntimeError("Transicao BA/ES/IN/SE invalida.")

def allowed(rel):
    rel=rel.replace("\\","/")
    if rel in GENERATED or any(rel==p.rstrip("/") or rel.startswith(p) for p in PROTECTED):return False
    p=Path(rel)
    if any(x.casefold() in IGNORED_PARTS for x in p.parts) or p.suffix.casefold() in IGNORED_SUFFIX:return False
    return any(rel==x or rel.startswith(x) for x in PATCHABLE)

def files(root):
    return {p.relative_to(root).as_posix():p for p in Path(root).rglob("*") if p.is_file() and not p.is_symlink() and allowed(p.relative_to(root).as_posix())}

def main():
    ap=argparse.ArgumentParser(description="Cria CJL Patch Format 7 branch-neutral")
    ap.add_argument("--base",required=True);ap.add_argument("--target",required=True);ap.add_argument("--output",required=True)
    ap.add_argument("--type",required=True,choices=["BA","ES","IN","SE"]);ap.add_argument("--package-version",type=int,default=1)
    ap.add_argument("--security-note",required=True);ap.add_argument("--declared-rule",action="append",default=[])
    ns=ap.parse_args();base=Path(ns.base).resolve();target=Path(ns.target).resolve();out=Path(ns.output).resolve()
    bc=read(base/"App/Config/sistema.json");tc=read(target/"App/Config/sistema.json")
    src,src_core,src_full=identity(bc);dst,dst_core,dst_full=identity(tc);transition(ns.type,src,dst)
    if int(tc.get("build") or 0)<=int(bc.get("build") or 0):raise RuntimeError("Target build deve ser maior.")
    bf,tf=files(base),files(target);ops=[]
    for rel in sorted(set(bf)|set(tf),key=str.casefold):
        if rel in bf and rel in tf:
            a,b=sha(bf[rel]),sha(tf[rel])
            if a!=b:ops.append({"action":"REPLACE","path":rel,"sha256_before":a,"sha256_after":b})
        elif rel in tf:ops.append({"action":"ADD","path":rel,"sha256_before":"","sha256_after":sha(tf[rel])})
        else:ops.append({"action":"REMOVE","path":rel,"sha256_before":sha(bf[rel]),"sha256_after":""})
    if not ops:raise RuntimeError("Nenhuma alteracao patchable.")
    sys.path.insert(0,str(target/"App"))
    from Core.cumulativity import audit_release_pair, parse_volume, rules_paths
    audit=audit_release_pair(base,target,files=[x["path"] for x in ops])
    declared=[str(x).strip().upper() for x in ns.declared_rule if str(x).strip()]
    target_ids={r.rule_id for r in parse_volume(rules_paths(target)[0])}
    invalid=[x for x in declared if x not in target_ids]
    if invalid:raise RuntimeError("Regra declarada inexistente no target: "+", ".join(invalid))
    if audit.get("findings") and not declared:
        raise RuntimeError("Auditoria semantica detectou alteracao/remocao e exige --declared-rule: "+json.dumps(audit["findings"],ensure_ascii=False))
    created=now_sp();pv=int(ns.package_version);patch_id=f"CJL_B{dst[0]:02d}_E{dst[1]:02d}_I{dst[2]:02d}_S{dst[3]:03d}_V{pv:02d}_{created.strftime('%Y%m%dT%H%M%S')}"
    host_rebuild=any(op["path"].startswith(("Dev/Host/","Host/Bridge/")) for op in ops)
    def ident(cfg,x,core,public):return {"business":x[0],"business_id":f"BA-{x[0]:02d}","version":core,"version_full":public,"version_core":core,"structural":x[1],"incremental":x[2],"security":x[3],"compat_sequence":x[4],"build":int(cfg["build"]),"schema":int(cfg["schema_version"]),"runtime":int(cfg["runtime_version"])}
    manifest={"format":7,"product":"CJL System","product_code":"CJL","layout":5,"patch_id":patch_id,"primary_type":ns.type,"package_version":pv,"created_at":created.isoformat(timespec="seconds"),"timezone":"America/Sao_Paulo","mode":"CRITICAL","root_contract":"RELATIVE_TO_SELECTED_CJL_ROOT","branch_contract":"SAME_PACKAGE_DEV_THEN_MAIN","source":ident(bc,src,src_core,src_full),"target":ident(tc,dst,dst_core,dst_full),"security_gate":{"required":True,"reviewed":True,"baseline_before":f"SE-{src[3]:03d}","baseline_after":f"SE-{dst[3]:03d}","security_changed":True,"note":ns.security_note},"host_rebuild":host_rebuild,"promotion":{"dev_first":True,"main_requires_same_zip_sha256_approval":True},"rules":{"source":audit["rules"]["source"],"target":audit["rules"]["target"],"added_rules":audit["rules"]["added_rules"],"declared_rules":declared,"semantic_findings":audit.get("findings") or []},"data_policy":"NO_OPERATIONAL_USER_DATA_IN_PATCH","operations":ops,"integrity":"SHA256_EXACT_BASELINE_AND_PAYLOAD","signature":"UNSIGNED_OPERATOR_PACKAGE","archive_contract":"SM_REPO_V1"}
    zpath=out if out.suffix.lower()==".zip" else out/(patch_id+".zip");zpath.parent.mkdir(parents=True,exist_ok=True);zpath.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="cjl_patch7_") as td:
        pkg=Path(td)/patch_id;(pkg/"Payload").mkdir(parents=True);(pkg/"patch.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        for op in ops:
            if op["action"] in {"ADD","REPLACE"}:
                d=pkg/"Payload"/op["path"];d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(tf[op["path"]],d)
        with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in sorted(pkg.rglob("*")):
                if p.is_file():z.write(p,p.relative_to(pkg.parent).as_posix())
    digest=sha(zpath);zpath.with_suffix(zpath.suffix+".sha256").write_text(f"{digest}  {zpath.name}\n",encoding="ascii")
    print(json.dumps({"ok":True,"patch_id":patch_id,"zip":str(zpath),"sha256":digest,"operations":len(ops),"host_rebuild":host_rebuild,"declared_rules":declared,"semantic_findings":len(audit.get("findings") or [])},ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
