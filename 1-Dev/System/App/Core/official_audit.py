from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from Core.config import station_id
from Core.context import current_identity
from Core.db import connect
from Core.ids import next_id


def record(event: str, entity_type: str = "", entity_id: str = "", **details) -> dict:
    identity = current_identity()
    now = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    with connect() as connection:
        event_id = next_id(connection, "auditoria", "AUD")
        connection.execute(
            """INSERT INTO auditoria_eventos(
                   id,ocorrido_em,usuario_id,usuario_nome,estacao_id,evento,
                   entidade_tipo,entidade_id,detalhes_json
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                event_id, now, identity.user_id, identity.user_name,
                identity.station_id or station_id(), event, entity_type,
                entity_id, json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )
    return {
        "id": event_id,
        "ocorrido_em": now,
        "evento": event,
        "entidade_tipo": entity_type,
        "entidade_id": entity_id,
    }


def recent(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit), 1000))
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM auditoria_eventos ORDER BY ocorrido_em DESC,id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["detalhes"] = json.loads(item.pop("detalhes_json") or "{}")
        except ValueError:
            item["detalhes"] = {}
        result.append(item)
    return result
