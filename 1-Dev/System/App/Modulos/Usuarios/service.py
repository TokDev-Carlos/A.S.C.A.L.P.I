from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from Core.db import connect
from Core.config import local_state_root
from Core.ids import next_id
from Core.text import upper_text
from Core.validation import boolean


SESSION_SECONDS = 8 * 60 * 60
MAX_SESSIONS_PER_USER = 8
MAX_SESSIONS_TOTAL = 256
INITIAL_CREDENTIAL_FILE = local_state_root() / "Estacao" / "CREDENCIAL_INICIAL_ADMIN.txt"
MASTER_ADMIN_NAME = "ADMIN"
PIN_MIN_DIGITS = 4
PIN_MAX_DIGITS = 32
_SESSIONS: dict[str, dict] = {}
_SESSION_LOCK = threading.RLock()

ADMIN_PERMISSIONS = {
    "OPERATIONS_WRITE": True,
    "DELETE_REQUEST": True,
    "DELETION_REVIEW": True,
    "PAYMENTS_MANAGE": True,
    "FINANCE_ADMIN": True,
    "SYSTEM_ADMIN": True,
    "USERS_MANAGE": True,
}
USER_PERMISSIONS = {
    "OPERATIONS_WRITE": True,
    "DELETE_REQUEST": True,
    "DELETION_REVIEW": False,
    "PAYMENTS_MANAGE": False,
    "FINANCE_ADMIN": False,
    "SYSTEM_ADMIN": False,
    "USERS_MANAGE": False,
}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _permissions(profile: str, custom: str | dict | None = None) -> dict:
    base = dict(ADMIN_PERMISSIONS if profile == "ADMIN" else USER_PERMISSIONS)
    if isinstance(custom, str):
        try:
            custom = json.loads(custom or "{}")
        except ValueError:
            custom = {}
    if isinstance(custom, dict):
        for key in base:
            if key in custom:
                try:
                    base[key] = boolean(custom[key], field=f"PERMISSÃO {key}")
                except ValueError:
                    base[key] = False
    return base


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _new_password(password: str, *, minimum: int = PIN_MIN_DIGITS, enforce_complexity: bool = False) -> tuple[str, str]:
    """Cria o hash do PIN. O CJL System usa PIN exclusivamente numérico.

    O parâmetro ``enforce_complexity`` permanece apenas por compatibilidade com
    chamadas antigas; regras alfanuméricas foram eliminadas no PATCH 000003.
    """
    value = str(password or "").strip()
    if len(value) < minimum:
        raise ValueError(f"O PIN PRECISA TER PELO MENOS {minimum} DÍGITOS.")
    if len(value) > PIN_MAX_DIGITS:
        raise ValueError(f"O PIN NÃO PODE TER MAIS DE {PIN_MAX_DIGITS} DÍGITOS.")
    if not value.isdigit():
        raise ValueError("O PIN DEVE CONTER SOMENTE NÚMEROS.")
    salt = secrets.token_bytes(16)
    digest = _password_digest(value, salt)
    return base64.b64encode(digest).decode("ascii"), base64.b64encode(salt).decode("ascii")


def _matches(row, password: str) -> bool:
    if not row["senha_hash"] or not row["senha_salt"]:
        return False
    try:
        salt = base64.b64decode(row["senha_salt"], validate=True)
        expected = base64.b64decode(row["senha_hash"], validate=True)
        actual = _password_digest(str(password or ""), salt)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _ensure_unique_password(connection, password: str, excluding: str = "") -> None:
    for row in connection.execute(
        "SELECT id,senha_hash,senha_salt FROM usuarios WHERE id<>?",
        (excluding,),
    ):
        if _matches(row, password):
            raise ValueError("ESSE PIN JÁ PERTENCE A OUTRO USUÁRIO. INFORME UM PIN ÚNICO.")


