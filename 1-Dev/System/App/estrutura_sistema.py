from __future__ import annotations

from pathlib import Path

from Core.config import ensure_local_layout, network_root, repository_root, shared_data_root
from Core.release import verify_manifest


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
REQUIRED = (
    APP_DIR / "Config" / "app.integrity.json",
    APP_DIR / "Config" / "sistema.json",
    APP_DIR / "Config" / "layout.json",
    APP_DIR / "Core" / "db.py",
    APP_DIR / "Core" / "release.py",
    APP_DIR / "Painel" / "index.html",
    APP_DIR / "Painel" / "app.js",
    APP_DIR / "Painel" / "app.css",
    APP_DIR / "Painel" / "vendor" / "leaflet" / "leaflet.js",
    APP_DIR / "Painel" / "vendor" / "leaflet" / "leaflet.css",
    APP_DIR / "Painel" / "vendor" / "mapa" / "brasil.geojson",
    APP_DIR / "Painel" / "vendor" / "mapa" / "config.json",
    APP_DIR / "Templates" / "Exportacao" / "TEMPLATE_PADRAO_CARREGAMENTO_FINAL.xlsx",
    APP_DIR / "Inicializacao" / "iniciar.py",
)


def ensure_structure() -> dict:
    # Dados corporativos são sempre resolvidos no Mestre; a estação só cria
    # estado/cache local isolado em AppData/ProgramData.
    shared_data_root().mkdir(parents=True, exist_ok=True)
    repository_root().mkdir(parents=True, exist_ok=True)
    (APP_DIR / "Templates" / "Exportacao").mkdir(parents=True, exist_ok=True)
    ensure_local_layout()
    missing = [str(path) for path in REQUIRED if not path.is_file()]
    if missing:
        raise RuntimeError("ESTRUTURA INCOMPLETA: " + "; ".join(missing))
    verify_manifest(PROJECT_ROOT, exact_file_set=True)
    return {
        "status": "OK",
        "application_root": str(APP_DIR),
        "project_root": str(PROJECT_ROOT),
        "master_root": str(network_root()),
        "shared_data_root": str(shared_data_root()),
        "repository_root": str(repository_root()),
    }
