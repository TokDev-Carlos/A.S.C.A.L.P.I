from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def boolean(value, *, field: str = "VALOR LÓGICO", default: bool | None = None) -> bool:
    if value is None:
        if default is None:
            raise ValueError(f"INFORME {field}.")
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "sim", "on"}:
            return True
        if normalized in {"0", "false", "não", "nao", "off"}:
            return False
    raise ValueError(f"{field} DEVE SER VERDADEIRO OU FALSO.")


def finite_number(
    value,
    *,
    field: str = "VALOR",
    minimum: float | None = None,
    maximum: float | None = None,
    default: float | None = None,
) -> float:
    if value in (None, ""):
        if default is None:
            raise ValueError(f"INFORME {field}.")
        result = float(default)
    else:
        try:
            result = float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} INVÁLIDO.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} DEVE SER UM NÚMERO FINITO.")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field} NÃO PODE SER MENOR QUE {minimum}.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{field} NÃO PODE SER MAIOR QUE {maximum}.")
    return result


def finite_integer(
    value,
    *,
    field: str = "VALOR",
    minimum: int | None = None,
    maximum: int | None = None,
    default: int | None = None,
) -> int:
    number = finite_number(
        value,
        field=field,
        minimum=float(minimum) if minimum is not None else None,
        maximum=float(maximum) if maximum is not None else None,
        default=float(default) if default is not None else None,
    )
    if not number.is_integer():
        raise ValueError(f"{field} DEVE SER UM NÚMERO INTEIRO.")
    return int(number)


def money(
    value,
    *,
    field: str = "VALOR",
    minimum: Decimal = Decimal("0"),
    maximum: Decimal = Decimal("1000000000000"),
) -> float:
    try:
        parsed = Decimal(str(value if value not in (None, "") else "0").strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} INVÁLIDO.") from exc
    if not parsed.is_finite() or parsed < minimum or parsed > maximum:
        raise ValueError(
            f"{field} DEVE SER FINITO E FICAR ENTRE {minimum} E {maximum}."
        )
    result = float(parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if not math.isfinite(result):
        raise ValueError(f"{field} NÃO PODE SER REPRESENTADO COM SEGURANÇA.")
    return result


def coordinates(latitude, longitude, *, optional: bool = True) -> tuple[float | None, float | None]:
    if latitude in (None, "") and longitude in (None, "") and optional:
        return None, None
    if latitude in (None, "") or longitude in (None, ""):
        raise ValueError("LATITUDE E LONGITUDE DEVEM SER INFORMADAS EM CONJUNTO.")
    return (
        round(finite_number(latitude, field="LATITUDE", minimum=-90, maximum=90), 8),
        round(finite_number(longitude, field="LONGITUDE", minimum=-180, maximum=180), 8),
    )
