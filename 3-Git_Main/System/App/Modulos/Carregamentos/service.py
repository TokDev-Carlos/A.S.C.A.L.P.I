from __future__ import annotations

import json
from datetime import date, datetime, time as clock_time
from zoneinfo import ZoneInfo
from urllib.parse import quote

from Core.audit import log
from Core.db import connect
from Core.context import current_identity
from Core.filetx import stage_bytes, stage_mkdir, stage_move
from Core.ids import next_id
from Core.paths import carregamento_global_path, carregamento_path, ensure_under_data
from Core.text import upper_code, upper_text
from Core.validation import boolean, coordinates, finite_integer, finite_number
from Modulos.Obras import service as obras_service


STATUSES = {"PLANEJADO", "EM CARREGAMENTO", "CARREGADO", "EXPEDIDO", "CANCELADO"}
PROPERTIES = {"PROPRIO", "ALUGADO"}
COST_GROUPS = {"PESSOAL", "FRETE"}
COST_MODES = {"FIXO", "POR_FUNCIONARIO", "POR_DIA", "POR_HORA", "POR_UNIDADE"}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _float_or_none(value):
    if value in (None, ""):
        return None
    return finite_number(value, field="COORDENADA GEOGRÁFICA")


def _number(value, label: str, *, maximum: float = 1_000_000_000_000) -> float:
    if value in (None, ""):
        return 0.0
    normalized = str(value)
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    return finite_number(
        normalized, field=label.upper(), minimum=0, maximum=maximum, default=0
    )


def _integer(value, label: str, *, maximum: int = 100_000) -> int:
    return finite_integer(
        _number(value, label, maximum=maximum),
        field=label.upper(), minimum=0, maximum=maximum,
    )


def assert_can_modify(carregamento_id: str, *, allow_expedited: bool = False) -> dict:
    """Aplica a autorização por objeto em qualquer módulo que altere a carga."""
    identity = current_identity()
    with connect() as connection:
        row = connection.execute(
            "SELECT id,status,criador_usuario_id,deleted_at FROM carregamentos WHERE id=?",
            (carregamento_id,),
        ).fetchone()
    if not row or row["deleted_at"]:
        raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
    if identity.role not in {"ADMIN", "SYSTEM"} and row["criador_usuario_id"] != identity.user_id:
        raise PermissionError("SOMENTE O CRIADOR DO REGISTRO OU UM ADMINISTRADOR PODE ALTERÁ-LO.")
    if row["status"] == "EXPEDIDO" and not allow_expedited:
        raise ValueError("CARREGAMENTO EXPEDIDO: O REGISTRO É TERMINAL E NÃO PODE SER ALTERADO.")
    return dict(row)


def _required_date(value: str, label: str = "DATA") -> str:
    try:
        return date.fromisoformat(str(value or "")).isoformat()
    except Exception as exc:
        raise ValueError(f"{label.upper()} INVÁLIDA.") from exc


def _optional_date(value: str, label: str = "DATA") -> str:
    return "" if not value else _required_date(value, label)


def _optional_time(value, label: str = "HORÁRIO") -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = clock_time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{label.upper()} INVÁLIDO. USE HH:MM.") from exc
    if parsed.tzinfo is not None or parsed.microsecond or parsed.second:
        raise ValueError(f"{label.upper()} INVÁLIDO. USE HH:MM.")
    return parsed.strftime("%H:%M")


