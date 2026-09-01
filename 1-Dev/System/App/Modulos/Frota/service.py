from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from Core.audit import log
from Core.db import connect
from Core.ids import next_id
from Core.text import upper_code, upper_text
from Core.validation import boolean, finite_integer, finite_number


TYPES = {"CARRO_PASSEIO", "CAMINHAO_TRANSPORTE"}
STATUSES = {"DISPONIVEL", "EM_ROTA", "MANUTENCAO", "INATIVO"}
PROPERTIES = {"PROPRIO", "ALUGADO"}
SIZES = {"LEVE", "MEDIO", "PESADO", "EXTRAPESADO"}
FUELS = {"GASOLINA", "ETANOL", "DIESEL", "FLEX", "ELETRICO", "HIBRIDO"}
PROFILES = {
    "CARRO_PASSEIO": {"porte": "LEVE", "eixos": 2, "combustivel": "FLEX", "consumo_km_l": 10.0, "tanque_litros": 50.0, "carroceria": "PASSEIO"},
    "CAMINHAO_3_4": {"porte": "LEVE", "eixos": 2, "combustivel": "DIESEL", "consumo_km_l": 7.0, "tanque_litros": 150.0, "carroceria": "CARGA SECA"},
    "CAMINHAO_TOCO": {"porte": "MEDIO", "eixos": 2, "combustivel": "DIESEL", "consumo_km_l": 5.0, "tanque_litros": 275.0, "carroceria": "CARGA SECA"},
    "CAMINHAO_TRUCK": {"porte": "PESADO", "eixos": 3, "combustivel": "DIESEL", "consumo_km_l": 3.5, "tanque_litros": 400.0, "carroceria": "CARGA SECA"},
    "CARRETA": {"porte": "EXTRAPESADO", "eixos": 6, "combustivel": "DIESEL", "consumo_km_l": 2.5, "tanque_litros": 600.0, "carroceria": "CARRETA"},
}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _number(value, label: str, maximum: float) -> float:
    return finite_number(value, field=label, minimum=0, maximum=maximum, default=0)


def _integer(value, label: str, minimum: int, maximum: int) -> int:
    return finite_integer(value, field=label, minimum=minimum, maximum=maximum, default=minimum)


def _metadata(row: dict) -> dict:
    try:
        raw = json.loads(row.get("parametros_estimados_json") or "{}")
        return raw if isinstance(raw, dict) else {}
    except (ValueError, TypeError):
        return {}


def _public(row) -> dict:
    item = dict(row)
    meta = _metadata(item)
    item["cadastro_pendente"] = bool(meta.get("cadastro_pendente"))
    item["localizacao_origem"] = "API_TELEMETRIA" if item.get("latitude") is not None or item.get("longitude") is not None else "NAO_DISPONIVEL"
    # Latitude/longitude do veículo são reservadas à futura telemetria. Não são
    # enviadas como campos editáveis do cadastro operacional.
    item.pop("latitude", None)
    item.pop("longitude", None)
    return item


def list_caminhoes(include_inactive: bool = True) -> list[dict]:
    sql = "SELECT * FROM caminhoes" + ("" if include_inactive else " WHERE ativo=1") + " ORDER BY ativo DESC,CASE propriedade WHEN 'PROPRIO' THEN 0 ELSE 1 END,tipo,modelo,placa"
    with connect() as conn:
        return [_public(row) for row in conn.execute(sql)]


