from __future__ import annotations

import json
import math
import os
import threading
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from estrutura_sistema import ensure_structure
from Core.audit import log
from Core.bootstrap import bootstrap
from Core.config import PROJECT_ROOT, local_state_root, network_root, station_id
from Core.instance import complete as complete_instance
from Core.instance import lifecycle_token, publish as publish_instance, request_shutdown
from Core.stations import (
    CriticalMaintenanceError,
    StationUpdateRequiredError,
    maintenance_status as station_maintenance_status,
    start as start_station_presence,
    stop as stop_station_presence,
)
from Core.provenance import public_notice
from Core import resources as resource_manager
from Core.geo import parse_location, search_location
from Core.context import RequestIdentity, reset_identity, set_identity
from Core.official_audit import recent as recent_official_audit
from Core.official_audit import record as official_audit
from Core.repository import (
    RepositoryConflictError,
    RepositoryOfflineError,
    maintenance_scope,
    read_scope,
    startup as repository_startup,
    write_scope,
)
from Core.version import app_version, app_version_full, schema_version, patch_ids
from Core.release import normalize_version, version_key
from Modulos.Anexos import service as anexos
from Modulos.Carregamentos import service as cargas
from Modulos.Catalogo import service as catalogo
from Modulos.Clientes import service as clientes
from Modulos.Exclusoes import service as exclusoes
from Modulos.Exportacao import service as exportacao
from Modulos.Evidencias import service as evidencias
from Modulos.Financeiro import service as financeiro
from Modulos.Frota import service as frota
from Modulos.Obras import service as obras
from Modulos.Rotas import service as rotas
from Modulos.Sistema import service as sistema
from Modulos.Usuarios import service as usuarios
from Modulos.Viagens import service as viagens


SYSTEM_DIR = Path(__file__).resolve().parent
PANEL_DIR = SYSTEM_DIR / "Painel"
SERVER = None
INSTANCE_TOKEN = ""
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_FAILURES_LOCK = threading.RLock()
LAST_WINDOW_ACTIVE = time.monotonic()
LIFECYCLE_CLIENTS: dict[str, float] = {}
LIFECYCLE_LOCK = threading.RLock()
LIFECYCLE_SEEN_CLIENT = False
LIFECYCLE_SHUTTING_DOWN = False
LIFECYCLE_STARTED_AT = time.monotonic()
FORCED_DISCONNECTED = os.environ.get("CJL_FORCE_DISCONNECTED", "").strip() == "1"


def _valid_client_id(value: str) -> str:
    candidate = str(value or "").strip()
    if not 16 <= len(candidate) <= 128 or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in candidate
    ):
        raise ValueError("IDENTIDADE DA JANELA INVÁLIDA.")
    return candidate


def _lifecycle_pulse(client_id: str) -> None:
    global LIFECYCLE_SEEN_CLIENT
    client = _valid_client_id(client_id)
    with LIFECYCLE_LOCK:
        LIFECYCLE_SEEN_CLIENT = True
        LIFECYCLE_CLIENTS[client] = time.monotonic()


def _lifecycle_close(client_id: str) -> None:
    client = _valid_client_id(client_id)
    with LIFECYCLE_LOCK:
        LIFECYCLE_CLIENTS.pop(client, None)


def _shutdown_from_lifecycle(reason: str) -> None:
    global LIFECYCLE_SHUTTING_DOWN
    with LIFECYCLE_LOCK:
        if LIFECYCLE_SHUTTING_DOWN:
            return
        LIFECYCLE_SHUTTING_DOWN = True
    request_shutdown(reason)
    usuarios.clear_sessions()
    if SERVER:
        SERVER.shutdown()


def _lifecycle_watchdog() -> None:
    empty_since: float | None = None
    while True:
        time.sleep(1)
        now = time.monotonic()
        with LIFECYCLE_LOCK:
            if LIFECYCLE_SHUTTING_DOWN:
                return
            stale = [client for client, seen in LIFECYCLE_CLIENTS.items() if now - seen > 15]
            for client in stale:
                LIFECYCLE_CLIENTS.pop(client, None)
            seen_any = LIFECYCLE_SEEN_CLIENT
            has_clients = bool(LIFECYCLE_CLIENTS)
        if has_clients:
            empty_since = None
            continue
        if seen_any:
            empty_since = empty_since or now
            if now - empty_since >= 5:
                _shutdown_from_lifecycle("NENHUMA_JANELA_ATIVA")
                return
        elif now - LIFECYCLE_STARTED_AT >= 90:
            _shutdown_from_lifecycle("JANELA_NAO_INICIALIZADA")
            return



def _maintenance_watchdog() -> None:
    """Revoga sessões locais assim que o Mestre entra em manutenção crítica."""
    was_active = False
    while True:
        time.sleep(1.5)
        try:
            state = station_maintenance_status()
        except Exception:
            continue
        active = bool(state.get("active"))
        if active and not was_active:
            usuarios.clear_sessions()
            log(
                "ESTACAO_DESCONECTADA_ATUALIZACAO_CRITICA",
                compat_sequence=int(state.get("compat_sequence") or 0),
                fase=str(state.get("phase") or ""),
            )
        was_active = active
        if LIFECYCLE_SHUTTING_DOWN:
            return


def _require_live_client(client_id: str) -> str:
    client = _valid_client_id(client_id)
    now = time.monotonic()
    with LIFECYCLE_LOCK:
        last_seen = LIFECYCLE_CLIENTS.get(client)
    if last_seen is None or now - last_seen > 20:
        raise PermissionError("JANELA LOCAL NÃO ESTÁ ATIVA PARA ESTA OPERAÇÃO.")
    return client


