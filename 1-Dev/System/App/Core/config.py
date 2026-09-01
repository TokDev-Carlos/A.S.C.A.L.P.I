from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from Core.atomic import atomic_write_json
from Core.provenance import master_id


SYSTEM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SYSTEM_DIR.parent
APP_NAME = "CJL"
DEPLOYMENT_FILE = SYSTEM_DIR / "Config" / "implantacao.json"


def _windows_folder(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable, "").strip()
    return Path(value) if value else fallback


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def config_file() -> Path:
    """Arquivo local de diagnóstico/estação; nunca define onde o Mestre está."""
    override = os.environ.get("CJL_CONFIG_FILE", "").strip()
    if override:
        return Path(override)
    return local_state_root() / "Estacao" / "config.json"


def local_config() -> dict:
    return _read_json(config_file())


def deployment_policy() -> dict:
    policy = _read_json(DEPLOYMENT_FILE)
    required = {
        "format": 3,
        "product": "CJL System",
        "path_mode": "PORTABLE_SELECTED",
        "master_id": master_id(),
        "automatic_drive_mapping": False,
        "remember_selected_master": True,
        "user_install_requires_selection": True,
    }
    for key, expected in required.items():
        actual = policy.get(key)
        if isinstance(expected, bool):
            valid = bool(actual) is expected
        else:
            valid = str(actual).casefold() == str(expected).casefold()
        if not valid:
            raise RuntimeError(f"POLÍTICA DE IMPLANTAÇÃO INVÁLIDA: {key}.")
    if not any(bool(policy.get(name)) for name in ("allow_local_drive", "allow_mapped_drive", "allow_unc")):
        raise RuntimeError("A POLÍTICA DE IMPLANTAÇÃO NÃO AUTORIZA NENHUM TIPO DE CAMINHO.")
    return policy


def expected_network_root_text() -> str:
    """Retorna o Mestre efetivamente selecionado/aberto, sem caminho fixo global."""
    return str(network_root())


def validate_deployment_root(value: str | Path | None = None) -> Path:
    """Valida o Mestre pelo caminho real e pela identidade, sem exigir letra de unidade fixa."""
    deployment_policy()
    raw = str(value if value is not None else network_root())
    normalized = normalize_network_path(raw)
    root = Path(normalized)
    if not root.is_dir():
        raise RuntimeError(f"O CAMINHO DO MESTRE NÃO ESTÁ DISPONÍVEL: {normalized}")
    required = (
        root / "App" / "Config" / "master.id",
        root / "App" / "Config" / "layout.json",
        root / "App" / "Config" / "sistema.json",
        root / "App" / "painel.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("O CAMINHO SELECIONADO NÃO É UM MESTRE CJL System VÁLIDO: " + "; ".join(missing))
    try:
        actual_id = (root / "App" / "Config" / "master.id").read_text(encoding="utf-8").strip().upper()
    except OSError as exc:
        raise RuntimeError("A IDENTIDADE DO MESTRE NÃO PÔDE SER LIDA.") from exc
    if actual_id != master_id():
        raise RuntimeError("O MASTER.ID DO CAMINHO SELECIONADO NÃO CORRESPONDE À LINHAGEM DESTE CJL System.")
    return root.resolve()


def normalize_network_path(value: str) -> str:
    """Aceita UNC, unidade mapeada ou qualquer caminho absoluto do Windows."""
    text = os.path.expandvars(str(value or "").strip().strip('"'))
    if not text:
        raise ValueError("INFORME O CAMINHO DO MESTRE.")
    if os.name == "nt":
        text = text.replace("/", "\\")
        if text.startswith("\\\\"):
            text = "\\\\" + "\\".join(part for part in text[2:].split("\\") if part)
        elif not (len(text) >= 3 and text[1] == ":" and text[2] == "\\"):
            raise ValueError("O CAMINHO DO MESTRE DEVE SER ABSOLUTO (UNC OU UNIDADE DO WINDOWS).")
        if len(text) > 3:
            text = text.rstrip("\\")
        return text
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ValueError("O CAMINHO DO MESTRE DEVE SER ABSOLUTO.")
    return str(path)


def network_root() -> Path:
    """
    O Mestre é a referência do sistema.

    - Execução direta: usa a pasta física que contém App/.
    - Estação: o iniciador define CJL_NETWORK_ROOT com o Mestre atual.
    - Configurações antigas em AppData nunca alteram esta decisão.
    """
    override = os.environ.get("CJL_NETWORK_ROOT", "").strip()
    if override:
        return Path(normalize_network_path(override))
    return PROJECT_ROOT


def configured_network_text() -> str:
    return str(network_root())


def install_root() -> Path | None:
    """Raiz persistente da instalação Windows nova, quando controlada pelo Host .NET."""
    value = os.environ.get("CJL_INSTALL_ROOT", "").strip()
    return Path(value).resolve() if value else None


def instance_id() -> str:
    """Identidade estável da instalação física usada para isolar o AppData.

    O identificador combina a linhagem do Mestre com o caminho efetivamente
    aberto. Duas cópias do pacote não disputam o mesmo SQLite mesmo quando são
    executadas pela mesma conta do Windows.
    """
    override = os.environ.get("CJL_INSTANCE_ID", "").strip().upper()
    if override:
        return override
    raw_root = os.environ.get("CJL_NETWORK_ROOT", "").strip() or str(PROJECT_ROOT)
    normalized = os.path.normcase(os.path.abspath(os.path.expandvars(raw_root))).rstrip("\\/")
    suffix = hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()[:12].upper()
    return f"{master_id()}-{suffix}"


def local_state_root() -> Path:
    override = os.environ.get("CJL_STATE_ROOT", "").strip()
    if override:
        return Path(override)
    if os.name == "nt":
        local = _windows_folder("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return local / APP_NAME / "Instancias" / instance_id()
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        / APP_NAME
        / "Instancias"
        / instance_id()
    )


def local_database_path() -> Path:
    return local_state_root() / "Dados" / "sistema.db"


def local_logs_path() -> Path:
    return local_state_root() / "Logs"


def local_backups_path() -> Path:
    return local_state_root() / "Backups"


def local_temp_path() -> Path:
    return local_state_root() / "Temp"


def local_resources_path() -> Path:
    """Recursos opcionais persistentes da estação.

    No Host .NET os recursos pesados ficam ao lado da instalação escolhida. Quando
    não existe instalação local registrada, o estado transitório permanece em AppData.
    """
    installed = install_root()
    if installed is not None:
        return installed / "Recursos"
    return local_state_root() / "Recursos" / "Instalados"


def _layout() -> dict:
    """Le o contrato canônico Layout 5 do Mestre atual."""
    path = SYSTEM_DIR / "Config" / "layout.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError("LAYOUT OFICIAL DO MESTRE AUSENTE OU INVÁLIDO.") from exc
    if not isinstance(value, dict) or int(value.get("format") or 0) != 5:
        raise RuntimeError("FORMATO DO LAYOUT OFICIAL NAO E O LAYOUT 5 CANONICO.")
    return value


def _safe_master_relative(raw: str, key: str) -> Path:
    text = str(raw or "").strip().replace("\\", "/")
    relative = Path(text)
    if not text or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"CAMINHO {key.upper()} INVÁLIDO NO LAYOUT OFICIAL.")
    root = network_root().resolve()
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"CAMINHO {key.upper()} ESCAPA DO MESTRE.") from exc
    return destination


