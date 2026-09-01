from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from Core.atomic import atomic_write_json
from Core.config import PROJECT_ROOT, SYSTEM_DIR, local_resources_path, local_state_root, network_root


CONFIG_PATH = SYSTEM_DIR / "Config" / "recursos.json"
STATE_PATH = local_state_root() / "Recursos" / "estado.json"


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _config() -> list[dict]:
    payload = _read_json(CONFIG_PATH)
    if int(payload.get("format") or 0) != 1 or payload.get("product") != "CJL System":
        raise RuntimeError("CATÁLOGO DE RECURSOS DO CJL System INVÁLIDO.")
    resources = payload.get("resources")
    if not isinstance(resources, list):
        raise RuntimeError("CATÁLOGO DE RECURSOS DO CJL System INVÁLIDO.")
    return [item for item in resources if isinstance(item, dict)]


def _definition(resource_id: str) -> dict:
    wanted = str(resource_id or "").strip().upper()
    definition = next(
        (item for item in _config() if str(item.get("id") or "").strip().upper() == wanted),
        None,
    )
    if not definition:
        raise ValueError("RECURSO NÃO RECONHECIDO.")
    return definition


def _safe_relative(value: str) -> Path:
    path = Path(str(value or "").replace("\\", "/"))
    if not str(path) or path.is_absolute() or ".." in path.parts:
        raise RuntimeError("CAMINHO INVÁLIDO NO CATÁLOGO DE RECURSOS.")
    return path


def _state() -> dict:
    value = _read_json(STATE_PATH)
    return value if isinstance(value.get("installed"), dict) else {"format": 1, "installed": {}}


def resource_target(resource_id: str) -> Path:
    """Destino persistente da estação, independente da versão da aplicação."""
    definition = _definition(resource_id)
    if str(definition.get("target_scope") or "STATE").upper() != "STATE":
        raise RuntimeError("ESCOPO DE DESTINO DE RECURSO NÃO SUPORTADO.")
    relative = _safe_relative(str(definition.get("target") or ""))
    root = local_resources_path().resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("DESTINO DE RECURSO ESCAPA DO ESTADO LOCAL.") from exc
    return target


def _master_source(raw: str) -> Path:
    relative = _safe_relative(raw)
    root = network_root().resolve()
    return root / relative


def _master_fallback(definition: dict) -> Path | None:
    raw = str(definition.get("master_fallback") or "").strip()
    return _master_source(raw) if raw else None


def _critical_valid(definition: dict, target: Path) -> bool:
    critical = definition.get("critical_files")
    if not isinstance(critical, list) or not critical:
        return target.is_dir() and any(path.is_file() for path in target.rglob("*"))
    for entry in critical:
        if not isinstance(entry, dict):
            return False
        candidate = target / _safe_relative(str(entry.get("path") or ""))
        expected = str(entry.get("sha256") or "").lower().strip()
        if not candidate.is_file() or (expected and _sha256(candidate) != expected):
            return False
    return True


def verify_installed_resource(resource_id: str) -> Path:
    """Validação rápida do recurso efetivamente usado pela estação.

    A integridade integral é garantida no transporte pelo SHA-256 do ZIP assinado
    no catálogo. Em uso normal são rechecados apenas arquivos críticos, evitando
    milhares de hashes a cada operação.
    """
    definition = _definition(resource_id)
    wanted = str(definition.get("id") or "").strip().upper()
    target = resource_target(wanted)
    saved = (_state().get("installed") or {}).get(wanted) or {}
    expected_version = str(definition.get("version") or "")
    if target.is_dir() and str(saved.get("version") or "") == expected_version:
        if not _critical_valid(definition, target):
            raise RuntimeError(f"O RECURSO {wanted} ESTÁ ALTERADO OU INCOMPLETO.")
        return target
    fallback = _master_fallback(definition)
    if fallback and fallback.is_dir():
        # O fallback integrado ao Mestre pertence ao Runtime oficial e será
        # validado pelo validador de Runtime no ponto de uso correspondente.
        return fallback
    raise RuntimeError(f"O RECURSO {wanted} NÃO ESTÁ INSTALADO NESTA ESTAÇÃO.")


def list_resources() -> list[dict]:
    master = network_root().resolve()
    local_root = PROJECT_ROOT.resolve()
    saved = _state().get("installed", {})
    result = []
    for item in _config():
        resource_id = str(item.get("id") or "").strip().upper()
        target = resource_target(resource_id)
        package = _master_source(str(item.get("package") or ""))
        fallback = _master_fallback(item)
        expected_version = str(item.get("version") or "")
        saved_version = str((saved.get(resource_id) or {}).get("version") or "")
        state_installed = target.is_dir() and _critical_valid(item, target)
        integrated_master = bool(local_root == master and fallback and fallback.is_dir())
        master_runtime_available = bool(fallback and fallback.is_dir())
        installed = bool(state_installed or integrated_master)
        installed_version = expected_version if integrated_master else (saved_version if state_installed else "")
        needs_update = bool(state_installed and installed_version != expected_version)
        package_available = package.is_file()
        can_install = bool(package_available or master_runtime_available)
        user_visible = bool(item.get("user_visible", False) and (installed or can_install or needs_update))
        result.append({
            "id": resource_id,
            "name": str(item.get("name") or resource_id),
            "description": str(item.get("description") or ""),
            "version": expected_version,
            "required": bool(item.get("required")),
            "installed": installed,
            "installed_version": installed_version,
            "needs_update": needs_update,
            "ready": bool(installed and not needs_update),
            "package_available": can_install,
            "user_visible": user_visible,
            "package_name": package.name,
            "package_size_bytes": int(item.get("package_size_bytes") or 0) if package_available else 0,
            "source": (
                "INTEGRADO_AO_MESTRE" if integrated_master
                else "LOCAL" if state_installed
                else "PACOTE_MESTRE" if package_available
                else "RUNTIME_MESTRE" if master_runtime_available
                else "AGUARDANDO_RECURSO"
            ),
        })
    return result


