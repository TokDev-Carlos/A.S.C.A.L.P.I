from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
APP_INTEGRITY_RELATIVE = Path("App") / "Config" / "app.integrity.json"
RUNTIME_MANIFEST_RELATIVE = Path("App") / "Config" / "runtime.integrity.json"
STATE_RELATIVE = Path("Updates") / "State" / "atual.json"
VERSION_PATTERN = re.compile(r"^(?P<structural>0|[1-9]\d*)\.(?P<incremental>\d{2})\.(?P<security>\d{3})$")
IGNORED_DIRECTORY_NAMES = {".git", ".pytest_cache", "__pycache__", ".validation-work", ".cjlstaging"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".tmp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def format_version(structural: int, incremental: int, security: int) -> str:
    structural = int(structural); incremental = int(incremental); security = int(security)
    if structural < 0 or not 0 <= incremental <= 99 or not 0 <= security <= 999:
        raise ValueError("COMPONENTES DE VERSAO FORA DO INTERVALO SUPORTADO.")
    return f"{structural}.{incremental:02d}.{security:03d}"


def normalize_version(value: str) -> str:
    text = str(value or "").strip()
    match = VERSION_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"VERSAO INVALIDA: {value!r}.")
    return format_version(*(int(match.group(name)) for name in ("structural", "incremental", "security")))


def version_key(value: str) -> tuple[int, int, int]:
    text = normalize_version(value)
    match = VERSION_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"VERSAO INVALIDA: {value!r}.")
    return tuple(int(match.group(name)) for name in ("structural", "incremental", "security"))


def _app_root(root: Path) -> Path:
    root = Path(root).resolve()
    if (root / "Config" / "sistema.json").is_file() and root.name.casefold() == "app":
        return root
    candidate = root / "App"
    if candidate.is_dir():
        return candidate
    raise RuntimeError(f"APLICAÇÃO CJL System AUSENTE EM: {root}")


def _project_root(root: Path) -> Path:
    app = _app_root(root)
    return app.parent


