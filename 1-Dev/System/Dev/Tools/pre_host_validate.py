from __future__ import annotations
import argparse,json,sqlite3,sys
from pathlib import Path

def read(p):
    v=json.loads(Path(p).read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}

def main()->int:
    ap=argparse.ArgumentParser(description="Pre-validacao CJL Base 5 antes do build do Host.")
    ap.add_argument("--root",required=True); ns=ap.parse_args(); root=Path(ns.root).resolve(); app=root/"App"
    site=root/"Runtime"/"Python"/"Lib"/"site-packages"
    if not site.is_dir(): raise RuntimeError("Runtime Python site-packages ausente.")
    sys.path.insert(0,str(site)); sys.path.insert(0,str(app))
    from Core.release import verify_manifest,verify_runtime_integrity,version_key
    from Core.version import versioning
    from Core.signature import verify_release_signature
    from Core.repository import _validate_head_chain
    from Core.updates import read_state
    cfg=read(app/"Config"/"sistema.json"); ids=versioning()
    if cfg.get("project_name")!="CJL System" or int(cfg.get("layout_version") or 0)!=5: raise RuntimeError("Identidade Base 5 invalida.")
    if version_key(cfg.get("version"))!=(int(ids["structural"]),int(ids["incremental"]),int(ids["security"])): raise RuntimeError("Version/ES.IN.SE divergentes.")
    state=read_state(root)
    if state["business_id"]!=ids["business_id"] or state["compat_sequence"]!=int(ids["compat_sequence"]): raise RuntimeError("Estado Base 5 diverge do versioning.")
    verify_manifest(root,exact_file_set=True); verify_runtime_integrity(root,exact_file_set=True,quick=False); trust=verify_release_signature(root)
    if trust.get("current_release_signed") is not False or trust.get("trust_mode")!="SHA256_MIGRATION_CHECKPOINT": raise RuntimeError("Trust Base 5 invalido.")
    db=root/"Data"/"sistema.db"; uri=db.as_uri()+"?mode=ro&immutable=1"
    with sqlite3.connect(uri,uri=True,timeout=15) as c:
        integrity=str(c.execute("PRAGMA integrity_check").fetchone()[0]); fk=c.execute("PRAGMA foreign_key_check").fetchall()
    if integrity.casefold()!="ok" or fk: raise RuntimeError("Banco nao passou na pre-validacao.")
    head=read(root/"Repo"/"HEAD.json"); tx=_validate_head_chain(head,{})
    anchor=read(app/"Config"/"repository.anchor.json")
    if int(anchor.get("revision") or 0)!=int(head.get("revision") or 0) or str(anchor.get("transaction_file_sha256") or "").lower()!=str(head.get("transaction_file_sha256") or "").lower(): raise RuntimeError("Anchor do Repo diverge do HEAD.")
    print(json.dumps({"ok":True,"product":"CJL System","business":ids["business_id"],"version":cfg["version"],"repo_revision":int(head.get("revision") or 0),"repo_transaction_sha256":tx,"database_integrity":integrity,"host_build_required":True},ensure_ascii=False,indent=2)); return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except SystemExit: raise
    except BaseException as exc: print("FALHA: "+str(exc),file=sys.stderr); raise SystemExit(1)