def _normalize(data: dict) -> dict:
    vehicle_type = upper_code(data.get("tipo") or "CAMINHAO_TRANSPORTE")
    profile_code = upper_code(data.get("perfil_codigo") or ("CARRO_PASSEIO" if vehicle_type == "CARRO_PASSEIO" else "CAMINHAO_TRUCK"))
    profile = PROFILES.get(profile_code, PROFILES["CARRO_PASSEIO" if vehicle_type == "CARRO_PASSEIO" else "CAMINHAO_TRUCK"])
    status = upper_code(data.get("status") or "DISPONIVEL")
    property_type = upper_code(data.get("propriedade") or "PROPRIO")
    plate = upper_code(data.get("placa"))
    model = upper_text(data.get("modelo"))
    size = upper_code(data.get("porte") or profile["porte"])
    fuel = upper_code(data.get("combustivel") or profile["combustivel"])
    if vehicle_type not in TYPES:
        raise ValueError("TIPO DE VEÍCULO INVÁLIDO.")
    if status not in STATUSES:
        raise ValueError("STATUS DO VEÍCULO INVÁLIDO.")
    if property_type not in PROPERTIES:
        raise ValueError("PROPRIEDADE DO VEÍCULO INVÁLIDA.")
    if size not in SIZES:
        raise ValueError("PORTE DO VEÍCULO INVÁLIDO.")
    if fuel not in FUELS:
        raise ValueError("COMBUSTÍVEL DO VEÍCULO INVÁLIDO.")
    if not plate or not model:
        raise ValueError("PLACA E MODELO SÃO OBRIGATÓRIOS NO CADASTRO COMPLETO.")
    return {
        "tipo": vehicle_type, "placa": plate, "modelo": model, "propriedade": property_type,
        "apelido": upper_text(data.get("apelido")), "perfil_codigo": profile_code,
        "carroceria": upper_text(data.get("carroceria") or profile["carroceria"]),
        "transportadora": upper_text(data.get("transportadora")),
        "motorista_padrao": upper_text(data.get("motorista_padrao")),
        "capacidade": upper_text(data.get("capacidade")), "status": status,
        "porte": size,
        "eixos": _integer(data.get("eixos") or profile["eixos"], "QUANTIDADE DE EIXOS", 2, 9),
        "combustivel": fuel,
        "consumo_km_l": round(_number(data.get("consumo_km_l") or profile["consumo_km_l"], "CONSUMO", 1000), 4),
        "tanque_litros": round(_number(data.get("tanque_litros") or profile["tanque_litros"], "TANQUE / BATERIA", 10000), 3),
        "tarifa_pedagio_eixo": round(_number(data.get("tarifa_pedagio_eixo"), "TARIFA DE PEDÁGIO POR EIXO", 100000), 4),
        "observacao": upper_text(data.get("observacao"), multiline=True),
        "ativo": 1 if boolean(data.get("ativo", True), field="VEÍCULO ATIVO") else 0,
    }


