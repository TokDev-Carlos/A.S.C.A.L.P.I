from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def validate_python_sources(root: Path) -> int:
    checked = 0
    for base in (root / "App", root / "Host" / "Bridge", root / "Dev" / "Tools"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(path))
            checked += 1
    return checked


def validate_database(root: Path) -> dict:
    database = root / "Data" / "sistema.db"
    if not database.is_file():
        raise RuntimeError(f"Database is absent: {database}")
    wal = database.with_name(database.name + "-wal")
    if wal.exists() and wal.stat().st_size != 0:
        raise RuntimeError("SQLite WAL is not empty; adoption stopped.")

    connection = sqlite3.connect(
        database.as_uri() + "?mode=ro&immutable=1",
        uri=True,
        timeout=15,
    )
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity.casefold() != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        foreign_key_errors = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        if foreign_key_errors:
            raise RuntimeError(
                f"SQLite foreign_key_check found {foreign_key_errors} error(s)."
            )
        admin = connection.execute(
            """
            SELECT count(*)
              FROM usuarios
             WHERE nome = 'ADMIN' COLLATE NOCASE
               AND ativo = 1
               AND length(coalesce(senha_hash, '')) > 0
               AND length(coalesce(senha_salt, '')) > 0
            """
        ).fetchone()[0]
        if int(admin) != 1:
            raise RuntimeError("Active ADMIN credential was not preserved.")
        tables = int(
            connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    return {
        "sha256": sha256_file(database),
        "tables": tables,
        "foreign_key_errors": 0,
        "admin_with_credential": 1,
        "wal_bytes": wal.stat().st_size if wal.exists() else 0,
    }


def validate_repository(root: Path) -> dict:
    head = read_json(root / "Repo" / "HEAD.json")
    anchor = read_json(root / "App" / "Config" / "repository.anchor.json")
    sys.path.insert(0, str(root / "App"))
    from Core.repository import _validate_head_chain

    transaction_sha256 = str(_validate_head_chain(head, {})).lower()
    expected_transaction = str(head.get("transaction_file_sha256") or "").lower()
    if transaction_sha256 != expected_transaction:
        raise RuntimeError("Repository transaction chain does not match HEAD.json.")
    if int(anchor.get("revision") or -1) != int(head.get("revision") or -2):
        raise RuntimeError("Repository anchor revision does not match HEAD.json.")
    if (
        str(anchor.get("transaction_file_sha256") or "").lower()
        != expected_transaction
    ):
        raise RuntimeError("Repository anchor transaction hash does not match.")
    if (
        str(anchor.get("snapshot_sha256") or "").lower()
        != str(head.get("snapshot_sha256") or "").lower()
    ):
        raise RuntimeError("Repository anchor snapshot hash does not match.")
    return {
        "revision": int(head.get("revision") or 0),
        "transaction_sha256": transaction_sha256,
    }


def validate(root: Path) -> dict:
    root = root.resolve()
    if root.name != "System":
        raise RuntimeError(f"Expected a System directory, received: {root}")
    required = (
        root / "CJL.root.json",
        root / "CJL.branch.json",
        root / "App" / "painel.py",
        root / "App" / "Config" / "app.integrity.json",
        root / "Data" / "sistema.db",
        root / "Repo" / "HEAD.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Required file(s) absent: " + " | ".join(missing))

    sys.path.insert(0, str(root / "App"))
    from Core.release import verify_manifest
    from Core.version import app_version_full

    manifest = verify_manifest(root, exact_file_set=True)
    config = read_json(root / "App" / "Config" / "sistema.json")
    root_identity = read_json(root / "CJL.root.json")
    branch = read_json(root / "CJL.branch.json")
    if str(manifest.get("version_full") or "") != app_version_full():
        raise RuntimeError("System version differs from the canonical VERSION authority.")
    if str(branch.get("branch") or "").upper() != "MAIN":
        raise RuntimeError("Backup is not the MAIN system requested by the operator.")
    if str(root_identity.get("master_id") or "") != str(
        manifest.get("master_id") or ""
    ):
        raise RuntimeError("System root identity does not match App manifest.")

    for module in ("openpyxl", "PIL", "tzdata"):
        __import__(module)

    python_files = validate_python_sources(root)
    database = validate_database(root)
    repository = validate_repository(root)
    if list(root.rglob("__pycache__")):
        raise RuntimeError("Python cache directory exists in the backup tree.")
    if list(root.rglob("*.pyc")) or list(root.rglob("*.pyo")):
        raise RuntimeError("Compiled Python residue exists in the backup tree.")

    return {
        "status": "PASS",
        "system": str(root),
        "version": str(config.get("version") or ""),
        "version_full": str(config.get("version_full") or ""),
        "branch": str(branch.get("branch") or ""),
        "app_manifest_files": len(manifest.get("files") or {}),
        "python_files": python_files,
        "database": database,
        "repository": repository,
        "runtime_embedded": (root / "Runtime").is_dir(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("system", type=Path)
    args = parser.parse_args()
    result = validate(args.system)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as error:
        print(f"[STOP] VALIDATION_FAILED={error}", file=sys.stderr)
        raise SystemExit(2)
