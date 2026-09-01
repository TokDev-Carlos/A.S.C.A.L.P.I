from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, subprocess, sys, tempfile, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TECH_DIRS=("App","Host","Runtime","Updates","Docs","Dev")
EMPTY_DIRS=("Data","Shared","Repo","Logs","Temp","Export")
ROOT_FILES=("CJL.exe","CJL.root.json","COPYRIGHT.txt","LICENSE.txt")
PATCHABLE=("App/","Host/Bridge/","Dev/Host/","Dev/Tools/","Docs/","Updates/Apply-Master.ps1","Updates/Apply-Worker.ps1")
PROTECTED=("Runtime/","Data/","Shared/","Repo/","Logs/","Temp/","Export/","Host/Bin/")
GENERATED={"App/Config/app.integrity.json","App/Config/master.id","App/Config/provenance.json","App/Config/repository.anchor.json","Updates/State/atual.json","Host/launcher-build.json","CJL.exe","CJL.root.json","CJL.branch.json"}

def now_sp():
    try:return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:return datetime.now(timezone(timedelta(hours=-3)))
def sha(path):
    h=hashlib.sha256();
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def readj(p):
    try:v=json.loads(Path(p).read_text(encoding="utf-8"));return v if isinstance(v,dict) else {}
    except Exception:return {}
