from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from Core.context import current_identity
from Core.db import connect
from Core.filetx import stage_move
from Core.ids import next_id
from Core.paths import DATA_ROOT, ensure_under_data
from Core.text import upper_text


TARGETS = {
    "CLIENTE": ("clientes", "nome"),
    "OBRA": ("obras", "nome"),
    "CARREGAMENTO": ("carregamentos", "id"),
}


def _now_dt() -> datetime:
    return datetime.now(ZoneInfo("America/Sao_Paulo"))


def _row_payload(row) -> dict:
    return {key: row[key] for key in row.keys() if key not in {"senha_hash", "senha_salt"}}


def request_deletion(target_type: str, target_id: str, reason: str = "") -> dict:
    kind = upper_text(target_type)
    if kind not in TARGETS:
        raise ValueError("TIPO DE EXCLUSÃO INVÁLIDO.")
    table, label_column = TARGETS[kind]
    if kind == "CARREGAMENTO":
        # A permissão geral de solicitar exclusão não substitui a autorização
        # por objeto: somente o criador ou um administrador pode ocultar a carga.
        from Modulos.Carregamentos.service import assert_can_modify
        assert_can_modify(target_id)
    identity = current_identity()
    now = _now_dt()
    with connect() as connection:
        row = connection.execute(f"SELECT * FROM {table} WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise ValueError("REGISTRO NÃO ENCONTRADO.")
        if row["deleted_at"]:
            existing = connection.execute(
                "SELECT * FROM solicitacoes_exclusao WHERE id=?", (row["deletion_request_id"],)
            ).fetchone()
            if existing:
                return dict(existing)
            raise ValueError("O REGISTRO JÁ ESTÁ OCULTO PARA EXCLUSÃO.")
        request_id = next_id(connection, "exclusao", "EXC")
        label = str(row[label_column] or target_id)
        expires = now + timedelta(days=30)
        connection.execute(
            """INSERT INTO solicitacoes_exclusao(
                   id,entidade_tipo,entidade_id,entidade_rotulo,motivo,status,
                   solicitante_id,solicitante_nome,solicitado_em,expira_em,payload_json
               ) VALUES(?,?,?,?,?,'PENDENTE',?,?,?,?,?)""",
            (
                request_id, kind, target_id, label, upper_text(reason, multiline=True),
                identity.user_id, identity.user_name, now.isoformat(timespec="seconds"),
                expires.isoformat(timespec="seconds"),
                json.dumps(_row_payload(row), ensure_ascii=False, sort_keys=True),
            ),
        )
        connection.execute(
            f"UPDATE {table} SET deleted_at=?,deletion_request_id=? WHERE id=?",
            (now.isoformat(timespec="seconds"), request_id, target_id),
        )
        result = connection.execute("SELECT * FROM solicitacoes_exclusao WHERE id=?", (request_id,)).fetchone()
    return dict(result)


def list_requests(include_resolved: bool = True) -> list[dict]:
    query = "SELECT * FROM solicitacoes_exclusao"
    parameters: tuple = ()
    if not include_resolved:
        query += " WHERE status='PENDENTE'"
    query += " ORDER BY CASE status WHEN 'PENDENTE' THEN 0 ELSE 1 END,solicitado_em DESC"
    with connect() as connection:
        return [dict(row) for row in connection.execute(query, parameters)]


def _stage_load_files(connection, request) -> None:
    load_id = request["entidade_id"]
    roots = {
        ensure_under_data(DATA_ROOT / "Anexos" / load_id),
        ensure_under_data(DATA_ROOT / "Evidencias" / load_id),
    }
    for row in connection.execute(
        "SELECT workbook_path FROM carregamento_documentos WHERE carregamento_id=?",
        (load_id,),
    ):
        relative = Path(str(row["workbook_path"] or "").replace("\\", "/"))
        if len(relative.parts) >= 4 and relative.parts[0].lower() == "documentos":
            roots.add(ensure_under_data(DATA_ROOT.joinpath(*relative.parts[:4])))
    operation = ensure_under_data(DATA_ROOT / "Operacao")
    if operation.is_dir():
        for candidate in operation.glob(f"*/*/_CARREGAMENTOS/*__{load_id}"):
            roots.add(ensure_under_data(candidate))
    removed = ensure_under_data(DATA_ROOT / "_Removidos" / "Exclusoes" / request["id"])
    for source in sorted(roots, key=lambda item: len(item.parts)):
        if not source.exists():
            continue
        relative = source.relative_to(DATA_ROOT)
        stage_move(source, ensure_under_data(removed / relative))


def _purge(connection, request, final_status: str) -> None:
    kind = request["entidade_tipo"]
    target_id = request["entidade_id"]
    table, _ = TARGETS[kind]
    now = _now_dt().isoformat(timespec="seconds")
    if kind == "CARREGAMENTO":
        _stage_load_files(connection, request)
        connection.execute("DELETE FROM carregamentos WHERE id=?", (target_id,))
    elif kind == "CLIENTE":
        connection.execute(
            """UPDATE clientes SET nome=?,documento='',contato='',telefone='',email='',
                   observacao='',ativo=0,deleted_at=?,deletion_request_id=? WHERE id=?""",
            (f"CLIENTE EXCLUÍDO {target_id}", now, request["id"], target_id),
        )
    elif kind == "OBRA":
        connection.execute(
            """UPDATE obras SET nome=?,codigo='',status='EXCLUÍDA',endereco='',latitude=NULL,
                   longitude=NULL,deleted_at=?,deletion_request_id=? WHERE id=?""",
            (f"OBRA EXCLUÍDA {target_id}", now, request["id"], target_id),
        )
    tombstone_id = next_id(connection, "tombstone", "TMB")
    connection.execute(
        """INSERT INTO exclusao_tombstones(
               id,entidade_tipo,entidade_id,entidade_rotulo,motivo,solicitante_id,
               revisor_id,removido_em,detalhes_json
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            tombstone_id, kind, target_id, request["entidade_rotulo"], request["motivo"],
            request["solicitante_id"], current_identity().user_id, now,
            json.dumps({"solicitacao": request["id"], "status": final_status}, ensure_ascii=False),
        ),
    )
    connection.execute(
        "UPDATE solicitacoes_exclusao SET status=?,purgado_em=? WHERE id=?",
        (final_status, now, request["id"]),
    )


def review(request_id: str, action: str) -> dict:
    normalized = upper_text(action)
    if normalized not in {"APROVAR", "REVOGAR"}:
        raise ValueError("AÇÃO DE REVISÃO INVÁLIDA.")
    identity = current_identity()
    now = _now_dt().isoformat(timespec="seconds")
    with connect() as connection:
        request = connection.execute("SELECT * FROM solicitacoes_exclusao WHERE id=?", (request_id,)).fetchone()
        if not request or request["status"] != "PENDENTE":
            raise ValueError("SOLICITAÇÃO NÃO ENCONTRADA OU JÁ RESOLVIDA.")
        connection.execute(
            """UPDATE solicitacoes_exclusao SET revisor_id=?,revisor_nome=?,revisado_em=?
                 WHERE id=?""",
            (identity.user_id, identity.user_name, now, request_id),
        )
        if normalized == "REVOGAR":
            table, _ = TARGETS[request["entidade_tipo"]]
            connection.execute(
                f"UPDATE {table} SET deleted_at='',deletion_request_id='' WHERE id=?",
                (request["entidade_id"],),
            )
            connection.execute("UPDATE solicitacoes_exclusao SET status='REVOGADA' WHERE id=?", (request_id,))
        else:
            request = connection.execute("SELECT * FROM solicitacoes_exclusao WHERE id=?", (request_id,)).fetchone()
            _purge(connection, request, "APROVADA")
        result = connection.execute("SELECT * FROM solicitacoes_exclusao WHERE id=?", (request_id,)).fetchone()
    return dict(result)


def purge_expired() -> int:
    now = _now_dt().isoformat(timespec="seconds")
    purged = 0
    with connect() as connection:
        requests = connection.execute(
            "SELECT * FROM solicitacoes_exclusao WHERE status='PENDENTE' AND expira_em<=? ORDER BY expira_em",
            (now,),
        ).fetchall()
        for request in requests:
            _purge(connection, request, "EXPIRADA")
            purged += 1
    return purged


def expired_count() -> int:
    now = _now_dt().isoformat(timespec="seconds")
    with connect() as connection:
        return int(connection.execute(
            "SELECT COUNT(*) FROM solicitacoes_exclusao WHERE status='PENDENTE' AND expira_em<=?",
            (now,),
        ).fetchone()[0])