def version_info(root: Path) -> tuple[str, int]:
    app = _app_root(Path(root))
    config = read_json(app / "Config" / "sistema.json")
    version = normalize_version(str(config.get("version") or ""))
    try:
        schema = int(config.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise ValueError("SCHEMA_VERSION INVÁLIDO NO SISTEMA.") from exc
    return version, schema


def release_state(root: Path) -> dict:
    project = _project_root(Path(root)); app = project / "App"
    state = read_json(project / STATE_RELATIVE); config = read_json(app / "Config" / "sistema.json")
    version, schema = version_info(app); block = config.get("versioning") if isinstance(config.get("versioning"), dict) else {}
    try:
        master_id=(app/"Config"/"master.id").read_text(encoding="utf-8").strip().upper()
        business=int(state.get("business",block.get("business"))); structural=int(state.get("structural",block.get("structural")))
        incremental=int(state.get("incremental",block.get("incremental"))); security=int(state.get("security",block.get("security")))
        compat=int(state.get("compat_sequence",block.get("compat_sequence"))); runtime=int(state.get("runtime",config.get("runtime_version"))); build=int(state.get("build",config.get("build")))
    except (OSError,TypeError,ValueError) as exc: raise RuntimeError("ESTADO NUMERICO DA RELEASE E INVALIDO.") from exc
    if not master_id.startswith("CJL-MST-") or business<1 or structural<1 or incremental<0 or security<1 or compat<1 or runtime<1 or build<1: raise RuntimeError("ESTADO OFICIAL DA RELEASE NAO CORRESPONDE AO CJL SYSTEM.")
    canonical=format_version(structural,incremental,security)
    if canonical!=version: raise RuntimeError("VERSION DIVERGE DOS COMPONENTES ES/IN/SE.")
    if state and (str(state.get("product") or "")!="CJL System" or normalize_version(str(state.get("version") or ""))!=version or int(state.get("schema") or -1)!=schema or str(state.get("master_id") or "").strip().upper()!=master_id or int(state.get("business") or -1)!=business): raise RuntimeError("ESTADO OFICIAL DA RELEASE NAO CORRESPONDE AO CJL SYSTEM.")
    patches={"business":f"BA-{business:02d}","structural":f"ES-{structural:02d}","incremental":f"IN-{incremental:02d}","security":f"SE-{security:03d}"}
    return {**state,"format":int(state.get("format") or 4),"product":"CJL System","business":business,"business_id":patches["business"],"version":version,"version_full":str(config.get("version_full") or ""),"structural":structural,"incremental":incremental,"security":security,"patches":patches,"compat_sequence":compat,"runtime":runtime,"build":build,"schema":schema,"master_id":master_id,"layout":int(config.get("layout_version") or 5),"timezone":str(state.get("timezone") or block.get("timezone") or "America/Sao_Paulo")}


def _application_files(app: Path) -> list[Path]:
    app = app.resolve()
    result: list[Path] = []
    integrity = (app / "Config" / "app.integrity.json").resolve()
    for current, directories, filenames in os.walk(app):
        current_path = Path(current)
        directories[:] = [d for d in directories if d.casefold() not in IGNORED_DIRECTORY_NAMES]
        for filename in filenames:
            path = current_path / filename
            if path.resolve() == integrity:
                continue
            if path.suffix.casefold() in IGNORED_SUFFIXES:
                continue
            result.append(path)
    return sorted(result, key=lambda p: p.relative_to(app).as_posix().casefold())


def build_app_integrity(root: Path) -> dict:
    app = _app_root(Path(root))
    config = read_json(app / "Config" / "sistema.json")
    state = release_state(app.parent)
    version, schema = version_info(app)
    files = {path.relative_to(app).as_posix(): sha256_file(path) for path in _application_files(app)}
    return {
        "format": 5,
        "product": "CJL System",
        "integrity_scope": "APP",
        "algorithm": "SHA-256",
        "version": version,
        "version_full": str(config.get("version_full") or ""),
        "business": state["business"],
        "business_id": state["business_id"],
        "structural": state["structural"],
        "incremental": state["incremental"],
        "security": state["security"],
        "patches": state["patches"],
        "compat_sequence": state["compat_sequence"],
        "schema_version": schema,
        "runtime_version": int(config.get("runtime_version") or 1),
        "build": int(config.get("build") or 0),
        "layout_version": int(config.get("layout_version") or 5),
        "master_id": (app / "Config" / "master.id").read_text(encoding="utf-8").strip().upper(),
        "generated_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
        "timezone": "America/Sao_Paulo",
        "complete_file_set": True,
        "files": files,
        "trust_note": "SHA-256 da camada App Base 5. Proveniencia de migracao em App/Config/provenance.json e checkpoint de migracao e historico preservado no SM_Repo.",
    }


def write_manifest(root: Path) -> dict:
    payload = build_app_integrity(root)
    app = _app_root(Path(root))
    destination = app / "Config" / "app.integrity.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return payload


def build_manifest(root: Path) -> dict:
    return build_app_integrity(root)


def verify_manifest(root: Path, *, exact_file_set: bool = True) -> dict:
    app = _app_root(Path(root))
    manifest = read_json(app / "Config" / "app.integrity.json")
    files = manifest.get("files")
    config = read_json(app / "Config" / "sistema.json")
    version, schema = version_info(app)
    expected_master_id = (app / "Config" / "master.id").read_text(encoding="utf-8").strip().upper()
    try:
        valid_header = (
            int(manifest.get("format") or 0) == 5
            and manifest.get("product") == "CJL System"
            and manifest.get("integrity_scope") == "APP"
            and manifest.get("algorithm") == "SHA-256"
            and normalize_version(str(manifest.get("version") or "")) == version
            and str(manifest.get("version_full") or "") == str(config.get("version_full") or "")
            and int(manifest.get("business", -1)) == int((config.get("versioning") or {}).get("business", -2))
            and (int(manifest.get("structural", -1)), int(manifest.get("incremental", -1)), int(manifest.get("security", -1))) == version_key(version)
            and int(manifest.get("compat_sequence", -1)) == int((config.get("versioning") or {}).get("compat_sequence", -2))
            and int(manifest.get("schema_version") or -1) == schema
            and int(manifest.get("runtime_version") or -1) == int(config.get("runtime_version") or -2)
            and int(manifest.get("build") or -1) == int(config.get("build") or -2)
            and int(manifest.get("layout_version") or -1) == int(config.get("layout_version") or 5)
            and str(manifest.get("master_id") or "").strip().upper() == expected_master_id
            and isinstance(files, dict) and bool(files)
        )
    except (TypeError, ValueError):
        valid_header = False
    if not valid_header:
        raise RuntimeError("MANIFESTO DE INTEGRIDADE DA APLICAÇÃO AUSENTE OU INVÁLIDO.")

    declared = {str(relative).replace("\\", "/"): str(expected).lower() for relative, expected in files.items()}
    for relative, expected in declared.items():
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise RuntimeError(f"CAMINHO INVÁLIDO NO MANIFESTO DA APLICAÇÃO: {relative}.")
        path = (app / rel).resolve()
        try:
            path.relative_to(app.resolve())
        except ValueError as exc:
            raise RuntimeError(f"CAMINHO INVÁLIDO NO MANIFESTO DA APLICAÇÃO: {relative}.") from exc
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"ARQUIVO DA APLICAÇÃO AUSENTE OU ALTERADO: App/{relative}.")

    if exact_file_set:
        discovered = {path.relative_to(app).as_posix() for path in _application_files(app)}
        if discovered != set(declared):
            extras = sorted(discovered - set(declared))[:8]
            missing = sorted(set(declared) - discovered)[:8]
            detail = []
            if extras:
                detail.append("extras=" + ", ".join(extras))
            if missing:
                detail.append("ausentes=" + ", ".join(missing))
            raise RuntimeError("O CONJUNTO FÍSICO DA APLICAÇÃO DIVERGE DO MANIFESTO" + (": " + "; ".join(detail) if detail else "."))
    return manifest