def writej(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(t,p)
def allowed(rel):
    rel=rel.replace("\\","/")
    if rel in GENERATED or any(rel==p.rstrip("/") or rel.startswith(p) for p in PROTECTED):return False
    parts=Path(rel).parts
    if any(x.casefold() in {"__pycache__","bin","obj",".git",".pytest_cache"} for x in parts) or Path(rel).suffix.casefold() in {".pyc",".pyo",".tmp"}:return False
    return any(rel==x or rel.startswith(x) for x in PATCHABLE)
def surface(root):
    root=Path(root).resolve();rows=[]
    for p in root.rglob("*"):
        if p.is_file() and not p.is_symlink():
            rel=p.relative_to(root).as_posix()
            if allowed(rel):rows.append((rel,sha(p)))
    rows.sort(key=lambda x:x[0].casefold());h=hashlib.sha256()
    for rel,d in rows:h.update((rel+"\n"+d+"\n").encode("utf-8"))
    return h.hexdigest(),rows
def run(cmd,cwd=None):
    p=subprocess.run([str(x) for x in cmd],cwd=str(cwd) if cwd else None,text=True,capture_output=True,encoding="utf-8",errors="replace")
    if p.returncode not in (0,1,2,3,4,5,6,7):raise RuntimeError("Comando falhou: "+" ".join(map(str,cmd))+"\n"+(p.stdout or "")+"\n"+(p.stderr or ""))
    return p
def copy_tree(src,dst):
    src=Path(src);dst=Path(dst)
    if os.name=="nt":
        dst.mkdir(parents=True,exist_ok=True);p=run(["robocopy",src,dst,"/MIR","/COPY:DAT","/DCOPY:DAT","/R:2","/W:1","/XJ","/NFL","/NDL","/NP"])
        if p.returncode>7:raise RuntimeError(f"Robocopy falhou {p.returncode}: {src} -> {dst}")
    else:shutil.copytree(src,dst,dirs_exist_ok=True)
def ensure_admin():
    if os.name!="nt":return
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError("Execute como Administrador do Windows/CJLAdmin.")
def powershell(script):
    p=subprocess.run(["powershell.exe","-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-Command",script],text=True,capture_output=True,encoding="utf-8",errors="replace")
    if p.returncode!=0:raise RuntimeError((p.stderr or p.stdout or f"PowerShell {p.returncode}").strip())
    return p.stdout
def configure_share(container,share_name):
    if os.name!="nt":return False
    q=lambda s:"'"+str(s).replace("'","''")+"'"
    script=("$ErrorActionPreference='Stop';"
            f"$name={q(share_name)};$path={q(str(container))};"
            "$acct=\"$env:COMPUTERNAME\\CJLAdmin\";$created=$false;"
            "try{"
            "$null=(New-Object System.Security.Principal.NTAccount($acct)).Translate([System.Security.Principal.SecurityIdentifier]);"
            "$s=Get-SmbShare -Name $name -ErrorAction SilentlyContinue;"
            "if($s -and ([IO.Path]::GetFullPath($s.Path).TrimEnd('\\') -ne [IO.Path]::GetFullPath($path).TrimEnd('\\'))){throw \"Share $name existe em outro caminho: $($s.Path)\"};"
            "if(-not $s){New-SmbShare -Name $name -Path $path -FullAccess $acct -CachingMode None | Out-Null;$created=$true}else{Grant-SmbShareAccess -Name $name -AccountName $acct -AccessRight Full -Force | Out-Null};"
            "& icacls.exe $path /grant (\"{0}:(OI)(CI)F\" -f $acct) /T /C | Out-Null;"
            "if($LASTEXITCODE -ne 0){throw (\"icacls falhou com codigo {0}\" -f $LASTEXITCODE)};"
            "Write-Output (\"CJL_SHARE_CREATED={0}\" -f ([int]$created))"
            "}catch{if($created){Remove-SmbShare -Name $name -Force -ErrorAction SilentlyContinue};throw}")
    out=powershell(script)
    return "CJL_SHARE_CREATED=1" in out

def remove_share_if_created(share_name,created):
    if os.name!="nt" or not created:return
    q=lambda s:"'"+str(s).replace("'","''")+"'"
    powershell(f"$ErrorActionPreference='Stop';$name={q(share_name)};if(Get-SmbShare -Name $name -ErrorAction SilentlyContinue){{Remove-SmbShare -Name $name -Force}}")

def provision(main_root,container,share_name):
    ensure_admin(); main_root=Path(main_root).resolve();container=Path(container).resolve();dev_root=container/"Sistema_Dev"
    sys.path.insert(0,str(main_root/"Runtime/Python/Lib/site-packages"));sys.path.insert(0,str(main_root/"App"))
    from Core.branch import read_branch,write_branch
    from Core.sm_repo import ensure_structure,append_index
    main_marker=read_branch(main_root)
    if main_marker["branch"]!="MAIN":raise RuntimeError("Origem precisa ser Branch MAIN.")
    cfg=readj(main_root/"App/Config/sistema.json");expected_share=str((cfg.get("branching") or {}).get("dev_share_name") or ".Dev CJL$")
    if share_name!=expected_share:raise RuntimeError(f"Share deve obedecer ao contrato: {expected_share}")
    runid=now_sp().strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8].upper();stage=container/(".Stage_"+runid)/"Sistema_Dev"
    if stage.parent.exists():shutil.rmtree(stage.parent)
    stage.mkdir(parents=True);container.mkdir(parents=True,exist_ok=True)
    try:
        for name in TECH_DIRS:copy_tree(main_root/name,stage/name)
        for name in EMPTY_DIRS:(stage/name).mkdir(parents=True,exist_ok=True)
        for name in ROOT_FILES:shutil.copy2(main_root/name,stage/name)
        # Temporary marker is valid only while the candidate is in staging. It is rewritten
        # after the atomic promotion so the physical-root fingerprint can never point to .Stage_*.
        mid=(stage/"App/Config/master.id").read_text(encoding="utf-8").strip().upper()
        write_branch(stage,"DEV","DEVELOPMENT",master_id=mid,source_root=str(main_root),share_name=share_name)
        root_marker=readj(stage/"CJL.root.json");root_marker.update({"role":"DEVELOPMENT","branch":"DEV","branch_contract":1,"source_main_root_hint":str(main_root),"version_full":str(cfg.get("version_full") or "")});writej(stage/"CJL.root.json",root_marker)
        state=readj(stage/"Updates/State/atual.json");state.update({"channel":"STABLE","branch":"DEV","branch_role":"DEVELOPMENT","version_full":str(cfg.get("version_full") or "")});writej(stage/"Updates/State/atual.json",state)
        updates_in=stage/"Updates/In"
        if updates_in.exists():
            for item in list(updates_in.iterdir()):
                if item.is_dir():shutil.rmtree(item)
                else:item.unlink()
        (stage/"Updates/State/operation.json").unlink(missing_ok=True)
        # DEV must not receive operational content.
        for name in ("Data","Shared","Repo"):
            if any((stage/name).iterdir()):raise RuntimeError(f"Dados operacionais encontrados no DEV: {name}")
        py=stage/"Runtime/Python/python.exe" if os.name=="nt" else Path(sys.executable)
        validator=stage/"App/Validacao/validar_sistema.py"
        if os.name=="nt":
            p=subprocess.run([str(py),"-B","-I","-S",str(validator),str(stage)],text=True,capture_output=True,encoding="utf-8",errors="replace")
            if p.returncode!=0:raise RuntimeError("Validacao DEV falhou: "+(p.stderr or p.stdout))
        main_hash,_=surface(main_root);dev_hash,_=surface(stage)
        if main_hash!=dev_hash:raise RuntimeError("Superficie patchable MAIN/DEV divergiu durante provisionamento.")
        # Prepare container contract from the user-approved layout.
        for p in [container/"Patches/Launcher",container/"Patches/Painel Remoto",container/"Patches/Sistema"]:p.mkdir(parents=True,exist_ok=True)
        (container/"readme.txt").write_text(str(container)+"\n",encoding="utf-8")
        dev_recovery=container/"SM_Repo/Recovery"
        dev_recovery.mkdir(parents=True,exist_ok=True)
        old=None; promoted=False
        if dev_root.exists():
            old=dev_recovery/("PreviousDev_"+runid);os.replace(dev_root,old)
        os.replace(stage,dev_root);promoted=True;shutil.rmtree(stage.parent,ignore_errors=True)
        # Rewrite all branch-generated identity only after final path exists. This is mandatory
        # because CJL.branch.json binds the physical root by fingerprint.
        mid=(dev_root/"App/Config/master.id").read_text(encoding="utf-8").strip().upper()
        write_branch(dev_root,"DEV","DEVELOPMENT",master_id=mid,source_root=str(main_root),share_name=share_name)
        root_marker=readj(dev_root/"CJL.root.json");root_marker.update({"role":"DEVELOPMENT","branch":"DEV","branch_contract":1,"source_main_root_hint":str(main_root),"version_full":str(cfg.get("version_full") or "")});writej(dev_root/"CJL.root.json",root_marker)
        state=readj(dev_root/"Updates/State/atual.json");state.update({"channel":"STABLE","branch":"DEV","branch_role":"DEVELOPMENT","version_full":str(cfg.get("version_full") or "")});writej(dev_root/"Updates/State/atual.json",state)
        ensure_structure(dev_root)
        # Validate again at FINAL physical path; staging validation is not enough for root-bound identity.
        if os.name=="nt":
            py=dev_root/"Runtime/Python/python.exe";validator=dev_root/"App/Validacao/validar_sistema.py"
            p=subprocess.run([str(py),"-B","-I","-S",str(validator),str(dev_root)],text=True,capture_output=True,encoding="utf-8",errors="replace")
            if p.returncode!=0:raise RuntimeError("Validacao DEV final falhou: "+(p.stderr or p.stdout))
        final_hash,_=surface(dev_root)
        if final_hash!=main_hash:raise RuntimeError("Superficie patchable MAIN/DEV divergiu apos promocao final.")
        if os.name=="nt":registry=Path(os.environ.get("ProgramData",r"C:\ProgramData"))/"CJL/Branches/branches.json"
        else:registry=container/"branches.json"
        registry_before=registry.read_bytes() if registry.is_file() else None
        share_created=configure_share(container,share_name)
        writej(registry,{"format":1,"product":"CJL System","updated_at":now_sp().isoformat(timespec="seconds"),"branches":{"MAIN":{"root":str(main_root),"branch":"MAIN"},"DEV":{"root":str(dev_root),"branch":"DEV","container":str(container),"share_name":share_name}}})
        append_index(main_root,{"type":"DEV_BRANCH_PROVISIONED","branch":"DEV","dev_root":str(dev_root),"share_name":share_name,"patchable_surface_sha256":main_hash})
        print(json.dumps({"ok":True,"main_root":str(main_root),"dev_root":str(dev_root),"share_name":share_name,"unc_hint":"\\\\" + (os.environ.get("COMPUTERNAME") or "localhost") + "\\"+share_name,"patchable_surface_sha256":main_hash,"operational_data_copied":False},ensure_ascii=False,indent=2))
    except Exception:
        # Provisioning is transactional for the DEV tree. MAIN application is never modified here.
        try:
            if 'share_created' in locals():
                try:remove_share_if_created(share_name,share_created)
                except Exception:pass
            if 'registry' in locals():
                try:
                    if 'registry_before' in locals() and registry_before is not None:
                        registry.parent.mkdir(parents=True,exist_ok=True);registry.write_bytes(registry_before)
                    elif registry.exists():registry.unlink()
                except Exception:pass
            if 'promoted' in locals() and promoted and dev_root.exists():shutil.rmtree(dev_root,ignore_errors=True)
            if 'old' in locals() and old is not None and old.exists() and not dev_root.exists():os.replace(old,dev_root)
        finally:
            shutil.rmtree(stage.parent,ignore_errors=True)
        raise

def compare(main_root,dev_root):
    mh,_=surface(main_root);dh,_=surface(dev_root);out={"ok":mh==dh,"main_surface_sha256":mh,"dev_surface_sha256":dh};print(json.dumps(out,indent=2));return 0 if out["ok"] else 2

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("provision-dev");p.add_argument("--main-root",default=r"C:\CJL\System");p.add_argument("--container",default=r"C:\.Dev CJL");p.add_argument("--share-name",default=".Dev CJL$")
    c=sub.add_parser("compare");c.add_argument("--main-root",required=True);c.add_argument("--dev-root",required=True)
    ns=ap.parse_args()
    if ns.cmd=="provision-dev":provision(ns.main_root,ns.container,ns.share_name);return 0
    return compare(ns.main_root,ns.dev_root)
if __name__=="__main__":
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:print("FALHA: "+str(exc),file=sys.stderr);raise SystemExit(1)
