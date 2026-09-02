#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCRIPT = Path(__file__).resolve()
TOOLS_LINUX = SCRIPT.parent
TOOLS = TOOLS_LINUX.parent
SM_REPO = TOOLS.parent
DEV_ROOT = SM_REPO.parent
SYSTEM = DEV_ROOT / "System"

CONFIG = TOOLS_LINUX / "CJL-LINUX.conf"
VALIDATOR = TOOLS_LINUX / "CJL-LINUX-VALIDAR.py"
STATUS_SCRIPT = TOOLS_LINUX / "STATUS-CJL-LINUX.sh"
STOP_SCRIPT = TOOLS_LINUX / "PARAR-CJL-LINUX.sh"
START_SCRIPT = DEV_ROOT / "INICIAR-CJL-LINUX.sh"
APPLY_CONTRACT = SYSTEM / "Dev" / "Tools" / "apply_patch.py"

PATCH_ROOT = SM_REPO / "Patches"
PATCH_INBOX = PATCH_ROOT / "Entrada"
PATCH_APPROVED = PATCH_ROOT / "Aplicados"
PATCH_REJECTED = PATCH_ROOT / "Reprovados"
BACKUP_ROOT = SM_REPO / "Backups" / "Linux-Patches"

COMPILER_INBOX = Path("/mnt/c/.Dev CJL/2-Compiler/Patches/Inbox")
EVIDENCE_ROOT = Path("/mnt/c/CJL_Work_Evidence/Linux-Patches/1-Dev")

TEXT_EXTENSIONS = {
    ".py", ".ps1", ".psm1", ".psd1", ".sh", ".bash", ".cmd", ".bat", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".txt", ".md", ".js",
    ".ts", ".html", ".css", ".xml", ".cs", ".csproj", ".sln"
}

SURFACE_SKIP_PARTS = {
    "Data", "Shared", "Repo", "Logs", "Temp", "Export", "Runtime", "__pycache__"
}
SURFACE_GENERATED = {
    "App/Config/app.integrity.json",
    "App/Config/provenance.json",
    "Updates/State/atual.json",
    "CJL.root.json",
}

SECURITY_PATTERNS = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("OPENAI_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PASSWORD_LITERAL", re.compile(r"(?i)\b(?:password|passwd|senha|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
]


def now_sp() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:
        return datetime.now(timezone(timedelta(hours=-3)))


def iso_now() -> str:
    return now_sp().isoformat(timespec="seconds")


def compact_now() -> str:
    return now_sp().strftime("%Y%m%dT%H%M%S")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_conf() -> dict[str, str]:
    if not CONFIG.is_file():
        raise RuntimeError(f"Config Linux ausente: {CONFIG}")
    out: dict[str, str] = {}
    for raw in CONFIG.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


CONF = load_conf()
RUNTIME = Path(CONF.get("CJL_LINUX_PYTHON", ""))
STATE_ROOT = Path(CONF.get("CJL_LINUX_STATE_ROOT", ""))
PATCH_STATE_ROOT = STATE_ROOT / "Patches"
STATE_FILE = PATCH_STATE_ROOT / "state.json"
MAINTENANCE_LOCK = PATCH_STATE_ROOT / "maintenance.lock"


def ensure_layout() -> None:
    for d in (
        PATCH_INBOX, PATCH_APPROVED, PATCH_REJECTED, BACKUP_ROOT,
        PATCH_STATE_ROOT, EVIDENCE_ROOT
    ):
        d.mkdir(parents=True, exist_ok=True)


def state_default() -> dict[str, Any]:
    return {
        "format": 1,
        "product": "ASCALPI",
        "stage": "LINUX",
        "current_sha256": "",
        "patches": {},
        "updated_at": iso_now(),
    }


def load_state() -> dict[str, Any]:
    ensure_layout()
    value = read_json(STATE_FILE, state_default())
    if not isinstance(value, dict):
        value = state_default()
    value.setdefault("format", 1)
    value.setdefault("product", "ASCALPI")
    value.setdefault("stage", "LINUX")
    value.setdefault("current_sha256", "")
    value.setdefault("patches", {})
    if not isinstance(value["patches"], dict):
        value["patches"] = {}
    return value


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = iso_now()
    write_json_atomic(STATE_FILE, state)


def get_record(state: dict[str, Any], digest: str) -> dict[str, Any]:
    patches = state["patches"]
    if digest not in patches or not isinstance(patches[digest], dict):
        patches[digest] = {
            "sha256": digest,
            "status": "RECEIVED",
            "created_at": iso_now(),
        }
    return patches[digest]


def current_record(require: bool = True) -> tuple[dict[str, Any], dict[str, Any] | None]:
    state = load_state()
    digest = str(state.get("current_sha256") or "")
    rec = state["patches"].get(digest) if digest else None
    if require and (not digest or not isinstance(rec, dict)):
        raise RuntimeError("Nenhum Patch Atual selecionado.")
    return state, rec


def patch_path(rec: dict[str, Any]) -> Path:
    value = Path(str(rec.get("current_path") or ""))
    if not value.is_file():
        raise RuntimeError(f"Arquivo do patch não localizado: {value}")
    return value


def manifest_from_zip(path: Path) -> dict[str, Any]:
    if not zipfile.is_zipfile(path):
        raise RuntimeError("O arquivo selecionado não é um ZIP válido.")
    with zipfile.ZipFile(path) as z:
        hits = [
            n for n in z.namelist()
            if n == "patch.json" or n.endswith("/patch.json")
        ]
        if len(hits) != 1:
            return {}
        value = json.loads(z.read(hits[0]).decode("utf-8"))
        return value if isinstance(value, dict) else {}


def patch_identity(path: Path) -> dict[str, Any]:
    m = manifest_from_zip(path)
    source = m.get("source") if isinstance(m.get("source"), dict) else {}
    target = m.get("target") if isinstance(m.get("target"), dict) else {}
    return {
        "patch_id": str(m.get("patch_id") or path.stem),
        "format": m.get("format"),
        "source_version": str(source.get("version_full") or source.get("version") or ""),
        "target_version": str(target.get("version_full") or target.get("version") or ""),
        "primary_type": str(m.get("primary_type") or ""),
    }


def resolve_managed_patch(digest: str, state: dict[str, Any]) -> Path | None:
    rec = state["patches"].get(digest)
    if isinstance(rec, dict):
        p = Path(str(rec.get("current_path") or ""))
        if p.is_file():
            return p
    for root in (PATCH_INBOX, PATCH_APPROVED, PATCH_REJECTED):
        for p in root.glob("*.zip"):
            try:
                if sha256_file(p) == digest:
                    return p
            except OSError:
                continue
    return None


def import_patch(source: Path) -> dict[str, Any]:
    ensure_layout()
    source = source.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"Patch não encontrado: {source}")
    if source.suffix.casefold() != ".zip":
        raise RuntimeError("Somente arquivos .zip são aceitos como patch.")
    if not zipfile.is_zipfile(source):
        raise RuntimeError("ZIP inválido ou corrompido.")

    digest = sha256_file(source)
    state = load_state()
    existing = resolve_managed_patch(digest, state)
    if existing:
        rec = get_record(state, digest)
        rec.update(patch_identity(existing))
        rec["current_path"] = str(existing)
        rec["selected_at"] = iso_now()
        state["current_sha256"] = digest
        save_state(state)
        return {"status": "ALREADY_MANAGED", "path": str(existing), "sha256": digest}

    target = PATCH_INBOX / source.name
    if target.exists():
        other = sha256_file(target)
        if other != digest:
            target = PATCH_INBOX / f"{source.stem}__{digest[:8]}{source.suffix}"

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))

    rec = get_record(state, digest)
    rec.update(patch_identity(target))
    rec.update({
        "filename": target.name,
        "current_path": str(target),
        "imported_at": iso_now(),
        "selected_at": iso_now(),
        "status": "RECEIVED",
        "source_original": str(source),
        "size_bytes": target.stat().st_size,
    })
    state["current_sha256"] = digest
    save_state(state)
    return {"status": "IMPORTED", "path": str(target), "sha256": digest}


