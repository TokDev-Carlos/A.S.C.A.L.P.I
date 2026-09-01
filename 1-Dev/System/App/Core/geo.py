from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from Core.atomic import atomic_write_json
from Core.config import local_temp_path
from Core.version import app_version


_NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
_GEOCODE_LOCK = threading.Lock()
_LAST_GEOCODE = 0.0


def _float(value: str) -> float:
    return float(str(value).replace(",", "."))


def _validate(latitude: float, longitude: float) -> tuple[float, float]:
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise ValueError("COORDENADA INVÁLIDA.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("COORDENADA FORA DO INTERVALO VÁLIDO.")
    return round(latitude, 8), round(longitude, 8)


def _signed(degrees: float, minutes: float, seconds: float, hemisphere: str) -> float:
    value = abs(degrees) + minutes / 60.0 + seconds / 3600.0
    if hemisphere.upper() in {"S", "W", "O"} or degrees < 0:
        value = -value
    return value


def _parse_url(text: str) -> tuple[float, float] | None:
    if not re.match(r"^https?://", text, re.I):
        return None
    decoded = unquote(text)
    patterns = [
        rf"/@({_NUMBER}),({_NUMBER})",
        rf"[?&](?:q|query|destination|origin)=({_NUMBER})\s*[,;]\s*({_NUMBER})",
        rf"/place/({_NUMBER})\s*[,;]\s*({_NUMBER})",
    ]
    for pattern in patterns:
        match = re.search(pattern, decoded, re.I)
        if match:
            return _validate(_float(match.group(1)), _float(match.group(2)))
    query = parse_qs(urlparse(decoded).query)
    for key in ("q", "query", "destination", "origin"):
        if key not in query:
            continue
        match = re.search(rf"({_NUMBER})\s*[,;]\s*({_NUMBER})", query[key][0])
        if match:
            return _validate(_float(match.group(1)), _float(match.group(2)))
    return None


def _utm_to_latlon(easting: float, northing: float, zone: int, south: bool) -> tuple[float, float]:
    if not 1 <= zone <= 60 or not 100000 <= easting <= 1000000 or not 0 <= northing <= 10000000:
        raise ValueError("COORDENADA UTM FORA DO INTERVALO VÁLIDO.")
    a = 6378137.0
    f = 1 / 298.257222101
    k0 = 0.9996
    e = math.sqrt(f * (2 - f))
    e1sq = e * e / (1 - e * e)
    x = easting - 500000.0
    y = northing - (10000000.0 if south else 0.0)
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))
    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = e1sq * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    n1 = a / math.sqrt(1 - e**2 * math.sin(fp) ** 2)
    r1 = a * (1 - e**2) / (1 - e**2 * math.sin(fp) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = fp - (n1 * math.tan(fp) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e1sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e1sq - 3 * c1**2) * d**6 / 720
    )
    lon = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e1sq + 24 * t1**2) * d**5 / 120
    ) / math.cos(fp)
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    return _validate(math.degrees(lat), math.degrees(lon0 + lon))