def _declared_master_path(key: str) -> Path:
    layout = _layout()
    return _safe_master_relative(str(layout.get(key) or ""), key)


def shared_data_root() -> Path:
    return _declared_master_path("shared_data")


def repository_root() -> Path:
    return _declared_master_path("repository")


def station_id() -> str:
    path = local_state_root() / "station.json"
    current = _read_json(path)
    value = str(current.get("station_id") or "").strip().upper()
    if value:
        return value
    value = "EST-" + uuid.uuid4().hex[:12].upper()
    atomic_write_json(path, {"station_id": value})
    return value


def save_local_config(network: str | None = None, state_root: str | Path | None = None) -> dict:
    """Grava localmente o Mestre utilizado pela estação sem impor caminho fixo global."""
    payload = {
        "state_root": str(state_root or local_state_root()),
        "station_id": station_id(),
    }
    if network:
        payload["master_root"] = normalize_network_path(network)
        payload["last_master_seen"] = payload["master_root"]
    atomic_write_json(config_file(), payload)
    return payload


def seed_database_path() -> Path:
    layout = _layout()
    if int(layout.get("format") or 0) >= 2 and layout.get("seed_database"):
        return _declared_master_path("seed_database")
    return network_root() / "Data" / "sistema.db"


def _master_runtime_root() -> Path:
    layout = _layout()
    if int(layout.get("format") or 0) >= 2 and layout.get("runtime"):
        return _declared_master_path("runtime")
    return network_root() / "Runtime"


def runtime_component_root(component: str) -> Path:
    """Resolve Runtime/recursos na ordem nova e preserva o host legado."""
    name = str(component or "").strip()
    installed = install_root()
    if installed is not None:
        if name.casefold() == "libreoffice":
            resource = installed / "Recursos" / "LibreOffice"
            if resource.is_dir():
                return resource
        local_component = installed / "Runtime" / name
        if local_component.is_dir():
            return local_component
    if name.casefold() == "libreoffice":
        state_resource = local_state_root() / "Recursos" / "Instalados" / "LibreOffice"
        if state_resource.is_dir():
            return state_resource
    return _master_runtime_root() / name


def runtime_component_installation_root(component: str) -> Path:
    """Raiz usada para conferir o manifesto oficial do componente."""
    name = str(component or "").strip()
    return network_root()


def runtime_root() -> Path:
    return runtime_component_root("Python").parent


def runtime_python() -> Path:
    return runtime_component_root("Python") / "python.exe"


def runtime_pythonw() -> Path:
    preferred = runtime_component_root("Python") / "pythonw.exe"
    return preferred if preferred.is_file() else runtime_python()


def runtime_libreoffice_candidates() -> list[Path]:
    root = runtime_component_root("LibreOffice")
    return [
        root / "App" / "libreoffice" / "program" / "soffice.exe",
        root / "App" / "LibreOffice" / "program" / "soffice.exe",
        root / "program" / "soffice.exe",
        root / "LibreOfficePortable.exe",
    ]


def runtime_libreoffice() -> Path | None:
    """Retorna o LibreOffice opcional do Runtime assinado da aplicação."""
    return next((path for path in runtime_libreoffice_candidates() if path.is_file()), None)


def ensure_local_layout() -> dict:
    root = local_state_root()
    for path in (
        root / "Dados",
        root / "Logs",
        root / "Backups",
        root / "Temp",
        root / "Rascunhos",
        root / "Cache" / "Arquivos",
        root / "Estacao",
        root / "Instancia",
        root / "Preferencias",
        local_resources_path(),
        root / "Recursos" / "Temp",
    ):
        path.mkdir(parents=True, exist_ok=True)
    station = station_id()
    return {
        "state_root": str(root),
        "station_id": station,
        "master_root": str(network_root()),
        "instance_id": instance_id(),
    }
