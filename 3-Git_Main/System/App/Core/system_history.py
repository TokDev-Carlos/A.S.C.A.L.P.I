from __future__ import annotations
import json,os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def append_event(root:Path,event:str,**detail)->Path:
    root=Path(root).resolve();cfg=json.loads((root/"App"/"Config"/"sistema.json").read_text(encoding="utf-8"));v=cfg.get("versioning") or {}
    record={"at":datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),"product":"CJL System","version":str(cfg.get("version_full") or ""),"version_core":str(cfg.get("version_core") or cfg.get("version") or ""),"business":f"BA-{int(v.get('business') or 0):02d}","structural":f"ES-{int(v.get('structural') or 0):02d}","incremental":f"IN-{int(v.get('incremental') or 0):02d}","security":f"SE-{int(v.get('security') or 0):03d}","compat_sequence":int(v.get("compat_sequence") or 0),"build":int(cfg.get("build") or 0),"event":str(event),**detail}
    path=root/"Logs"/"System"/"release-history.jsonl";path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8",newline="\n") as f:f.write(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n");f.flush();os.fsync(f.fileno())
    return path