def records_sorted(scope: str = "all") -> list[dict[str, Any]]:
    state = load_state()
    items: list[dict[str, Any]] = []
    for digest, raw in state["patches"].items():
        if not isinstance(raw, dict):
            continue
        rec = dict(raw)
        rec["sha256"] = digest
        status = str(rec.get("status") or "")
        if scope == "entrada" and status in {"LINUX_PASS", "LINUX_FAIL"}:
            continue
        if scope == "aprovados" and status != "LINUX_PASS":
            continue
        if scope == "reprovados" and status != "LINUX_FAIL":
            continue
        stamp = (
            rec.get("decision_at")
            or rec.get("tests_at")
            or rec.get("applied_at")
            or rec.get("selected_at")
            or rec.get("imported_at")
            or rec.get("created_at")
            or ""
        )
        rec["_sort"] = str(stamp)
        items.append(rec)
    items.sort(key=lambda x: x.get("_sort", ""), reverse=True)
    return items


def print_record(rec: dict[str, Any], index: int | None = None) -> None:
    prefix = f"[{index:02d}] " if index is not None else ""
    print(f"{prefix}{rec.get('patch_id') or rec.get('filename') or 'PATCH'}")
    print(f"     STATUS: {rec.get('status') or 'UNKNOWN'}")
    print(f"     DATA:   {rec.get('_sort') or rec.get('selected_at') or rec.get('imported_at') or '-'}")
    print(f"     SHA256: {str(rec.get('sha256') or '')[:16]}...")
    if rec.get("source_version") or rec.get("target_version"):
        print(f"     VERSÃO: {rec.get('source_version') or '?'} -> {rec.get('target_version') or '?'}")
    handoff = rec.get("compiler_handoff")
    if isinstance(handoff, dict):
        print(f"     COMPILER: {handoff.get('status') or 'N/A'}")
    print()


def ui_list() -> None:
    state = load_state()
    print("\n=== PATCH ATUAL ===")
    digest = str(state.get("current_sha256") or "")
    rec = state["patches"].get(digest)
    if isinstance(rec, dict):
        value = dict(rec)
        value["sha256"] = digest
        print_record(value)
    else:
        print("Nenhum patch atual.\n")

    print("=== TODOS OS PATCHES (MAIS RECENTES PRIMEIRO) ===")
    items = records_sorted("all")
    if not items:
        print("Nenhum patch gerenciado.")
        return
    for i, item in enumerate(items, 1):
        print_record(item, i)


def ui_select() -> None:
    items = records_sorted("all")
    if not items:
        print("Nenhum patch gerenciado.")
        return
    for i, item in enumerate(items, 1):
        print_record(item, i)
    raw = input("Número do patch para tornar atual [0 cancela]: ").strip()
    if raw in {"", "0"}:
        return
    try:
        idx = int(raw)
    except ValueError:
        raise RuntimeError("Seleção inválida.")
    if idx < 1 or idx > len(items):
        raise RuntimeError("Seleção fora da lista.")
    digest = str(items[idx - 1]["sha256"])
    state = load_state()
    rec = state["patches"].get(digest)
    if not isinstance(rec, dict):
        raise RuntimeError("Registro do patch não encontrado.")
    if str(rec.get("status") or "") in {"LINUX_PASS", "LINUX_FAIL"}:
        print("Aviso: patch histórico selecionado apenas para consulta.")
    state["current_sha256"] = digest
    rec["selected_at"] = iso_now()
    save_state(state)
    print(f"PATCH_ATUAL={rec.get('patch_id') or digest[:12]}")