def _custos_da_carga(conn, carregamento_id: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id,grupo,descricao,modo,valor_unitario,quantidade,total,ativo,ordem,
                   funcionarios_aplicados,quantidade_tipo,ajuste_manual,calculo_versao
              FROM carregamento_custos
             WHERE carregamento_id=?
             ORDER BY CASE grupo WHEN 'PESSOAL' THEN 0 ELSE 1 END,ordem,id
            """,
            (carregamento_id,),
        )
    ]


def _resumo_custos(costs: list[dict]) -> dict:
    personnel = round(sum(float(row["total"] or 0) for row in costs if row["grupo"] == "PESSOAL"), 2)
    freight = round(sum(float(row["total"] or 0) for row in costs if row["grupo"] == "FRETE"), 2)
    base_rate = round(
        sum(
            float(row["valor_unitario"] or 0)
            for row in costs
            if row["grupo"] == "PESSOAL" and row["modo"] == "POR_FUNCIONARIO" and row.get("ativo", 1)
        ),
        2,
    )
    return {
        "tarifa_base_pessoal": base_rate,
        "custo_pessoal": personnel,
        "custo_frete": freight,
        "custo_total": round(personnel + freight, 2),
    }


def _obras_da_carga(conn, carregamento_id: str) -> list[dict]:
    works = [
        dict(row)
        for row in conn.execute(
            """
            SELECT co.obra_id id,o.nome,o.codigo,o.status,u.id unidade_id,u.nome estado,u.uf,
                   o.cliente_id,cl.nome cliente_nome,
                   co.op_numero,co.municipio,co.endereco,co.latitude,co.longitude,
                   co.distancia_km,co.custo_pessoal,co.custo_frete,co.custo_viagem,
                   co.valor_obra,co.percentual_rateio,co.observacao,co.ordem,
                   co.previsao_entrega,co.referencia_contrato
              FROM carregamento_obras co
              JOIN obras o ON o.id=co.obra_id
              JOIN unidades u ON u.id=o.unidade_id
              LEFT JOIN clientes cl ON cl.id=o.cliente_id
             WHERE co.carregamento_id=?
             ORDER BY co.ordem,o.nome
            """,
            (carregamento_id,),
        )
    ]
    for work in works:
        work_value = float(work["valor_obra"] or 0)
        work["percentual_frete_obra"] = round(float(work["custo_frete"] or 0) / work_value * 100, 4) if work_value else 0.0
        work["percentual_total_obra"] = round(float(work["custo_viagem"] or 0) / work_value * 100, 4) if work_value else 0.0
    return works


def _anexos_da_carga(conn, carregamento_id: str) -> list[dict]:
    rows = []
    for record in conn.execute(
        """SELECT * FROM carregamento_anexos
             WHERE carregamento_id=? AND deleted_at=''
             ORDER BY created_at,id""",
        (carregamento_id,),
    ):
        item = dict(record)
        item["download_url"] = f"/api/anexos/{item['id']}/download"
        rows.append(item)
    return rows


def _documentos_da_carga(conn, carregamento_id: str) -> list[dict]:
    documents = []
    for record in conn.execute(
        """SELECT id,carregamento_id,revisao,tipo,workbook_nome,workbook_sha256,
                  template_sha256,conteudo_sha256,arquivos_json,usuario_id,usuario_nome,
                  estacao_id,gerado_em
             FROM carregamento_documentos
            WHERE carregamento_id=? ORDER BY revisao DESC""",
        (carregamento_id,),
    ):
        item = dict(record)
        item["arquivos"] = json.loads(item.pop("arquivos_json") or "[]")
        for file in item["arquivos"]:
            file["download_url"] = (
                f"/api/documentos/{item['id']}/arquivos/{quote(file['nome'], safe='')}"
            )
        documents.append(item)
    return documents


def _evidencias_da_carga(conn, carregamento_id: str) -> list[dict]:
    rows = []
    for record in conn.execute(
        """SELECT id,carregamento_id,etapa,nome_original,nome_seguro,mime,tamanho,sha256,
                  usuario_id,usuario_nome,estacao_id,created_at
             FROM carregamento_evidencias
            WHERE carregamento_id=? AND deleted_at='' ORDER BY etapa,created_at,id""",
        (carregamento_id,),
    ):
        item = dict(record)
        item["download_url"] = f"/api/evidencias/{item['id']}/download"
        rows.append(item)
    return rows


def list_carregamentos() -> list[dict]:
    identity = current_identity()
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.* FROM carregamentos c WHERE c.deleted_at='' ORDER BY c.data DESC,c.hora DESC,c.id DESC"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["obras"] = _obras_da_carga(conn, row["id"])
            if item["obras"]:
                item["obra_nome"] = " + ".join(work["nome"] for work in item["obras"])
                item["uf"] = " / ".join(dict.fromkeys(work["uf"] for work in item["obras"]))
                item["unidade_nome"] = " / ".join(dict.fromkeys(work["estado"] for work in item["obras"]))
            else:
                old = conn.execute(
                    """SELECT o.nome obra_nome,u.nome unidade_nome,u.uf
                         FROM obras o JOIN unidades u ON u.id=o.unidade_id WHERE o.id=?""",
                    (row["obra_id"],),
                ).fetchone()
                item.update(dict(old) if old else {"obra_nome": "", "unidade_nome": "", "uf": ""})
            item["pracas"] = [
                dict(record)
                for record in conn.execute(
                    """SELECT p.id,p.nome,p.op_numero,p.obra_id
                         FROM carregamento_pracas cp JOIN pracas p ON p.id=cp.praca_id
                        WHERE cp.carregamento_id=? ORDER BY p.nome,p.op_numero""",
                    (row["id"],),
                )
            ]
            item["itens"] = [
                dict(record)
                for record in conn.execute(
                    """
                    SELECT ci.id,ci.obra_id,ci.praca_id,ci.equipamento_codigo,ci.quantidade,
                           e.nome equipamento_nome,e.grupo,
                           COALESCE(ci.valor_unitario,e.valor_unit,0) valor_unit,
                           COALESCE(ci.valor_unitario,e.valor_unit,0) valor_unitario,
                           e.imagem_arquivo,e.imagem_atualizada_em,
                           ci.unidade,ci.observacao,
                           (ci.quantidade*COALESCE(ci.valor_unitario,e.valor_unit,0)) valor_total,o.nome obra_nome
                      FROM carregamento_itens ci
                      JOIN equipamentos e ON e.codigo=ci.equipamento_codigo
                      LEFT JOIN obras o ON o.id=ci.obra_id
                     WHERE ci.carregamento_id=?
                     ORDER BY COALESCE(o.nome,''),CAST(e.codigo AS INTEGER),e.codigo
                    """,
                    (row["id"],),
                )
            ]
            item["quantidade_total"] = sum(float(value["quantidade"] or 0) for value in item["itens"])
            item["tipos_itens"] = len(item["itens"])
            item["valor_itens"] = sum(float(value["valor_total"] or 0) for value in item["itens"])
            item["valor_carga"] = round(sum(float(work["valor_obra"] or 0) for work in item["obras"]), 2)
            item["custos"] = _custos_da_carga(conn, row["id"])
            item["anexos"] = _anexos_da_carga(conn, row["id"])
            item["documentos"] = _documentos_da_carga(conn, row["id"])
            item["evidencias"] = _evidencias_da_carga(conn, row["id"])
            item["custos_resumo"] = _resumo_custos(item["custos"])
            if not item["custos"]:
                item["custos_resumo"] = {
                    "tarifa_base_pessoal": 0.0,
                    "custo_pessoal": round(sum(float(work["custo_pessoal"] or 0) for work in item["obras"]), 2),
                    "custo_frete": round(sum(float(work["custo_frete"] or 0) for work in item["obras"]), 2),
                    "custo_total": round(sum(float(work["custo_viagem"] or 0) for work in item["obras"]), 2),
                }
            item["custo_total"] = item["custos_resumo"]["custo_total"]
            item["bloqueado"] = item["status"] == "EXPEDIDO"
            item["aguardando_complementacao"] = item["status"] == "PLANEJADO" and not item["itens"]
            item["pode_editar"] = identity.role in {"ADMIN", "SYSTEM"} or (
                bool(item.get("criador_usuario_id")) and item.get("criador_usuario_id") == identity.user_id
            )
            if item["status"] == "EXPEDIDO" and identity.role not in {"ADMIN", "SYSTEM"}:
                item["pode_editar"] = False
            result.append(item)
        return result


def get_carregamento(carregamento_id: str) -> dict:
    record = next((item for item in list_carregamentos() if item["id"] == carregamento_id), None)
    if not record:
        raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
    return record


def _resolve_obra(entry: dict, *, allow_incomplete: bool = False) -> dict:
    obra_id = str(entry.get("obra_id") or "").strip()
    municipio = upper_text(entry.get("municipio"))
    endereco = upper_text(entry.get("endereco"))
    op = upper_code(entry.get("op_numero"))
    latitude, longitude = coordinates(entry.get("latitude"), entry.get("longitude"), optional=True)
    cliente_id = str(entry.get("cliente_id") or "").strip()
    cliente_nome = upper_text(entry.get("cliente_nome"))
    client_supplied = "cliente_id" in entry or "cliente_nome" in entry

    if obra_id:
        found = next((work for work in obras_service.list_obras() if work["id"] == obra_id), None)
        if not found:
            raise ValueError(f"OBRA {obra_id} NÃO ENCONTRADA.")
        desired_client_name = cliente_nome or municipio
        client_changed = (
            cliente_id != str(found.get("cliente_id") or "")
            if cliente_id
            else client_supplied and bool(desired_client_name) and desired_client_name != upper_text(found.get("cliente_nome", ""))
        )
        changed = any(
            (
                municipio and municipio != found.get("municipio", ""),
                endereco and endereco != found.get("endereco", ""),
                latitude is not None and latitude != found.get("latitude"),
                longitude is not None and longitude != found.get("longitude"),
                op and op != found.get("op_padrao", ""),
                client_changed,
            )
        )
        if changed:
            obras_service.update_obra(
                obra_id,
                found["nome"],
                municipio or found.get("municipio", ""),
                found.get("codigo", ""),
                found.get("status", "ATIVA"),
                endereco if endereco else found.get("endereco", ""),
                latitude if latitude is not None else found.get("latitude"),
                longitude if longitude is not None else found.get("longitude"),
                op or found.get("op_padrao", ""),
                cliente_id if client_supplied else found.get("cliente_id"),
                desired_client_name if client_supplied else found.get("cliente_nome"),
            )
        found = next(work for work in obras_service.list_obras() if work["id"] == obra_id)
    else:
        name = upper_text(entry.get("nome"))
        if not name:
            raise ValueError("INFORME OU SELECIONE O NOME DA OBRA.")
        uf = upper_code(entry.get("uf"))
        state_name = upper_text(entry.get("estado"))
        unit_id = str(entry.get("unidade_id") or "").strip()
        if unit_id:
            unit = next((value for value in obras_service.list_unidades() if value["id"] == unit_id), None)
            if not unit:
                raise ValueError("ESTADO/UNIDADE INVÁLIDO.")
        else:
            unit = obras_service.get_or_create_unidade(uf, state_name or uf)
        match = obras_service.find_matching_obra(unit["id"], name, municipio)
        if match:
            obras_service.update_obra(
                match["id"], name, municipio, match.get("codigo", ""), match.get("status", "ATIVA"),
                endereco, latitude, longitude, op, cliente_id, cliente_nome,
            )
            found = next(work for work in obras_service.list_obras() if work["id"] == match["id"])
        else:
            created = obras_service.create_obra(unit["id"], name, municipio, "", endereco, latitude, longitude, op, cliente_id, cliente_nome)
            found = next(work for work in obras_service.list_obras() if work["id"] == created["id"])

    municipality = municipio or upper_text(found.get("municipio", ""))
    production_order = op or upper_code(found.get("op_padrao", ""))
    if not municipality:
        raise ValueError(f"INFORME O MUNICÍPIO DA OBRA {found['nome']}.")
    if not production_order and not allow_incomplete:
        raise ValueError(f"INFORME A ORDEM DE PRODUÇÃO DA OBRA {found['nome']}.")

    personnel_cost = _number(entry.get("custo_pessoal"), "CUSTO DE PESSOAL ANTERIOR")
    freight_cost = _number(entry.get("custo_frete"), "CUSTO DE FRETE ANTERIOR")
    total_cost = _number(entry.get("custo_viagem"), "CUSTO TOTAL ANTERIOR")
    legacy_cost = total_cost or personnel_cost + freight_cost

    return {
        "obra": found,
        "op_numero": production_order,
        "municipio": municipality,
        "endereco": endereco or upper_text(found.get("endereco", "")),
        "latitude": latitude if latitude is not None else found.get("latitude"),
        "longitude": longitude if longitude is not None else found.get("longitude"),
        "distancia_km": _number(entry.get("distancia_km"), "DISTÂNCIA"),
        "previsao_entrega": _optional_date(entry.get("previsao_entrega"), "PREVISÃO DE ENTREGA"),
        "referencia_contrato": upper_text(entry.get("referencia_contrato")),
        # O valor enviado pelo painel nunca é aceito como fonte financeira.
        # Ele será recalculado abaixo a partir dos itens e preços do catálogo.
        "valor_obra": 0.0,
        "percentual_rateio": 0.0,
        "legacy_custo_pessoal": personnel_cost,
        "legacy_custo_frete": freight_cost,
        "legacy_custo": legacy_cost,
        "observacao": upper_text(entry.get("observacao"), multiline=True),
        "itens": list(entry.get("itens") or []),
    }


def _normalize_header(data: dict) -> dict:
    status = upper_text(data.get("status") or "PLANEJADO")
    if status not in STATUSES:
        raise ValueError("STATUS INVÁLIDO.")
    property_type = upper_text(data.get("propriedade") or "PROPRIO")
    if property_type not in PROPERTIES:
        raise ValueError("TIPO DO CAMINHÃO INVÁLIDO.")
    header = {
        "data": _required_date(data.get("data"), "DATA DO CARREGAMENTO"),
        "hora": _optional_time(data.get("hora"), "HORA DO CARREGAMENTO"),
        "status": status,
        "observacao": upper_text(data.get("observacao"), multiline=True),
        "motorista": upper_text(data.get("motorista")),
        "veiculo": upper_text(data.get("veiculo")),
        "placa": upper_code(data.get("placa")),
        "propriedade": property_type,
        "transportadora": upper_text(data.get("transportadora")),
        "data_saida": _optional_date(data.get("data_saida"), "DATA DE SAÍDA"),
        "hora_saida": _optional_time(data.get("hora_saida"), "HORA DE SAÍDA"),
        "data_retorno": _optional_date(data.get("data_retorno"), "DATA DE RETORNO"),
        "solicitante": upper_text(data.get("solicitante")),
        "funcionarios": _integer(
            data.get("funcionarios"), "QUANTIDADE DE FUNCIONÁRIOS", maximum=10_000
        ),
        "dias_viagem": _number(
            data.get("dias_viagem"), "QUANTIDADE DE DIAS", maximum=3_650
        ),
        "distancia_km": _number(
            data.get("distancia_km"), "DISTÂNCIA DA VIAGEM", maximum=10_000_000
        ),
        "caminhao_id": upper_code(data.get("caminhao_id")),
    }
    if header["data_retorno"] and header["data_saida"] and header["data_retorno"] < header["data_saida"]:
        raise ValueError("A DATA DE RETORNO NÃO PODE SER ANTERIOR À DATA DE SAÍDA.")
    return header


def _require_expedition_confirmation(status: str, confirmed=False) -> None:
    accepted = confirmed is True or str(confirmed).strip().lower() in {"1", "true", "sim"}
    if upper_text(status) == "EXPEDIDO" and not accepted:
        raise ValueError(
            "CONFIRMAÇÃO EXPLÍCITA OBRIGATÓRIA: EXPEDIDO BLOQUEIA O CARREGAMENTO DEFINITIVAMENTE."
        )


def _apply_registered_vehicle(header: dict) -> dict:
    vehicle_id = header.get("caminhao_id") or ""
    if not vehicle_id:
        return header
    with connect() as conn:
        vehicle = conn.execute("SELECT * FROM caminhoes WHERE id=? AND ativo=1", (vehicle_id,)).fetchone()
    if not vehicle:
        raise ValueError("VEÍCULO CADASTRADO NÃO ENCONTRADO OU INATIVO.")
    # O cadastro da frota é a fonte oficial do veículo selecionado. A carga
    # guarda uma cópia destes dados para preservar seu histórico operacional.
    header["veiculo"] = vehicle["modelo"]
    header["placa"] = vehicle["placa"]
    header["propriedade"] = vehicle["propriedade"]
    header["transportadora"] = vehicle["transportadora"]
    header["motorista"] = header["motorista"] or vehicle["motorista_padrao"]
    return header


def _prepare_works(entries: list[dict], *, allow_empty_items: bool = False) -> list[dict]:
    if not isinstance(entries, list) or not entries:
        raise ValueError("ADICIONE PELO MENOS UMA OBRA AO CARREGAMENTO.")
    if len(entries) > 100:
        raise ValueError("UM CARREGAMENTO PODE CONTER NO MÁXIMO 100 OBRAS.")
    if not allow_empty_items and not any((entry or {}).get("itens") for entry in entries):
        raise ValueError("SELECIONE PELO MENOS UM ITEM PARA O CARREGAMENTO.")
    result = []
    seen = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError("DADOS DE OBRA INVÁLIDOS NO CARREGAMENTO.")
        items = raw.get("itens") or []
        if not isinstance(items, list) or len(items) > 1_000:
            raise ValueError("CADA OBRA PODE CONTER NO MÁXIMO 1.000 LINHAS DE ITENS.")
        resolved = _resolve_obra(raw or {}, allow_incomplete=allow_empty_items)
        work_id = resolved["obra"]["id"]
        if work_id in seen:
            raise ValueError(f"A OBRA {resolved['obra']['nome']} FOI ADICIONADA DUAS VEZES.")
        seen.add(work_id)
        result.append(resolved)
    return result


def _calculate_work_values(works: list[dict], *, allow_empty: bool = False) -> None:
    """Calcula o valor de cada Obra exclusivamente pelos itens selecionados.

    O preço consultado é anexado internamente ao item para que o mesmo valor
    seja gravado como fotografia histórica durante a transação da carga.
    """
    codes = {
        upper_code(item.get("equipamento_codigo") or item.get("codigo"))
        for work in works for item in work.get("itens", [])
        if upper_code(item.get("equipamento_codigo") or item.get("codigo"))
    }
    with connect() as conn:
        catalog = {
            row["codigo"]: dict(row)
            for row in conn.execute(
                f"SELECT codigo,nome,valor_unit,ativo FROM equipamentos WHERE codigo IN ({','.join('?' for _ in codes)})",
                tuple(sorted(codes)),
            )
        } if codes else {}
    for work in works:
        total = 0.0
        valid_items = 0
        for raw_item in work.get("itens", []):
            code = upper_code(raw_item.get("equipamento_codigo") or raw_item.get("codigo"))
            quantity = _integer(raw_item.get("quantidade"), "QUANTIDADE")
            if not code or quantity <= 0:
                continue
            if quantity > 1000:
                raise ValueError("A QUANTIDADE DE CADA ITEM DEVE FICAR ENTRE 1 E 1000.")
            item = catalog.get(code)
            if not item or not item["ativo"]:
                raise ValueError(f"ITEM {code} NÃO ENCONTRADO OU INATIVO.")
            if item["valor_unit"] is None or float(item["valor_unit"]) <= 0:
                raise ValueError(f"ITEM {code} · {item['nome']} ESTÁ SEM VALOR UNITÁRIO POSITIVO.")
            unit_value = round(float(item["valor_unit"]), 4)
            raw_item["_valor_unitario_calculado"] = unit_value
            total += quantity * unit_value
            valid_items += 1
        if not valid_items:
            if allow_empty:
                work["valor_obra"] = 0.0
                continue
            raise ValueError(f"SELECIONE PELO MENOS UM ITEM PARA A OBRA {work['obra']['nome']}.")
        work["valor_obra"] = round(
            finite_number(
                total, field=f"VALOR DA OBRA {work['obra']['nome']}", minimum=0,
                maximum=1_000_000_000_000,
            ),
            2,
        )
        if work["valor_obra"] <= 0:
            raise ValueError(f"O VALOR CALCULADO DA OBRA {work['obra']['nome']} DEVE SER MAIOR QUE ZERO.")


def _legacy_cost_rows(works: list[dict]) -> list[dict]:
    personnel = round(sum(float(work.get("legacy_custo_pessoal") or 0) for work in works), 2)
    explicit_total = round(sum(float(work.get("legacy_custo") or 0) for work in works), 2)
    freight = round(sum(float(work.get("legacy_custo_frete") or 0) for work in works), 2)
    if explicit_total > personnel:
        freight = round(explicit_total - personnel, 2)
    rows = []
    if personnel:
        rows.append({
            "grupo": "PESSOAL", "descricao": "CUSTO PESSOAL ANTERIOR", "modo": "FIXO",
            "valor_unitario": personnel, "quantidade": 1,
        })
    if freight:
        rows.append({
            "grupo": "FRETE", "descricao": "CUSTO DE FRETE ANTERIOR", "modo": "FIXO",
            "valor_unitario": freight, "quantidade": 1,
        })
    return rows


def _prepare_costs(entries, funcionarios: int, dias_viagem: float, works: list[dict]) -> list[dict]:
    if isinstance(entries, list) and len(entries) > 200:
        raise ValueError("UM CARREGAMENTO PODE CONTER NO MÁXIMO 200 DESPESAS.")
    raw_entries = entries if isinstance(entries, list) and entries else _legacy_cost_rows(works)
    result = []
    for index, raw in enumerate(raw_entries):
        raw = raw or {}
        group = upper_text(raw.get("grupo"))
        description = upper_text(raw.get("descricao"))
        mode = upper_code(raw.get("modo") or ("POR_FUNCIONARIO" if group == "PESSOAL" else "FIXO"))
        unit_value = _number(raw.get("valor_unitario"), "VALOR UNITÁRIO DO CUSTO")
        raw_quantity = raw.get("quantidade")
        quantity = _number(raw_quantity, "DIAS / HORAS APLICADOS") if raw_quantity not in (None, "") else 0.0
        enabled = boolean(raw.get("ativo", True), field="DESPESA ATIVA")
        manual = boolean(raw.get("ajuste_manual", False), field="AJUSTE MANUAL")
        if not description and unit_value == 0:
            continue
        if group not in COST_GROUPS:
            raise ValueError("GRUPO DE CUSTO INVÁLIDO. USE PESSOAL OU FRETE.")
        if not description:
            raise ValueError("INFORME A DESCRIÇÃO DE CADA DESPESA.")
        if mode not in COST_MODES:
            raise ValueError(f"BASE DE CÁLCULO INVÁLIDA PARA {description}.")
        legacy_personnel_fixed = (
            group == "PESSOAL" and mode == "FIXO" and "ANTERIOR" in description
            and int(raw.get("calculo_versao") or 0) < 2
        )
        if group == "PESSOAL" and not legacy_personnel_fixed:
            # O único modo operacional novo de pessoal é por funcionário/dia.
            # FIXO permanece apenas para históricos convertidos de versões
            # antigas, sem reinterpretação retroativa.
            mode = "POR_FUNCIONARIO"
            quantity = quantity if raw_quantity not in (None, "") else dias_viagem
            quantity_type = "DIAS"
            total = unit_value * float(funcionarios) * quantity
            applied_employees = funcionarios
        elif group == "PESSOAL":
            quantity = 1.0
            quantity_type = "FIXO"
            total = unit_value
            applied_employees = 0
        elif mode == "FIXO":
            quantity = 1.0
            quantity_type = "FIXO"
            total = unit_value
            applied_employees = 0
        elif mode == "POR_DIA":
            quantity = quantity if raw_quantity not in (None, "") else dias_viagem
            quantity_type = "DIAS"
            total = unit_value * quantity
            applied_employees = 0
        elif mode == "POR_HORA":
            quantity_type = "HORAS"
            total = unit_value * quantity
            applied_employees = 0
        else:
            quantity_type = "UNIDADES"
            total = unit_value * quantity
            applied_employees = 0
        if not enabled:
            total = 0.0
        total = finite_number(
            total, field=f"TOTAL DO CUSTO {description}", minimum=0,
            maximum=1_000_000_000_000,
        )
        result.append(
            {
                "grupo": group,
                "descricao": description,
                "modo": mode,
                "valor_unitario": round(unit_value, 4),
                "quantidade": round(quantity, 4),
                "total": round(total, 2),
                "ativo": 1 if enabled else 0,
                "ordem": index,
                "funcionarios_aplicados": applied_employees,
                "quantidade_tipo": quantity_type,
                "ajuste_manual": 1 if manual else 0,
                "calculo_versao": 2,
            }
        )
    return result


def _split_total(total: float, shares: list[float]) -> list[float]:
    allocated = []
    used = 0.0
    for index, share in enumerate(shares):
        if index == len(shares) - 1:
            amount = round(total - used, 2)
        else:
            amount = round(total * share / 100, 2)
            used = round(used + amount, 2)
        allocated.append(amount)
    return allocated


def _apply_allocations(works: list[dict], summary: dict, *, allow_empty: bool = False) -> None:
    values = [round(float(work.get("valor_obra") or 0), 2) for work in works]
    if any(value <= 0 for value in values):
        if allow_empty:
            total_positive = sum(values)
            if total_positive > 0:
                shares = [round(value / total_positive * 100, 6) if value > 0 else 0.0 for value in values]
                last_positive = max(index for index, value in enumerate(values) if value > 0)
                shares[last_positive] = round(shares[last_positive] + 100.0 - sum(shares), 6)
            else:
                shares = []
                used = 0.0
                for index in range(len(works)):
                    share = round(100.0 - used, 6) if index == len(works) - 1 else round(100.0 / len(works), 6)
                    shares.append(share); used += share
            personnel = _split_total(summary["custo_pessoal"], shares)
            freight = _split_total(summary["custo_frete"], shares)
            for index, work in enumerate(works):
                work["percentual_rateio"] = shares[index]
                work["custo_pessoal"] = personnel[index]
                work["custo_frete"] = freight[index]
                work["custo_viagem"] = round(personnel[index] + freight[index], 2)
            return
        raise ValueError("INFORME UM VALOR MAIOR QUE ZERO PARA CADA OBRA. O RATEIO É AUTOMÁTICO PELO VALOR DAS OBRAS.")
    total_value = sum(values)
    shares = []
    used = 0.0
    for index, value in enumerate(values):
        share = round(100.0 - used, 6) if index == len(values) - 1 else round(value / total_value * 100, 6)
        shares.append(share)
        used += share
    personnel = _split_total(summary["custo_pessoal"], shares)
    freight = _split_total(summary["custo_frete"], shares)
    for index, work in enumerate(works):
        work["percentual_rateio"] = shares[index]
        work["custo_pessoal"] = personnel[index]
        work["custo_frete"] = freight[index]
        work["custo_viagem"] = round(personnel[index] + freight[index], 2)


def _insert_costs(conn, carregamento_id: str, costs: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO carregamento_custos(
            carregamento_id,grupo,descricao,modo,valor_unitario,quantidade,total,ativo,ordem,
            funcionarios_aplicados,quantidade_tipo,ajuste_manual,calculo_versao
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                carregamento_id, row["grupo"], row["descricao"], row["modo"],
                row["valor_unitario"], row["quantidade"], row["total"], row["ativo"], row["ordem"],
                row["funcionarios_aplicados"],row["quantidade_tipo"],row["ajuste_manual"],row["calculo_versao"],
            )
            for row in costs
        ],
    )


def _insert_works_and_items(conn, carregamento_id: str, works: list[dict]) -> int:
    inserted_items = 0
    for order, work in enumerate(works):
        obra = work["obra"]
        conn.execute(
            """
            INSERT INTO carregamento_obras(
                carregamento_id,obra_id,op_numero,municipio,endereco,latitude,longitude,
                distancia_km,custo_pessoal,custo_frete,custo_viagem,valor_obra,
                percentual_rateio,observacao,ordem,previsao_entrega,referencia_contrato
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                carregamento_id, obra["id"], work["op_numero"], work["municipio"], work["endereco"],
                work["latitude"], work["longitude"], work["distancia_km"], work["custo_pessoal"],
                work["custo_frete"], work["custo_viagem"], work["valor_obra"],
                work["percentual_rateio"], work["observacao"], order,
                work["previsao_entrega"],work["referencia_contrato"],
            ),
        )
        merged: dict[tuple[str, str | None, str, str], tuple[float, float]] = {}
        for raw_item in work["itens"]:
            code = upper_code(raw_item.get("equipamento_codigo") or raw_item.get("codigo"))
            quantity = _integer(raw_item.get("quantidade"), "QUANTIDADE")
            if not code or quantity <= 0:
                continue
            if quantity > 1000:
                raise ValueError("A QUANTIDADE DE CADA ITEM DEVE FICAR ENTRE 1 E 1000.")
            catalog_item = conn.execute(
                "SELECT valor_unit FROM equipamentos WHERE codigo=? AND ativo=1", (code,)
            ).fetchone()
            if not catalog_item:
                raise ValueError(f"ITEM {code} NÃO ENCONTRADO OU INATIVO.")
            square_id = str(raw_item.get("praca_id") or "").strip() or None
            if square_id:
                square = conn.execute("SELECT obra_id FROM pracas WHERE id=?", (square_id,)).fetchone()
                if not square or square["obra_id"] != obra["id"]:
                    raise ValueError(f"PRAÇA {square_id} NÃO PERTENCE À OBRA {obra['nome']}.")
            unit = upper_code(raw_item.get("unidade") or "UN")[:12] or "UN"
            item_note = upper_text(raw_item.get("observacao"), multiline=True)
            key = (code, square_id, unit, item_note)
            unit_value = float(raw_item.get("_valor_unitario_calculado", catalog_item["valor_unit"] or 0))
            previous_quantity, previous_value = merged.get(key, (0.0, unit_value))
            if abs(previous_value - unit_value) > 0.0001:
                raise ValueError(f"VALORES DIVERGENTES PARA O ITEM {code}.")
            merged_quantity = previous_quantity + quantity
            if merged_quantity > 1000:
                raise ValueError(f"A QUANTIDADE TOTAL DO ITEM {code} NÃO PODE ULTRAPASSAR 1000.")
            merged[key] = (merged_quantity, unit_value)
        for (code, square_id, unit, item_note), (quantity, unit_value) in merged.items():
            conn.execute(
                """INSERT INTO carregamento_itens(
                       carregamento_id,praca_id,equipamento_codigo,quantidade,obra_id,valor_unitario,
                       unidade,observacao
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (carregamento_id, square_id, code, quantity, obra["id"], unit_value, unit, item_note),
            )
            inserted_items += 1
    return inserted_items


def _recalculate_stored_allocations(conn, carregamento_id: str) -> None:
    status_row = conn.execute("SELECT status FROM carregamentos WHERE id=?", (carregamento_id,)).fetchone()
    rows = [dict(row) for row in conn.execute(
        "SELECT obra_id FROM carregamento_obras WHERE carregamento_id=? ORDER BY ordem,obra_id",
        (carregamento_id,),
    )]
    if not rows:
        return
    for row in rows:
        value = conn.execute(
            """SELECT COALESCE(SUM(ci.quantidade*COALESCE(ci.valor_unitario,e.valor_unit,0)),0)
                 FROM carregamento_itens ci JOIN equipamentos e ON e.codigo=ci.equipamento_codigo
                WHERE ci.carregamento_id=? AND ci.obra_id=?""",
            (carregamento_id, row["obra_id"]),
        ).fetchone()[0]
        row["valor_obra"] = round(float(value or 0), 2)
    summary_row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN grupo='PESSOAL' THEN total ELSE 0 END),0) pessoal,
                  COALESCE(SUM(CASE WHEN grupo='FRETE' THEN total ELSE 0 END),0) frete
             FROM carregamento_custos WHERE carregamento_id=?""",
        (carregamento_id,),
    ).fetchone()
    _apply_allocations(rows, {
        "custo_pessoal": float(summary_row["pessoal"] or 0),
        "custo_frete": float(summary_row["frete"] or 0),
    }, allow_empty=bool(status_row and status_row["status"] == "PLANEJADO"))
    conn.executemany(
        """UPDATE carregamento_obras
              SET valor_obra=?,percentual_rateio=?,custo_pessoal=?,custo_frete=?,custo_viagem=?
            WHERE carregamento_id=? AND obra_id=?""",
        [(
            row["valor_obra"], row["percentual_rateio"], row["custo_pessoal"],
            row["custo_frete"], row["custo_viagem"], carregamento_id, row["obra_id"],
        ) for row in rows],
    )