def initial_credential_notice() -> dict | None:
    """Remove qualquer lembrete legado de credencial em texto claro.

    A partir de SE-001 nenhuma credencial administrativa existe no source, em
    manifests ou em arquivos de lembrete do CJL System.
    """
    try:
        INITIAL_CREDENTIAL_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def ensure_initial_users() -> None:
    """Garante a identidade ADMIN sem conhecer nem redefinir sua credencial.

    Baselines antigas podem possuir o ADMIN com hash Scrypt ja configurado; esse
    hash e preservado integralmente. Se um Mestre novo nao possuir ADMIN, a conta
    nasce sem credencial e deve ser provisionada pela recuperacao administrativa
    local, que exige autoridade do Windows no proprio Mestre.
    """
    now = _now()
    with connect() as connection:
        admin = connection.execute("SELECT * FROM usuarios WHERE nome=? COLLATE NOCASE", (MASTER_ADMIN_NAME,)).fetchone()
        if not admin:
            user_id = next_id(connection, "usuario", "USR")
            connection.execute(
                """INSERT INTO usuarios(
                       id,nome,perfil,senha_hash,senha_salt,permissoes_json,ativo,
                       trocar_senha,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (user_id, MASTER_ADMIN_NAME, "ADMIN", "", "", "{}", 1, 1, now, now),
            )
            connection.execute(
                "INSERT INTO app_meta(key,value) VALUES('admin_provisioning_required','1') "
                "ON CONFLICT(key) DO UPDATE SET value='1'"
            )
        else:
            # Nunca reescrever senha_hash/senha_salt automaticamente.
            connection.execute(
                "INSERT INTO app_meta(key,value) VALUES('security_hardening_se001','1') "
                "ON CONFLICT(key) DO UPDATE SET value='1'"
            )
        if not connection.execute("SELECT 1 FROM usuarios WHERE nome='DAVID'").fetchone():
            user_id = next_id(connection, "usuario", "USR")
            connection.execute(
                """INSERT INTO usuarios(
                       id,nome,perfil,senha_hash,senha_salt,permissoes_json,ativo,
                       trocar_senha,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (user_id, "DAVID", "USUARIO", "", "", "{}", 0, 1, now, now),
            )


def _public_user(row) -> dict:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "perfil": row["perfil"],
        "ativo": bool(row["ativo"]),
        "trocar_senha": bool(row["trocar_senha"]),
        "senha_definida": bool(row["senha_hash"]),
        "ultimo_acesso": row["ultimo_acesso"],
        "permissoes": _permissions(row["perfil"], row["permissoes_json"]),
    }


def _new_session(row) -> dict:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    value = {
        "token": token,
        "csrf": csrf,
        "user": _public_user(row),
        "auth_version": int(row["auth_version"] or 1),
        "created": time.time(),
        "expires": time.time() + SESSION_SECONDS,
    }
    with _SESSION_LOCK:
        now = time.time()
        for existing_token, existing in list(_SESSIONS.items()):
            if float(existing.get("expires") or 0) <= now:
                _SESSIONS.pop(existing_token, None)
        same_user = sorted(
            (
                (existing_token, existing)
                for existing_token, existing in _SESSIONS.items()
                if existing.get("user", {}).get("id") == row["id"]
            ),
            key=lambda item: float(item[1].get("created") or 0),
        )
        for existing_token, _existing in same_user[: max(0, len(same_user) - MAX_SESSIONS_PER_USER + 1)]:
            _SESSIONS.pop(existing_token, None)
        if len(_SESSIONS) >= MAX_SESSIONS_TOTAL:
            oldest = min(
                _SESSIONS.items(),
                key=lambda item: float(item[1].get("created") or 0),
            )[0]
            _SESSIONS.pop(oldest, None)
        _SESSIONS[token] = value
    return value


def _revoke_user_sessions(user_id: str) -> None:
    with _SESSION_LOCK:
        for token, value in list(_SESSIONS.items()):
            if value.get("user", {}).get("id") == user_id:
                _SESSIONS.pop(token, None)


def list_users() -> list[dict]:
    with connect() as connection:
        return [_public_user(row) for row in connection.execute("SELECT * FROM usuarios ORDER BY nome")]


def get_user(user_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (user_id,)).fetchone()
    return _public_user(row) if row else None


def login(password: str, *, update_access: bool = True) -> dict:
    with connect() as connection:
        matches = [row for row in connection.execute("SELECT * FROM usuarios WHERE ativo=1") if _matches(row, password)]
        if len(matches) != 1:
            raise PermissionError("PIN INVÁLIDO OU USUÁRIO SEM ACESSO.")
        row = matches[0]
        if update_access:
            connection.execute("UPDATE usuarios SET ultimo_acesso=?,updated_at=? WHERE id=?", (_now(), _now(), row["id"]))
    return _new_session(row)


