from __future__ import annotations
import json, os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from Core.config import local_logs_path, station_id
from Core.context import current_identity

LOG_DIR = local_logs_path()

def log(event: str, **detail: Any) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    identity = current_identity()
    record = {
        'at': datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds'),
        'event': event,
        'user_id': identity.user_id,
        'user_name': identity.user_name,
        'station_id': identity.station_id or station_id(),
        **detail,
    }
    path = LOG_DIR / f"{datetime.now(ZoneInfo('America/Sao_Paulo')):%Y-%m}.jsonl"
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        stream.flush(); os.fsync(stream.fileno())
