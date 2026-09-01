from __future__ import annotations

import base64
import hashlib
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

from Core.context import current_identity
from Core.config import station_id
from Core.db import connect
from Core.filetx import stage_bytes, stage_move
from Core.ids import next_id
from Core.paths import DATA_ROOT, ensure_under_data
from Core.storage import ensure_data_quota
from Core.text import upper_code
from Modulos.Carregamentos.service import assert_can_modify


MAX_IMAGES_PER_STAGE = 50
MAX_BYTES = 12 * 1024 * 1024
MIMES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
MAX_DIMENSION = 12000
MAX_PIXELS = 50_000_000


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _public(row) -> dict:
    item = dict(row)
    item["download_url"] = f"/api/evidencias/{item['id']}/download"
    item.pop("relative_path", None)
    return item


def list_evidences(load_id: str) -> list[dict]:
    with connect() as conn:
        return [_public(row) for row in conn.execute(
            "SELECT * FROM carregamento_evidencias WHERE carregamento_id=? AND deleted_at='' ORDER BY etapa,created_at,id",
            (load_id,),
        )]


def create_evidence(load_id: str, payload: dict) -> dict:
    assert_can_modify(load_id, allow_expedited=True)
    stage = upper_code(payload.get("etapa") or "CARREGAMENTO")
    if stage not in {"CARREGAMENTO", "DESCARREGAMENTO"}:
        raise ValueError("ETAPA DA EVIDÊNCIA INVÁLIDA.")
    raw_text = str(payload.get("imagem_base64") or "")
    match = re.fullmatch(r"data:([^;]+);base64,(.+)", raw_text, re.DOTALL)
    if not match or match.group(1).lower() not in MIMES:
        raise ValueError("ENVIE UMA IMAGEM JPEG, PNG OU WEBP VÁLIDA.")
    mime = match.group(1).lower()
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception as exc:
        raise ValueError("CONTEÚDO BASE64 DA IMAGEM INVÁLIDO.") from exc
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("A IMAGEM DEVE TER NO MÁXIMO 12 MB.")
    ensure_data_quota(DATA_ROOT, len(raw))
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != FORMATS[mime]:
                raise ValueError("O CONTEÚDO DA IMAGEM NÃO CORRESPONDE AO TIPO DECLARADO.")
            if (
                image.width < 1 or image.height < 1
                or image.width > MAX_DIMENSION or image.height > MAX_DIMENSION
                or image.width * image.height > MAX_PIXELS
            ):
                raise ValueError("AS DIMENSÕES DA IMAGEM SÃO INVÁLIDAS OU EXCESSIVAS.")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("O ARQUIVO NÃO É UMA IMAGEM VÁLIDA.") from exc
    identity = current_identity()
    with connect() as conn:
        load = conn.execute("SELECT status FROM carregamentos WHERE id=? AND deleted_at=''", (load_id,)).fetchone()
        if not load:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        if load["status"] == "EXPEDIDO" and stage != "DESCARREGAMENTO":
            raise ValueError("APÓS EXPEDIDO, SOMENTE EVIDÊNCIAS DE DESCARREGAMENTO PODEM SER ADICIONADAS.")
        if stage == "DESCARREGAMENTO" and load["status"] != "EXPEDIDO":
            raise ValueError("FOTOS DE DESCARREGAMENTO SÃO LIBERADAS SOMENTE APÓS EXPEDIDO.")
        total = conn.execute(
            "SELECT COUNT(*) FROM carregamento_evidencias WHERE carregamento_id=? AND etapa=? AND deleted_at=''",
            (load_id, stage),
        ).fetchone()[0]
        if int(total) >= MAX_IMAGES_PER_STAGE:
            raise ValueError(f"LIMITE DE {MAX_IMAGES_PER_STAGE} FOTOS NESTA ETAPA ATINGIDO.")
        evidence_id = next_id(conn, "evidencia", "EVI")
        suffix = MIMES[mime]
        safe_name = f"{evidence_id}{suffix}"
        relative = Path("Evidencias") / load_id / stage / safe_name
        target = ensure_under_data(DATA_ROOT / relative)
        stage_bytes(target, raw)
        sha256 = hashlib.sha256(raw).hexdigest()
        original = str(payload.get("nome_original") or safe_name)[:180]
        conn.execute(
            """INSERT INTO carregamento_evidencias(
                   id,carregamento_id,etapa,nome_original,nome_seguro,mime,tamanho,sha256,relative_path,
                   usuario_id,usuario_nome,estacao_id,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (evidence_id,load_id,stage,original,safe_name,mime,len(raw),sha256,str(relative),
             identity.user_id,identity.user_name,identity.station_id or station_id(),_now()),
        )
        row = conn.execute("SELECT * FROM carregamento_evidencias WHERE id=?", (evidence_id,)).fetchone()
    return _public(row)


def evidence_file(evidence_id: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM carregamento_evidencias WHERE id=? AND deleted_at=''", (evidence_id,)).fetchone()
    if not row:
        raise FileNotFoundError("EVIDÊNCIA NÃO ENCONTRADA.")
    path = ensure_under_data(DATA_ROOT / row["relative_path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise FileNotFoundError("ARQUIVO DA EVIDÊNCIA AUSENTE OU ALTERADO.")
    return path, {"nome_seguro": row["nome_seguro"], "nome_original": row["nome_original"], "mime": row["mime"]}


def remove_evidence(evidence_id: str) -> dict:
    identity = current_identity()
    with connect() as conn:
        row = conn.execute(
            """SELECT e.*,c.status FROM carregamento_evidencias e
                 JOIN carregamentos c ON c.id=e.carregamento_id
                WHERE e.id=? AND e.deleted_at=''""", (evidence_id,),
        ).fetchone()
        if not row:
            raise ValueError("EVIDÊNCIA NÃO ENCONTRADA.")
        assert_can_modify(row["carregamento_id"], allow_expedited=True)
        if row["status"] == "EXPEDIDO" and identity.role not in {"ADMIN", "SYSTEM"}:
            raise PermissionError("APÓS EXPEDIDO, SOMENTE UM ADMINISTRADOR PODE REMOVER EVIDÊNCIAS.")
        source = ensure_under_data(DATA_ROOT / row["relative_path"])
        removed_relative = Path("Evidencias") / "_Removidos" / f"{evidence_id}__{row['nome_seguro']}"
        destination = ensure_under_data(DATA_ROOT / removed_relative)
        if source.exists():
            stage_move(source, destination)
        conn.execute(
            "UPDATE carregamento_evidencias SET deleted_at=?,relative_path=? WHERE id=?",
            (_now(), removed_relative.as_posix(), evidence_id),
        )
    return {"id": evidence_id, "carregamento_id": row["carregamento_id"], "removed": True}