def start_session_for_user(user_id: str) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (user_id,)).fetchone()
    if not row:
        raise PermissionError("USUÁRIO NÃO ENCONTRADO OU INATIVO.")
    return _new_session(row)


def session(token: str) -> dict | None:
    if not token:
        return None
    with _SESSION_LOCK:
        value = _SESSIONS.get(token)
        if not value:
            return None
        if float(value.get("expires") or 0) <= time.time():
            _SESSIONS.pop(token, None)
            return None
        user_id = str(value.get("user", {}).get("id") or "")
        expected_auth_version = int(value.get("auth_version") or 0)
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (user_id,)).fetchone()
    if not row or int(row["auth_version"] or 1) != expected_auth_version:
        logout(token)
        return None
    refreshed = _public_user(row)
    with _SESSION_LOCK:
        active = _SESSIONS.get(token)
        if not active:
            return None
        active["user"] = refreshed
        return active


def logout(token: str) -> None:
    with _SESSION_LOCK:
        _SESSIONS.pop(token, None)


def clear_sessions() -> None:
    with _SESSION_LOCK:
        _SESSIONS.clear()


def change_password(user_id: str, new_password: str) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=? AND ativo=1", (user_id,)).fetchone()
        if not row:
            raise ValueError("USUÁRIO NÃO ENCONTRADO OU INATIVO.")
        _ensure_unique_password(connection, new_password, user_id)
        password_hash, salt = _new_password(new_password)
        connection.execute(
            "UPDATE usuarios SET senha_hash=?,senha_salt=?,trocar_senha=0,auth_version=auth_version+1,updated_at=? WHERE id=?",
            (password_hash, salt, _now(), user_id),
        )
        updated = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    _revoke_user_sessions(user_id)
    if str(row["nome"] or "").upper() == "ADMIN":
        try:
            INITIAL_CREDENTIAL_FILE.unlink(missing_ok=True)
        except OSError:
            pass
    return _public_user(updated)


