from __future__ import annotations

import hashlib, json, os, shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SM_REPO_FOLDER = "SM_Repo"
POLICY_FORMAT = 1


def now_sp() -> datetime:
    try: return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError: return datetime.now(timezone(timedelta(hours=-3)))


def repo_root(master_root: str | Path) -> Path:
    root = Path(master_root).resolve()
    return root.parent / SM_REPO_FOLDER


def ensure_structure(master_root: str | Path) -> dict[str, Path]:
    root = repo_root(master_root)
    paths = {
        "root": root,
        "archive": root,
        "master_legacy": root / "Legacy" / "Master",
        "snapshots": root / "Snapshots",
        "logs": root / "Logs",
        "patch_backups": root / "Recovery" / "PatchBackups",
        "patch_archive": root / "Patches" / "Applied",
        "patch_failed": root / "Patches" / "Failed",
        "patch_legacy": root / "Patches" / "Legacy",
        "recovery": root / "Recovery",
        "legacy": root / "Legacy",
        "provenance": root / "Provenance",
        "index": root / "Index",
        "promotions": root / "Promotions",
        "promotion_approved": root / "Promotions" / "Approved",
        "promotion_packages": root / "Promotions" / "Packages",
        "branches": root / "Branches",
    }
    for path in paths.values(): path.mkdir(parents=True, exist_ok=True)
    policy = root / "Index" / "sm_repo.policy.json"
    if not policy.exists():
        _write_json(policy, {
            "format": POLICY_FORMAT, "product": "CJL System", "product_code": "CJL",
            "root_mode": "SIBLING_OF_SYSTEM", "folder": SM_REPO_FOLDER,
            "timezone": "America/Sao_Paulo", "system_policy": "CURRENT_OPERATIONAL_STATE_ONLY_STRICT",
            "repository_policy": "HISTORY_RECOVERY_PROVENANCE_APPEND_ONLY", "created_at": now_sp().isoformat(timespec="seconds"),
        })
    return paths


def sha256_file(path: str | Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""): digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(temporary,path)


def append_index(master_root: str | Path, event: dict) -> Path:
    paths=ensure_structure(master_root)
    entry={"product":"CJL System","recorded_at":now_sp().isoformat(timespec="seconds"),"timezone":"America/Sao_Paulo",**event}
    index=paths["index"] / "sm_repo.index.jsonl"
    with index.open("a",encoding="utf-8",newline="\n") as stream:
        stream.write(json.dumps(entry,ensure_ascii=False,separators=(",",":"))+"\n"); stream.flush()
        try: os.fsync(stream.fileno())
        except OSError: pass
    return index


def copy_file_verified(source: str | Path, destination: str | Path) -> dict:
    source=Path(source); destination=Path(destination)
    if not source.is_file(): raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True,exist_ok=True)
    before=sha256_file(source); temporary=destination.with_name(destination.name+".copy.tmp")
    shutil.copy2(source,temporary); after=sha256_file(temporary)
    if after!=before: temporary.unlink(missing_ok=True); raise RuntimeError(f"Copia divergiu por SHA-256: {source}")
    os.replace(temporary,destination)
    return {"sha256":before,"bytes":source.stat().st_size,"destination":str(destination)}


def archive_snapshot_file(master_root: str | Path, source: str | Path, version: str, *, remove_source: bool=True) -> dict:
    source=Path(source); paths=ensure_structure(master_root); bucket=paths["snapshots"] / str(version or "UNKNOWN"); bucket.mkdir(parents=True,exist_ok=True)
    destination=bucket/source.name
    if destination.exists() and sha256_file(destination)!=sha256_file(source): destination=bucket/f"{source.stem}_{now_sp().strftime('%Y%m%dT%H%M%S')}{source.suffix}"
    result=copy_file_verified(source,destination)
    append_index(master_root,{"type":"SNAPSHOT_ARCHIVE","source":str(source),"destination":str(destination),"sha256":result["sha256"],"bytes":result["bytes"],"version":str(version or "UNKNOWN")})
    if remove_source: source.unlink()
    return result


def master_is_direct() -> bool:
    return str(os.environ.get("CJL_HOST_MODE") or "").upper()=="MASTER_DIRECT"
