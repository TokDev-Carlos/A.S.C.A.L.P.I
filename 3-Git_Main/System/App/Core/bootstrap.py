from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from Core.audit import log
from Core.db import connect, initialize


SYSTEM_DIR = Path(__file__).resolve().parents[1]
CATALOG = SYSTEM_DIR / "Modulos" / "Catalogo" / "Config" / "catalogo_equipamentos.json"

BRAZIL_STATES = (
    ("AC", "ACRE"), ("AL", "ALAGOAS"), ("AP", "AMAPÁ"), ("AM", "AMAZONAS"),
    ("BA", "BAHIA"), ("CE", "CEARÁ"), ("DF", "DISTRITO FEDERAL"),
    ("ES", "ESPÍRITO SANTO"), ("GO", "GOIÁS"), ("MA", "MARANHÃO"),
    ("MT", "MATO GROSSO"), ("MS", "MATO GROSSO DO SUL"), ("MG", "MINAS GERAIS"),
    ("PA", "PARÁ"), ("PB", "PARAÍBA"), ("PR", "PARANÁ"), ("PE", "PERNAMBUCO"),
    ("PI", "PIAUÍ"), ("RJ", "RIO DE JANEIRO"), ("RN", "RIO GRANDE DO NORTE"),
    ("RS", "RIO GRANDE DO SUL"), ("RO", "RONDÔNIA"), ("RR", "RORAIMA"),
    ("SC", "SANTA CATARINA"), ("SP", "SÃO PAULO"), ("SE", "SERGIPE"),
    ("TO", "TOCANTINS"),
)


def bootstrap() -> dict:
    initialize()
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        inserted_states = 0
        for uf, name in BRAZIL_STATES:
            if conn.execute("SELECT 1 FROM unidades WHERE uf=?", (uf,)).fetchone():
                continue
            conn.execute(
                "INSERT INTO unidades(id,nome,uf,created_at,updated_at) VALUES(?,?,?,?,?)",
                (f"UNI-{uf}", name, uf, now, now),
            )
            inserted_states += 1
        if inserted_states:
            log("ESTADOS_BRASILEIROS_CARREGADOS", quantidade=inserted_states)

        imported = 0
        if CATALOG.is_file() and conn.execute("SELECT COUNT(*) FROM equipamentos").fetchone()[0] == 0:
            items = json.loads(CATALOG.read_text(encoding="utf-8"))["equipamentos"]
            conn.executemany(
                "INSERT INTO equipamentos(codigo,grupo,nome,valor_unit,origem_linha,observacao) VALUES(?,?,?,?,?,?)",
                [
                    (
                        str(item["codigo"]).strip().upper(),
                        str(item.get("grupo", "")).strip().upper(),
                        str(item["nome"]).strip().upper(),
                        item.get("valor_unit"),
                        item.get("origem_linha"),
                        str(item.get("observacao", "")).strip().upper(),
                    )
                    for item in items
                ],
            )
            imported = len(items)
            log("CATALOGO_IMPORTADO", quantidade=imported)

    # Usuários são inicializados depois da migração estrutural. O expurgo não
    # pertence à migração: ele é executado depois da abertura, dentro de um
    # write_scope com journal de arquivos externos.
    from Modulos.Usuarios.service import ensure_initial_users

    ensure_initial_users()
    return {
        "status": "OK",
        "estados_criados": inserted_states,
        "itens_importados": imported,
        "exclusoes_expiradas": 0,
    }
