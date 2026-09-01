from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from Core.config import station_id
from Core.context import current_identity
from Core.db import connect
from Core.filetx import current as current_file_transaction, stage_bytes, stage_move
from Core.ids import next_id
from Core.paths import DATA_ROOT, ensure_under_data, slug
from Core.storage import ensure_data_quota
from Core.text import upper_code
from Modulos.Carregamentos.service import assert_can_modify


MAX_ATTACHMENTS = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".pdf", ".docx"}
MIME_BY_EXTENSION = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _decode(name: str, encoded: str) -> tuple[str, str, bytes]:
    original = Path(str(name or "").replace("\\", "/")).name.strip()
    if len(original) > 180:
        raise ValueError("O NOME ORIGINAL DO ANEXO DEVE TER NO MÁXIMO 180 CARACTERES.")
    extension = Path(original).suffix.lower()
    if not original or extension not in ALLOWED_EXTENSIONS:
        raise ValueError("ANEXO INVÁLIDO. USE XLSX, XLS, PDF OU DOCX.")
    raw = str(encoded or "").strip()
    if raw.startswith("data:"):
        _, _, raw = raw.partition(",")
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("CONTEÚDO BASE64 DO ANEXO É INVÁLIDO.") from exc
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("CADA ANEXO DEVE TER ENTRE 1 BYTE E 10 MB.")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("O CONTEÚDO DO ARQUIVO NÃO É UM PDF VÁLIDO.")
    if extension == ".pdf" and b"%%EOF" not in data[-4096:]:
        raise ValueError("O PDF NÃO POSSUI MARCADOR DE ENCERRAMENTO VÁLIDO.")
    if extension == ".xls" and not data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ValueError("O CONTEÚDO DO ARQUIVO NÃO É UM XLS VÁLIDO.")
    if extension in {".xlsx", ".docx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > 5000:
                    raise ValueError("O PACOTE OFFICE POSSUI QUANTIDADE INVÁLIDA DE COMPONENTES.")
                names = {entry.filename for entry in entries}
                required_prefix = "xl/" if extension == ".xlsx" else "word/"
                valid = "[Content_Types].xml" in names and any(item.startswith(required_prefix) for item in names)
        except (OSError, ValueError, zipfile.BadZipFile):
            valid = False
        if not valid:
            raise ValueError(f"O CONTEÚDO DO ARQUIVO NÃO É UM {extension[1:].upper()} VÁLIDO.")
    return original, extension, data


def _public(row) -> dict:
    item = dict(row)
    item["download_url"] = f"/api/anexos/{item['id']}/download"
    return item


def list_attachments(load_id: str, include_deleted: bool = False) -> list[dict]:
    query = "SELECT * FROM carregamento_anexos WHERE carregamento_id=?"
    if not include_deleted:
        query += " AND deleted_at=''"
    query += " ORDER BY created_at,id"
    with connect() as connection:
        return [_public(row) for row in connection.execute(query, (load_id,))]


def create_attachment(load_id: str, data: dict) -> dict:
    assert_can_modify(load_id)
    original, extension, content = _decode(data.get("nome_original", ""), data.get("data_base64", ""))
    ensure_data_quota(DATA_ROOT, len(content))
    digest = hashlib.sha256(content).hexdigest()
    work_id = str(data.get("obra_id") or "").strip() or None
    order_number = upper_code(data.get("op_numero"))
    identity = current_identity()
    with connect() as connection:
        load = connection.execute(
            "SELECT status,deleted_at FROM carregamentos WHERE id=?", (load_id,)
        ).fetchone()
        if not load or load["deleted_at"]:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        if load["status"] == "EXPEDIDO":
            raise ValueError("CARREGAMENTO EXPEDIDO: NÃO É POSSÍVEL ADICIONAR ANEXOS.")
        duplicate = connection.execute(
            """SELECT * FROM carregamento_anexos
                 WHERE carregamento_id=? AND sha256=? AND deleted_at=''""",
            (load_id, digest),
        ).fetchone()
        if duplicate:
            return _public(duplicate)
        count = connection.execute(
            "SELECT COUNT(*) FROM carregamento_anexos WHERE carregamento_id=? AND deleted_at=''", (load_id,)
        ).fetchone()[0]
        if count >= MAX_ATTACHMENTS:
            raise ValueError("O CARREGAMENTO JÁ POSSUI O LIMITE DE 10 ANEXOS.")
        if work_id:
            relation = connection.execute(
                "SELECT op_numero FROM carregamento_obras WHERE carregamento_id=? AND obra_id=?",
                (load_id, work_id),
            ).fetchone()
            if not relation:
                raise ValueError("A OBRA INFORMADA NÃO PERTENCE AO CARREGAMENTO.")
            order_number = order_number or relation["op_numero"]
        attachment_id = next_id(connection, "anexo", "ANX")
        safe_name = f"{attachment_id}__{slug(Path(original).stem, 'ARQUIVO')}{extension}"
        relative = Path("Anexos") / load_id / safe_name
        target = ensure_under_data(DATA_ROOT / relative)
        stage_bytes(target, content)
        try:
            connection.execute(
                """INSERT INTO carregamento_anexos(
                       id,carregamento_id,obra_id,op_numero,nome_original,nome_seguro,
                       extensao,mime,tamanho,sha256,relative_path,usuario_id,usuario_nome,
                       estacao_id,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    attachment_id, load_id, work_id, order_number, original, safe_name,
                    extension, MIME_BY_EXTENSION[extension], len(content), digest,
                    relative.as_posix(), identity.user_id, identity.user_name,
                    identity.station_id or station_id(), _now(),
                ),
            )
            connection.execute(
                "UPDATE carregamentos SET revisao_operacional=revisao_operacional+1,updated_at=? WHERE id=?",
                (_now(), load_id),
            )
        except Exception:
            # Dentro do write_scope o arquivo real ainda não foi trocado e o
            # rollback do journal descarta o staging. Não remover um destino
            # preexistente que possa pertencer a outra revisão.
            if current_file_transaction() is None:
                try:
                    target.unlink()
                except OSError:
                    pass
            raise
        row = connection.execute("SELECT * FROM carregamento_anexos WHERE id=?", (attachment_id,)).fetchone()
    return _public(row)


def attachment_file(attachment_id: str) -> tuple[Path, dict]:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM carregamento_anexos WHERE id=? AND deleted_at=''", (attachment_id,)
        ).fetchone()
    if not row:
        raise FileNotFoundError("ANEXO NÃO ENCONTRADO.")
    path = ensure_under_data(DATA_ROOT / row["relative_path"])
    if not path.is_file():
        raise FileNotFoundError("ARQUIVO DO ANEXO NÃO ESTÁ DISPONÍVEL.")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise RuntimeError("O HASH DO ANEXO NÃO CONFERE; DOWNLOAD BLOQUEADO.")
    return path, _public(row)


def remove_attachment(attachment_id: str) -> dict:
    with connect() as connection:
        row = connection.execute(
            """SELECT a.*,c.status FROM carregamento_anexos a
                 JOIN carregamentos c ON c.id=a.carregamento_id
                WHERE a.id=? AND a.deleted_at=''""",
            (attachment_id,),
        ).fetchone()
        if not row:
            raise ValueError("ANEXO NÃO ENCONTRADO.")
        assert_can_modify(row["carregamento_id"])
        if row["status"] == "EXPEDIDO":
            raise ValueError("CARREGAMENTO EXPEDIDO: O ANEXO NÃO PODE SER REMOVIDO.")
        source = ensure_under_data(DATA_ROOT / row["relative_path"])
        removed_relative = Path("Anexos") / "_Removidos" / f"{attachment_id}__{row['nome_seguro']}"
        destination = ensure_under_data(DATA_ROOT / removed_relative)
        if source.exists():
            stage_move(source, destination)
        now = _now()
        connection.execute(
            "UPDATE carregamento_anexos SET deleted_at=?,relative_path=? WHERE id=?",
            (now, removed_relative.as_posix(), attachment_id),
        )
        connection.execute(
            "UPDATE carregamentos SET revisao_operacional=revisao_operacional+1,updated_at=? WHERE id=?",
            (now, row["carregamento_id"]),
        )
        updated = connection.execute("SELECT * FROM carregamento_anexos WHERE id=?", (attachment_id,)).fetchone()
    return _public(updated)
