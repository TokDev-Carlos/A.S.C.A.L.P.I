from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from Core.audit import log
from Core.config import PROJECT_ROOT, SYSTEM_DIR, network_root, station_id
from Core.context import current_identity
from Core.db import connect
from Core.geo import parse_location
from Core.ids import next_id
from Core.text import upper_code, upper_text
from Core.validation import boolean, coordinates
from Core.version import app_version
from Core.resources import resource_target
from Modulos.Carregamentos import service as cargas_service
from Modulos.Carregamentos.service import assert_can_modify


ORDER_MODES = {"OTIMIZADA", "CADASTRO", "MANUAL"}
COST_MODES = {"ESTIMADO", "MANUAL"}
ROUTE_CONFIG = SYSTEM_DIR / "Config" / "rotas.json"
GENERATED_COST_DESCRIPTIONS = {"COMBUSTÍVEL DA ROTA", "PEDÁGIO DA ROTA"}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _number(value, label: str, *, minimum: float = 0, maximum: float | None = None) -> float:
    try:
        result = float(str(value if value not in (None, "") else 0).replace(",", "."))
    except Exception as exc:
        raise ValueError(f"{label} INVÁLIDO.") from exc
    if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{label} FORA DO INTERVALO PERMITIDO.")
    return result


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _route_config() -> dict:
    value = _read_json(ROUTE_CONFIG)
    return value if int(value.get("format") or 0) == 1 else {}


def get_fabrica() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM locais_rota WHERE id='FABRICA'").fetchone()
        return dict(row) if row else {
            "id": "FABRICA", "tipo": "FABRICA", "origem_tipo": "FABRICA", "nome": "FÁBRICA / ORIGEM",
            "endereco": "", "latitude": None, "longitude": None,
        }


