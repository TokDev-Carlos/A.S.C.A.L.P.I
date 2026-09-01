from __future__ import annotations

import os
import shutil
from pathlib import Path


MIB = 1024 * 1024
GIB = 1024 * MIB


def _existing_ancestor(path: Path) -> Path:
    current = Path(path)
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def directory_size(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for base, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not Path(base, name).is_symlink()]
        for name in files:
            path = Path(base, name)
            try:
                if not path.is_symlink():
                    total += path.stat().st_size
            except OSError:
                continue
    return total


def status(root: Path) -> dict:
    usage = shutil.disk_usage(_existing_ancestor(root))
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": round(usage.free / usage.total * 100, 2) if usage.total else 0,
    }


def ensure_disk_space(path: Path, incoming_bytes: int, *, label: str = "ARQUIVO") -> None:
    usage = shutil.disk_usage(_existing_ancestor(path))
    reserve = max(512 * MIB, int(usage.total * 0.05))
    if incoming_bytes < 0 or usage.free - int(incoming_bytes) < reserve:
        raise RuntimeError(
            f"ESPAÇO INSUFICIENTE PARA {label}. O CJL System PRESERVA 5% DO DISCO (MÍNIMO 512 MB)."
        )


def ensure_data_quota(root: Path, incoming_bytes: int) -> None:
    quota_gib = max(1, int(os.environ.get("CJL_DATA_QUOTA_GB", "100")))
    if directory_size(root) + int(incoming_bytes) > quota_gib * GIB:
        raise RuntimeError(f"A COTA DE DADOS DO CJL System ({quota_gib} GB) SERIA ULTRAPASSADA.")
    ensure_disk_space(root, incoming_bytes, label="DADOS DO SISTEMA")