def load_apply_contract():
    if not APPLY_CONTRACT.is_file():
        raise RuntimeError(f"Contrato de patch ausente: {APPLY_CONTRACT}")
    spec = importlib.util.spec_from_file_location("ascalpi_existing_apply_contract", APPLY_CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Não foi possível carregar o contrato de patch existente.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("extract", "validate_patch", "state_payload", "sha"):
        if not hasattr(module, name):
            raise RuntimeError(f"Contrato existente não oferece função obrigatória: {name}")
    return module


def validate_current(update_state: bool = True) -> dict[str, Any]:
    state, rec = current_record()
    assert rec is not None
    p = patch_path(rec)
    digest = sha256_file(p)
    if digest != str(rec.get("sha256") or state.get("current_sha256")):
        raise RuntimeError("SHA-256 do Patch Atual mudou desde a importação.")

    module = load_apply_contract()
    with tempfile.TemporaryDirectory(prefix="ascalpi-linux-validate-") as td:
        patch_root = module.extract(p, Path(td))
        manifest, ops = module.validate_patch(SYSTEM, patch_root, p, "DEV")

    result = {
        "status": "PASS",
        "patch_id": str(manifest.get("patch_id") or rec.get("patch_id") or p.stem),
        "patch_sha256": digest,
        "operations": len(ops),
        "host_rebuild": bool(manifest.get("host_rebuild")),
        "source_version": str((manifest.get("source") or {}).get("version_full") or ""),
        "target_version": str((manifest.get("target") or {}).get("version_full") or ""),
        "validated_at": iso_now(),
    }

    if update_state:
        rec.update({
            "patch_id": result["patch_id"],
            "source_version": result["source_version"],
            "target_version": result["target_version"],
            "status": "PATCH_READY",
            "validation": result,
        })
        save_state(state)
    return result


def run_cmd(args: list[str | Path], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [str(x) for x in args],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            "Comando falhou:\n"
            + " ".join(str(x) for x in args)
            + "\nSTDOUT:\n" + (proc.stdout or "")
            + "\nSTDERR:\n" + (proc.stderr or "")
        )
    return proc


def run_linux_validator() -> dict[str, Any]:
    if not RUNTIME.is_file() and not os.access(RUNTIME, os.X_OK):
        raise RuntimeError(f"Python Linux indisponível: {RUNTIME}")
    proc = run_cmd([RUNTIME, VALIDATOR, SYSTEM], check=True, cwd=DEV_ROOT)
    text = (proc.stdout or "").strip()
    try:
        result = json.loads(text)
    except Exception:
        result = {"status": "PASS", "raw": text}
    result["checked_at"] = iso_now()
    return result


def process_conflicts() -> list[dict[str, str]]:
    proc = run_cmd(["ps", "-eo", "pid=,args="], check=False)
    conflicts: list[dict[str, str]] = []
    sys_text = str(SYSTEM)
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(None, 1)
        if len(parts) != 2:
            continue
        pid, cmd = parts
        if pid == str(os.getpid()):
            continue
        if (
            "App/painel.py" in cmd
            or sys_text in cmd
            or "CJL_NETWORK_ROOT=" + sys_text in cmd
        ):
            if "ASCALPI-LINUX-PATCH.py" in cmd:
                continue
            conflicts.append({"pid": pid, "command": cmd[:400]})
    return conflicts


def stop_linux_authorized() -> dict[str, Any]:
    proc = run_cmd(["bash", STOP_SCRIPT], check=False, cwd=DEV_ROOT)
    if proc.returncode != 0:
        raise RuntimeError(
            "Fechamento autorizado do ambiente Linux falhou.\n"
            + (proc.stdout or "") + "\n" + (proc.stderr or "")
        )
    time.sleep(0.3)
    conflicts = process_conflicts()
    if conflicts:
        raise RuntimeError(
            "Ainda existem processos relacionados ao 1-Dev após o fechamento autorizado: "
            + json.dumps(conflicts, ensure_ascii=False)
        )
    return {
        "status": "PASS",
        "stdout": (proc.stdout or "").strip(),
        "stopped_at": iso_now(),
    }


@contextlib.contextmanager
def maintenance_lock(patch_id: str):
    PATCH_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": 1,
        "stage": "LINUX_PATCH_APPLY",
        "patch_id": patch_id,
        "pid": os.getpid(),
        "started_at": iso_now(),
    }
    for _ in range(2):
        try:
            fd = os.open(MAINTENANCE_LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
            break
        except FileExistsError:
            old = read_json(MAINTENANCE_LOCK, {})
            pid = int(old.get("pid") or 0) if isinstance(old, dict) else 0
            alive = False
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
            if alive:
                raise RuntimeError(f"Ambiente já está em manutenção pelo PID {pid}.")
            stale = MAINTENANCE_LOCK.with_name(
                "maintenance.stale." + compact_now() + ".json"
            )
            try:
                os.replace(MAINTENANCE_LOCK, stale)
            except OSError:
                raise RuntimeError("Lock de manutenção antigo não pôde ser saneado.")
    try:
        yield
    finally:
        try:
            MAINTENANCE_LOCK.unlink()
        except FileNotFoundError:
            pass


def surface_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(SYSTEM.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(SYSTEM)
        if any(part in SURFACE_SKIP_PARTS for part in rel.parts):
            continue
        rel_text = rel.as_posix()
        if rel_text in SURFACE_GENERATED:
            continue
        if rel_text.endswith((".pyc", ".pyo")):
            continue
        out[rel_text] = sha256_file(p)
    return out


def surface_digest(surface: dict[str, str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(surface, key=str.casefold):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(surface[rel].encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".ascalpi.tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def backup_for_ops(ops: list[dict[str, Any]], patch_id: str, digest: str) -> tuple[Path, dict[str, Any]]:
    run_id = f"{compact_now()}_{patch_id}_{digest[:8]}"
    root = BACKUP_ROOT / run_id
    root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []

    rels = {str(x["path"]) for x in ops}
    rels |= {
        "App/Config/app.integrity.json",
        "App/Config/provenance.json",
        "Updates/State/atual.json",
        "CJL.root.json",
    }
    for rel in sorted(rels, key=str.casefold):
        src = SYSTEM / rel
        item = {
            "path": rel,
            "existed": src.is_file(),
            "sha256": sha256_file(src) if src.is_file() else "",
        }
        if src.is_file():
            safe_copy(src, root / "Files" / rel)
        entries.append(item)

    protected_state_dirs = []
    for rel in ("Data", "Repo", "Shared"):
        src_dir = SYSTEM / rel
        if not src_dir.is_dir():
            continue
        dst_dir = root / "ProtectedState" / rel
        shutil.copytree(src_dir, dst_dir)
        protected_state_dirs.append(rel)

    manifest = {
        "format": 1,
        "patch_id": patch_id,
        "patch_sha256": digest,
        "created_at": iso_now(),
        "system": str(SYSTEM),
        "entries": entries,
        "protected_state_dirs": protected_state_dirs,
        "pre_surface_sha256": surface_digest(surface_map()),
    }
    write_json_atomic(root / "backup.json", manifest)
    return root, manifest


def restore_backup(root: Path) -> dict[str, Any]:
    manifest = read_json(root / "backup.json", {})
    if not isinstance(manifest, dict):
        raise RuntimeError("Manifesto de backup inválido.")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("Lista de backup inválida.")

    for item in entries:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "")
        dest = SYSTEM / rel
        if bool(item.get("existed")):
            src = root / "Files" / rel
            if not src.is_file():
                raise RuntimeError(f"Backup ausente para restauração: {rel}")
            if sha256_file(src) != str(item.get("sha256") or ""):
                raise RuntimeError(f"SHA do backup divergiu: {rel}")
            safe_copy(src, dest)
        else:
            if dest.is_file():
                dest.unlink()

    protected_dirs = manifest.get("protected_state_dirs") or []
    if isinstance(protected_dirs, list):
        for rel in protected_dirs:
            rel = str(rel)
            src_dir = root / "ProtectedState" / rel
            dest_dir = SYSTEM / rel
            if not src_dir.is_dir():
                raise RuntimeError(f"Snapshot de estado protegido ausente: {rel}")
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)

    result = run_linux_validator()
    return {
        "status": "PASS",
        "restored_at": iso_now(),
        "integrity": result,
        "backup": str(root),
    }


def rebuild_app_integrity() -> dict[str, Any]:
    app = SYSTEM / "App"
    sys.path.insert(0, str(app))
    from Core.release import write_manifest, verify_manifest  # type: ignore
    manifest = write_manifest(SYSTEM)
    verify_manifest(SYSTEM, exact_file_set=True)
    return {
        "manifest": str(app / "Config" / "app.integrity.json"),
        "files": len(manifest.get("files") or {}),
    }


def update_generated_metadata(contract, manifest: dict[str, Any], digest: str) -> None:
    branch_json = read_json(SYSTEM / "CJL.branch.json", {})
    branch = str(branch_json.get("branch") or "MAIN").upper()

    state_payload = contract.state_payload(SYSTEM, manifest, branch)
    state_payload["patch_sha256"] = digest
    write_json_atomic(SYSTEM / "Updates" / "State" / "atual.json", state_payload)

    target = manifest.get("target") or {}
    marker_path = SYSTEM / "CJL.root.json"
    marker = read_json(marker_path, {})
    marker.update({
        "version": target.get("version"),
        "version_full": target.get("version_full"),
        "incremental_id": f"IN-{int(target.get('incremental') or 0):02d}",
        "security_id": f"SE-{int(target.get('security') or 0):03d}",
        "branch": branch,
        "branch_contract": int(marker.get("branch_contract") or 1),
    })
    write_json_atomic(marker_path, marker)

    prov_path = SYSTEM / "App" / "Config" / "provenance.json"
    prov = read_json(prov_path, {})
    prov.update({
        "current_version": target.get("version"),
        "current_version_full": target.get("version_full"),
        "current_incremental": f"IN-{int(target.get('incremental') or 0):02d}",
        "current_security": f"SE-{int(target.get('security') or 0):03d}",
        "current_build": int(target.get("build") or 0),
        "branch_contract": int(prov.get("branch_contract") or 1),
    })
    write_json_atomic(prov_path, prov)


def apply_current() -> dict[str, Any]:
    state, rec = current_record()
    assert rec is not None
    if str(rec.get("status") or "") != "PATCH_READY":
        raise RuntimeError("Aplicação exige PATCH_READY. Execute a validação primeiro.")

    validation = validate_current(update_state=False)
    p = patch_path(rec)
    digest = sha256_file(p)
    contract = load_apply_contract()
    patch_id = str(validation["patch_id"])

    evidence = EVIDENCE_ROOT / f"{compact_now()}_{patch_id}_{digest[:8]}"
    evidence.mkdir(parents=True, exist_ok=False)

    with tempfile.TemporaryDirectory(prefix="ascalpi-linux-apply-") as td:
        patch_root = contract.extract(p, Path(td))
        manifest, ops = contract.validate_patch(SYSTEM, patch_root, p, "DEV")

        with maintenance_lock(patch_id):
            stop_info = stop_linux_authorized()
            write_json_atomic(evidence / "01-stop.json", stop_info)

            pre_integrity = run_linux_validator()
            write_json_atomic(evidence / "02-pre-integrity.json", pre_integrity)

            backup_root, backup_manifest = backup_for_ops(ops, patch_id, digest)
            write_json_atomic(evidence / "03-backup.json", backup_manifest)

            applied: list[dict[str, Any]] = []
            try:
                for op in ops:
                    action = str(op["action"]).upper()
                    rel = str(op["path"])
                    dest = SYSTEM / rel

                    if process_conflicts():
                        raise RuntimeError("Processo relacionado ao 1-Dev reapareceu durante a aplicação.")

                    if action == "REMOVE":
                        if dest.is_file():
                            dest.unlink()
                    else:
                        src = patch_root / "Payload" / rel
                        if not src.is_file():
                            raise RuntimeError(f"Payload ausente: {rel}")
                        expected = str(op.get("after") or "")
                        if sha256_file(src) != expected:
                            raise RuntimeError(f"SHA do payload divergiu: {rel}")
                        safe_copy(src, dest)
                        if sha256_file(dest) != expected:
                            raise RuntimeError(f"SHA aplicado divergiu: {rel}")
                    applied.append({"action": action, "path": rel})

                update_generated_metadata(contract, manifest, digest)
                integrity_manifest = rebuild_app_integrity()
                post_integrity = run_linux_validator()
                post_surface = surface_map()

                result = {
                    "status": "PASS",
                    "patch_id": patch_id,
                    "patch_sha256": digest,
                    "applied_at": iso_now(),
                    "operations": applied,
                    "backup": str(backup_root),
                    "host_rebuild_deferred_to_compiler": bool(manifest.get("host_rebuild")),
                    "integrity_manifest": integrity_manifest,
                    "post_integrity": post_integrity,
                    "post_surface_sha256": surface_digest(post_surface),
                    "evidence": str(evidence),
                }
                write_json_atomic(evidence / "04-apply-pass.json", result)

                rec["status"] = "PATCH_APPLIED"
                rec["applied_at"] = result["applied_at"]
                rec["apply"] = result
                save_state(state)
                return result

            except Exception as exc:
                rollback = restore_backup(backup_root)
                failure = {
                    "status": "FAIL",
                    "failed_at": iso_now(),
                    "error": str(exc),
                    "rollback": rollback,
                }
                write_json_atomic(evidence / "04-apply-fail-rollback.json", failure)
                rec["status"] = "PATCH_READY"
                rec["last_apply_failure"] = failure
                save_state(state)
                raise RuntimeError(
                    "Aplicação falhou e o rollback foi executado: " + str(exc)
                ) from exc


def regression_test(rec: dict[str, Any]) -> dict[str, Any]:
    apply_info = rec.get("apply")
    if not isinstance(apply_info, dict):
        raise RuntimeError("Não há estado de aplicação para teste de regressão.")

    state, _ = current_record()
    p = patch_path(rec)
    contract = load_apply_contract()
    with tempfile.TemporaryDirectory(prefix="ascalpi-regression-") as td:
        patch_root = contract.extract(p, Path(td))
        manifest, ops = contract.validate_patch(SYSTEM, patch_root, p, "DEV")
        # validate_patch checks source baseline, so after application it is expected
        # to fail. Therefore regression verification below uses target file hashes.
        # This call is kept only to parse/extract safely; source-baseline mismatch
        # is handled by reading the manifest directly if needed.
    return {"status": "SKIPPED_INTERNAL"}


def parse_patch_ops_without_source_gate(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        hits = [n for n in names if n == "patch.json" or n.endswith("/patch.json")]
        if len(hits) != 1:
            raise RuntimeError("patch.json ausente/ambíguo.")
        manifest = json.loads(z.read(hits[0]).decode("utf-8"))
        if not isinstance(manifest, dict) or int(manifest.get("format") or 0) != 7:
            raise RuntimeError("Patch não é Format 7.")
        ops = manifest.get("operations")
        if not isinstance(ops, list) or not ops:
            raise RuntimeError("Patch sem operações.")
        return manifest, [x for x in ops if isinstance(x, dict)]


def regression_after_apply(rec: dict[str, Any]) -> dict[str, Any]:
    p = patch_path(rec)
    manifest, ops = parse_patch_ops_without_source_gate(p)
    errors: list[str] = []

    for x in ops:
        action = str(x.get("action") or "").upper()
        rel = str(x.get("path") or "").replace("\\", "/").strip("/")
        dest = SYSTEM / rel
        after = str(x.get("sha256_after") or "").lower()
        if action in {"ADD", "REPLACE"}:
            if not dest.is_file():
                errors.append(f"Arquivo esperado ausente: {rel}")
            elif sha256_file(dest) != after:
                errors.append(f"SHA pós-patch divergiu: {rel}")
        elif action == "REMOVE":
            if dest.exists():
                errors.append(f"Arquivo removido reapareceu: {rel}")

    apply_info = rec.get("apply") or {}
    expected_surface = str(apply_info.get("post_surface_sha256") or "")
    current_surface = surface_digest(surface_map())
    if expected_surface and current_surface != expected_surface:
        errors.append("Superfície do sistema mudou desde a aplicação controlada.")

    target = manifest.get("target") or {}
    sistema = read_json(SYSTEM / "App" / "Config" / "sistema.json", {})
    expected_version = str(target.get("version_full") or "")
    if expected_version and str(sistema.get("version_full") or "") != expected_version:
        errors.append("Versão atual não corresponde ao target do patch.")

    return {
        "status": "PASS" if not errors else "FAIL",
        "checked_at": iso_now(),
        "errors": errors,
        "surface_sha256": current_surface,
    }


def functional_smoke() -> dict[str, Any]:
    start = run_cmd(["bash", START_SCRIPT], check=False, cwd=DEV_ROOT)
    if start.returncode != 0:
        return {
            "status": "FAIL",
            "started_at": iso_now(),
            "stdout": (start.stdout or "").strip(),
            "stderr": (start.stderr or "").strip(),
        }

    time.sleep(0.5)
    status = run_cmd(["bash", STATUS_SCRIPT], check=False, cwd=DEV_ROOT)
    online = status.returncode == 0 and "CJL_LINUX_STATUS=ONLINE" in (status.stdout or "")

    stop = run_cmd(["bash", STOP_SCRIPT], check=False, cwd=DEV_ROOT)
    stopped = stop.returncode == 0

    return {
        "status": "PASS" if online and stopped else "FAIL",
        "checked_at": iso_now(),
        "start_stdout": (start.stdout or "").strip(),
        "status_stdout": (status.stdout or "").strip(),
        "stop_stdout": (stop.stdout or "").strip(),
        "stop_stderr": (stop.stderr or "").strip(),
    }


def optional_security_scan(rec: dict[str, Any]) -> dict[str, Any]:
    p = patch_path(rec)
    findings: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                name = str(info.filename or "").replace("\\", "/")
                low = name.casefold()
                if any(part in low for part in ("/.env", "id_rsa", "id_ed25519", ".pem", ".pfx", ".p12")):
                    findings.append({"type": "SUSPICIOUS_FILENAME", "path": name})
                ext = Path(name).suffix.casefold()
                if ext not in TEXT_EXTENSIONS or info.file_size > 2 * 1024 * 1024:
                    continue
                try:
                    text = z.read(info).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                for label, pattern in SECURITY_PATTERNS:
                    if pattern.search(text):
                        findings.append({"type": label, "path": name})
    except Exception as exc:
        return {
            "status": "WARNING",
            "blocking": False,
            "checked_at": iso_now(),
            "error": str(exc),
            "findings": [],
        }

    return {
        "status": "WARNING" if findings else "PASS",
        "blocking": False,
        "checked_at": iso_now(),
        "findings": findings,
        "note": "Security test is informational/non-blocking in Linux Stage R1.",
    }


def run_tests(run_security: bool) -> dict[str, Any]:
    state, rec = current_record()
    assert rec is not None
    if str(rec.get("status") or "") not in {"PATCH_APPLIED", "LINUX_TESTING"}:
        raise RuntimeError("Testes exigem PATCH_APPLIED.")

    rec["status"] = "LINUX_TESTING"
    save_state(state)

    evidence = EVIDENCE_ROOT / f"{compact_now()}_TEST_{rec.get('patch_id') or str(rec.get('sha256'))[:8]}"
    evidence.mkdir(parents=True, exist_ok=False)

    integrity: dict[str, Any]
    try:
        integrity = run_linux_validator()
        integrity["status"] = "PASS"
    except Exception as exc:
        integrity = {"status": "FAIL", "error": str(exc), "checked_at": iso_now()}

    functional = functional_smoke() if integrity["status"] == "PASS" else {
        "status": "FAIL",
        "error": "Functional smoke skipped because integrity failed.",
        "checked_at": iso_now(),
    }

    regression = regression_after_apply(rec) if integrity["status"] == "PASS" else {
        "status": "FAIL",
        "errors": ["Regression skipped because integrity failed."],
        "checked_at": iso_now(),
    }

    security = optional_security_scan(rec) if run_security else {
        "status": "NOT_RUN",
        "blocking": False,
        "checked_at": iso_now(),
        "note": "Optional in Linux Stage R1.",
    }

    mandatory_pass = all(
        x.get("status") == "PASS"
        for x in (integrity, functional, regression)
    )

    result = {
        "status": "PASS" if mandatory_pass else "FAIL",
        "mandatory_gate": {
            "integrity": integrity.get("status"),
            "functional": functional.get("status"),
            "regression": regression.get("status"),
        },
        "security_gate": "NON_BLOCKING",
        "security": security,
        "integrity": integrity,
        "functional": functional,
        "regression": regression,
        "tests_at": iso_now(),
        "evidence": str(evidence),
    }
    write_json_atomic(evidence / "tests.json", result)

    rec["tests"] = result
    rec["tests_at"] = result["tests_at"]
    rec["status"] = "PATCH_TESTED" if mandatory_pass else "PATCH_APPLIED"
    save_state(state)
    return result


def compiler_handoff(rec: dict[str, Any]) -> dict[str, Any]:
    p = patch_path(rec)
    digest = sha256_file(p)
    COMPILER_INBOX.mkdir(parents=True, exist_ok=True)
    dest = COMPILER_INBOX / p.name
    if dest.exists():
        existing = sha256_file(dest)
        if existing != digest:
            dest = COMPILER_INBOX / f"{p.stem}__{digest[:8]}{p.suffix}"
    safe_copy(p, dest)
    copied = sha256_file(dest)
    if copied != digest:
        raise RuntimeError("SHA do handoff ao Compiler divergiu.")
    return {
        "status": "PASS",
        "path": str(dest),
        "sha256": copied,
        "handed_off_at": iso_now(),
    }


def decision_receipt(rec: dict[str, Any], status: str, extra: dict[str, Any]) -> Path:
    digest = str(rec.get("sha256") or "")
    out = EVIDENCE_ROOT / "Receipts"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{digest}__{status}.json"
    value = {
        "format": 1,
        "product": "ASCALPI",
        "stage": "LINUX",
        "status": status,
        "patch_id": rec.get("patch_id"),
        "patch_sha256": digest,
        "timestamp": iso_now(),
        **extra,
    }
    write_json_atomic(path, value)
    return path


def approve_current() -> dict[str, Any]:
    state, rec = current_record()
    assert rec is not None
    if str(rec.get("status") or "") != "PATCH_TESTED":
        raise RuntimeError("Aprovação exige PATCH_TESTED com todos os testes obrigatórios PASS.")
    tests = rec.get("tests")
    if not isinstance(tests, dict) or tests.get("status") != "PASS":
        raise RuntimeError("Testes obrigatórios não estão em PASS.")

    # Final integrity and regression gate immediately before approval.
    final_integrity = run_linux_validator()
    final_regression = regression_after_apply(rec)
    if final_regression.get("status") != "PASS":
        raise RuntimeError("Regressão final falhou antes da aprovação.")

    p = patch_path(rec)
    digest = sha256_file(p)
    if digest != str(rec.get("sha256") or ""):
        raise RuntimeError("SHA do patch mudou antes da aprovação.")

    approved_path = PATCH_APPROVED / p.name
    if approved_path.exists() and sha256_file(approved_path) != digest:
        approved_path = PATCH_APPROVED / f"{p.stem}__{digest[:8]}{p.suffix}"
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(approved_path))

    rec["current_path"] = str(approved_path)
    handoff = compiler_handoff(rec)
    rec["compiler_handoff"] = handoff
    rec["status"] = "LINUX_PASS"
    rec["decision"] = "APPROVED"
    rec["decision_at"] = iso_now()
    rec["final_integrity"] = final_integrity
    rec["final_regression"] = final_regression
    receipt = decision_receipt(
        rec, "LINUX_PASS",
        {"compiler_handoff": handoff, "tests": tests}
    )
    rec["receipt"] = str(receipt)
    state["current_sha256"] = ""
    save_state(state)
    return {
        "status": "LINUX_PASS",
        "patch_id": rec.get("patch_id"),
        "patch_sha256": digest,
        "approved_path": str(approved_path),
        "compiler_handoff": handoff,
        "receipt": str(receipt),
        "approved_at": rec["decision_at"],
    }


def reject_current(reason: str) -> dict[str, Any]:
    reason = reason.strip()
    if not reason:
        raise RuntimeError("Motivo da reprovação é obrigatório.")
    state, rec = current_record()
    assert rec is not None

    if str(rec.get("status") or "") == "LINUX_PASS":
        raise RuntimeError("Patch já aprovado não pode ser reprovado pelo estágio Linux.")

    p = patch_path(rec)
    rollback: dict[str, Any] = {"status": "NOT_REQUIRED"}
    apply_info = rec.get("apply")
    if isinstance(apply_info, dict) and apply_info.get("backup"):
        with maintenance_lock(str(rec.get("patch_id") or "PATCH")):
            stop_linux_authorized()
            rollback = restore_backup(Path(str(apply_info["backup"])))

    rejected_path = PATCH_REJECTED / p.name
    digest = sha256_file(p)
    if rejected_path.exists() and sha256_file(rejected_path) != digest:
        rejected_path = PATCH_REJECTED / f"{p.stem}__{digest[:8]}{p.suffix}"
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(rejected_path))

    rec["current_path"] = str(rejected_path)
    rec["status"] = "LINUX_FAIL"
    rec["decision"] = "REJECTED"
    rec["decision_at"] = iso_now()
    rec["reason"] = reason
    rec["rollback"] = rollback
    receipt = decision_receipt(
        rec, "LINUX_FAIL",
        {"reason": reason, "rollback": rollback}
    )
    rec["receipt"] = str(receipt)
    state["current_sha256"] = ""
    save_state(state)
    return {
        "status": "LINUX_FAIL",
        "patch_id": rec.get("patch_id"),
        "patch_sha256": digest,
        "rejected_path": str(rejected_path),
        "rollback": rollback,
        "receipt": str(receipt),
        "rejected_at": rec["decision_at"],
    }


def ui_delete() -> None:
    state = load_state()
    current = str(state.get("current_sha256") or "")
    items = [
        x for x in records_sorted("all")
        if str(x.get("status") or "") in {"LINUX_PASS", "LINUX_FAIL"}
    ]
    if not items:
        print("Nenhum patch concluído elegível para análise de exclusão.")
        return
    for i, item in enumerate(items, 1):
        print_record(item, i)
    raw = input("Número do patch a excluir [0 cancela]: ").strip()
    if raw in {"", "0"}:
        return
    try:
        idx = int(raw)
    except ValueError:
        raise RuntimeError("Seleção inválida.")
    if idx < 1 or idx > len(items):
        raise RuntimeError("Seleção fora da lista.")
    item = items[idx - 1]
    digest = str(item["sha256"])
    if digest == current:
        raise RuntimeError("PATCH EM USO: o Patch Atual não pode ser excluído.")

    status = str(item.get("status") or "")
    p = Path(str(item.get("current_path") or ""))
    if not p.is_file():
        raise RuntimeError("Arquivo histórico já não existe no caminho registrado.")

    if status == "LINUX_PASS":
        handoff = item.get("compiler_handoff")
        if not isinstance(handoff, dict) or handoff.get("status") != "PASS":
            raise RuntimeError("Exclusão bloqueada: handoff ao Compiler ainda não está confirmado.")
        cp = Path(str(handoff.get("path") or ""))
        if not cp.is_file() or sha256_file(cp) != digest:
            raise RuntimeError("Exclusão bloqueada: cópia do Compiler ausente ou com SHA divergente.")
    elif status == "LINUX_FAIL":
        rollback = item.get("rollback")
        if isinstance(rollback, dict):
            rb = str(rollback.get("status") or "")
            if rb not in {"PASS", "NOT_REQUIRED"}:
                raise RuntimeError("Exclusão bloqueada: rollback não está confirmado.")

    print("\nPATCH:")
    print(f"  {item.get('patch_id')}")
    print(f"STATUS: {status}")
    print(f"DATA:   {item.get('decision_at') or '-'}")
    print(f"SHA256: {digest}")
    print(f"TAMANHO:{p.stat().st_size} bytes")
    phrase = f"EXCLUIR {str(item.get('patch_id') or digest[:8])}"
    typed = input(f"\nDigite exatamente: {phrase}\n> ").strip()
    if typed != phrase:
        print("Exclusão cancelada.")
        return

    p.unlink()
    rec = state["patches"][digest]
    rec["deleted_at"] = iso_now()
    rec["deleted_from_linux_archive"] = True
    rec["current_path"] = ""
    save_state(state)
    print("PATCH_DELETE=PASS")


def evidence_current() -> None:
    state, rec = current_record(require=False)
    if not rec:
        print("Nenhum Patch Atual. Últimos registros:")
        for item in records_sorted("all")[:5]:
            print_record(item)
        return
    digest = str(state.get("current_sha256") or "")
    value = dict(rec)
    value["sha256"] = digest
    print(json.dumps(value, ensure_ascii=False, indent=2))


def status_summary() -> dict[str, Any]:
    state = load_state()
    digest = str(state.get("current_sha256") or "")
    rec = state["patches"].get(digest) if digest else None
    return {
        "status": "PASS",
        "dev_root": str(DEV_ROOT),
        "system": str(SYSTEM),
        "runtime": str(RUNTIME),
        "runtime_available": os.access(RUNTIME, os.X_OK),
        "state_root": str(STATE_ROOT),
        "maintenance": MAINTENANCE_LOCK.exists(),
        "current_patch": rec if isinstance(rec, dict) else None,
        "counts": {
            "all": len(records_sorted("all")),
            "approved": len(records_sorted("aprovados")),
            "rejected": len(records_sorted("reprovados")),
        },
        "checked_at": iso_now(),
    }


def doctor() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for label, path, kind in (
        ("DEV_ROOT", DEV_ROOT, "dir"),
        ("SYSTEM", SYSTEM, "dir"),
        ("CONFIG", CONFIG, "file"),
        ("VALIDATOR", VALIDATOR, "file"),
        ("STATUS_SCRIPT", STATUS_SCRIPT, "file"),
        ("STOP_SCRIPT", STOP_SCRIPT, "file"),
        ("START_SCRIPT", START_SCRIPT, "file"),
        ("APPLY_CONTRACT", APPLY_CONTRACT, "file"),
    ):
        ok = path.is_dir() if kind == "dir" else path.is_file()
        checks[label] = {"ok": ok, "path": str(path)}
    checks["RUNTIME"] = {"ok": os.access(RUNTIME, os.X_OK), "path": str(RUNTIME)}
    required_ok = all(bool(x.get("ok")) for x in checks.values())
    result = {
        "status": "PASS" if required_ok else "FAIL",
        "checks": checks,
        "runtime": str(RUNTIME),
        "state_root": str(STATE_ROOT),
        "checked_at": iso_now(),
    }
    if required_ok:
        contract = load_apply_contract()
        result["patch_contract_functions"] = [
            x for x in ("extract", "validate_patch", "state_payload", "sha")
            if hasattr(contract, x)
        ]
    return result


def main() -> int:
    ensure_layout()
    parser = argparse.ArgumentParser(description="ASCALPI Linux Patch Stage R1")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor")
    sub.add_parser("status")
    sub.add_parser("integrity")
    p_import = sub.add_parser("import")
    p_import.add_argument("path")
    sub.add_parser("list")
    sub.add_parser("select")
    sub.add_parser("validate")
    sub.add_parser("apply")
    p_tests = sub.add_parser("tests")
    p_tests.add_argument("--security", action="store_true")
    sub.add_parser("approve")
    p_reject = sub.add_parser("reject")
    p_reject.add_argument("--reason", required=True)
    sub.add_parser("delete")
    sub.add_parser("evidence")
    p_restore = sub.add_parser("restore")
    p_restore.add_argument("--backup", default="")

    args = parser.parse_args()

    if args.cmd == "doctor":
        result = doctor()
    elif args.cmd == "status":
        result = status_summary()
    elif args.cmd == "integrity":
        result = run_linux_validator()
        result["status"] = "PASS"
    elif args.cmd == "import":
        result = import_patch(Path(args.path))
    elif args.cmd == "list":
        ui_list()
        return 0
    elif args.cmd == "select":
        ui_select()
        return 0
    elif args.cmd == "validate":
        result = validate_current(update_state=True)
    elif args.cmd == "apply":
        result = apply_current()
    elif args.cmd == "tests":
        result = run_tests(bool(args.security))
    elif args.cmd == "approve":
        result = approve_current()
    elif args.cmd == "reject":
        result = reject_current(str(args.reason))
    elif args.cmd == "delete":
        ui_delete()
        return 0
    elif args.cmd == "evidence":
        evidence_current()
        return 0
    elif args.cmd == "restore":
        if args.backup:
            root = Path(args.backup)
        else:
            _, rec = current_record()
            assert rec is not None
            apply_info = rec.get("apply")
            if not isinstance(apply_info, dict) or not apply_info.get("backup"):
                raise RuntimeError("Patch Atual não possui backup registrado.")
            root = Path(str(apply_info["backup"]))
        with maintenance_lock("MANUAL_RESTORE"):
            stop_linux_authorized()
            result = restore_backup(root)
    else:
        raise RuntimeError("Comando não implementado.")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        eprint("\nOperação cancelada pelo operador.")
        raise SystemExit(130)
    except SystemExit:
        raise
    except BaseException as exc:
        eprint(f"[STOP] {exc}")
        raise SystemExit(2)
