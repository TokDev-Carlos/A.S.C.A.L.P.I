from __future__ import annotations

from datetime import datetime

from Core.audit import log
from Core.db import connect
from Core.ids import next_id
from Core.text import plain_text, upper_text
from Core.validation import boolean


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _contact_fields(documento="", contato="", telefone="", email="", observacao="") -> tuple[str, str, str, str, str]:
    normalized_email = plain_text(email, max_length=254).lower()
    if normalized_email and (
        normalized_email.count("@") != 1
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
    ):
        raise ValueError("E-MAIL DO CLIENTE INVÁLIDO.")
    return (
        upper_text(documento, max_length=40),
        upper_text(contato, max_length=160),
        plain_text(telefone, max_length=40),
        normalized_email,
        upper_text(observacao, multiline=True, max_length=4000),
    )


def list_clientes(include_inactive: bool = True) -> list[dict]:
    sql = "SELECT * FROM clientes WHERE deleted_at=''"
    if not include_inactive:
        sql += " AND ativo=1"
    sql += " ORDER BY nome"
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql)]


def get_or_create(nome: str) -> dict:
    name = upper_text(nome, max_length=200)
    if not name:
        raise ValueError("NOME DO CLIENTE É OBRIGATÓRIO.")
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM clientes WHERE deleted_at='' AND UPPER(TRIM(nome))=UPPER(TRIM(?)) LIMIT 1", (name,)
        ).fetchone()
        if row:
            return dict(row)
        now = _now()
        client_id = next_id(conn, "cliente", "CLI")
        conn.execute(
            "INSERT INTO clientes(id,nome,created_at,updated_at) VALUES(?,?,?,?)",
            (client_id, name, now, now),
        )
    log("CLIENTE_CRIADO_AUTOMATICAMENTE", id=client_id, nome=name)
    return next(item for item in list_clientes() if item["id"] == client_id)


def create_cliente(nome: str, documento: str = "", contato: str = "", telefone: str = "", email: str = "", observacao: str = "", ativo=True) -> dict:
    name = upper_text(nome, max_length=200)
    if not name:
        raise ValueError("NOME DO CLIENTE É OBRIGATÓRIO.")
    now = _now()
    document, contact, phone, mail, note = _contact_fields(
        documento, contato, telefone, email, observacao
    )
    with connect() as conn:
        if conn.execute("SELECT 1 FROM clientes WHERE UPPER(TRIM(nome))=UPPER(TRIM(?))", (name,)).fetchone():
            raise ValueError("JÁ EXISTE UM CLIENTE COM ESSE NOME.")
        client_id = next_id(conn, "cliente", "CLI")
        conn.execute(
            """INSERT INTO clientes(id,nome,documento,contato,telefone,email,observacao,ativo,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (client_id, name, document, contact, phone, mail, note, 1 if boolean(ativo, field="CLIENTE ATIVO", default=True) else 0, now, now),
        )
    log("CLIENTE_CRIADO", id=client_id, nome=name)
    return next(item for item in list_clientes() if item["id"] == client_id)


def update_cliente(client_id: str, data: dict) -> dict:
    name = upper_text(data.get("nome"), max_length=200)
    if not name:
        raise ValueError("NOME DO CLIENTE É OBRIGATÓRIO.")
    document, contact, phone, mail, note = _contact_fields(
        data.get("documento"), data.get("contato"), data.get("telefone"),
        data.get("email"), data.get("observacao"),
    )
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM clientes WHERE id=? AND deleted_at=''", (client_id,)).fetchone():
            raise ValueError("CLIENTE NÃO ENCONTRADO.")
        duplicate = conn.execute(
            "SELECT id FROM clientes WHERE UPPER(TRIM(nome))=UPPER(TRIM(?)) AND id<>?", (name, client_id)
        ).fetchone()
        if duplicate:
            raise ValueError("JÁ EXISTE UM CLIENTE COM ESSE NOME.")
        conn.execute(
            """UPDATE clientes SET nome=?,documento=?,contato=?,telefone=?,email=?,observacao=?,ativo=?,updated_at=? WHERE id=?""",
            (
                name, document, contact, phone, mail, note,
                1 if boolean(data.get("ativo", True), field="CLIENTE ATIVO") else 0,
                _now(), client_id,
            ),
        )
    log("CLIENTE_EDITADO", id=client_id, nome=name)
    return next(item for item in list_clientes() if item["id"] == client_id)
