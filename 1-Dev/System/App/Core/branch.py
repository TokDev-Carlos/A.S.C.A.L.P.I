from __future__ import annotations
import hashlib, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MARKER_NAME = "CJL.branch.json"
VALID_BRANCHES = {"MAIN", "DEV"}
VALID_ROLES = {"PRODUCTION", "DEVELOPMENT"}

def now_sp():
    try: return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError: return datetime.now(timezone(timedelta(hours=-3)))

def root_fingerprint(root: str | Path) -> str:
    value = os.path.normcase(os.path.abspath(os.path.expandvars(str(Path(root).resolve())))).rstrip("\\/")
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:24].upper()

def marker_path(root: str | Path) -> Path: return Path(root).resolve() / MARKER_NAME

def read_branch(root: str | Path, *, required: bool = True) -> dict:
    root = Path(root).resolve(); path = marker_path(root)
    if not path.is_file():
        if required: raise RuntimeError(f"MARCADOR DE BRANCH AUSENTE: {path}")
        return {}
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: raise RuntimeError("MARCADOR DE BRANCH INVALIDO.") from exc
    if not isinstance(value, dict) or int(value.get("format") or 0) != 1 or value.get("product") != "CJL System": raise RuntimeError("MARCADOR DE BRANCH INVALIDO.")
    branch = str(value.get("branch") or "").upper(); role = str(value.get("role") or "").upper()
    if branch not in VALID_BRANCHES or role not in VALID_ROLES: raise RuntimeError("IDENTIDADE DE BRANCH INVALIDA.")
    if branch == "MAIN" and role != "PRODUCTION": raise RuntimeError("MAIN deve usar role PRODUCTION.")
    if branch == "DEV" and role != "DEVELOPMENT": raise RuntimeError("DEV deve usar role DEVELOPMENT.")
    if str(value.get("root_fingerprint") or "").upper() != root_fingerprint(root): raise RuntimeError("MARCADOR DE BRANCH PERTENCE A OUTRA RAIZ FISICA.")
    return value

def write_branch(root: str | Path, branch: str, role: str, *, master_id: str, source_root: str | None = None, share_name: str | None = None) -> dict:
    root = Path(root).resolve(); branch = str(branch).upper(); role = str(role).upper()
    if branch not in VALID_BRANCHES or role not in VALID_ROLES: raise ValueError("Branch/role invalidos.")
    payload = {
        "format": 1, "product": "CJL System", "branch": branch, "role": role,
        "master_id": str(master_id).strip().upper(), "root_fingerprint": root_fingerprint(root),
        "root_hint": str(root), "created_at": now_sp().isoformat(timespec="seconds"), "timezone": "America/Sao_Paulo",
        "patch_contract": "ROOT_RELATIVE_FORMAT_7", "promotion_contract": "SAME_ZIP_SHA256_DEV_TO_MAIN",
        "production_data_allowed": branch == "MAIN",
    }
    if source_root: payload["source_root_hint"] = str(Path(source_root).resolve())
    if share_name: payload["share_name"] = str(share_name)
    path = marker_path(root); tmp = path.with_suffix(path.suffix+".tmp"); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); os.replace(tmp,path)
    return payload

def branch_name(root: str | Path) -> str: return str(read_branch(root)["branch"])
def is_main(root: str | Path) -> bool: return branch_name(root) == "MAIN"
def is_dev(root: str | Path) -> bool: return branch_name(root) == "DEV"