def parse_location(raw: str) -> dict:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("INFORME UMA COORDENADA OU LINK DE MAPA.")
    url_value = _parse_url(text)
    if url_value:
        return {"original": text, "format": "MAPA_URL", "latitude": url_value[0], "longitude": url_value[1]}

    decimal = re.fullmatch(rf"\s*({_NUMBER})\s*[,;]\s*({_NUMBER})\s*", text)
    if decimal:
        lat, lon = _validate(_float(decimal.group(1)), _float(decimal.group(2)))
        return {"original": text, "format": "DECIMAL", "latitude": lat, "longitude": lon}

    dms = re.findall(
        rf"({_NUMBER})\s*[°º]\s*({_NUMBER})\s*['′]\s*(?:({_NUMBER})\s*[\"″]\s*)?([NSEWO])",
        text.upper(),
    )
    if len(dms) == 2:
        values = [_signed(_float(d), _float(m), _float(s or "0"), h) for d, m, s, h in dms]
        lat, lon = _validate(values[0], values[1])
        return {"original": text, "format": "DMS" if any(row[2] for row in dms) else "DMM", "latitude": lat, "longitude": lon}

    utm = re.search(
        rf"(?:SIRGAS\s*2000\s*)?(?:UTM\s*)?(?:ZONA\s*)?(\d{{1,2}})\s*([NS])?[^\d]+E\s*[:=]?\s*({_NUMBER})[^\d]+N\s*[:=]?\s*({_NUMBER})",
        text.upper(),
    )
    if not utm:
        utm = re.search(
            rf"(?:SIRGAS\s*2000\s*)?(?:UTM\s*)?({_NUMBER})\s*[,; ]+({_NUMBER})\s+(?:ZONA\s*)?(\d{{1,2}})\s*([NS])",
            text.upper(),
        )
        if utm:
            easting, northing, zone, hemisphere = utm.groups()
        else:
            raise ValueError("FORMATO NÃO RECONHECIDO. USE DECIMAL, DMS, DMM, SIRGAS 2000/UTM OU LINK DE MAPA.")
    else:
        zone, hemisphere, easting, northing = utm.groups()
    lat, lon = _utm_to_latlon(_float(easting), _float(northing), int(zone), (hemisphere or "S") == "S")
    return {"original": text, "format": "SIRGAS2000_UTM", "latitude": lat, "longitude": lon, "utm_zone": int(zone), "hemisphere": hemisphere or "S"}


def search_location(raw: str) -> list[dict]:
    """Pesquisa endereço no serviço público do OpenStreetMap com limite e cache local."""
    global _LAST_GEOCODE
    query = " ".join(str(raw or "").strip().split())
    if len(query) < 3 or len(query) > 240:
        raise ValueError("INFORME UM ENDEREÇO ENTRE 3 E 240 CARACTERES.")
    cache_dir = local_temp_path() / "Geocodificacao"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if time.time() - float(cached.get("stored_epoch") or 0) < 7 * 24 * 60 * 60:
            results = cached.get("results")
            if isinstance(results, list):
                return results
    except (OSError, ValueError, TypeError):
        pass

    with _GEOCODE_LOCK:
        delay = 1.05 - (time.monotonic() - _LAST_GEOCODE)
        if delay > 0:
            time.sleep(delay)
        url = "https://nominatim.openstreetmap.org/search?" + urlencode({
            "format": "jsonv2",
            "limit": 5,
            "countrycodes": "br",
            "addressdetails": 1,
            "q": query,
        })
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"CJL/{app_version()} (Carlosjr.projetos25@gmail.com)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                raw_data = response.read(256 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("A PESQUISA ONLINE DO MAPA ESTÁ INDISPONÍVEL.") from exc
        finally:
            _LAST_GEOCODE = time.monotonic()
    if len(raw_data) > 256 * 1024:
        raise RuntimeError("A RESPOSTA DO MAPA EXCEDEU O LIMITE DE SEGURANÇA.")
    try:
        payload = json.loads(raw_data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("O SERVIÇO DE MAPA DEVOLVEU UMA RESPOSTA INVÁLIDA.") from exc
    results: list[dict] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            latitude, longitude = _validate(float(item["lat"]), float(item["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        address = item.get("address") if isinstance(item.get("address"), dict) else {}
        results.append({
            "label": str(item.get("display_name") or "")[:500],
            "latitude": latitude,
            "longitude": longitude,
            "state_code": str(address.get("ISO3166-2-lvl4") or "").split("-")[-1].upper(),
            "city": str(address.get("city") or address.get("town") or address.get("municipality") or address.get("village") or "")[:160],
        })
    atomic_write_json(cache_path, {"query": query, "stored_epoch": time.time(), "results": results})
    return results
