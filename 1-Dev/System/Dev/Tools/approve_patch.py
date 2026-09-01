from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
def sha(p):
    h=hashlib.sha256();
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def read(p):
    try:v=json.loads(Path(p).read_text(encoding="utf-8"));return v if isinstance(v,dict) else {}
    except:return {}
def patch_manifest(p):
    with zipfile.ZipFile(p) as z:
        hits=[n for n in z.namelist() if n.endswith('/patch.json') or n=='patch.json']
        if len(hits)!=1:raise RuntimeError("patch.json ausente/ambiguo.")
        return json.loads(z.read(hits[0]).decode('utf-8'))
def writej(p,v):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,p)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dev-root',required=True);ap.add_argument('--main-root',required=True);ap.add_argument('--patch',required=True);ns=ap.parse_args();dev=Path(ns.dev_root).resolve();main=Path(ns.main_root).resolve();patch=Path(ns.patch).resolve();m=patch_manifest(patch);digest=sha(patch)
    sys.path.insert(0,str(dev/'Runtime/Python/Lib/site-packages'));sys.path.insert(0,str(dev/'App'));from Core.branch import read_branch;import importlib.util;spec=importlib.util.spec_from_file_location('branch_manager',dev/'Dev/Tools/branch_manager.py');branch_manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(branch_manager)
    if read_branch(dev)['branch']!='DEV' or read_branch(main)['branch']!='MAIN':raise RuntimeError('Branches DEV/MAIN invalidas.')
    state=read(dev/'Updates/State/atual.json');target=m.get('target') or {}
    if state.get('version')!=target.get('version') or state.get('version_full')!=target.get('version_full') or state.get('last_patch_id')!=m.get('patch_id') or state.get('patch_sha256')!=digest:raise RuntimeError('DEV nao esta exatamente no target deste ZIP.')
    py=dev/'Runtime/Python/python.exe';r=subprocess.run([str(py),'-B','-I','-S',str(dev/'App/Validacao/validar_sistema.py'),str(dev)],text=True,capture_output=True,encoding='utf-8',errors='replace')
    if r.returncode!=0:raise RuntimeError('DEV nao passou validacao: '+(r.stderr or r.stdout))
    surface_hash,_=branch_manager.surface(dev);sm=main.parent/'SM_Repo';receipt=sm/'Promotions'/'Approved'/(digest+'.json');package=sm/'Promotions'/'Packages'/(digest+'__'+patch.name);package.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(patch,package)
    value={'format':1,'product':'CJL System','status':'APPROVED','patch_id':m['patch_id'],'patch_sha256':digest,'source':m['source'],'target':m['target'],'dev_root_hint':str(dev),'dev_surface_sha256':surface_hash,'approved_at':datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec='seconds'),'approved_by':os.environ.get('USERNAME') or 'CJLAdmin','approved_package':str(package)};writej(receipt,value);print(json.dumps({'ok':True,'patch_sha256':digest,'receipt':str(receipt),'approved_package':str(package),'main_next_action':'copiar o MESMO ZIP para Main Updates\\In e usar opcao 5'},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except BaseException as exc:print('FALHA: '+str(exc),file=sys.stderr);raise SystemExit(1)
