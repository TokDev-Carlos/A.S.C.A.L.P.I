from __future__ import annotations

import json
from pathlib import Path

from Core.release import normalize_version, read_json, verify_manifest, version_key


STATE_RELATIVE = Path("Updates") / "State" / "atual.json"


def _patch_ids(business: int, structural: int, incremental: int, security: int) -> dict:
    return {
        "business": f"BA-{int(business):02d}",
        "structural": f"ES-{int(structural):02d}",
        "incremental": f"IN-{int(incremental):02d}",
        "security": f"SE-{int(security):03d}",
    }


def read_state(root: str | Path) -> dict:
    candidate = Path(root).resolve()
    state = read_json(candidate / STATE_RELATIVE)
    try:
        version = normalize_version(str(state.get("version") or ""))
        vk = version_key(version)
        business = int(state.get("business"))
        structural = int(state.get("structural", vk[0]))
        incremental = int(state.get("incremental", vk[1]))
        security = int(state.get("security", vk[2]))
        compat = int(state.get("compat_sequence"))
        minimum_compat = int(state.get("minimum_station_compat") or 0)
        patches = _patch_ids(business, structural, incremental, security)
        value = {
            **state,
            "format": int(state.get("format") or 0),
            "product": str(state.get("product") or ""),
            "product_code": str(state.get("product_code") or ""),
            "business": business,
            "business_id": str(state.get("business_id") or patches["business"]),
            "version": version,
            "structural": structural,
            "incremental": incremental,
            "security": security,
            "patches": patches,
            "compat_sequence": compat,
            "schema": int(state.get("schema")),
            "runtime": int(state.get("runtime")),
            "build": int(state.get("build")),
            "master_id": str(state.get("master_id") or "").strip().upper(),
            "channel": str(state.get("channel") or "").strip().upper(),
            "minimum_station_version": normalize_version(str(state.get("minimum_station_version") or version)),
            "minimum_station_compat": minimum_compat,
            "last_update_mode": str(state.get("last_update_mode") or "LIVE").strip().upper(),
            "last_update_type": str(state.get("last_update_type") or "SE").strip().upper(),
            "timezone": str(state.get("timezone") or "America/Sao_Paulo"),
        }
    except (TypeError, ValueError) as exc:
        raise RuntimeError("ESTADO DE ATUALIZACAO AUSENTE OU INVALIDO.") from exc
    if (
        value["format"] != 4
        or value["product"] != "CJL System"
        or value["product_code"] != "CJL"
        or value["business"] < 1
        or value["business_id"] != f"BA-{value['business']:02d}"
        or version_key(value["version"]) != (value["structural"], value["incremental"], value["security"])
        or value["compat_sequence"] < 1
        or value["schema"] < 1
        or value["runtime"] < 1
        or value["build"] < 1
        or not value["master_id"].startswith("CJL-MST-")
        or value["channel"] != "STABLE"
        or value["minimum_station_compat"] < 0
        or value["last_update_mode"] not in {"LIVE", "CRITICAL", "STRUCTURAL_REBASE"}
        or value["last_update_type"] not in {"BA", "ES", "IN", "SE"}
        or value["timezone"] != "America/Sao_Paulo"
    ):
        raise RuntimeError("ESTADO OFICIAL DA ATUALIZACAO E INVALIDO.")
    return value


def compare(local: dict, master: dict) -> int:
    """Retorna -1 se local esta atras, 0 se igual e 1 se esta a frente."""
    local_key = (version_key(str(local["version"])), int(local["build"]), int(local.get("compat_sequence") or 0))
    master_key = (version_key(str(master["version"])), int(master["build"]), int(master.get("compat_sequence") or 0))
    return (local_key > master_key) - (local_key < master_key)


def validate_candidate(root: str | Path, expected_master_id: str) -> dict:
    candidate = Path(root).resolve()
    state = read_state(candidate)
    if state["master_id"] != str(expected_master_id or "").strip().upper():
        raise RuntimeError("A RELEASE CANDIDATA PERTENCE A OUTRO MESTRE.")
    manifest = verify_manifest(candidate, exact_file_set=True)
    if (
        manifest.get("version") != state["version"]
        or int(manifest.get("business") or -1) != state["business"]
        or str(manifest.get("business_id") or "") != state["business_id"]
        or int(manifest.get("structural", -1)) != state["structural"]
        or int(manifest.get("incremental", -1)) != state["incremental"]
        or int(manifest.get("security", -1)) != state["security"]
        or int(manifest.get("compat_sequence") or -1) != state["compat_sequence"]
        or int(manifest.get("schema_version") or -1) != state["schema"]
        or int(manifest.get("runtime_version") or -1) != state["runtime"]
        or int(manifest.get("build") or -1) != state["build"]
    ):
        raise RuntimeError("MANIFESTO E ESTADO DA RELEASE CANDIDATA DIVERGEM.")
    return {"state": state, "manifest_files": len(manifest["files"]), "ok": True}


def write_local_receipt(path: str | Path, state: dict, application_root: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": 4,
        "product": "CJL System",
        "product_code": "CJL",
        "business": int(state["business"]),
        "business_id": str(state["business_id"]),
        "version": state["version"],
        "structural": int(state["structural"]),
        "incremental": int(state["incremental"]),
        "security": int(state["security"]),
        "patches": state.get("patches") or _patch_ids(state["business"], state["structural"], state["incremental"], state["security"]),
        "compat_sequence": int(state["compat_sequence"]),
        "schema": int(state["schema"]),
        "runtime": int(state["runtime"]),
        "build": int(state["build"]),
        "master_id": state["master_id"],
        "minimum_station_version": str(state.get("minimum_station_version") or state["version"]),
        "minimum_station_compat": int(state.get("minimum_station_compat") or 0),
        "last_update_mode": str(state.get("last_update_mode") or "LIVE"),
        "last_update_type": str(state.get("last_update_type") or "SE"),
        "timezone": "America/Sao_Paulo",
        "application_root": str(Path(application_root)),
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