def update_fabrica(data: dict) -> dict:
    name = upper_text(data.get("nome") or "FÁBRICA / ORIGEM")
    origin_type = upper_code(data.get("origem_tipo") or "FABRICA")
    if origin_type not in {"EMPRESA", "FABRICA", "UNIDADE"}:
        raise ValueError("TIPO DE ORIGEM INVÁLIDO.")
    address = upper_text(data.get("endereco"))
    location = str(data.get("localizacao") or "").strip()
    if location:
        parsed = parse_location(location)
        latitude, longitude = float(parsed["latitude"]), float(parsed["longitude"])
    else:
        latitude, longitude = coordinates(data.get("latitude"), data.get("longitude"), optional=True)
    now = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO locais_rota(id,tipo,origem_tipo,nome,endereco,latitude,longitude,updated_at)
               VALUES('FABRICA','FABRICA',?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                   origem_tipo=excluded.origem_tipo,nome=excluded.nome,endereco=excluded.endereco,
                   latitude=excluded.latitude,longitude=excluded.longitude,
                   updated_at=excluded.updated_at""",
            (origin_type, name, address, latitude, longitude, now),
        )
    log("FABRICA_ROTA_ATUALIZADA", nome=name, latitude=latitude, longitude=longitude)
    return get_fabrica()


def _haversine(first: dict, second: dict) -> float:
    lat1, lon1 = math.radians(float(first["latitude"])), math.radians(float(first["longitude"]))
    lat2, lon2 = math.radians(float(second["latitude"])), math.radians(float(second["longitude"]))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0, 1 - value)))


def _load_and_works(load_id: str) -> tuple[dict, list[dict]]:
    with connect() as conn:
        load = conn.execute("SELECT * FROM carregamentos WHERE id=? AND deleted_at=''", (load_id,)).fetchone()
        if not load:
            raise ValueError("CARREGAMENTO NÃO ENCONTRADO.")
        if load["status"] == "CANCELADO":
            raise ValueError("NÃO É POSSÍVEL PLANEJAR ROTA PARA CARREGAMENTO CANCELADO.")
        rows = conn.execute(
            """SELECT co.obra_id id,o.nome,o.municipio,u.uf,co.op_numero,co.endereco,
                      COALESCE(co.latitude,o.latitude) latitude,
                      COALESCE(co.longitude,o.longitude) longitude,co.ordem
                 FROM carregamento_obras co
                 JOIN obras o ON o.id=co.obra_id
                 JOIN unidades u ON u.id=o.unidade_id
                WHERE co.carregamento_id=? AND o.deleted_at=''
                ORDER BY co.ordem,o.id""",
            (load_id,),
        ).fetchall()
    return dict(load), _validate_works([dict(row) for row in rows])


def _works_from_entries(entries: list[dict]) -> list[dict]:
    ids = [str((entry or {}).get("obra_id") or (entry or {}).get("id") or "").strip() for entry in entries or []]
    ids = [value for value in ids if value]
    if not ids:
        raise ValueError("SELECIONE PELO MENOS UMA OBRA / PONTO DE PARADA.")
    if len(ids) != len(set(ids)):
        raise ValueError("A MESMA OBRA FOI SELECIONADA MAIS DE UMA VEZ.")
    placeholders = ",".join("?" for _ in ids)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT o.id,o.nome,o.municipio,u.uf,o.op_padrao op_numero,o.endereco,o.latitude,o.longitude,0 ordem
                  FROM obras o JOIN unidades u ON u.id=o.unidade_id
                 WHERE o.id IN ({placeholders}) AND o.deleted_at=''""",
            tuple(ids),
        ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    missing = [value for value in ids if value not in by_id]
    if missing:
        raise ValueError("OBRA NÃO ENCONTRADA: " + "; ".join(missing))
    ordered = []
    entry_by_id = {str((entry or {}).get("obra_id") or (entry or {}).get("id") or "").strip(): entry or {} for entry in entries}
    for index, work_id in enumerate(ids):
        work = by_id[work_id]
        override = entry_by_id[work_id]
        work["ordem"] = index
        work["op_numero"] = upper_code(override.get("op_numero") or work.get("op_numero"))
        ordered.append(work)
    return _validate_works(ordered)


def _validate_works(works: list[dict]) -> list[dict]:
    if not works:
        raise ValueError("O CARREGAMENTO NÃO POSSUI OBRAS PARA PLANEJAR.")
    missing = [work["nome"] for work in works if work.get("latitude") is None or work.get("longitude") is None]
    if missing:
        raise ValueError("INFORME AS COORDENADAS DAS OBRAS: " + "; ".join(missing))
    for work in works:
        work["latitude"] = float(work["latitude"])
        work["longitude"] = float(work["longitude"])
    return works


def _vehicle(vehicle_id: str, load: dict | None = None) -> dict:
    selected = str(vehicle_id or (load or {}).get("caminhao_id") or "").strip()
    if not selected:
        raise ValueError("SELECIONE UM VEÍCULO CADASTRADO OU CRIE UM VEÍCULO NOVO.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM caminhoes WHERE id=? AND ativo=1", (selected,)).fetchone()
    if not row:
        raise ValueError("VEÍCULO CADASTRADO NÃO ENCONTRADO OU INATIVO.")
    result = dict(row)
    try:
        meta = json.loads(result.get("parametros_estimados_json") or "{}")
    except (TypeError, ValueError):
        meta = {}
    result["cadastro_pendente"] = bool(meta.get("cadastro_pendente"))
    return result


def _ordered_works(origin: dict, works: list[dict], mode: str, manual_order) -> list[dict]:
    if mode == "CADASTRO":
        return list(works)
    if mode == "MANUAL":
        values = [str(value or "").strip() for value in (manual_order or []) if str(value or "").strip()]
        expected = {work["id"] for work in works}
        if len(values) != len(expected) or len(set(values)) != len(values) or set(values) != expected:
            raise ValueError("A ORDEM MANUAL PRECISA CONTER CADA OBRA EXATAMENTE UMA VEZ.")
        by_id = {work["id"]: work for work in works}
        return [by_id[value] for value in values]
    pending = list(works)
    result = []
    current = origin
    while pending:
        nearest = min(pending, key=lambda work: (_haversine(current, work), work["id"]))
        result.append(nearest)
        pending.remove(nearest)
        current = nearest
    return result


def _graphhopper_route(stops: list[dict], vehicle: dict) -> dict | None:
    config = _route_config()
    engine = config.get("engine") if isinstance(config.get("engine"), dict) else {}
    endpoint = str(engine.get("local_endpoint") or "http://127.0.0.1:8989/route").strip()
    if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
        return None
    profile = "car" if vehicle.get("tipo") == "CARRO_PASSEIO" else "truck"
    query: list[tuple[str, str]] = [("profile", profile), ("points_encoded", "false"), ("instructions", "false"), ("calc_points", "true")]
    for stop in stops:
        query.append(("point", f"{float(stop['latitude']):.8f},{float(stop['longitude']):.8f}"))
    url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": f"CJL/{app_version()}"})
    timeout = float(engine.get("timeout_seconds") or 5)
    try:
        with urllib.request.urlopen(request, timeout=max(1, min(timeout, 15))) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if len(raw) > 8 * 1024 * 1024:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
        path = payload["paths"][0]
        distance = float(path["distance"]) / 1000.0
        duration = float(path["time"]) / 60000.0
        raw_coords = ((path.get("points") or {}).get("coordinates") or [])
        geometry = [
            {"latitude": float(point[1]), "longitude": float(point[0])}
            for point in raw_coords
            if isinstance(point, list) and len(point) >= 2
        ]
        if distance <= 0 or duration <= 0:
            return None
    except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError):
        return None
    return {
        "distance_km": round(distance, 2),
        "time_min": round(duration, 1),
        "geometry": geometry,
        "engine": "GRAPHHOPPER_LOCAL",
        "source": "RODOVIARIA_LOCAL",
        "base_version": str(config.get("road_base_version") or "LOCAL"),
    }