def _runtime_directory(root: Path) -> Path:
    project = _project_root(Path(root))
    install = os.environ.get("CJL_INSTALL_ROOT", "").strip()
    if install:
        install_path = Path(install).resolve()
        if project == install_path:
            candidate = install_path / "Runtime"
            if candidate.is_dir():
                return candidate
    modern = project / "Runtime"
    if modern.is_dir():
        return modern
    raise RuntimeError("RUNTIME OFICIAL AUSENTE.")


def runtime_files(root: Path) -> list[Path]:
    runtime = _runtime_directory(root)
    return sorted(
        path for path in runtime.rglob("*")
        if path.is_file() and not path.is_symlink()
        and "__pycache__" not in {part.casefold() for part in path.parts}
        and path.suffix.casefold() not in IGNORED_SUFFIXES
    )


def runtime_component_files(root: Path, component: str) -> list[Path]:
    component_root = _runtime_directory(root) / str(component)
    if not component_root.is_dir():
        raise RuntimeError(f"COMPONENTE {str(component).upper()} AUSENTE DO RUNTIME.")
    return sorted(
        path for path in component_root.rglob("*")
        if path.is_file() and not path.is_symlink()
        and "__pycache__" not in {part.casefold() for part in path.parts}
        and path.suffix.casefold() not in IGNORED_SUFFIXES
    )


def build_runtime_integrity(root: Path) -> dict:
    app = _app_root(Path(root))
    config = read_json(app / "Config" / "sistema.json")
    version, _schema = version_info(app)
    runtime = _runtime_directory(root)
    files = {"Runtime/" + path.relative_to(runtime).as_posix(): sha256_file(path) for path in runtime_files(root)}
    return {
        "format": 3,
        "product": "CJL System",
        "runtime_version": int(config.get("runtime_version") or 1),
        "algorithm": "SHA-256",
        "complete_file_set": True,
        "files": files,
    }


def write_runtime_integrity(root: Path) -> dict:
    payload = build_runtime_integrity(root)
    app = _app_root(Path(root))
    destination = app / "Config" / "runtime.integrity.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return payload


def _runtime_manifest(root: Path) -> tuple[dict, Path]:
    app = _app_root(Path(root))
    manifest = read_json(app / "Config" / "runtime.integrity.json")
    return manifest, app


def _runtime_manifest_header_valid(manifest: dict, expected_runtime: int) -> bool:
    files=manifest.get("files")
    try:
        return int(manifest.get("format") or 0)==3 and str(manifest.get("product") or "")=="CJL System" and str(manifest.get("algorithm") or "").upper()=="SHA-256" and int(manifest.get("runtime_version") or -1)==int(expected_runtime) and isinstance(files,dict) and bool(files)
    except (TypeError,ValueError): return False