def create_user(name: str, profile: str = "USUARIO", password: str = "", active: bool = True) -> dict:
    normalized_name = upper_text(name, max_length=120)
    normalized_profile = upper_text(profile or "USUARIO")
    if not normalized_name:
        raise ValueError("INFORME O NOME DO USUÁRIO.")
    if normalized_profile not in {"ADMIN", "USUARIO"}:
        raise ValueError("PERFIL DE USUÁRIO INVÁLIDO.")
    active = boolean(active, field="USUÁRIO ATIVO", default=True)
    if active and not password:
        raise ValueError("INFORME UM PIN NUMÉRICO PROVISÓRIO PARA ATIVAR O NOVO USUÁRIO.")
    now = _now()
    with connect() as connection:
        if connection.execute("SELECT 1 FROM usuarios WHERE nome=? COLLATE NOCASE", (normalized_name,)).fetchone():
            raise ValueError("JÁ EXISTE UM USUÁRIO COM ESSE NOME.")
        password_hash = salt = ""
        if password:
            _ensure_unique_password(connection, password)
            password_hash, salt = _new_password(password)
        user_id = next_id(connection, "usuario", "USR")
        connection.execute(
            """INSERT INTO usuarios(
                   id,nome,perfil,senha_hash,senha_salt,permissoes_json,ativo,
                   trocar_senha,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (user_id, normalized_name, normalized_profile, password_hash, salt, "{}", int(active), int(bool(password)), now, now),
        )
        row = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    return _public_user(row)


def update_user(user_id: str, data: dict, actor_id: str = "") -> dict:
    with connect() as connection:
        current = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
        if not current:
            raise ValueError("USUÁRIO NÃO ENCONTRADO.")
        name = upper_text(data.get("nome", current["nome"]), max_length=120)
        profile = upper_text(data.get("perfil", current["perfil"]))
        active = boolean(
            data.get("ativo", bool(current["ativo"])), field="USUÁRIO ATIVO"
        )
        if profile not in {"ADMIN", "USUARIO"}:
            raise ValueError("PERFIL DE USUÁRIO INVÁLIDO.")
        if not name:
            raise ValueError("INFORME O NOME DO USUÁRIO.")
        if connection.execute(
            "SELECT 1 FROM usuarios WHERE id<>? AND nome=? COLLATE NOCASE",
            (user_id, name),
        ).fetchone():
            raise ValueError("JÁ EXISTE UM USUÁRIO COM ESSE NOME.")
        if actor_id == user_id and not active:
            raise ValueError("VOCÊ NÃO PODE DESATIVAR O PRÓPRIO USUÁRIO.")
        password_hash, salt = current["senha_hash"], current["senha_salt"]
        must_change = int(current["trocar_senha"])
        password = str(data.get("senha") or "")
        if password:
            _ensure_unique_password(connection, password, user_id)
            password_hash, salt = _new_password(password)
            must_change = 1
        if active and not password_hash:
            raise ValueError("DEFINA UM PIN NUMÉRICO ANTES DE ATIVAR O USUÁRIO.")
        custom = data.get("permissoes") if isinstance(data.get("permissoes"), dict) else json.loads(current["permissoes_json"] or "{}")
        projected_permissions = _permissions(profile, custom)
        remaining_admins = 0
        for candidate in connection.execute("SELECT * FROM usuarios WHERE id<>?", (user_id,)).fetchall():
            public = _public_user(candidate)
            if public["ativo"] and has_permission(public, "SYSTEM_ADMIN") and has_permission(public, "USERS_MANAGE"):
                remaining_admins += 1
        if active and projected_permissions.get("SYSTEM_ADMIN") and projected_permissions.get("USERS_MANAGE"):
            remaining_admins += 1
        if remaining_admins < 1:
            raise ValueError("O SISTEMA PRECISA MANTER PELO MENOS UM ADMINISTRADOR ATIVO COM GESTÃO DE USUÁRIOS.")
        connection.execute(
            """UPDATE usuarios SET nome=?,perfil=?,senha_hash=?,senha_salt=?,
                   permissoes_json=?,ativo=?,trocar_senha=?,auth_version=auth_version+1,updated_at=? WHERE id=?""",
            (name, profile, password_hash, salt, json.dumps(custom, ensure_ascii=False), int(active), must_change, _now(), user_id),
        )
        row = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    public = _public_user(row)
    _revoke_user_sessions(user_id)
    return public


def is_master_admin(user: dict | None) -> bool:
    return bool(user) and str(user.get("nome") or "").upper() == MASTER_ADMIN_NAME and str(user.get("perfil") or "").upper() == "ADMIN" and bool(user.get("ativo"))


def reset_pin(user_id: str, new_pin: str, actor: dict) -> dict:
    if not is_master_admin(actor):
        raise PermissionError("SOMENTE O ADMINISTRADOR PRINCIPAL PODE RESETAR PINS.")
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("USUÁRIO NÃO ENCONTRADO.")
        _ensure_unique_password(connection, new_pin, user_id)
        password_hash, salt = _new_password(new_pin)
        connection.execute(
            "UPDATE usuarios SET senha_hash=?,senha_salt=?,ativo=1,trocar_senha=?,auth_version=auth_version+1,updated_at=? WHERE id=?",
            (password_hash, salt, 0 if str(row["nome"] or "").upper() == MASTER_ADMIN_NAME else 1, _now(), user_id),
        )
        updated = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    _revoke_user_sessions(user_id)
    return _public_user(updated)


def revoke_pin(user_id: str, actor: dict) -> dict:
    if not is_master_admin(actor):
        raise PermissionError("SOMENTE O ADMINISTRADOR PRINCIPAL PODE REVOGAR PINS.")
    with connect() as connection:
        row = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise ValueError("USUÁRIO NÃO ENCONTRADO.")
        if str(row["nome"] or "").upper() == MASTER_ADMIN_NAME:
            raise ValueError("O PIN DO ADMINISTRADOR PRINCIPAL NÃO PODE SER REVOGADO.")
        connection.execute(
            "UPDATE usuarios SET senha_hash='',senha_salt='',ativo=0,trocar_senha=1,auth_version=auth_version+1,updated_at=? WHERE id=?",
            (_now(), user_id),
        )
        updated = connection.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    _revoke_user_sessions(user_id)
    return _public_user(updated)


def has_permission(user: dict, permission: str) -> bool:
    return bool((user.get("permissoes") or {}).get(permission))
