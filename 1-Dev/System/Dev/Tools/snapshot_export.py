from __future__ import annotations
import argparse,hashlib,json,os,shutil,sys,tempfile,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
EXCLUDED_ROOTS={"Runtime","Data","Shared","Repo","Temp","Export"};EXCLUDED_PREFIX={"Host/Bin"};SKIP_PARTS={"__pycache__","bin","obj",".git",".pytest_cache"};SKIP_SUFFIX={".pyc",".pyo",".tmp",".key",".pem",".p12",".pfx",".kdbx"}
def now_sp():
    try:return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:return datetime.now(timezone(timedelta(hours=-3)))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def include_rel(rel:str)->bool:
    rel=rel.replace("\\","/");parts=rel.split('/');
    if rel=='CJL.branch.json':return False
    if parts[0] in EXCLUDED_ROOTS:return False
    if parts[0]=="Logs" and not rel.startswith("Logs/System/"):return False
    if any(rel==x or rel.startswith(x+'/') for x in EXCLUDED_PREFIX):return False
    p=Path(rel)
    if any(x.casefold() in SKIP_PARTS for x in p.parts) or p.suffix.casefold() in SKIP_SUFFIX:return False
    return True
def tree_files(root):
    out=[]
    for p in Path(root).rglob("*"):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(root).as_posix()
        if include_rel(rel):out.append((rel,p))
    return sorted(out,key=lambda x:x[0].casefold())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--output');ns=ap.parse_args();root=Path(ns.root).resolve();app=root/'App';cfg=read(app/'Config/sistema.json');v=cfg['versioning'];created=now_sp();mid=(app/'Config/master.id').read_text(encoding='utf-8').strip().upper();branch=json.loads((root/'CJL.branch.json').read_text(encoding='utf-8'));branch_name=str(branch.get('branch') or 'UNKNOWN').upper();name=f"CJL_{branch_name}_DEV_B{int(v['business']):02d}_E{int(v['structural']):02d}_I{int(v['incremental']):02d}_S{int(v['security']):03d}_{created.strftime('%Y%m%dT%H%M%S')}.zip";out=Path(ns.output).resolve() if ns.output else root/'Export'/'Dev'/name;out.parent.mkdir(parents=True,exist_ok=True)
    import subprocess;py=root/'Runtime/Python/python.exe';p=subprocess.run([str(py),'-B','-I','-S',str(app/'Validacao/validar_sistema.py'),str(root)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode!=0:raise RuntimeError('Mestre nao passou na validacao antes do snapshot: '+(p.stderr or p.stdout))
    sys.path.insert(0,str(app));from Core.cumulativity import metadata as rules_metadata;from Core.data_policy import snapshot_policy_metadata;from Core.system_history import append_event
    rules=rules_metadata(root);policy=snapshot_policy_metadata(root);files=tree_files(root);snapshot={'format':5,'product':'CJL System','product_code':'CJL','type':'DEVELOPMENT_SNAPSHOT','layout':5,'business':int(v['business']),'business_id':f"BA-{int(v['business']):02d}",'version':cfg['version_full'],'version_full':cfg['version_full'],'version_core':cfg['version_core'],'structural':int(v['structural']),'incremental':int(v['incremental']),'security':int(v['security']),'patches':{'business':v['business_id'],'structural':v['structural_id'],'incremental':v['incremental_id'],'security':v['security_id']},'compat_sequence':int(v['compat_sequence']),'build':int(cfg['build']),'runtime':int(cfg['runtime_version']),'schema':int(cfg['schema_version']),'master_id':mid,'branch':branch_name,'created_at':created.isoformat(timespec='seconds'),'timezone':'America/Sao_Paulo','contents':'SYSTEM_SOURCE_METADATA_RULES_AND_CURRENT_TECHNICAL_HISTORY','operational_user_data_included':False,'retention':'SYSTEM_LATEST_ONLY_SM_REPO_HISTORY','rules':rules,'data_policy':policy}
    with tempfile.TemporaryDirectory(prefix='cjl_snapshot_') as td:
        stage=Path(td);(stage/'Files').mkdir();(stage/'_Snapshot').mkdir();hashes=[]
        for rel,pth in files:
            d=stage/'Files'/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(pth,d);hashes.append(f"{sha(d)}  Files/{rel}")
        (stage/'_Snapshot'/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(stage/'_Snapshot'/'included.sha256').write_text('\n'.join(hashes)+'\n',encoding='ascii');(stage/'_Snapshot'/'data-policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for pth in sorted(stage.rglob('*')):
                if pth.is_file():z.write(pth,pth.relative_to(stage).as_posix())
    digest=sha(out);out.with_suffix(out.suffix+'.sha256').write_text(f"{digest}  {out.name}\n",encoding='ascii');append_event(root,'DEVELOPMENT_SNAPSHOT_CREATED',snapshot=out.name,sha256=digest,files=len(files))
    sys.path.insert(0,str(root/'Runtime/Python/Lib/site-packages'));from Core.sm_repo import ensure_structure,copy_file_verified,append_index
    sm=ensure_structure(root);devdir=root/'Export'/'Dev';others=[p for p in devdir.glob('CJL_*_DEV_B*.zip') if p.resolve()!=out.resolve()]
    for old in others:
        d=sm['snapshots']/old.name;copy_file_verified(old,d);append_index(root,{'type':'SNAPSHOT_ARCHIVE','source':str(old),'destination':str(d),'sha256':sha(d),'version':cfg['version_full']});old.unlink(missing_ok=True);old.with_suffix(old.suffix+'.sha256').unlink(missing_ok=True)
    print(json.dumps({'ok':True,'snapshot':str(out),'sha256':digest,'files':len(files),'business':snapshot['business_id'],'version':snapshot['version_full'],'rules':rules,'data_policy':policy},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