def verify_runtime_integrity(root: Path, *, exact_file_set: bool = True, quick: bool = False) -> dict:
    manifest, app = _runtime_manifest(Path(root))
    files = manifest.get("files")
    config = read_json(app / "Config" / "sistema.json")
    expected_runtime = int(config.get("runtime_version") or 1)
    if not _runtime_manifest_header_valid(manifest, expected_runtime):
        raise RuntimeError("MANIFESTO INTEGRAL DO RUNTIME AUSENTE OU INVÁLIDO.")
    runtime_root = _runtime_directory(root).resolve()
    selected = list(files.items())
    if quick:
        critical_exact = {
            "Runtime/Python/python.exe",
            "Runtime/Python/pythonw.exe",
            "Runtime/Python/DLLs/_sqlite3.pyd",
            "Runtime/Python/Lib/site-packages/openpyxl/__init__.py",
            "Runtime/Python/Lib/site-packages/PIL/__init__.py",
            "Runtime/Python/Lib/site-packages/tzdata/__init__.py",
            "Runtime/Python/Lib/site-packages/tzdata/zoneinfo/America/Sao_Paulo",
        }
        selected = [
            (relative, expected) for relative, expected in files.items()
            if relative in critical_exact
            or (relative.startswith("Runtime/Python/python") and relative.endswith(".dll") and relative[len("Runtime/Python/python"):-4].isdigit())
        ]
        critical_names = {relative for relative, _ in selected}
        if len(selected) < 7 or "Runtime/Python/python.exe" not in critical_names or not any(relative.endswith(".dll") for relative in critical_names):
            raise RuntimeError("O MANIFESTO DO RUNTIME NÃO CONTÉM OS COMPONENTES CRÍTICOS.")
    for relative, expected in selected:
        relative_text = str(relative).replace("\\", "/")
        if not relative_text.startswith("Runtime/"):
            raise RuntimeError(f"CAMINHO INVÁLIDO NO MANIFESTO DO RUNTIME: {relative}.")
        path = (runtime_root / relative_text[len("Runtime/"):]).resolve()
        try:
            path.relative_to(runtime_root)
        except ValueError as exc:
            raise RuntimeError(f"CAMINHO INVÁLIDO NO MANIFESTO DO RUNTIME: {relative}.") from exc
        if not path.is_file() or sha256_file(path) != str(expected).lower():
            raise RuntimeError(f"ARQUIVO DO RUNTIME AUSENTE OU ALTERADO: {relative}.")
    if exact_file_set and not quick:
        discovered = {"Runtime/" + path.relative_to(runtime_root).as_posix() for path in runtime_files(root)}
        if discovered != {str(path) for path in files}:
            raise RuntimeError("O CONJUNTO DE ARQUIVOS DO RUNTIME DIVERGE DO MANIFESTO INTEGRAL.")
    return manifest


def verify_runtime_component(root: Path, component: str, *, runtime_root_override: Path | None = None) -> dict:
    name = str(component or "").strip()
    if name not in {"Python", "LibreOffice"}:
        raise ValueError("COMPONENTE DO RUNTIME NÃO SUPORTADO.")
    manifest, app = _runtime_manifest(Path(root))
    files = manifest.get("files")
    config = read_json(app / "Config" / "sistema.json")
    expected_runtime = int(config.get("runtime_version") or 1)
    if not _runtime_manifest_header_valid(manifest, expected_runtime):
        raise RuntimeError("MANIFESTO INTEGRAL DO RUNTIME AUSENTE OU INVÁLIDO.")
    runtime_base = Path(runtime_root_override).resolve() if runtime_root_override is not None else _runtime_directory(root).resolve()
    prefix = f"Runtime/{name}/"
    selected = {str(relative): str(expected).lower() for relative, expected in files.items() if str(relative).startswith(prefix)}
    if not selected:
        raise RuntimeError(f"COMPONENTE {name.upper()} AUSENTE DO MANIFESTO DO RUNTIME.")
    for relative, expected in selected.items():
        path = runtime_base / relative[len("Runtime/"):]
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"ARQUIVO DO RUNTIME AUSENTE OU ALTERADO: {relative}.")
    discovered = {
        "Runtime/" + path.relative_to(runtime_base).as_posix()
        for path in sorted((runtime_base / name).rglob("*"))
        if path.is_file() and not path.is_symlink()
        and "__pycache__" not in {part.casefold() for part in path.parts}
        and path.suffix.casefold() not in IGNORED_SUFFIXES
    }
    if discovered != set(selected):
        raise RuntimeError(f"O CONJUNTO DE ARQUIVOS DO COMPONENTE {name.upper()} DIVERGE DO MANIFESTO.")
    return {"component": name, "files": len(selected), "ok": True}
