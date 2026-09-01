from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Gera manifesto SHA-256 da App CJL System Base 5.")
    ap.add_argument("--root",required=True); ns=ap.parse_args(); root=Path(ns.root).resolve(); app=root/"App"
    site=root/"Runtime"/"Python"/"Lib"/"site-packages"
    if not site.is_dir(): raise RuntimeError(f"Runtime site-packages ausente: {site}")
    sys.path.insert(0,str(site)); sys.path.insert(0,str(app))
    from Core.release import write_manifest,verify_manifest
    manifest=write_manifest(root); verify_manifest(root,exact_file_set=True)
    print(json.dumps({"ok":True,"manifest":str(app/"Config"/"app.integrity.json"),"files":len(manifest.get("files") or {}),"business":manifest.get("business_id"),"version":manifest.get("version"),"structural":manifest.get("structural"),"incremental":manifest.get("incremental"),"security":manifest.get("security"),"compat_sequence":manifest.get("compat_sequence"),"build":manifest.get("build"),"layout":manifest.get("layout_version")},ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
