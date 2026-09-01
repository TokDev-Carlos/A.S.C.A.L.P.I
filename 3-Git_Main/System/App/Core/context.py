from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestIdentity:
    user_id: str = "SISTEMA"
    user_name: str = "SISTEMA"
    station_id: str = ""
    role: str = "SYSTEM"


_identity: ContextVar[RequestIdentity] = ContextVar("cjl_identity", default=RequestIdentity())


def current_identity() -> RequestIdentity:
    return _identity.get()


def set_identity(identity: RequestIdentity):
    return _identity.set(identity)


def reset_identity(token) -> None:
    _identity.reset(token)

