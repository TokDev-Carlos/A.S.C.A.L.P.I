from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from Core.atomic import atomic_write_json
from Core.config import local_state_root


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def registry_path() -> Path:
    return local_state_root() / "Instancia" / "instance.json"


def shutdown_request_path() -> Path:
    return local_state_root() / "Instancia" / "shutdown.request"


def shutdown_complete_path() -> Path:
    return local_state_root() / "Instancia" / "shutdown.complete.json"


def lifecycle_token() -> str:
    value = os.environ.get("CJL_LIFECYCLE_TOKEN", "").strip()
    return value or secrets.token_urlsafe(32)


def publish(port: int, token: str) -> dict:
    payload = {
        "product": "CJL System",
        "pid": os.getpid(),
        "port": int(port),
        "token": token,
        "started_at": _now(),
        "state_root": str(local_state_root()),
    }
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutdown_request_path().unlink()
    except FileNotFoundError:
        pass
    atomic_write_json(path, payload)
    return payload


def request_shutdown(reason: str) -> None:
    path = shutdown_request_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        path,
        {"pid": os.getpid(), "reason": str(reason or "USUARIO"), "requested_at": _now()},
    )


def complete(port: int, reason: str = "ENCERRAMENTO_LIMPO") -> None:
    path = shutdown_complete_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        path,
        {"pid": os.getpid(), "port": int(port), "reason": reason, "completed_at": _now()},
    )
    try:
        registry_path().unlink()
    except FileNotFoundError:
        pass


def read_registry() -> dict:
    try:
        value = json.loads(registry_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}