def _fallback_route(stops: list[dict], vehicle: dict, factor: float) -> dict:
    straight = [_haversine(stops[index - 1], stops[index]) for index in range(1, len(stops))]
    distance = sum(straight) * factor
    config = _route_config()
    speeds = config.get("average_speed_kmh") if isinstance(config.get("average_speed_kmh"), dict) else {}
    speed = float(speeds.get("car" if vehicle.get("tipo") == "CARRO_PASSEIO" else "truck") or (70 if vehicle.get("tipo") == "CARRO_PASSEIO" else 58))
    time_min = distance / max(speed, 1) * 60
    return {
        "distance_km": round(distance, 2),
        "time_min": round(time_min, 1),
        "geometry": [{"latitude": float(stop["latitude"]), "longitude": float(stop["longitude"])} for stop in stops],
        "engine": "FALLBACK_GEODESICO",
        "source": "ESTIMADA_CONTINGENCIA",
        "base_version": "",
    }


def _allocate_distance(stops: list[dict], total: float, factor: float) -> list[dict]:
    segments = []
    estimated = []
    for index in range(1, len(stops)):
        straight = _haversine(stops[index - 1], stops[index])
        estimated.append(straight * factor)
        segments.append({
            "ordem": index,
            "origem_id": stops[index - 1]["id"], "origem": stops[index - 1]["nome"],
            "destino_id": stops[index]["id"], "destino": stops[index]["nome"],
            "distancia_reta_km": round(straight, 2), "distancia_estimada_km": round(straight * factor, 2),
        })
    source_total = sum(estimated)
    used = 0.0
    for index, segment in enumerate(segments):
        if index == len(segments) - 1:
            value = round(total - used, 2)
        elif source_total:
            value = round(total * estimated[index] / source_total, 2)
            used = round(used + value, 2)
        else:
            value = 0.0
        segment["distancia_adotada_km"] = value
    return segments


def _toll_base_candidates() -> list[Path]:
    # Base canônica instalada como recurso local da estação. Publicações futuras
    # permanecem versionadas em Repo e passam pelo catálogo de recursos.
    return [resource_target("BASE_PEDAGIOS_BR") / "pedagios.json"]


def _load_tolls() -> tuple[str, list[dict]]:
    for path in _toll_base_candidates():
        if not path.is_file():
            continue
        value = _read_json(path)
        entries = value.get("pedagios") if isinstance(value.get("pedagios"), list) else []
        return str(value.get("version") or value.get("reference_date") or ""), [item for item in entries if isinstance(item, dict)]
    return "", []