def _read_release_state(root: Path) -> dict:
    root = Path(root).resolve()
    candidates = (root / "Updates" / "State" / "atual.json", root / "App" / "Config" / "sistema.json")
    value: dict = {}
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                value = raw
                break
        except (OSError, ValueError, TypeError):
            continue
    if not value:
        return {}
    version = normalize_version(str(value.get("version") or "0.0.0"))
    key = version_key(version)
    patches = value.get("patches") if isinstance(value.get("patches"), dict) else {}
    versioning = value.get("versioning") if isinstance(value.get("versioning"), dict) else {}
    business = int(value.get("business") or versioning.get("business") or 1)
    structural = int(value.get("structural", versioning.get("structural", key[0])))
    incremental = int(value.get("incremental", versioning.get("incremental", key[1])))
    security = int(value.get("security", versioning.get("security", key[2])))
    return {
        "version": version,
        "business": business,
        "business_id": str(value.get("business_id") or patches.get("business") or f"BA-{business:02d}"),
        "structural": structural,
        "incremental": incremental,
        "security": security,
        "patches": {
            "business": str(patches.get("business") or f"BA-{business:02d}"),
            "structural": str(patches.get("structural") or versioning.get("structural_id") or f"ES-{structural:02d}"),
            "incremental": str(patches.get("incremental") or versioning.get("incremental_id") or f"IN-{incremental:02d}"),
            "security": str(patches.get("security") or versioning.get("security_id") or f"SE-{security:03d}"),
        },
        "compat_sequence": int(value.get("compat_sequence") or versioning.get("compat_sequence") or 0),
        "schema": int(value.get("schema") or value.get("schema_version") or 0),
        "runtime": int(value.get("runtime") or value.get("runtime_version") or 0),
        "version_full": str(value.get("version_full") or versioning.get("public_version") or ""),
        "build": str(value.get("build") or ""),
        "minimum_station_version": normalize_version(str(value.get("minimum_station_version") or version)),
        "minimum_station_compat": int(value.get("minimum_station_compat") or 0),
        "last_update_mode": str(value.get("last_update_mode") or "LIVE").upper(),
        "last_update_type": str(value.get("last_update_type") or "SE").upper(),
    }


def _station_update_status() -> dict:
    local_root = PROJECT_ROOT.resolve()
    master_root = network_root().resolve()
    local = _read_release_state(local_root)
    master = _read_release_state(master_root)
    reachable = bool(master)
    available = False
    mandatory = False
    minimum_station_compat = int(master.get("minimum_station_compat") or 0) if master else 0
    minimum_station_version = str(master.get("minimum_station_version") or master.get("version") or "0.00.000") if master else "0.00.000"
    if reachable and local_root != master_root:
        available = (
            version_key(str(local.get("version") or "0.00.000")) < version_key(str(master.get("version") or "0.00.000"))
            or str(master.get("build") or "") != str(local.get("build") or "")
        )
        mandatory = available and (
            int(master.get("schema") or 0) != int(local.get("schema") or 0)
            or int(master.get("runtime") or 0) != int(local.get("runtime") or 0)
            or version_key(str(local.get("version") or "0.00.000")) < version_key(minimum_station_version)
            or int(local.get("compat_sequence") or 0) < minimum_station_compat
        )
    maintenance = station_maintenance_status()
    blocked_by_critical = bool(
        maintenance.get("active")
        or (minimum_station_compat and int(local.get("compat_sequence") or 0) < minimum_station_compat)
        or (reachable and version_key(str(local.get("version") or "0.00.000")) < version_key(minimum_station_version))
    )
    return {
        "station": local_root != master_root,
        "reachable": reachable,
        "available": available,
        "mandatory": mandatory,
        "blocked_by_critical": blocked_by_critical,
        "minimum_station_version": minimum_station_version,
        "minimum_station_compat": minimum_station_compat,
        "maintenance": maintenance,
        "local": local,
        "master": master,
    }