def _extract_safe(package: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            candidate = (destination / member.filename).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise RuntimeError("PACOTE DE RECURSO CONTÉM CAMINHO INVÁLIDO.") from exc
        archive.extractall(destination)


def install_resource(resource_id: str) -> dict:
    definition = _definition(resource_id)
    wanted = str(definition.get("id") or "").strip().upper()
    master = network_root().resolve()
    local_root = PROJECT_ROOT.resolve()
    target = resource_target(wanted)
    fallback = _master_fallback(definition)
    if local_root == master and fallback and fallback.is_dir():
        return next(item for item in list_resources() if item["id"] == wanted)

    package = _master_source(str(definition.get("package") or ""))
    package_available = package.is_file()
    fallback_available = bool(fallback and fallback.is_dir())
    if not package_available and not fallback_available:
        raise FileNotFoundError(
            f"O RECURSO {wanted} AINDA NÃO ESTÁ DISPONÍVEL NO MESTRE. "
            "PUBLIQUE O PACOTE OU MANTENHA A FONTE OFICIAL NO RUNTIME DO MESTRE."
        )

    temp_root = local_state_root() / "Recursos" / "Temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{wanted}_", dir=temp_root) as raw_temp:
        temporary = Path(raw_temp)
        payload_root: Path
        transport_hash = ""
        if package_available:
            expected = str(definition.get("sha256") or "").lower().strip()
            if not expected:
                raise RuntimeError("O PACOTE DE RECURSO NÃO POSSUI SHA-256 OFICIAL.")
            if _sha256(package) != expected:
                raise RuntimeError("O PACOTE DE RECURSO NÃO PASSOU NA VERIFICAÇÃO SHA-256.")
            local_package = temporary / package.name
            shutil.copy2(package, local_package)
            actual = _sha256(local_package)
            if actual != expected:
                raise RuntimeError("O PACOTE COPIADO PARA ESTA ESTAÇÃO FOI ALTERADO.")
            extracted = temporary / "extraido"
            extracted.mkdir()
            _extract_safe(local_package, extracted)
            payload_root = extracted / _safe_relative(str(definition.get("payload_root") or ""))
            transport_hash = expected
        else:
            # Fonte direta: reaproveita a árvore oficial já existente no Runtime
            # do Mestre. Evita exigir uma segunda cópia ZIP de centenas de MB.
            assert fallback is not None
            if not _critical_valid(definition, fallback):
                raise RuntimeError("A FONTE DO RECURSO NO RUNTIME DO MESTRE NÃO PASSOU NA VALIDAÇÃO CRÍTICA.")
            payload_root = fallback

        if not payload_root.is_dir():
            raise RuntimeError("O RECURSO NÃO POSSUI A ESTRUTURA ESPERADA.")
        minimum_files = int(definition.get("minimum_files") or 1)
        count = sum(1 for path in payload_root.rglob("*") if path.is_file())
        if count < minimum_files:
            raise RuntimeError("O RECURSO ESTÁ INCOMPLETO.")
        if not _critical_valid(definition, payload_root):
            raise RuntimeError("ARQUIVOS CRÍTICOS DO RECURSO NÃO CONFEREM COM O CATÁLOGO ASSINADO.")

        staging = target.parent / (target.name + ".novo")
        previous = target.parent / (target.name + ".anterior")
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(previous, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        # copytree funciona tanto para o ZIP extraído quanto para Runtime\LibreOffice
        # no Mestre. A validação final de arquivos críticos acontece localmente.
        shutil.copytree(payload_root, staging)
        if not _critical_valid(definition, staging):
            shutil.rmtree(staging, ignore_errors=True)
            raise RuntimeError("A CÓPIA LOCAL DO RECURSO NÃO PASSOU NA VALIDAÇÃO CRÍTICA.")
        if target.exists():
            os.replace(target, previous)
        try:
            os.replace(staging, target)
        except Exception:
            if previous.exists() and not target.exists():
                os.replace(previous, target)
            raise
        shutil.rmtree(previous, ignore_errors=True)

    state = _state()
    state.setdefault("installed", {})[wanted] = {
        "version": str(definition.get("version") or ""),
        "package_sha256": transport_hash,
        "source": "PACOTE_MESTRE" if package_available else "RUNTIME_MESTRE",
    }
    atomic_write_json(STATE_PATH, state)
    return next(item for item in list_resources() if item["id"] == wanted)

