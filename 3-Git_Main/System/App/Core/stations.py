from __future__ import annotations

import json
import os
import secrets
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from Core.atomic import atomic_write_json
from Core.config import network_root, repository_root, station_id
from Core.version import app_version, build_number, compatibility_sequence, versioning
from Core.release import normalize_version, version_key


HEARTBEAT_SECONDS = 10
ACTIVE_SECONDS = 40
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_NONCE = secrets.token_hex(16)


class CriticalMaintenanceError(RuntimeError):
    """Bloqueio deliberado do Mestre durante atualização estrutural/crítica."""


class StationUpdateRequiredError(RuntimeError):
    """A estação está abaixo do piso mínimo de compatibilidade do Mestre."""


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _directory() -> Path:
    return repository_root() / "Estacoes"


def _presence_path() -> Path:
    return _directory() / f"{station_id()}.json"


def maintenance_path() -> Path:
    return repository_root() / "Manutencao" / "estado.json"


def _master_state_path() -> Path:
    return network_root().resolve() / "Updates" / "State" / "atual.json"


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def maintenance_status() -> dict:
    marker = maintenance_path()
    state = _read_json(marker) if marker.is_file() else {}
    if not state:
        return {
            "active": False,
            "mode": "NONE",
            "phase": "NONE",
            "compat_sequence": 0,
            "minimum_station_compat": 0,
            "message": "",
        }
    mode = str(state.get("mode") or "CRITICAL").strip().upper()
    phase = str(state.get("phase") or "APPLYING").strip().upper()
    compat = int(state.get("compat_sequence") or 0)
    minimum = int(state.get("minimum_station_compat") or 0)
    active = bool(state.get("active", True)) and mode == "CRITICAL" and phase not in {"RELEASED", "IDLE", "NONE"}
    return {
        **state,
        "active": bool(active),
        "mode": mode,
        "phase": phase,
        "compat_sequence": compat,
        "minimum_station_compat": minimum,
        "message": str(state.get("message") or ""),
    }


def _minimum_station_compat() -> int:
    state = _read_json(_master_state_path())
    try:
        return max(0, int(state.get("minimum_station_compat") or 0))
    except (TypeError, ValueError):
        return 0


def _minimum_station_version() -> str:
    state = _read_json(_master_state_path())
    value = str(state.get("minimum_station_version") or state.get("version") or "").strip()
    if not value:
        return "0.00.000"
    try:
        return normalize_version(value)
    except ValueError:
        return "0.00.000"


def ensure_operational() -> None:
    maintenance = maintenance_status()
    if maintenance["active"]:
        version = str(maintenance.get("target_version") or maintenance.get("version") or "")
        operation_id = str(maintenance.get("operation_id") or maintenance.get("patch_id") or "").strip()
        detail = operation_id or (f"VERSION {version}" if version else f"COMPAT {int(maintenance.get('compat_sequence') or 0):06d}")
        raise CriticalMaintenanceError(
            f"ATUALIZACAO CRITICA DO CJL System EM ANDAMENTO ({detail}). "
            "ESTA ESTACAO ESTA TEMPORARIAMENTE DESCONECTADA DO MESTRE."
        )
    minimum_version = _minimum_station_version()
    local_version = normalize_version(app_version())
    minimum_compat = max(int(maintenance.get("minimum_station_compat") or 0), _minimum_station_compat())
    local_compat = compatibility_sequence()
    if version_key(local_version) < version_key(minimum_version) or (minimum_compat and local_compat < minimum_compat):
        raise StationUpdateRequiredError(
            f"ESTA ESTACAO ESTA NA VERSION {local_version} E O MESTRE EXIGE NO MINIMO "
            f"VERSION {minimum_version} / COMPAT {minimum_compat:06d}. ATUALIZE A ESTACAO ANTES DE RECONECTAR."
        )


def _payload(port: int) -> dict:
    ids = versioning()
    return {
        "format": 3,
        "product": "CJL System",
        "station_id": station_id(),
        "nonce": _NONCE,
        "pid": os.getpid(),
        "port": int(port),
        "host": socket.gethostname()[:80],
        "version": app_version(),
        "business": int(ids["business"]),
        "business_id": ids["business_id"],
        "structural": int(ids["structural"]),
        "incremental": int(ids["incremental"]),
        "security": int(ids["security"]),
        "patches": {"business": ids["business_id"], "structural": ids["structural_id"], "incremental": ids["incremental_id"], "security": ids["security_id"]},
        "compat_sequence": compatibility_sequence(),
        "build": build_number(),
        "last_seen": _now(),
        "last_seen_epoch": time.time(),
    }


def _remove_presence() -> None:
    path = _presence_path()
    try:
        if _read_json(path).get("nonce") == _NONCE:
            path.unlink()
    except OSError:
        pass


def publish(port: int) -> None:
    ensure_operational()
    path = _presence_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, _payload(port))


def start(port: int) -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _STOP.clear()
    try:
        publish(port)
    except (CriticalMaintenanceError, StationUpdateRequiredError):
        _remove_presence()

    def heartbeat() -> None:
        while not _STOP.wait(HEARTBEAT_SECONDS):
            try:
                publish(port)
            except OSError:
                continue
            except (CriticalMaintenanceError, StationUpdateRequiredError):
                _remove_presence()
                continue

    _THREAD = threading.Thread(target=heartbeat, name="CJLStationHeartbeat", daemon=True)
    _THREAD.start()


def stop() -> None:
    _STOP.set()
    if _THREAD and _THREAD.is_alive():
        _THREAD.join(timeout=2)
    _remove_presence()


def active() -> list[dict]:
    now = time.time()
    items: list[dict] = []
    directory = _directory()
    if not directory.is_dir():
        return items
    for path in directory.glob("*.json"):
        value = _read_json(path)
        try:
            age = now - float(value.get("last_seen_epoch") or 0)
        except (TypeError, ValueError):
            age = ACTIVE_SECONDS + 1
        if 0 <= age <= ACTIVE_SECONDS and value.get("station_id"):
            items.append(value)
    return items