def create_caminhao(data: dict) -> dict:
    value = _normalize(data)
    now = _now()
    with connect() as conn:
        if conn.execute("SELECT 1 FROM caminhoes WHERE UPPER(placa)=UPPER(?)", (value["placa"],)).fetchone():
            raise ValueError("JÁ EXISTE UM VEÍCULO COM ESSA PLACA.")
        vehicle_id = next_id(conn, "caminhao", "VEI")
        conn.execute(
            """INSERT INTO caminhoes(
                   id,tipo,placa,modelo,propriedade,transportadora,motorista_padrao,capacidade,status,
                   porte,eixos,combustivel,consumo_km_l,tanque_litros,tarifa_pedagio_eixo,
                   apelido,perfil_codigo,carroceria,parametros_estimados_json,
                   latitude,longitude,observacao,ativo,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vehicle_id, value["tipo"], value["placa"], value["modelo"], value["propriedade"], value["transportadora"], value["motorista_padrao"], value["capacidade"], value["status"], value["porte"], value["eixos"], value["combustivel"], value["consumo_km_l"], value["tanque_litros"], value["tarifa_pedagio_eixo"], value["apelido"], value["perfil_codigo"], value["carroceria"], "{}", None, None, value["observacao"], value["ativo"], now, now),
        )
    log("VEICULO_CRIADO", id=vehicle_id, placa=value["placa"], tipo=value["tipo"])
    return next(item for item in list_caminhoes() if item["id"] == vehicle_id)


def create_pending_caminhao(data: dict) -> dict:
    """Cria o mínimo operacional para uma rota sem fingir ficha técnica completa."""
    vehicle_type = upper_code(data.get("tipo") or "CAMINHAO_TRANSPORTE")
    if vehicle_type not in TYPES:
        raise ValueError("TIPO DE VEÍCULO INVÁLIDO.")
    property_type = upper_code(data.get("propriedade") or "PROPRIO")
    if property_type not in PROPERTIES:
        raise ValueError("PROPRIEDADE DO VEÍCULO INVÁLIDA.")
    model = upper_text(data.get("modelo") or data.get("apelido") or "VEÍCULO NOVO")
    alias = upper_text(data.get("apelido") or model)
    transport = upper_text(data.get("transportadora"))
    now = _now()
    with connect() as conn:
        vehicle_id = next_id(conn, "caminhao", "VEI")
        plate = f"PEND-{vehicle_id[-8:]}"
        conn.execute(
            """INSERT INTO caminhoes(
                   id,tipo,placa,modelo,propriedade,transportadora,motorista_padrao,capacidade,status,
                   porte,eixos,combustivel,consumo_km_l,tanque_litros,tarifa_pedagio_eixo,
                   apelido,perfil_codigo,carroceria,parametros_estimados_json,
                   latitude,longitude,observacao,ativo,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                vehicle_id, vehicle_type, plate, model, property_type, transport, "", "", "DISPONIVEL",
                "LEVE" if vehicle_type == "CARRO_PASSEIO" else "MEDIO", 2,
                "FLEX" if vehicle_type == "CARRO_PASSEIO" else "DIESEL", 0, 0, 0,
                alias, "PENDENTE", "", json.dumps({"cadastro_pendente": True}, ensure_ascii=False),
                None, None, "CADASTRO RÁPIDO CRIADO NO PLANEJAMENTO DE ROTA. COMPLETAR FICHA TÉCNICA.", 1, now, now,
            ),
        )
    log("VEICULO_PENDENTE_CRIADO", id=vehicle_id, tipo=vehicle_type, propriedade=property_type)
    return next(item for item in list_caminhoes() if item["id"] == vehicle_id)


def update_caminhao(vehicle_id: str, data: dict) -> dict:
    value = _normalize(data)
    with connect() as conn:
        current = conn.execute("SELECT * FROM caminhoes WHERE id=?", (vehicle_id,)).fetchone()
        if not current:
            raise ValueError("VEÍCULO NÃO ENCONTRADO.")
        if conn.execute("SELECT 1 FROM caminhoes WHERE UPPER(placa)=UPPER(?) AND id<>?", (value["placa"], vehicle_id)).fetchone():
            raise ValueError("JÁ EXISTE UM VEÍCULO COM ESSA PLACA.")
        # Localização existente é preservada exclusivamente para futura API de
        # telemetria; o cadastro humano não pode sobrescrevê-la.
        conn.execute(
            """UPDATE caminhoes SET
                   tipo=?,placa=?,modelo=?,propriedade=?,transportadora=?,motorista_padrao=?,capacidade=?,status=?,
                   porte=?,eixos=?,combustivel=?,consumo_km_l=?,tanque_litros=?,tarifa_pedagio_eixo=?,
                   apelido=?,perfil_codigo=?,carroceria=?,parametros_estimados_json='{}',
                   observacao=?,ativo=?,updated_at=? WHERE id=?""",
            (value["tipo"], value["placa"], value["modelo"], value["propriedade"], value["transportadora"], value["motorista_padrao"], value["capacidade"], value["status"], value["porte"], value["eixos"], value["combustivel"], value["consumo_km_l"], value["tanque_litros"], value["tarifa_pedagio_eixo"], value["apelido"], value["perfil_codigo"], value["carroceria"], value["observacao"], value["ativo"], _now(), vehicle_id),
        )
    log("VEICULO_EDITADO", id=vehicle_id, placa=value["placa"], status=value["status"])
    return next(item for item in list_caminhoes() if item["id"] == vehicle_id)
