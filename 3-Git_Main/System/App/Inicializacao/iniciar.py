from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
import hashlib


SYSTEM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SYSTEM_DIR.parent


def _configure_environment() -> None:
    # Na execução direta a aplicação e o Mestre coincidem. Na instalação de
    # usuário, o supervisor já informa o Mestre e este arquivo roda no cache
    # local assinado; nunca sobrescrevemos esse ponteiro.
    if not os.environ.get("CJL_NETWORK_ROOT", "").strip():
        os.environ["CJL_NETWORK_ROOT"] = str(PROJECT_ROOT)
    if not os.environ.get("CJL_STATE_ROOT", "").strip():
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            master_id = (SYSTEM_DIR / "Config" / "master.id").read_text(encoding="utf-8").strip().upper()
            master_root = os.environ.get("CJL_NETWORK_ROOT", str(PROJECT_ROOT))
            normalized = os.path.normcase(os.path.abspath(master_root)).rstrip("\\/")
            suffix = hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()[:12].upper()
            instance_id = f"{master_id}-{suffix}"
            os.environ["CJL_INSTANCE_ID"] = instance_id
            os.environ["CJL_STATE_ROOT"] = str(base / "CJL" / "Instancias" / instance_id)
    # O supervisor usa -B -I -S. No Host .NET o Runtime fica fora da aplicação;
    # no execucao sem instalacao local registrada o Core.config mantém a resolução histórica.
    if str(SYSTEM_DIR) not in sys.path:
        sys.path.insert(0, str(SYSTEM_DIR))
    from Core.config import runtime_component_root
    site_packages = runtime_component_root("Python") / "Lib" / "site-packages"
    if site_packages.is_dir() and str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))


def _validate_master_runtime() -> None:
    # O núcleo do CJL System depende somente do Python da aplicação assinada.
    # LibreOffice é utilitário opcional e é verificado apenas no momento da exportação PDF.
    from Core.config import runtime_python, save_local_config, validate_deployment_root
    python = runtime_python()
    if not python.is_file():
        raise RuntimeError(f"RUNTIME PYTHON ASSINADO AUSENTE: {python}")
    from Core.provenance import public_notice
    from Core.release import verify_manifest, verify_runtime_integrity
    forced_disconnected = os.environ.get("CJL_FORCE_DISCONNECTED", "").strip() == "1"
    if forced_disconnected:
        # Durante uma atualização crítica o Mestre pode estar em transição.
        # A estação confia apenas na sua aplicação local já assinada e abre
        # exclusivamente a interface de desconexão/atualização.
        verify_manifest(PROJECT_ROOT)
        verify_runtime_integrity(PROJECT_ROOT, exact_file_set=False, quick=True)
    else:
        validated_master = validate_deployment_root(os.environ.get("CJL_NETWORK_ROOT", str(PROJECT_ROOT)))
        save_local_config(str(validated_master))
        verify_manifest(PROJECT_ROOT)
        verify_runtime_integrity(PROJECT_ROOT, exact_file_set=False, quick=True)
    public_notice()
    try:
        import sqlite3  # noqa: F401
        import openpyxl  # noqa: F401
        import PIL  # noqa: F401
        import tzdata  # noqa: F401
        from zoneinfo import ZoneInfo
        if str(ZoneInfo("America/Sao_Paulo")) != "America/Sao_Paulo":
            raise RuntimeError("FUSO HORÁRIO AMERICA/SAO_PAULO INDISPONÍVEL.")
    except Exception as exc:
        raise RuntimeError(
            "RUNTIME PYTHON ASSINADO INCOMPLETO. SÃO OBRIGATÓRIOS: "
            "SQLITE3, OPENPYXL, PILLOW E TZDATA."
        ) from exc


def _error_log(error: BaseException) -> Path:
    raw_root = os.environ.get("CJL_STATE_ROOT", "").strip()
    state = Path(raw_root) if raw_root else Path.home() / "CJL"
    log_dir = state / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"inicializacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    path.write_text(
        "CJL System - FALHA DE INICIALIZACAO\n"
        f"APLICAÇÃO: {PROJECT_ROOT}\n"
        f"MESTRE: {os.environ.get('CJL_NETWORK_ROOT', str(PROJECT_ROOT))}\n"
        f"PYTHON: {sys.executable}\n\n"
        + "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        encoding="utf-8",
    )
    return path


def _show_error(error: BaseException, log_path: Path) -> None:
    if os.name != "nt":
        return
    message = (
        "O CJL System NÃO PÔDE SER INICIADO.\n\n"
        f"{error}\n\n"
        f"LOG: {log_path}"
    )
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "CJL System", 0x10)
    except Exception:
        pass


def main() -> int:
    _configure_environment()
    if str(SYSTEM_DIR) not in sys.path:
        sys.path.insert(0, str(SYSTEM_DIR))
    _validate_master_runtime()
    painel = SYSTEM_DIR / "painel.py"
    if not painel.is_file():
        raise RuntimeError(f"INSTALAÇÃO DO CJL System INCOMPLETA: {painel}")
    from painel import main as run_panel

    run_panel()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        log = _error_log(exc)
        _show_error(exc, log)
        raise
