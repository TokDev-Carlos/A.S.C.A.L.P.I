from __future__ import annotations

import base64
import hashlib
import io
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from Core.audit import log
from Core.db import connect
from Core.filetx import current as current_file_transaction, stage_bytes, stage_move
from Core.paths import DATA_ROOT, ensure_under_data
from Core.storage import ensure_data_quota
from Core.text import upper_code, upper_text
from Core.validation import boolean, finite_number


IMAGE_ROOT = ensure_under_data(DATA_ROOT / "Imagens" / "Equipamentos")
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _with_image_url(row) -> dict:
    item = dict(row)
    item["imagem_url"] = (
        f"/api/equipamentos/{item['codigo']}/imagem?v={item['imagem_atualizada_em']}"
        if item.get("imagem_arquivo") else ""
    )
    return item


def list_equipamentos(limit: int = 1000, include_inactive: bool = False):
    sql = "SELECT * FROM equipamentos" + ("" if include_inactive else " WHERE ativo=1") + " ORDER BY CAST(codigo AS INTEGER),codigo LIMIT ?"
    with connect() as conn:
        return [_with_image_url(row) for row in conn.execute(sql, (max(1, min(int(limit), 5000)),))]


def _decode_image(value: str) -> tuple[bytes, str, str] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("data:"):
        header, _, payload = raw.partition(",")
        mime = header[5:].split(";", 1)[0].lower()
    else:
        mime, payload = "image/png", raw
    if mime not in IMAGE_TYPES:
        raise ValueError("FORMATO DE IMAGEM INVÁLIDO. USE PNG, JPG OU WEBP.")
    try:
        data = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError("ARQUIVO DE IMAGEM INVÁLIDO.") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("A IMAGEM DEVE TER NO MÁXIMO 4 MB.")
    valid = (
        mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")
        or mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff")
        or mime == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    )
    if not valid:
        raise ValueError("O CONTEÚDO NÃO CORRESPONDE AO FORMATO DA IMAGEM.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[mime]
            if (
                image.format != expected or image.width < 1 or image.height < 1
                or image.width > 12000 or image.height > 12000
                or image.width * image.height > 50_000_000
            ):
                raise ValueError("IMAGEM INVÁLIDA OU COM DIMENSÕES EXCESSIVAS.")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("O ARQUIVO NÃO É UMA IMAGEM VÁLIDA.") from exc
    digest = hashlib.sha256(data).hexdigest()[:20]
    return data, mime, f"{digest}{IMAGE_TYPES[mime]}"


def _store_image(code: str, value: str) -> tuple[str, str, str] | None:
    decoded = _decode_image(value)
    if not decoded:
        return None
    data, mime, suffix_name = decoded
    ensure_data_quota(DATA_ROOT, len(data))
    file_name = f"{upper_code(code)}__{suffix_name}"
    stage_bytes(ensure_under_data(IMAGE_ROOT / file_name), data)
    return file_name, mime, _now()


def _remove_stored_image(file_name: str) -> None:
    if not file_name:
        return
    source = ensure_under_data(IMAGE_ROOT / file_name)
    destination = ensure_under_data(IMAGE_ROOT / "_Removidos" / file_name)
    if source.exists() and not destination.exists():
        stage_move(source, destination)


def _discard_failed_new_image(file_name: str) -> None:
    if not file_name or current_file_transaction() is not None:
        return
    try:
        ensure_under_data(IMAGE_ROOT / file_name).unlink(missing_ok=True)
    except OSError:
        pass


def image_file(codigo: str) -> tuple[Path, str]:
    code = upper_code(codigo)
    with connect() as conn:
        row = conn.execute("SELECT imagem_arquivo,imagem_mime FROM equipamentos WHERE codigo=?", (code,)).fetchone()
    if not row or not row["imagem_arquivo"]:
        raise FileNotFoundError("IMAGEM NÃO CADASTRADA.")
    path = ensure_under_data(IMAGE_ROOT / row["imagem_arquivo"])
    if not path.is_file():
        raise FileNotFoundError("ARQUIVO DE IMAGEM NÃO ENCONTRADO.")
    expected = Path(row["imagem_arquivo"]).stem.rsplit("__", 1)[-1].lower()
    if len(expected) != 20 or hashlib.sha256(path.read_bytes()).hexdigest()[:20] != expected:
        raise RuntimeError("A INTEGRIDADE DA IMAGEM DO CATÁLOGO NÃO CONFERE.")
    return path, row["imagem_mime"] or "application/octet-stream"


def create_equipamento(codigo: str, nome: str, grupo: str = "", valor_unit=None, observacao: str = "", imagem_base64: str = ""):
    code = upper_code(codigo)
    name = upper_text(nome)
    if not code or not name:
        raise ValueError("CÓDIGO E NOME DO ITEM SÃO OBRIGATÓRIOS.")
    value = None if valor_unit in ("", None) else finite_number(
        valor_unit, field="VALOR UNITÁRIO", minimum=0, maximum=1_000_000_000
    )
    with connect() as conn:
        if conn.execute("SELECT 1 FROM equipamentos WHERE codigo=?", (code,)).fetchone():
            raise ValueError("JÁ EXISTE ITEM COM ESSE CÓDIGO.")
    image = _store_image(code, imagem_base64)
    try:
        with connect() as conn:
            conn.execute(
                """INSERT INTO equipamentos(codigo,grupo,nome,valor_unit,observacao,ativo,imagem_arquivo,imagem_mime,imagem_atualizada_em)
                   VALUES(?,?,?,?,?,1,?,?,?)""",
                (code, upper_text(grupo), name, value, upper_text(observacao, multiline=True), *(image or ("", "", ""))),
            )
    except Exception:
        if image:
            _discard_failed_new_image(image[0])
        raise
    log("EQUIPAMENTO_CRIADO", codigo=code, nome=name, valor=value, imagem=bool(image))
    return next(item for item in list_equipamentos(include_inactive=True) if item["codigo"] == code)


def update_equipamento(codigo: str, nome: str, grupo: str = "", valor_unit=None, observacao: str = "", ativo=True, motivo: str = "", imagem_base64: str = "", remover_imagem: bool = False):
    code = upper_code(codigo)
    name = upper_text(nome)
    if not name:
        raise ValueError("NOME DO ITEM É OBRIGATÓRIO.")
    value = None if valor_unit in ("", None) else finite_number(
        valor_unit, field="VALOR UNITÁRIO", minimum=0, maximum=1_000_000_000
    )
    active = boolean(ativo, field="ITEM ATIVO", default=True)
    remove_image = boolean(remover_imagem, field="REMOVER IMAGEM", default=False)
    image = _store_image(code, imagem_base64)
    old_file = ""
    try:
        with connect() as conn:
            old = conn.execute("SELECT * FROM equipamentos WHERE codigo=?", (code,)).fetchone()
            if not old:
                raise ValueError("ITEM NÃO ENCONTRADO.")
            old_file = old["imagem_arquivo"] or ""
            image_fields = image if image else (("", "", "") if remove_image else (old["imagem_arquivo"], old["imagem_mime"], old["imagem_atualizada_em"]))
            conn.execute(
                """UPDATE equipamentos SET nome=?,grupo=?,valor_unit=?,observacao=?,ativo=?,imagem_arquivo=?,imagem_mime=?,imagem_atualizada_em=? WHERE codigo=?""",
                (name, upper_text(grupo), value, upper_text(observacao, multiline=True), 1 if active else 0, *image_fields, code),
            )
            if old["valor_unit"] != value:
                conn.execute(
                    "INSERT INTO equipamento_valores_historico(equipamento_codigo,valor_anterior,valor_novo,alterado_em,motivo) VALUES(?,?,?,?,?)",
                    (code, old["valor_unit"], value, _now(), upper_text(motivo, multiline=True)),
                )
    except Exception:
        if image and image[0] != old_file:
            _discard_failed_new_image(image[0])
        raise
    new_file = image[0] if image else ("" if remove_image else old_file)
    if old_file and old_file != new_file:
        _remove_stored_image(old_file)
    log("EQUIPAMENTO_EDITADO", codigo=code, valor_anterior=old["valor_unit"], valor_novo=value, imagem_atualizada=bool(image), imagem_removida=remove_image)
    return next(item for item in list_equipamentos(include_inactive=True) if item["codigo"] == code)