def _request_station_update_restart(client_id: str) -> dict:
    _require_live_client(client_id)
    status = _station_update_status()
    if not status["station"]:
        raise ValueError("O PAINEL MESTRE NÃO USA ATUALIZAÇÃO DE ESTAÇÃO.")
    if not status["reachable"]:
        raise RuntimeError("O MESTRE NÃO ESTÁ ACESSÍVEL PARA ATUALIZAÇÃO.")
    if not status["available"]:
        return {"ok": True, "restart": False, "status": status}
    request_file = local_state_root() / "Instancia" / "restart-update.request"
    request_file.parent.mkdir(parents=True, exist_ok=True)
    request_file.write_text(
        json.dumps({"requested_at": time.time(), "target": status["master"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    request_shutdown("ATUALIZACAO_ESTACAO_SOLICITADA")
    return {"ok": True, "restart": True, "status": status}

def _validate_json_payload(root) -> None:
    nodes = 0
    stack = [(root, 0)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > 50_000 or depth > 12:
            raise ValueError("JSON EXCESSIVAMENTE COMPLEXO.")
        if isinstance(value, dict):
            if len(value) > 5_000:
                raise ValueError("OBJETO JSON POSSUI CAMPOS DEMAIS.")
            for key, item in value.items():
                if not isinstance(key, str) or len(key) > 128:
                    raise ValueError("NOME DE CAMPO JSON INVÁLIDO.")
                stack.append((item, depth + 1))
        elif isinstance(value, list):
            if len(value) > 5_000:
                raise ValueError("LISTA JSON POSSUI ITENS DEMAIS.")
            stack.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            if len(value) > 18 * 1024 * 1024:
                raise ValueError("TEXTO JSON EXCEDE O LIMITE PERMITIDO.")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("JSON CONTÉM NÚMERO NÃO FINITO.")
        elif isinstance(value, int) and not isinstance(value, bool) and abs(value) > 10**15:
            raise ValueError("NÚMERO INTEIRO JSON EXCEDE O LIMITE PERMITIDO.")


class AuthenticationError(PermissionError):
    pass


class CsrfError(PermissionError):
    pass


class RouteNotFound(ValueError):
    pass


class Handler(SimpleHTTPRequestHandler):
    server_version = f"CJL/{app_version()}"
    sys_version = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PANEL_DIR), **kwargs)

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob: https://tile.openstreetmap.org; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self' https://nominatim.openstreetmap.org; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        super().end_headers()

    def _guard_local_request(self, *, state_change: bool = False) -> None:
        raw_host = str(self.headers.get("Host") or "").strip()
        try:
            parsed_host = urlparse("//" + raw_host)
            host = str(parsed_host.hostname or "").lower()
            host_port = parsed_host.port
        except ValueError as exc:
            raise PermissionError("HOST NÃO AUTORIZADO.") from exc
        expected_port = int(self.server.server_address[1])
        if (
            host not in {"127.0.0.1", "localhost", "::1"}
            or parsed_host.username is not None
            or parsed_host.password is not None
            or (host_port is not None and host_port != expected_port)
        ):
            raise PermissionError("HOST NÃO AUTORIZADO.")
        if state_change:
            origin = str(self.headers.get("Origin") or "").strip()
            if origin:
                try:
                    parsed_origin = urlparse(origin)
                    origin_port = parsed_origin.port
                except ValueError as exc:
                    raise PermissionError("ORIGEM DA REQUISIÇÃO NÃO AUTORIZADA.") from exc
                if (
                    parsed_origin.scheme != "http"
                    or str(parsed_origin.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}
                    or origin_port != expected_port
                    or parsed_origin.username is not None
                    or parsed_origin.password is not None
                    or parsed_origin.path not in {"", "/"}
                    or parsed_origin.params
                    or parsed_origin.query
                    or parsed_origin.fragment
                ):
                    raise PermissionError("ORIGEM DA REQUISIÇÃO NÃO AUTORIZADA.")

    def _json(self, data, status: int = 200, headers: dict | None = None):
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        length = str(self.headers.get("Content-Length") or "0").strip()
        if not length.isdigit():
            raise ValueError("CONTENT-LENGTH INVÁLIDO.")
        size = int(length)
        if size > 20 * 1024 * 1024:
            raise ValueError("REQUISIÇÃO MUITO GRANDE.")
        content_type = str(self.headers.get("Content-Type") or "").lower()
        if size and "application/json" not in content_type:
            raise ValueError("O CORPO DA REQUISIÇÃO DEVE USAR APPLICATION/JSON.")
        raw = self.rfile.read(size) if size else b"{}"
        def reject_non_standard_number(value: str):
            raise ValueError(f"NÚMERO JSON NÃO PADRONIZADO: {value}.")
        try:
            value = json.loads(raw or b"{}", parse_constant=reject_non_standard_number)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise ValueError("JSON DA REQUISIÇÃO É INVÁLIDO.") from exc
        if not isinstance(value, dict):
            raise ValueError("O CORPO DA REQUISIÇÃO PRECISA SER UM OBJETO JSON.")
        _validate_json_payload(value)
        return value

    def _raw_upload(self, *, max_bytes: int) -> tuple[int, str]:
        length = str(self.headers.get("Content-Length") or "0").strip()
        if not length.isdigit():
            raise ValueError("CONTENT-LENGTH INVÁLIDO.")
        size = int(length)
        if size <= 0 or size > int(max_bytes):
            raise ValueError("TAMANHO DO ARQUIVO ENVIADO É INVÁLIDO.")
        content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type not in {"application/zip", "application/octet-stream"}:
            raise ValueError("O PATCH DEVE SER ENVIADO COMO APPLICATION/ZIP.")
        filename = str(self.headers.get("X-CJL-Filename") or "").strip()
        if not filename:
            raise ValueError("NOME DO PATCH AUSENTE.")
        return size, filename

    def _html(self, content: str, status: int = 200):
        raw = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _download(self, file_path: Path, metadata: dict, *, inline: bool = False):
        raw = file_path.read_bytes()
        fallback = str(metadata.get("nome_seguro") or "anexo").replace('"', "")
        original = quote(str(metadata.get("nome_original") or fallback), safe="")
        self.send_response(200)
        self.send_header("Content-Type", str(metadata.get("mime") or "application/octet-stream"))
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{original}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, error: Exception):
        if isinstance(error, AuthenticationError):
            status = 401
        elif isinstance(error, CsrfError) or isinstance(error, PermissionError):
            status = 403
        elif isinstance(error, CriticalMaintenanceError):
            status = 423
        elif isinstance(error, StationUpdateRequiredError):
            status = 426
        elif isinstance(error, RepositoryOfflineError):
            status = 503
        elif isinstance(error, RepositoryConflictError):
            status = 409
        elif isinstance(error, RouteNotFound):
            status = 404
        elif isinstance(error, (ValueError, json.JSONDecodeError)):
            status = 400
        else:
            status = 500
        if status == 500:
            log("ERRO_INTERNO_API", rota=urlparse(self.path).path, tipo=type(error).__name__, detalhe=str(error)[:1000])
            message = "ERRO INTERNO. A OPERAÇÃO FOI INTERROMPIDA E NENHUMA REVISÃO PARCIAL FOI PUBLICADA."
        else:
            message = str(error)
        return self._json({"error": message}, status)

    def _token(self) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return cookie.get("cjl_session").value if cookie.get("cjl_session") else ""
        except Exception:
            return ""

    def _session(self, permission: str = "", *, csrf: bool = False, allow_password_change: bool = False) -> dict:
        if FORCED_DISCONNECTED:
            raise StationUpdateRequiredError("ESTA ESTAÇÃO ESTÁ EM MODO DESCONECTADO. ATUALIZE-A ANTES DE ENTRAR.")
        value = usuarios.session(self._token())
        if not value:
            raise AuthenticationError("SESSÃO AUSENTE OU EXPIRADA. ENTRE NOVAMENTE.")
        user = value["user"]
        if user.get("trocar_senha") and not allow_password_change:
            raise AuthenticationError("ALTERE A SENHA PROVISÓRIA PARA CONTINUAR.")
        if csrf and self.headers.get("X-CJL-CSRF") != value.get("csrf"):
            raise CsrfError("VALIDAÇÃO DE SEGURANÇA DA REQUISIÇÃO FALHOU.")
        if permission and not usuarios.has_permission(user, permission):
            raise PermissionError("SEU USUÁRIO NÃO TEM PERMISSÃO PARA ESTA AÇÃO.")
        return value

    @staticmethod
    def _identity(user: dict) -> RequestIdentity:
        return RequestIdentity(
            user_id=user["id"], user_name=user["nome"],
            station_id=station_id(),
            role="ADMIN" if usuarios.has_permission(user, "SYSTEM_ADMIN") else "USUARIO",
        )

    def _state(self, user: dict) -> dict:
        administrative = usuarios.has_permission(user, "FINANCE_ADMIN")
        return {
            "unidades": obras.list_unidades(), "obras": obras.list_obras(),
            "pracas": obras.list_pracas(), "carregamentos": cargas.list_carregamentos(),
            "viagens": viagens.list_viagens(),
            # Pagamentos e descrições administrativas nunca são enviados ao
            # usuário padrão, nem como dados ocultos na interface.
            "receitas": financeiro.list_receitas() if administrative else [],
            "clientes": clientes.list_clientes(), "caminhoes": frota.list_caminhoes(),
            "fabrica": rotas.get_fabrica(),
        }

    def _auth_login(self, body: dict):
        if FORCED_DISCONNECTED:
            raise StationUpdateRequiredError("ESTA ESTAÇÃO ESTÁ EM MODO DESCONECTADO DURANTE A ATUALIZAÇÃO CRÍTICA DO MESTRE.")
        address = self.client_address[0]
        now = time.monotonic()
        with LOGIN_FAILURES_LOCK:
            failures = [entry for entry in LOGIN_FAILURES.get(address, []) if now - entry < 60]
        if len(failures) >= 6:
            raise PermissionError("MUITAS TENTATIVAS. AGUARDE UM MINUTO E TENTE NOVAMENTE.")
        password = str(body.get("senha") or "")
        try:
            with read_scope() as repository:
                value = usuarios.login(password, update_access=False)
                offline = not bool(repository.get("online"))
        except PermissionError:
            with LOGIN_FAILURES_LOCK:
                LOGIN_FAILURES[address] = failures + [now]
            raise
        with LOGIN_FAILURES_LOCK:
            LOGIN_FAILURES.pop(address, None)
        log("LOGIN_OFFLINE" if offline else "LOGIN", usuario=value["user"]["id"])
        cookie = (
            f"cjl_session={value['token']}; Path=/; HttpOnly; SameSite=Strict; "
            f"Max-Age={usuarios.SESSION_SECONDS}"
        )
        self._json(
            {"user": value["user"], "csrf": value["csrf"], "offline": offline},
            headers={"Set-Cookie": cookie},
        )

    def _auth_me(self):
        value = self._session(allow_password_change=True)
        self._json({"user": value["user"], "csrf": value["csrf"]})

    def _auth_change_password(self, body: dict):
        value = self._session(csrf=True, allow_password_change=True)
        new_password = str(body.get("nova_senha") or "")
        if new_password != str(body.get("confirmacao") or ""):
            raise ValueError("A CONFIRMAÇÃO DA NOVA SENHA NÃO CONFERE.")
        with write_scope("ALTERAR_SENHA", app_version=app_version(), schema_version=schema_version()):
            value = self._session(csrf=True, allow_password_change=True)
            identity_token = set_identity(self._identity(value["user"]))
            try:
                user = usuarios.change_password(value["user"]["id"], new_password)
                official_audit("SENHA_ALTERADA", "USUARIO", user["id"])
            finally:
                reset_identity(identity_token)
        refreshed = usuarios.start_session_for_user(user["id"])
        cookie = (
            f"cjl_session={refreshed['token']}; Path=/; HttpOnly; SameSite=Strict; "
            f"Max-Age={usuarios.SESSION_SECONDS}"
        )
        self._json({"user": refreshed["user"], "csrf": refreshed["csrf"]}, headers={"Set-Cookie": cookie})

    def _auth_logout(self):
        value = self._session(csrf=True, allow_password_change=True)
        log("LOGOUT", usuario=value["user"]["id"])
        usuarios.logout(value["token"])
        self._json(
            {"ok": True},
            headers={"Set-Cookie": "cjl_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"},
        )

    def do_GET(self):
        global LAST_WINDOW_ACTIVE
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            self._guard_local_request()
            if path == "/api/instance/ping":
                token = (query.get("token") or [""])[0]
                if not INSTANCE_TOKEN or token != INSTANCE_TOKEN:
                    raise PermissionError("TOKEN DA INSTÂNCIA INVÁLIDO.")
                return self._json({"ok": True, "pid": os.getpid(), "version": app_version(), "version_full": app_version_full()})
            if path == "/api/lifecycle/pulse":
                _lifecycle_pulse((query.get("client") or [""])[0])
                return self._json({"ok": True})
            if path == "/api/system/update-status":
                return self._json(_station_update_status())
            if path == "/api/system/maintenance-status":
                return self._json(station_maintenance_status())
            if path == "/api/resources":
                return self._json({"resources": resource_manager.list_resources()})
            if path.startswith("/api/resources/map-tile/"):
                parts = path.strip("/").split("/")
                if len(parts) != 6 or parts[:3] != ["api", "resources", "map-tile"]:
                    raise RouteNotFound("TILE DE MAPA INVÁLIDO.")
                z_text, x_text, y_name = parts[3], parts[4], parts[5]
                if not (z_text.isdigit() and x_text.isdigit() and y_name.lower().endswith(".png") and y_name[:-4].isdigit()):
                    raise RouteNotFound("TILE DE MAPA INVÁLIDO.")
                z, x, y = int(z_text), int(x_text), int(y_name[:-4])
                if not (0 <= z <= 22 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
                    raise RouteNotFound("TILE DE MAPA FORA DO LIMITE.")
                tile = resource_manager.resource_target("MAPA_OFFLINE_BR") / str(z) / str(x) / f"{y}.png"
                if not tile.is_file():
                    return self._json({"error": "TILE OFFLINE NÃO DISPONÍVEL."}, 404)
                raw = tile.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "private,max-age=86400")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/auth/me":
                with read_scope():
                    return self._auth_me()
            if not (path.startswith("/api/") or path.startswith("/export/")):
                return super().do_GET()
            with read_scope():
                value = self._session()
            if path == "/api/about":
                return self._json(public_notice())
            if path == "/api/lifecycle/active":
                LAST_WINDOW_ACTIVE = time.monotonic()
                return self._json({"ok": True})
            if path == "/api/geo/parse":
                return self._json(parse_location((query.get("value") or [""])[0]))
            if path == "/api/geo/search":
                return self._json({"results": search_location((query.get("q") or [""])[0])})
            identity_token = None
            try:
                with read_scope():
                    value = self._session()
                    identity_token = set_identity(self._identity(value["user"]))
                    if path == "/api/state":
                        return self._json(self._state(value["user"]))
                    parts = path.strip("/").split("/")
                    if len(parts) == 4 and parts[:2] == ["api", "carregamentos"] and parts[3] == "anexos":
                        return self._json({"anexos": anexos.list_attachments(parts[2])})
                    if len(parts) == 4 and parts[:2] == ["api", "carregamentos"] and parts[3] == "documentos":
                        return self._json({"documentos": exportacao.list_documents(parts[2])})
                    if len(parts) == 4 and parts[:2] == ["api", "carregamentos"] and parts[3] == "evidencias":
                        return self._json({"evidencias": evidencias.list_evidences(parts[2])})
                    if len(parts) == 5 and parts[:2] == ["api", "documentos"] and parts[3] == "arquivos":
                        try:
                            file_path, _, metadata = exportacao.document_file(parts[2], unquote(parts[4]))
                        except FileNotFoundError as error:
                            return self._json({"error": str(error)}, 404)
                        return self._download(file_path, metadata)
                    if len(parts) == 4 and parts[:2] == ["api", "anexos"] and parts[3] == "download":
                        try:
                            file_path, metadata = anexos.attachment_file(parts[2])
                        except FileNotFoundError as error:
                            return self._json({"error": str(error)}, 404)
                        return self._download(file_path, metadata)
                    if len(parts) == 4 and parts[:2] == ["api", "evidencias"] and parts[3] == "download":
                        try:
                            file_path, metadata = evidencias.evidence_file(parts[2])
                        except FileNotFoundError as error:
                            return self._json({"error": str(error)}, 404)
                        return self._download(file_path, metadata, inline=True)
                    if path.startswith("/api/carregamentos/") and len(path.strip("/").split("/")) == 3:
                        return self._json(cargas.get_carregamento(path.strip("/").split("/")[2]))
                    if path == "/api/catalogo":
                        return self._json({"equipamentos": catalogo.list_equipamentos(include_inactive=True)})
                    if path.startswith("/api/equipamentos/") and path.endswith("/imagem"):
                        code = path.strip("/").split("/")[2]
                        try:
                            image_path, mime = catalogo.image_file(code)
                        except FileNotFoundError as error:
                            return self._json({"error": str(error)}, 404)
                        raw = image_path.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", mime)
                        self.send_header("Cache-Control", "private,max-age=86400")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return
                    if path == "/api/financeiro/resumo":
                        year = (query.get("ano") or [""])[0] or None
                        month = (query.get("mes") or [""])[0] or None
                        state = (query.get("uf") or [""])[0] or None
                        administrative = usuarios.has_permission(value["user"], "FINANCE_ADMIN")
                        return self._json(
                            financeiro.resumo(
                                year, month, state, administrative=administrative
                            )
                        )
                    if path == "/api/financeiro/grafico":
                        year = (query.get("ano") or [""])[0] or None
                        month = (query.get("mes") or [""])[0] or None
                        state = (query.get("uf") or [""])[0] or None
                        chart_type = (query.get("tipo") or [""])[0]
                        administrative = usuarios.has_permission(value["user"], "FINANCE_ADMIN")
                        return self._json(
                            financeiro.grafico(
                                chart_type, year, month, state,
                                administrative=administrative,
                            )
                        )
                    if path == "/api/rotas/planejamentos":
                        load_id = (query.get("carregamento_id") or [""])[0]
                        if not load_id:
                            raise ValueError("INFORME O CARREGAMENTO.")
                        return self._json({"planejamentos": rotas.list_plans(load_id)})
                    if path == "/api/system":
                        sensitive = usuarios.has_permission(value["user"], "SYSTEM_ADMIN")
                        return self._json(sistema.status(include_sensitive=sensitive))
                    if path == "/api/system/master-patches":
                        managed = self._session("SYSTEM_ADMIN")
                        if not usuarios.is_master_admin(managed["user"]):
                            raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR PATCHES DO MESTRE.")
                        return self._json(sistema.master_patch_status())
                    if path == "/api/logs":
                        self._session("SYSTEM_ADMIN")
                        return self._json({"logs": sistema.recent_logs(80)})
                    if path == "/api/auditoria":
                        self._session("SYSTEM_ADMIN")
                        return self._json({"eventos": recent_official_audit(300)})
                    if path == "/api/usuarios":
                        managed = self._session("USERS_MANAGE")
                        if not usuarios.is_master_admin(managed["user"]):
                            raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR CREDENCIAIS.")
                        return self._json({"usuarios": usuarios.list_users()})
                    if path == "/api/exclusoes":
                        self._session("DELETION_REVIEW")
                        return self._json({"solicitacoes": exclusoes.list_requests(True)})
                    if len(parts) == 5 and parts[0] == "export" and parts[1] == "carregamentos" and parts[3] == "obras":
                        return self._html(exportacao.render_work_export(parts[2], parts[4]))
                    raise RouteNotFound("ROTA NÃO ENCONTRADA.")
            finally:
                if identity_token is not None:
                    reset_identity(identity_token)
        except Exception as error:
            return self._error(error)

    def do_POST(self):
        global SERVER, LAST_WINDOW_ACTIVE
        path = urlparse(self.path).path
        try:
            self._guard_local_request(state_change=True)
            if path == "/api/system/master-patch/import":
                managed = self._session("SYSTEM_ADMIN", csrf=True)
                if not usuarios.is_master_admin(managed["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE IMPORTAR PATCHES.")
                size, filename = self._raw_upload(max_bytes=sistema.MAX_MASTER_PATCH_BYTES)
                return self._json(sistema.import_master_patch(self.rfile, size, filename), 201)
            body = self._body()
            if path == "/api/lifecycle/close":
                _lifecycle_close(str(body.get("client") or ""))
                return self._json({"ok": True})
            if path == "/api/lifecycle/shutdown":
                client = str(body.get("client") or "")
                _require_live_client(client)
                self._json({"ok": True})
                threading.Thread(
                    target=_shutdown_from_lifecycle,
                    args=("BOTAO_FECHAR_LOGIN",),
                    daemon=True,
                ).start()
                return
            if path == "/api/resources/install":
                _require_live_client(str(body.get("client") or ""))
                return self._json(resource_manager.install_resource(str(body.get("resource_id") or "")), 201)
            if path == "/api/system/apply-update":
                result = _request_station_update_restart(str(body.get("client") or ""))
                self._json(result)
                if result.get("restart"):
                    threading.Thread(
                        target=_shutdown_from_lifecycle,
                        args=("ATUALIZACAO_ESTACAO_SOLICITADA",),
                        daemon=True,
                    ).start()
                return
            if path == "/api/instance/shutdown":
                token = str(body.get("token") or "")
                if not INSTANCE_TOKEN or token != INSTANCE_TOKEN:
                    raise PermissionError("TOKEN DA INSTÂNCIA INVÁLIDO.")
                self._json({"ok": True})
                threading.Thread(
                    target=_shutdown_from_lifecycle,
                    args=("ENCERRAMENTO_EXTERNO_AUTORIZADO",),
                    daemon=True,
                ).start()
                return
            if path == "/api/auth/login":
                return self._auth_login(body)
            if path == "/api/auth/change-password":
                return self._auth_change_password(body)
            if path == "/api/auth/logout":
                return self._auth_logout()
            self._session(csrf=True)
            if path in {"/api/system/master-patch/validate", "/api/system/master-patch/remove", "/api/system/master-patch/apply"}:
                managed = self._session("SYSTEM_ADMIN", csrf=True)
                if not usuarios.is_master_admin(managed["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR PATCHES DO MESTRE.")
                filename = str(body.get("arquivo") or "")
                if path == "/api/system/master-patch/validate":
                    return self._json(sistema.validate_master_patch(filename))
                if path == "/api/system/master-patch/remove":
                    return self._json(sistema.remove_master_patch(filename))
                result = sistema.prepare_master_patch_apply(filename, backend_pid=os.getpid())
                self._json(result)
                threading.Thread(
                    target=_shutdown_from_lifecycle,
                    args=("PATCH_MESTRE_SOLICITADO",),
                    daemon=True,
                ).start()
                return
            if path == "/api/system/backup":
                with maintenance_scope("BACKUP_COMPLETO"):
                    value = self._session("SYSTEM_ADMIN", csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        return self._json(sistema.backup(), 201)
                    finally:
                        reset_identity(identity_token)
            if path == "/api/system/open-data":
                with read_scope():
                    value = self._session("SYSTEM_ADMIN", csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        root = sistema.status(include_sensitive=True)["paths"]["data_root"]
                        if os.name == "nt":
                            os.startfile(root)  # type: ignore[attr-defined]
                        return self._json({"path": root, "opened": os.name == "nt"})
                    finally:
                        reset_identity(identity_token)
            if path == "/api/shutdown":
                with read_scope():
                    value = self._session(csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        sistema.prepare_shutdown()
                    finally:
                        reset_identity(identity_token)
                usuarios.clear_sessions()
                request_shutdown("BOTAO_FECHAR_SISTEMA")
                self._json({"ok": True})
                if SERVER:
                    threading.Thread(target=SERVER.shutdown, daemon=True).start()
                return
            if path.startswith("/api/carregamentos/") and path.endswith("/documentos"):
                load_id = path.strip("/").split("/")[2]
                with read_scope():
                    value = self._session("OPERATIONS_WRITE", csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        captured = exportacao.capture_package_input(load_id)
                    finally:
                        reset_identity(identity_token)
                identity_token = set_identity(self._identity(value["user"]))
                try:
                    prepared = exportacao.prepare_package(load_id, captured)
                finally:
                    reset_identity(identity_token)
                try:
                    with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                        value = self._session("OPERATIONS_WRITE", csrf=True)
                        identity_token = set_identity(self._identity(value["user"]))
                        try:
                            payload = exportacao.commit_prepared_package(prepared)
                            official_audit("DOCUMENTOS_GERADOS", "CARREGAMENTO", load_id, documento=payload["id"])
                        finally:
                            reset_identity(identity_token)
                    return self._json(payload, 201)
                finally:
                    exportacao.discard_prepared(prepared)
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "usuarios"] and parts[3] in {"reset-pin", "revoke-pin"}:
                with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                    value = self._session("USERS_MANAGE", csrf=True)
                    if not usuarios.is_master_admin(value["user"]):
                        raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR CREDENCIAIS.")
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        if parts[3] == "reset-pin":
                            result = usuarios.reset_pin(parts[2], str(body.get("pin") or ""), value["user"])
                            official_audit("PIN_REDEFINIDO", "USUARIO", parts[2])
                        else:
                            result = usuarios.revoke_pin(parts[2], value["user"])
                            official_audit("PIN_REVOGADO", "USUARIO", parts[2])
                    finally:
                        reset_identity(identity_token)
                return self._json(result)

            permission = "PAYMENTS_MANAGE" if path in {"/api/receitas", "/api/pagamentos"} else "OPERATIONS_WRITE"
            if path == "/api/usuarios":
                permission = "USERS_MANAGE"
            if path == "/api/rota/fabrica":
                permission = "SYSTEM_ADMIN"
            if path == "/api/exclusoes":
                permission = "DELETE_REQUEST"
            with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                value = self._session(permission, csrf=True)
                if path == "/api/usuarios" and not usuarios.is_master_admin(value["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR CREDENCIAIS.")
                identity_token = set_identity(self._identity(value["user"]))
                try:
                    payload, status = self._dispatch_post(path, body, value["user"])
                    entity_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
                    official_audit("API_POST", "ROTA", entity_id, rota=path)
                finally:
                    reset_identity(identity_token)
            return self._json(payload, status)
        except Exception as error:
            return self._error(error)

    def _dispatch_post(self, path: str, body: dict, actor: dict) -> tuple[dict, int]:
        if path == "/api/unidades":
            return obras.create_unidade(body.get("nome", ""), body.get("uf", "")), 201
        if path == "/api/obras":
            return obras.create_obra(
                body.get("unidade_id", "UNI-MT"), body.get("nome", ""), body.get("municipio", ""),
                body.get("codigo", ""), body.get("endereco", ""), body.get("latitude"), body.get("longitude"),
                body.get("op_padrao", ""), body.get("cliente_id", ""), body.get("cliente_nome", ""),
            ), 201
        if path == "/api/clientes":
            return clientes.create_cliente(
                body.get("nome", ""), body.get("documento", ""), body.get("contato", ""),
                body.get("telefone", ""), body.get("email", ""), body.get("observacao", ""), body.get("ativo", True),
            ), 201
        if path == "/api/caminhoes":
            return frota.create_caminhao(body), 201
        if path == "/api/rota/fabrica":
            return rotas.update_fabrica(body), 201
        if path == "/api/rotas/planejar":
            return rotas.plan_route(body), 201
        if path == "/api/rotas/criar-planejado":
            return rotas.create_planned_route(body), 201
        if path == "/api/caminhoes/pendente":
            return frota.create_pending_caminhao(body), 201
        if path == "/api/pracas":
            return obras.create_praca(
                body.get("obra_id", ""), body.get("nome", ""), body.get("op_numero", ""),
                body.get("endereco", ""), body.get("observacao", ""),
            ), 201
        if path == "/api/carregamentos":
            if isinstance(body.get("obras"), list):
                return cargas.create_carregamento_multi(
                    body.get("obras") or [], body.get("data", ""), body.get("hora", ""),
                    body.get("observacao", ""), body.get("status", "PLANEJADO"), body.get("motorista", ""),
                    body.get("veiculo", ""), body.get("placa", ""), body.get("propriedade", "PROPRIO"),
                    body.get("transportadora", ""), body.get("data_saida", ""), body.get("hora_saida", ""),
                    body.get("funcionarios", 0), body.get("dias_viagem", 0), body.get("distancia_km", 0),
                    body.get("custos") or [], body.get("caminhao_id", ""),
                    body.get("data_retorno", ""), body.get("solicitante", ""),
                    body.get("confirmar_expedicao", False),
                ), 201
            return cargas.create_carregamento(
                body.get("obra_id", ""), body.get("data", ""), body.get("hora", ""),
                body.get("praca_ids") or [], body.get("observacao", ""), body.get("status", "PLANEJADO"),
                body.get("confirmar_expedicao", False),
            ), 201
        if path.startswith("/api/carregamentos/") and path.endswith("/anexos"):
            load_id = path.strip("/").split("/")[2]
            return anexos.create_attachment(load_id, body), 201
        if path.startswith("/api/carregamentos/") and path.endswith("/documentos"):
            load_id = path.strip("/").split("/")[2]
            return exportacao.generate_package(load_id), 201
        if path.startswith("/api/carregamentos/") and path.endswith("/evidencias"):
            load_id = path.strip("/").split("/")[2]
            return evidencias.create_evidence(load_id, body), 201
        if path.startswith("/api/carregamentos/") and path.endswith("/itens"):
            load_id = path.strip("/").split("/")[2]
            return cargas.add_item(
                load_id, body.get("equipamento_codigo", ""), body.get("quantidade", ""),
                body.get("praca_id") or None, body.get("obra_id") or None,
            ), 201
        if path == "/api/viagens":
            return viagens.create_viagem(
                body.get("obra_id", ""), body.get("data_saida", ""), body.get("praca_ids") or [],
                body.get("municipio", ""), body.get("local_obra", ""), body.get("veiculo", ""),
                body.get("motorista", ""), body.get("funcionarios", 0), body.get("dias", 0),
                body.get("distancia_km", 0), body.get("custo_pessoal", 0), body.get("custo_frete", 0),
                body.get("custo_total", 0), body.get("observacao", ""), body.get("origem", "MANUAL"),
            ), 201
        if path in {"/api/receitas", "/api/pagamentos"}:
            return financeiro.create_receita(
                body.get("obra_id", ""), body.get("data_competencia", ""), body.get("valor", 0),
                body.get("descricao", ""), body.get("origem", "PAGO_MANUAL"),
            ), 201
        if path == "/api/equipamentos":
            return catalogo.create_equipamento(
                body.get("codigo", ""), body.get("nome", ""), body.get("grupo", ""),
                body.get("valor_unit"), body.get("observacao", ""), body.get("imagem_base64", ""),
            ), 201
        if path == "/api/usuarios":
            return usuarios.create_user(
                body.get("nome", ""), body.get("perfil", "USUARIO"), body.get("senha", ""), body.get("ativo", True),
            ), 201
        if path == "/api/exclusoes":
            return exclusoes.request_deletion(
                body.get("entidade_tipo", ""), body.get("entidade_id", ""), body.get("motivo", ""),
            ), 201
        raise RouteNotFound("ROTA NÃO ENCONTRADA.")

    def do_PATCH(self):
        path = urlparse(self.path).path
        try:
            self._guard_local_request(state_change=True)
            if path == "/api/system/master-patch/import":
                managed = self._session("SYSTEM_ADMIN", csrf=True)
                if not usuarios.is_master_admin(managed["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE IMPORTAR PATCHES.")
                size, filename = self._raw_upload(max_bytes=sistema.MAX_MASTER_PATCH_BYTES)
                return self._json(sistema.import_master_patch(self.rfile, size, filename), 201)
            body = self._body()
            self._session(csrf=True)
            permission = "PAYMENTS_MANAGE" if path.startswith(("/api/receitas/", "/api/pagamentos/")) else "OPERATIONS_WRITE"
            if path.startswith("/api/usuarios/"):
                permission = "USERS_MANAGE"
            if path.startswith("/api/exclusoes/"):
                permission = "DELETION_REVIEW"
            with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                value = self._session(permission, csrf=True)
                if path.startswith("/api/usuarios/") and not usuarios.is_master_admin(value["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE GERENCIAR CREDENCIAIS.")
                identity_token = set_identity(self._identity(value["user"]))
                try:
                    payload = self._dispatch_patch(path, body, value["user"])
                    entity_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
                    official_audit("API_PATCH", "ROTA", entity_id, rota=path)
                finally:
                    reset_identity(identity_token)
            return self._json(payload)
        except Exception as error:
            return self._error(error)

    def _dispatch_patch(self, path: str, body: dict, actor: dict) -> dict:
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "obras"]:
            return obras.update_obra(
                parts[2], body.get("nome", ""), body.get("municipio", ""), body.get("codigo", ""),
                body.get("status", "ATIVA"), body.get("endereco"), body.get("latitude"),
                body.get("longitude"), body.get("op_padrao"), body.get("cliente_id"), body.get("cliente_nome"),
            )
        if len(parts) == 3 and parts[:2] == ["api", "clientes"]:
            return clientes.update_cliente(parts[2], body)
        if len(parts) == 3 and parts[:2] == ["api", "caminhoes"]:
            return frota.update_caminhao(parts[2], body)
        if len(parts) == 3 and parts[:2] == ["api", "pracas"]:
            return obras.update_praca(
                parts[2], body.get("nome", ""), body.get("op_numero", ""), body.get("endereco", ""),
                body.get("observacao", ""), body.get("status", "ATIVA"),
            )
        if len(parts) == 3 and parts[:2] == ["api", "carregamentos"]:
            if isinstance(body.get("obras"), list):
                return cargas.update_carregamento(parts[2], body)
            return cargas.update_status(
                parts[2], body.get("status", "PLANEJADO"), body.get("confirmar_expedicao", False)
            )
        if len(parts) == 3 and parts[:2] == ["api", "viagens"]:
            return viagens.update_viagem(
                parts[2], body.get("data_saida", ""), body.get("municipio", ""), body.get("local_obra", ""),
                body.get("veiculo", ""), body.get("motorista", ""), body.get("funcionarios", 0),
                body.get("dias", 0), body.get("distancia_km", 0), body.get("custo_pessoal", 0),
                body.get("custo_frete", 0), body.get("custo_total", 0), body.get("observacao", ""),
            )
        if len(parts) == 3 and parts[:2] in (["api", "receitas"], ["api", "pagamentos"]):
            return financeiro.update_receita(
                parts[2], body.get("data_competencia", ""), body.get("valor", 0), body.get("descricao", ""),
            )
        if len(parts) == 3 and parts[:2] == ["api", "equipamentos"]:
            return catalogo.update_equipamento(
                parts[2], body.get("nome", ""), body.get("grupo", ""), body.get("valor_unit"),
                body.get("observacao", ""), body.get("ativo", True), body.get("motivo", ""),
                body.get("imagem_base64", ""), body.get("remover_imagem", False),
            )
        if len(parts) == 3 and parts[:2] == ["api", "usuarios"]:
            return usuarios.update_user(parts[2], body, actor["id"])
        if len(parts) == 3 and parts[:2] == ["api", "exclusoes"]:
            return exclusoes.review(parts[2], body.get("acao", ""))
        raise RouteNotFound("ROTA NÃO ENCONTRADA.")

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            self._guard_local_request(state_change=True)
            if path == "/api/system/master-patch/import":
                managed = self._session("SYSTEM_ADMIN", csrf=True)
                if not usuarios.is_master_admin(managed["user"]):
                    raise PermissionError("SOMENTE O ADMINISTRADOR MESTRE PODE IMPORTAR PATCHES.")
                size, filename = self._raw_upload(max_bytes=sistema.MAX_MASTER_PATCH_BYTES)
                return self._json(sistema.import_master_patch(self.rfile, size, filename), 201)
            body = self._body()
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "anexos"]:
                self._session("OPERATIONS_WRITE", csrf=True)
                with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                    value = self._session("OPERATIONS_WRITE", csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        payload = anexos.remove_attachment(parts[2])
                        official_audit("ANEXO_REMOVIDO", "ANEXO", parts[2], carregamento=payload["carregamento_id"])
                    finally:
                        reset_identity(identity_token)
                return self._json(payload)
            if len(parts) == 3 and parts[:2] == ["api", "evidencias"]:
                self._session("OPERATIONS_WRITE", csrf=True)
                with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                    value = self._session("OPERATIONS_WRITE", csrf=True)
                    identity_token = set_identity(self._identity(value["user"]))
                    try:
                        payload = evidencias.remove_evidence(parts[2])
                        official_audit("EVIDENCIA_REMOVIDA", "EVIDENCIA", parts[2], carregamento=payload["carregamento_id"])
                    finally:
                        reset_identity(identity_token)
                return self._json(payload)
            self._session("DELETE_REQUEST", csrf=True)
            kinds = {"clientes": "CLIENTE", "obras": "OBRA", "carregamentos": "CARREGAMENTO"}
            if len(parts) != 3 or parts[0] != "api" or parts[1] not in kinds:
                raise RouteNotFound("ROTA NÃO ENCONTRADA.")
            with write_scope(path, app_version=app_version(), schema_version=schema_version()):
                value = self._session("DELETE_REQUEST", csrf=True)
                identity_token = set_identity(self._identity(value["user"]))
                try:
                    payload = exclusoes.request_deletion(kinds[parts[1]], parts[2], body.get("motivo", ""))
                    official_audit("EXCLUSAO_SOLICITADA", kinds[parts[1]], parts[2], solicitacao=payload["id"])
                finally:
                    reset_identity(identity_token)
            return self._json(payload, 202)
        except Exception as error:
            return self._error(error)

    def log_message(self, format, *args):
        pass


def main():
    global SERVER, INSTANCE_TOKEN
    startup_result = {"online": False, "revision": 0, "published": False}
    if not FORCED_DISCONNECTED:
        ensure_structure()
        startup_result = repository_startup(
            bootstrap, app_version=app_version(), schema_version=schema_version()
        )
    if not FORCED_DISCONNECTED:
        usuarios.initial_credential_notice()
    if startup_result.get("online"):
        try:
            with read_scope():
                expired = exclusoes.expired_count()
            if expired:
                with write_scope(
                    "EXPURGO_EXCLUSOES_VENCIDAS",
                    app_version=app_version(),
                    schema_version=schema_version(),
                ):
                    purged = exclusoes.purge_expired()
                    if purged:
                        official_audit(
                            "EXCLUSOES_VENCIDAS_EXPURGADAS",
                            "SISTEMA",
                            "EXCLUSOES",
                            quantidade=purged,
                        )
        except (RepositoryConflictError, RepositoryOfflineError) as exc:
            # Outra estação poderá executar a manutenção; isso não impede a
            # abertura nem cria divergência local.
            log("MANUTENCAO_EXCLUSOES_ADIADA", erro=str(exc))
    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True
        block_on_close = False
        request_queue_size = 64

        def __init__(self, *args, **kwargs):
            self._workers = threading.BoundedSemaphore(32)
            super().__init__(*args, **kwargs)

        def get_request(self):
            request, address = super().get_request()
            request.settimeout(15)
            return request, address

        def process_request(self, request, client_address):
            if not self._workers.acquire(timeout=1):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self._workers.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self._workers.release()
    SERVER = LocalServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{SERVER.server_address[1]}"
    INSTANCE_TOKEN = lifecycle_token()
    publish_instance(SERVER.server_address[1], INSTANCE_TOKEN)
    if not FORCED_DISCONNECTED:
        start_station_presence(SERVER.server_address[1])
    threading.Thread(target=_lifecycle_watchdog, name="CJLWindowWatchdog", daemon=True).start()
    threading.Thread(target=_maintenance_watchdog, name="CJLMaintenanceWatchdog", daemon=True).start()
    print(f"CJL System — CONTROLE DE CARREGAMENTOS {app_version_full()}:", url)
    if os.environ.get("CJL_BROWSER_MANAGED") != "1":
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        SERVER.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        port = int(SERVER.server_address[1])
        SERVER.server_close()
        stop_station_presence()
        if not FORCED_DISCONNECTED:
            sistema.prepare_shutdown()
        usuarios.clear_sessions()
        complete_instance(port)


if __name__ == "__main__":
    main()