def _snapshot(record: dict, previous_date: str | None = None) -> None:
    current_date = date.fromisoformat(record["data"])
    path = ensure_under_data(carregamento_global_path(current_date, record["id"]))
    if previous_date and previous_date != record["data"]:
        old = ensure_under_data(carregamento_global_path(date.fromisoformat(previous_date), record["id"]))
        if old.exists() and not path.exists():
            stage_move(old, path)
    stage_mkdir(path)
    payload = {key: value for key, value in record.items() if key not in {"bloqueado"}}
    payload["tipo"] = "CARREGAMENTO"
    stage_bytes(
        path / "carregamento.json",
        (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"),
    )


def _sync_snapshot(record: dict, previous_date: str | None = None) -> bool:
    """Atualiza a cópia de consulta sem transformar falha de arquivo em
    duplicidade operacional: o SQLite confirmado continua sendo a fonte oficial.
    """
    _snapshot(record, previous_date)
    return True


def create_carregamento_multi(
    obras: list[dict], data: str, hora: str = "", observacao: str = "", status: str = "PLANEJADO",
    motorista: str = "", veiculo: str = "", placa: str = "", propriedade: str = "PROPRIO",
    transportadora: str = "", data_saida: str = "", hora_saida: str = "",
    funcionarios=0, dias_viagem=0, distancia_km=0, custos: list[dict] | None = None,
    caminhao_id: str = "", data_retorno: str = "", solicitante: str = "",
    confirmar_expedicao=False,
):
    header = _normalize_header(
        {
            "data": data, "hora": hora, "observacao": observacao, "status": status,
            "motorista": motorista, "veiculo": veiculo, "placa": placa,
            "propriedade": propriedade, "transportadora": transportadora,
            "data_saida": data_saida, "hora_saida": hora_saida,
            "data_retorno": data_retorno, "solicitante": solicitante,
            "funcionarios": funcionarios, "dias_viagem": dias_viagem, "distancia_km": distancia_km,
            "caminhao_id": caminhao_id,
        }
    )
    _require_expedition_confirmation(header["status"], confirmar_expedicao)
    header = _apply_registered_vehicle(header)
    works = _prepare_works(obras, allow_empty_items=header["status"] == "PLANEJADO")
    _calculate_work_values(works, allow_empty=header["status"] == "PLANEJADO")
    cost_rows = _prepare_costs(custos, header["funcionarios"], header["dias_viagem"], works)
    cost_summary = _resumo_custos(cost_rows)
    _apply_allocations(works, cost_summary, allow_empty=header["status"] == "PLANEJADO")
    now = _now()
    identity = current_identity()
    with connect() as conn:
        carregamento_id = next_id(conn, "carregamento", "CRG")
        main_work = works[0]["obra"]["id"]
        conn.execute(
            """
            INSERT INTO carregamentos(
                id,obra_id,data,hora,status,observacao,caminhao_id,motorista,veiculo,placa,propriedade,
                transportadora,data_saida,hora_saida,funcionarios,dias_viagem,distancia_km,
                data_retorno,solicitante,revisao_operacional,criador_usuario_id,criador_usuario_nome,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                carregamento_id, main_work, header["data"], header["hora"], header["status"],
                header["observacao"], header["caminhao_id"] or None, header["motorista"], header["veiculo"], header["placa"],
                header["propriedade"], header["transportadora"], header["data_saida"],
                header["hora_saida"], header["funcionarios"], header["dias_viagem"],
                header["distancia_km"], header["data_retorno"],header["solicitante"],1,
                identity.user_id,identity.user_name,now,now,
            ),
        )
        _insert_costs(conn, carregamento_id, cost_rows)
        if _insert_works_and_items(conn, carregamento_id, works) == 0 and header["status"] != "PLANEJADO":
            raise ValueError("SELECIONE PELO MENOS UM ITEM COM QUANTIDADE MAIOR QUE ZERO.")
    record = get_carregamento(carregamento_id)
    _sync_snapshot(record)
    log(
        "CARREGAMENTO_CRIADO", id=carregamento_id, data=header["data"], status=header["status"],
        obras=[work["obra"]["id"] for work in works], itens=record["tipos_itens"],
        custo_total=record["custo_total"],
    )
    return record


def update_carregamento(carregamento_id: str, data: dict):
    assert_can_modify(carregamento_id)
    with connect() as conn:
        current = conn.execute("SELECT * FROM carregamentos WHERE id=?", (carregamento_id,)).fetchone()
        if not current:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        previous_date = current["data"]

    header = _apply_registered_vehicle(_normalize_header(data))
    _require_expedition_confirmation(header["status"], data.get("confirmar_expedicao", False))
    works = _prepare_works(data.get("obras") or [], allow_empty_items=header["status"] == "PLANEJADO")
    _calculate_work_values(works, allow_empty=header["status"] == "PLANEJADO")
    cost_rows = _prepare_costs(data.get("custos"), header["funcionarios"], header["dias_viagem"], works)
    cost_summary = _resumo_custos(cost_rows)
    _apply_allocations(works, cost_summary, allow_empty=header["status"] == "PLANEJADO")
    with connect() as conn:
        current = conn.execute("SELECT * FROM carregamentos WHERE id=?", (carregamento_id,)).fetchone()
        if not current:
            raise ValueError("CARREGAMENTO EXPEDIDO OU NÃO ENCONTRADO.")
        retained_work_ids = [work["obra"]["id"] for work in works]
        placeholders = ",".join("?" for _ in retained_work_ids)
        conn.execute(
            f"""UPDATE carregamento_anexos SET obra_id=NULL
                   WHERE carregamento_id=? AND obra_id IS NOT NULL
                     AND obra_id NOT IN ({placeholders})""",
            (carregamento_id, *retained_work_ids),
        )
        conn.execute("DELETE FROM carregamento_itens WHERE carregamento_id=?", (carregamento_id,))
        conn.execute("DELETE FROM carregamento_pracas WHERE carregamento_id=?", (carregamento_id,))
        conn.execute("DELETE FROM carregamento_obras WHERE carregamento_id=?", (carregamento_id,))
        conn.execute("DELETE FROM carregamento_custos WHERE carregamento_id=?", (carregamento_id,))
        conn.execute(
            """
            UPDATE carregamentos SET
                obra_id=?,data=?,hora=?,status=?,observacao=?,caminhao_id=?,motorista=?,veiculo=?,placa=?,
                propriedade=?,transportadora=?,data_saida=?,hora_saida=?,funcionarios=?,
                dias_viagem=?,distancia_km=?,data_retorno=?,solicitante=?,
                revisao_operacional=revisao_operacional+1,updated_at=?
             WHERE id=?
            """,
            (
                works[0]["obra"]["id"], header["data"], header["hora"], header["status"],
                header["observacao"], header["caminhao_id"] or None, header["motorista"], header["veiculo"], header["placa"],
                header["propriedade"], header["transportadora"], header["data_saida"],
                header["hora_saida"], header["funcionarios"], header["dias_viagem"],
                header["distancia_km"],header["data_retorno"],header["solicitante"],_now(),carregamento_id,
            ),
        )
        _insert_costs(conn, carregamento_id, cost_rows)
        if _insert_works_and_items(conn, carregamento_id, works) == 0 and header["status"] != "PLANEJADO":
            raise ValueError("SELECIONE PELO MENOS UM ITEM COM QUANTIDADE MAIOR QUE ZERO.")
    record = get_carregamento(carregamento_id)
    _sync_snapshot(record, previous_date)
    log(
        "CARREGAMENTO_EDITADO", id=carregamento_id, status=record["status"],
        obras=[work["id"] for work in record["obras"]], itens=record["tipos_itens"],
        custo_total=record["custo_total"],
    )
    return record


def update_status(carregamento_id: str, status: str, confirmar_expedicao=False):
    new_status = upper_text(status)
    if new_status not in STATUSES:
        raise ValueError("STATUS INVÁLIDO.")
    _require_expedition_confirmation(new_status, confirmar_expedicao)
    assert_can_modify(carregamento_id)
    with connect() as conn:
        current = conn.execute("SELECT status,criador_usuario_id FROM carregamentos WHERE id=?", (carregamento_id,)).fetchone()
        if not current:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        conn.execute(
            "UPDATE carregamentos SET status=?,revisao_operacional=revisao_operacional+1,updated_at=? WHERE id=?",
            (new_status, _now(), carregamento_id),
        )
    record = get_carregamento(carregamento_id)
    _sync_snapshot(record)
    log("CARREGAMENTO_STATUS", id=carregamento_id, status=new_status)
    return record


def add_item(
    carregamento_id: str, equipamento_codigo: str, quantidade,
    praca_id: str | None = None, obra_id: str | None = None,
):
    code = upper_code(equipamento_codigo)
    quantity = _integer(quantidade, "QUANTIDADE")
    if quantity <= 0:
        raise ValueError("QUANTIDADE DEVE SER MAIOR QUE ZERO.")
    if quantity > 1000:
        raise ValueError("A QUANTIDADE DE CADA ITEM DEVE FICAR ENTRE 1 E 1000.")
    assert_can_modify(carregamento_id)
    with connect() as conn:
        load = conn.execute("SELECT status FROM carregamentos WHERE id=?", (carregamento_id,)).fetchone()
        if not load:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        if load["status"] == "EXPEDIDO":
            raise ValueError("CARREGAMENTO EXPEDIDO: NÃO É POSSÍVEL ADICIONAR ITENS.")
        catalog_item = conn.execute("SELECT nome,valor_unit FROM equipamentos WHERE codigo=? AND ativo=1", (code,)).fetchone()
        if not catalog_item:
            raise ValueError("ITEM INVÁLIDO OU INATIVO.")
        if catalog_item["valor_unit"] is None or float(catalog_item["valor_unit"]) <= 0:
            raise ValueError(f"ITEM {code} · {catalog_item['nome']} ESTÁ SEM VALOR UNITÁRIO POSITIVO.")
        work_ids = [
            row["obra_id"]
            for row in conn.execute(
                "SELECT obra_id FROM carregamento_obras WHERE carregamento_id=? ORDER BY ordem",
                (carregamento_id,),
            )
        ]
        if obra_id and obra_id not in work_ids:
            raise ValueError("A OBRA SELECIONADA NÃO PERTENCE AO CARREGAMENTO.")
        if not obra_id:
            if len(work_ids) == 1:
                obra_id = work_ids[0]
            else:
                raise ValueError("SELECIONE A OBRA DE DESTINO DO ITEM.")
        if praca_id:
            square = conn.execute("SELECT obra_id FROM pracas WHERE id=?", (praca_id,)).fetchone()
            if not square or square["obra_id"] != obra_id:
                raise ValueError("PRAÇA INVÁLIDA PARA A OBRA SELECIONADA.")
        existing = conn.execute(
            """SELECT id,quantidade FROM carregamento_itens
                 WHERE carregamento_id=? AND equipamento_codigo=?
                   AND COALESCE(praca_id,'')=COALESCE(?,'')
                   AND COALESCE(obra_id,'')=COALESCE(?,'')""",
            (carregamento_id, code, praca_id, obra_id),
        ).fetchone()
        if existing:
            new_quantity = float(existing["quantidade"]) + quantity
            if new_quantity > 1000:
                raise ValueError("A QUANTIDADE TOTAL DO ITEM NÃO PODE ULTRAPASSAR 1000.")
            conn.execute("UPDATE carregamento_itens SET quantidade=? WHERE id=?", (new_quantity, existing["id"]))
            item_id = existing["id"]
        else:
            cursor = conn.execute(
                """INSERT INTO carregamento_itens(
                       carregamento_id,praca_id,equipamento_codigo,quantidade,obra_id,valor_unitario,
                       unidade,observacao
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (carregamento_id, praca_id, code, quantity, obra_id, float(catalog_item["valor_unit"]), "UN", ""),
            )
            item_id = cursor.lastrowid
        _recalculate_stored_allocations(conn, carregamento_id)
        conn.execute(
            "UPDATE carregamentos SET revisao_operacional=revisao_operacional+1,updated_at=? WHERE id=?",
            (_now(),carregamento_id),
        )
    record = get_carregamento(carregamento_id)
    _sync_snapshot(record)
    log(
        "CARREGAMENTO_ITEM", carregamento=carregamento_id, equipamento=code,
        quantidade=quantity, praca=praca_id, obra=obra_id,
    )
    return next(item for item in record["itens"] if item["id"] == item_id)


def create_carregamento(
    obra_id: str, data: str, hora: str = "", praca_ids: list[str] | None = None,
    observacao: str = "", status: str = "PLANEJADO", confirmar_expedicao=False,
):
    """Compatibilidade com registros antigos de uma única Obra."""
    load_date = _required_date(data)
    now = _now()
    praca_ids = list(dict.fromkeys(praca_ids or []))
    if len(praca_ids) > 500:
        raise ValueError("UM CARREGAMENTO PODE VINCULAR NO MÁXIMO 500 PRAÇAS.")
    with connect() as conn:
        work = conn.execute(
            """SELECT o.*,u.nome unidade_nome,u.uf FROM obras o
                 JOIN unidades u ON u.id=o.unidade_id WHERE o.id=?""",
            (obra_id,),
        ).fetchone()
        if not work:
            raise ValueError("OBRA INVÁLIDA.")
        for square_id in praca_ids:
            square = conn.execute("SELECT obra_id FROM pracas WHERE id=?", (square_id,)).fetchone()
            if not square or square["obra_id"] != obra_id:
                raise ValueError(f"PRAÇA {square_id} NÃO PERTENCE À OBRA.")
        carregamento_id = next_id(conn, "carregamento", "CRG")
        normalized_status = upper_text(status or "PLANEJADO")
        if normalized_status not in STATUSES:
            raise ValueError("STATUS INVÁLIDO.")
        _require_expedition_confirmation(normalized_status, confirmar_expedicao)
        identity = current_identity()
        conn.execute(
            """INSERT INTO carregamentos(
                   id,obra_id,data,hora,status,observacao,criador_usuario_id,criador_usuario_nome,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (carregamento_id, obra_id, load_date, _optional_time(hora), normalized_status, upper_text(observacao, multiline=True),
             identity.user_id, identity.user_name, now, now),
        )
        conn.execute(
            """INSERT INTO carregamento_obras(
                   carregamento_id,obra_id,op_numero,municipio,endereco,latitude,longitude,
                   percentual_rateio,ordem
               ) VALUES(?,?,?,?,?,?,?,?,0)""",
            (
                carregamento_id, obra_id, work["op_padrao"] or "", work["municipio"] or "",
                work["endereco"] or "", work["latitude"], work["longitude"], 100,
            ),
        )
        conn.executemany(
            "INSERT INTO carregamento_pracas(carregamento_id,praca_id) VALUES(?,?)",
            [(carregamento_id, square_id) for square_id in praca_ids],
        )
        path = ensure_under_data(
            carregamento_path(date.fromisoformat(load_date), work["uf"], work["unidade_nome"], work["folder_name"], carregamento_id)
        )
        stage_mkdir(path)
        stage_bytes(
            path / "carregamento.json",
            (json.dumps({
                "tipo": "CARREGAMENTO", "id": carregamento_id, "obra_id": obra_id,
                "data": load_date, "hora": hora, "pracas": praca_ids,
                "status": normalized_status, "observacao": upper_text(observacao, multiline=True),
                "created_at": now,
            }, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"),
        )
    log("CARREGAMENTO_LEGADO_CRIADO", id=carregamento_id, obra=obra_id, data=load_date)
    return get_carregamento(carregamento_id)
