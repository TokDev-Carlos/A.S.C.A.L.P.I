from __future__ import annotations

import json
import os
import re
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parents[1] / "Config" / "sistema.json"
CORE_VERSION_PATTERN = re.compile(
    r"^(?P<structural>0|[1-9]\d*)\.(?P<incremental>\d{2})\.(?P<security>\d{3})$"
)
DISPLAY_VERSION_PATTERN = re.compile(
    r"^(?P<business>0|[1-9]\d*)\.(?P<structural>0|[1-9]\d*)\."
    r"(?P<incremental>\d{2})\.(?P<security>\d{3})$"
)
VERSION_PATTERN = CORE_VERSION_PATTERN


def _canonical_version_file() -> Path:
    override = os.environ.get("CJL_VERSION_FILE", "").strip()
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate
    raise RuntimeError("AUTORIDADE CANONICA VERSION NAO FOI LOCALIZADA.")


def _canonical_components() -> tuple[int, int, int, int]:
    path = _canonical_version_file()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"AUTORIDADE VERSION INDISPONIVEL: {path}") from exc
    match = DISPLAY_VERSION_PATTERN.fullmatch(value)
    if not match:
        raise RuntimeError(f"AUTORIDADE VERSION INVALIDA: {path}")
    return tuple(
        int(match.group(name))
        for name in ("business", "structural", "incremental", "security")
    )


def canonical_version_file() -> Path:
    return _canonical_version_file()


def _load() -> dict:
    value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("CONFIGURACAO DE VERSAO INVALIDA.")
    return value


def format_version(structural: int, incremental: int, security: int) -> str:
    structural = int(structural)
    incremental = int(incremental)
    security = int(security)
    if structural < 0 or not 0 <= incremental <= 99 or not 0 <= security <= 999:
        raise ValueError("COMPONENTES DE VERSAO FORA DO INTERVALO SUPORTADO.")
    return f"{structural}.{incremental:02d}.{security:03d}"


def parse_version(value: str) -> tuple[int, int, int]:
    match = CORE_VERSION_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError(f"VERSAO INVALIDA: {value!r}.")
    return tuple(
        int(match.group(name))
        for name in ("structural", "incremental", "security")
    )


def normalize_version(value: str) -> str:
    return format_version(*parse_version(value))


def version_key(value: str) -> tuple[int, int, int]:
    return parse_version(value)


def format_full_version(
    business: int, structural: int, incremental: int, security: int
) -> str:
    return (
        f"{int(business)}.{int(structural)}."
        f"{int(incremental):02d}.{int(security):03d}"
    )


def versioning() -> dict:
    cfg = _load()
    block = cfg.get("versioning")
    if not isinstance(block, dict) or int(block.get("format") or 0) != 3:
        raise RuntimeError("BLOCO VERSIONING BASE 5 INVALIDO.")
    business, structural, incremental, security = _canonical_components()
    compat = int(block.get("compat_sequence") or 0)
    if business < 1 or structural < 1 or security < 1 or compat < 1:
        raise RuntimeError("IDENTIDADE BASE 5 INVALIDA.")
    expected = {
        "business_id": f"BA-{business:02d}",
        "structural_id": f"ES-{structural:02d}",
        "incremental_id": f"IN-{incremental:02d}",
        "security_id": f"SE-{security:03d}",
    }
    return {
        **block,
        **expected,
        "business": business,
        "structural": structural,
        "incremental": incremental,
        "security": security,
        "compat_sequence": compat,
        "public_version": format_full_version(
            business, structural, incremental, security
        ),
        "core_version": format_version(structural, incremental, security),
        "timezone": str(block.get("timezone") or "America/Sao_Paulo"),
    }


def app_version() -> str:
    _, structural, incremental, security = _canonical_components()
    return format_version(structural, incremental, security)


def app_version_full() -> str:
    return format_full_version(*_canonical_components())


def business_version() -> int:
    return _canonical_components()[0]


def structural_version() -> int:
    return _canonical_components()[1]


def incremental_version() -> int:
    return _canonical_components()[2]


def security_version() -> int:
    return _canonical_components()[3]


def patch_ids() -> dict:
    value = versioning()
    return {
        "business": value["business_id"],
        "structural": value["structural_id"],
        "incremental": value["incremental_id"],
        "security": value["security_id"],
    }


def compatibility_sequence() -> int:
    return int(versioning()["compat_sequence"])


def patch_number() -> int:
    return compatibility_sequence()


def schema_version() -> int:
    return int(_load().get("schema_version") or 0)


def runtime_version() -> int:
    return int(_load().get("runtime_version") or 0)


def build_number() -> int:
    return int(_load().get("build") or 0)


def version_identity() -> dict:
    value = versioning()
    return {
        "version_core": app_version(),
        "version_full": app_version_full(),
        "business": value["business"],
        "structural": value["structural"],
        "incremental": value["incremental"],
        "security": value["security"],
        "compat_sequence": value["compat_sequence"],
    }