def _near_geometry(latitude: float, longitude: float, geometry: list[dict], threshold_km: float = 2.5) -> bool:
    point = {"latitude": latitude, "longitude": longitude}
    # A geometria do roteador costuma ser densa; amostragem limitada evita custo
    # excessivo em rotas continentais sem sacrificar o cruzamento aproximado.
    if len(geometry) > 10000:
        step = max(1, len(geometry) // 10000)
        geometry = geometry[::step]
    return any(_haversine(point, candidate) <= threshold_km for candidate in geometry)


def _automatic_tolls(geometry: list[dict], vehicle: dict, engine_source: str) -> tuple[float, list[dict], str, str]:
    version, entries = _load_tolls()
    if engine_source != "RODOVIARIA_LOCAL" or len(geometry) < 2 or not entries:
        return 0.0, [], version, "BASE LOCAL / ROTA RODOVIÁRIA AINDA NÃO DISPONÍVEL; USE CUSTO MANUAL SE HOUVER PEDÁGIO."
    axes = int(vehicle.get("eixos") or 0)
    found = []
    total = 0.0
    for entry in entries:
        try:
            lat = float(entry.get("latitude"))
            lon = float(entry.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not _near_geometry(lat, lon, geometry):
            continue
        tariffs = entry.get("tarifas") if isinstance(entry.get("tarifas"), dict) else {}
        raw = tariffs.get(str(axes))
        if raw in (None, ""):
            base = entry.get("tarifa_por_eixo")
            raw = float(base) * axes if base not in (None, "") and axes else None
        try:
            value = round(float(raw), 2)
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue
        found.append({
            "id": str(entry.get("id") or ""), "nome": str(entry.get("nome") or "PEDÁGIO"),
            "rodovia": str(entry.get("rodovia") or ""), "uf": str(entry.get("uf") or ""),
            "km": entry.get("km"), "tipo": str(entry.get("tipo") or "PRACA"), "valor": value,
        })
        total += value
    return round(total, 2), found, version, "BASE LOCAL VERSIONADA × ROTA CALCULADA × CATEGORIA/EIXOS DO VEÍCULO."


def _build_route(data: dict, works: list[dict], load: dict | None = None) -> dict:
    factory = get_fabrica()
    if factory.get("latitude") is None or factory.get("longitude") is None:
        raise ValueError("INFORME A LOCALIZAÇÃO DA FÁBRICA / ORIGEM.")
    origin = {
        "id": "FABRICA", "tipo": "FABRICA", "nome": factory.get("nome") or "FÁBRICA / ORIGEM",
        "endereco": factory.get("endereco") or "", "latitude": float(factory["latitude"]), "longitude": float(factory["longitude"]),
    }
    vehicle = _vehicle(str(data.get("caminhao_id") or ""), load)
    order_mode = upper_code(data.get("ordem_modo") or "OTIMIZADA")
    if order_mode not in ORDER_MODES:
        raise ValueError("MODO DE ORDENAÇÃO INVÁLIDO.")
    ordered = _ordered_works(origin, works, order_mode, data.get("ordem_obras"))
    return_to_origin = boolean(data.get("retorno_origem", False), field="RETORNO À ORIGEM")
    stops = [origin] + [{
        "id": work["id"], "tipo": "OBRA", "nome": work["nome"], "municipio": work.get("municipio") or "",
        "uf": work.get("uf") or "", "op_numero": work.get("op_numero") or "", "endereco": work.get("endereco") or "",
        "latitude": work["latitude"], "longitude": work["longitude"],
    } for work in ordered]
    if return_to_origin:
        stops.append({**origin, "tipo": "RETORNO", "nome": f"RETORNO · {origin['nome']}"})
    for index, stop in enumerate(stops):
        stop["ordem"] = index

    config = _route_config()
    fallback = config.get("fallback") if isinstance(config.get("fallback"), dict) else {}
    road_factor = _number(data.get("fator_rodoviario") or fallback.get("road_factor") or 1.2, "FATOR RODOVIÁRIO", minimum=1, maximum=2)
    engine_result = _graphhopper_route(stops, vehicle) or _fallback_route(stops, vehicle, road_factor)

    distance_mode = upper_code(data.get("distancia_modo") or "ESTIMADA")
    if distance_mode not in {"ESTIMADA", "MANUAL"}:
        raise ValueError("MODO DE DISTÂNCIA INVÁLIDO.")
    manual_distance = _number(data.get("distancia_manual_km"), "DISTÂNCIA MANUAL", minimum=0, maximum=100000)
    if distance_mode == "MANUAL":
        if manual_distance <= 0:
            raise ValueError("INFORME A DISTÂNCIA MANUAL OU VOLTE AO MODO AUTOMÁTICO.")
        adopted_distance = round(manual_distance, 2)
        speed = adopted_distance / max(float(engine_result["time_min"]) / 60, 0.01) if engine_result["distance_km"] > 0 else 58
        time_min = round(adopted_distance / max(speed, 1) * 60, 1)
        distance_source = "MANUAL"
    else:
        adopted_distance = float(engine_result["distance_km"])
        time_min = float(engine_result["time_min"])
        distance_source = str(engine_result["source"])
    segments = _allocate_distance(stops, adopted_distance, road_factor)
    straight_total = round(sum(float(segment["distancia_reta_km"]) for segment in segments), 2)

    pending_vehicle = bool(vehicle.get("cadastro_pendente"))
    fuel_mode = upper_code(data.get("combustivel_modo") or ("MANUAL" if pending_vehicle else "ESTIMADO"))
    if fuel_mode not in COST_MODES:
        raise ValueError("MODO DE CÁLCULO DO COMBUSTÍVEL INVÁLIDO.")
    consumption = _number(vehicle.get("consumo_km_l"), "CONSUMO DO VEÍCULO", minimum=0, maximum=1000)
    unit_price = _number(data.get("preco_combustivel"), "PREÇO DO COMBUSTÍVEL", minimum=0, maximum=10000)
    if pending_vehicle or consumption <= 0:
        fuel_mode = "MANUAL"
    liters = round(adopted_distance / consumption, 3) if consumption > 0 else 0.0
    if fuel_mode == "ESTIMADO":
        if unit_price <= 0:
            raise ValueError("INFORME O PREÇO DO COMBUSTÍVEL PARA O CÁLCULO AUTOMÁTICO.")
        fuel_cost = round(liters * unit_price, 2)
    else:
        fuel_cost = round(_number(data.get("custo_combustivel_manual"), "CUSTO MANUAL DO COMBUSTÍVEL", minimum=0, maximum=10000000), 2)
        if pending_vehicle and data.get("custo_combustivel_manual") in (None, ""):
            raise ValueError("VEÍCULO COM CADASTRO PENDENTE: INFORME MANUALMENTE O CUSTO DO COMBUSTÍVEL.")

    toll_mode = upper_code(data.get("pedagio_modo") or ("MANUAL" if pending_vehicle else "ESTIMADO"))
    if toll_mode not in COST_MODES:
        raise ValueError("MODO DE CÁLCULO DO PEDÁGIO INVÁLIDO.")
    auto_toll, tolls, toll_base_version, toll_formula = _automatic_tolls(engine_result["geometry"], vehicle, str(engine_result["source"]))
    if pending_vehicle:
        toll_mode = "MANUAL"
    if toll_mode == "MANUAL":
        toll_cost = round(_number(data.get("custo_pedagio_manual"), "CUSTO MANUAL DO PEDÁGIO", minimum=0, maximum=10000000), 2)
        toll_formula = "CUSTO MANUAL INFORMADO."
    else:
        toll_cost = auto_toll

    vehicle_snapshot = {key: vehicle.get(key) for key in (
        "id", "tipo", "placa", "modelo", "propriedade", "transportadora", "porte", "eixos",
        "combustivel", "consumo_km_l", "tanque_litros", "apelido", "perfil_codigo", "cadastro_pendente",
    )}
    return {
        "vehicle": vehicle, "vehicle_snapshot": vehicle_snapshot, "order_mode": order_mode,
        "return_to_origin": return_to_origin, "stops": stops, "segments": segments,
        "straight_total": straight_total, "road_factor": road_factor, "distance_mode": distance_mode,
        "adopted_distance": adopted_distance, "time_min": time_min, "engine": engine_result["engine"],
        "distance_source": distance_source, "geometry": engine_result["geometry"], "road_base_version": engine_result["base_version"],
        "fuel_mode": fuel_mode, "unit_price": unit_price, "liters": liters, "fuel_cost": fuel_cost,
        "toll_mode": toll_mode, "tolls": tolls, "toll_cost": toll_cost, "toll_base_version": toll_base_version,
        "toll_formula": toll_formula, "total_cost": round(fuel_cost + toll_cost, 2),
    }


def _persist_plan(load_id: str, result: dict) -> dict:
    identity = current_identity()
    created_at = _now()
    with connect() as conn:
        revision = int(conn.execute("SELECT COALESCE(MAX(revisao),0)+1 FROM planejamentos_rota WHERE carregamento_id=?", (load_id,)).fetchone()[0])
        plan_id = next_id(conn, "planejamento_rota", "ROT")
        conn.execute(
            """INSERT INTO planejamentos_rota(
                   id,carregamento_id,revisao,caminhao_id,ordem_modo,retorno_origem,
                   distancia_modo,distancia_reta_km,fator_rodoviario,distancia_adotada_km,
                   combustivel_modo,preco_combustivel,litros_estimados,custo_combustivel,
                   pedagio_modo,pracas_pedagio,tarifa_pedagio_eixo,custo_pedagio,custo_total,
                   tempo_estimado_min,motor_rota,distancia_fonte,rota_geometria_json,pedagios_json,
                   base_rodoviaria_versao,base_pedagios_versao,
                   veiculo_json,paradas_json,trechos_json,usuario_id,usuario_nome,estacao_id,criado_em
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                plan_id, load_id, revision, result["vehicle"]["id"], result["order_mode"], int(result["return_to_origin"]),
                result["distance_mode"], result["straight_total"], round(result["road_factor"], 4), result["adopted_distance"],
                result["fuel_mode"], round(result["unit_price"], 4), result["liters"], result["fuel_cost"],
                result["toll_mode"], len(result["tolls"]), 0, result["toll_cost"], result["total_cost"],
                result["time_min"], result["engine"], result["distance_source"],
                json.dumps(result["geometry"], ensure_ascii=False), json.dumps(result["tolls"], ensure_ascii=False),
                result["road_base_version"], result["toll_base_version"],
                json.dumps(result["vehicle_snapshot"], ensure_ascii=False, sort_keys=True),
                json.dumps(result["stops"], ensure_ascii=False), json.dumps(result["segments"], ensure_ascii=False),
                identity.user_id, identity.user_name, identity.station_id or station_id(), created_at,
            ),
        )
        conn.execute("UPDATE carregamentos SET distancia_km=?,caminhao_id=?,updated_at=? WHERE id=?", (result["adopted_distance"], result["vehicle"]["id"], created_at, load_id))
        conn.execute(
            "DELETE FROM carregamento_custos WHERE carregamento_id=? AND grupo='FRETE' AND descricao IN (?,?)",
            (load_id, *sorted(GENERATED_COST_DESCRIPTIONS)),
        )
        if result["fuel_cost"] > 0:
            conn.execute(
                "INSERT INTO carregamento_custos(carregamento_id,grupo,descricao,modo,valor_unitario,quantidade,total,ativo,ordem) VALUES(?,?,?,?,?,?,?,?,?)",
                (load_id, "FRETE", "COMBUSTÍVEL DA ROTA", "FIXO", result["fuel_cost"], 1, result["fuel_cost"], 1, 900),
            )
        if result["toll_cost"] > 0:
            conn.execute(
                "INSERT INTO carregamento_custos(carregamento_id,grupo,descricao,modo,valor_unitario,quantidade,total,ativo,ordem) VALUES(?,?,?,?,?,?,?,?,?)",
                (load_id, "FRETE", "PEDÁGIO DA ROTA", "FIXO", result["toll_cost"], 1, result["toll_cost"], 1, 901),
            )
        # Distância por ponto de parada segue o trecho que chega a cada obra.
        for segment in result["segments"]:
            if segment["destino_id"] != "FABRICA":
                conn.execute(
                    "UPDATE carregamento_obras SET distancia_km=? WHERE carregamento_id=? AND obra_id=?",
                    (segment["distancia_adotada_km"], load_id, segment["destino_id"]),
                )
        cargas_service._recalculate_stored_allocations(conn, load_id)
        row = conn.execute("SELECT * FROM planejamentos_rota WHERE id=?", (plan_id,)).fetchone()
    try:
        cargas_service._sync_snapshot(cargas_service.get_carregamento(load_id))
    except Exception:
        # O SQLite é a fonte operacional. Snapshot será reconstruído em manutenção
        # se a gravação de arquivo estiver temporariamente indisponível.
        pass
    log("ROTA_PLANEJADA", id=plan_id, carregamento=load_id, revisao=revision, distancia_km=result["adopted_distance"], tempo_min=result["time_min"], motor=result["engine"], custo_total=result["total_cost"])
    return _public_plan(row)


def _public_plan(row) -> dict:
    item = dict(row)
    item["retorno_origem"] = bool(item["retorno_origem"])
    for field, fallback in (
        ("veiculo_json", {}), ("paradas_json", []), ("trechos_json", []),
        ("rota_geometria_json", []), ("pedagios_json", []),
    ):
        try:
            item[field.removesuffix("_json")] = json.loads(item.pop(field) or json.dumps(fallback))
        except (TypeError, ValueError):
            item[field.removesuffix("_json")] = fallback
    vehicle = item.get("veiculo") or {}
    tank = float(vehicle.get("tanque_litros") or 0)
    consumption = float(vehicle.get("consumo_km_l") or 0)
    liters = float(item.get("litros_estimados") or 0)
    item["autonomia_tanque_km"] = round(tank * consumption, 2) if tank and consumption else 0.0
    item["abastecimentos_estimados"] = max(0, math.ceil(liters / tank) - 1) if tank else 0
    if item["distancia_modo"] == "MANUAL":
        item["formula_distancia"] = "DISTÂNCIA MANUAL INFORMADA"
    elif item.get("distancia_fonte") == "RODOVIARIA_LOCAL":
        item["formula_distancia"] = "ROTA RODOVIÁRIA CALCULADA PELO MOTOR LOCAL"
    else:
        item["formula_distancia"] = f"CONTINGÊNCIA: SOMA GEODÉSICA × FATOR {float(item['fator_rodoviario']):.2f}"
    item["formula_combustivel"] = "CUSTO MANUAL INFORMADO" if item["combustivel_modo"] == "MANUAL" else "DISTÂNCIA ÷ CONSUMO × PREÇO DO COMBUSTÍVEL"
    if item["pedagio_modo"] == "MANUAL":
        item["formula_pedagio"] = "CUSTO MANUAL INFORMADO"
    elif item.get("base_pedagios_versao"):
        item["formula_pedagio"] = "BASE LOCAL VERSIONADA × ROTA × CATEGORIA/EIXOS"
    else:
        item["formula_pedagio"] = "BASE LOCAL DE PEDÁGIOS AINDA NÃO DISPONÍVEL"
    return item


def list_plans(load_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM planejamentos_rota WHERE carregamento_id=? ORDER BY revisao DESC", (str(load_id or "").strip(),)).fetchall()
    return [_public_plan(row) for row in rows]


def plan_route(data: dict) -> dict:
    load_id = str(data.get("carregamento_id") or "").strip()
    if not load_id:
        raise ValueError("SELECIONE O CARREGAMENTO OU USE NOVO CARREGAMENTO.")
    assert_can_modify(load_id)
    load, works = _load_and_works(load_id)
    result = _build_route(data, works, load)
    return _persist_plan(load_id, result)


def create_planned_route(data: dict) -> dict:
    """Calcula primeiro e só então materializa o Carregamento PLANEJADO."""
    entries = data.get("obras") if isinstance(data.get("obras"), list) else []
    works = _works_from_entries(entries)
    result = _build_route(data, works, None)
    payload_works = []
    by_id = {str((entry or {}).get("obra_id") or (entry or {}).get("id") or "").strip(): entry or {} for entry in entries}
    for work in works:
        source = by_id.get(work["id"], {})
        payload_works.append({
            "obra_id": work["id"], "op_numero": source.get("op_numero") or work.get("op_numero") or "",
            "municipio": work.get("municipio") or "", "endereco": work.get("endereco") or "",
            "latitude": work["latitude"], "longitude": work["longitude"], "itens": [],
        })
    vehicle = result["vehicle"]
    load = cargas_service.create_carregamento_multi(
        payload_works,
        str(data.get("data") or date.today().isoformat()),
        str(data.get("hora") or ""),
        "CRIADO A PARTIR DO PLANEJAMENTO DE ROTAS E FROTA.",
        "PLANEJADO",
        vehicle.get("motorista_padrao") or "", vehicle.get("modelo") or "", vehicle.get("placa") or "",
        vehicle.get("propriedade") or "PROPRIO", vehicle.get("transportadora") or "",
        "", "", 0, 0, result["adopted_distance"], [], vehicle["id"], "", str(data.get("solicitante") or ""), False,
    )
    try:
        plan = _persist_plan(load["id"], result)
    except Exception:
        with connect() as conn:
            conn.execute("DELETE FROM carregamentos WHERE id=?", (load["id"],))
        raise
    return {"carregamento": cargas_service.get_carregamento(load["id"]), "planejamento": plan}
