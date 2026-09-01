from __future__ import annotations

import hashlib
import re
from pathlib import Path


SYSTEM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SYSTEM_DIR.parent
PRODUCT = "CJL System"
CREATOR = "Carlos Alberto da Silva Pinto Júnior"
PUBLIC_ID = "CJL"
OFFICIAL_CONTACT = "Carlosjr.projetos25@gmail.com"
COPYRIGHT = "© 2026 Carlos Alberto da Silva Pinto Júnior — CRJ. Todos os direitos reservados."


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def master_id() -> str:
    path = SYSTEM_DIR / "Config" / "master.id"
    try:
        value = path.read_text(encoding="utf-8").strip().upper()
    except OSError as exc:
        raise RuntimeError("IDENTIDADE DO MESTRE AUSENTE.") from exc
    if not re.fullmatch(r"CJL-MST-[A-Z0-9][A-Z0-9_-]{7,63}", value):
        raise RuntimeError("IDENTIDADE DO MESTRE INVÁLIDA.")
    return value


def license_path() -> Path:
    return PROJECT_ROOT / "LICENSE.txt"


def license_sha256() -> str:
    path = license_path()
    if not path.is_file():
        raise RuntimeError("LICENÇA OFICIAL DO CJL System AUSENTE.")
    return _hash(path)


def copyright_sha256() -> str:
    path = PROJECT_ROOT / "COPYRIGHT.txt"
    if not path.is_file():
        raise RuntimeError("AVISO DE COPYRIGHT DO CJL System AUSENTE.")
    return _hash(path)


def public_notice() -> dict:
    from Core.signature import verify_release_signature
    from Core.version import app_version, build_number, compatibility_sequence, patch_ids, versioning

    trust = verify_release_signature(PROJECT_ROOT)
    return {
        "product": PRODUCT,
        "version": app_version(),
        "patches": patch_ids(),
        "compat_sequence": compatibility_sequence(),
        "versioning": versioning(),
        "build": build_number(),
        "creator": CREATOR,
        "public_id": PUBLIC_ID,
        "official_contact": OFFICIAL_CONTACT,
        "copyright": COPYRIGHT,
        "license": "LICENÇA CRJ DE USO PRIVADO, INTERNO E PRESTAÇÃO DE SERVIÇOS",
        "license_sha256": license_sha256(),
        "copyright_sha256": copyright_sha256(),
        "master_id": master_id(),
        "source_available_is_not_open_source": True,
        "current_release_signed": bool(trust.get("current_release_signed")),
        "trust_mode": str(trust.get("trust_mode") or "SHA256_MIGRATION_CHECKPOINT"),
        "historical_evidence_archived": bool(trust.get("historical_evidence_archived")),
    }
