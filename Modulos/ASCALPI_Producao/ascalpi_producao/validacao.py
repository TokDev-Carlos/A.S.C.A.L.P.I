"""Validação pura de entradas do ASCALPI Produção (sem banco, HTTP ou dependências externas).

O serviço e o servidor devem aplicar estas funções *antes* de iniciar mutações.
Mensagens de erro são destinadas à interface e seguem o padrão em maiúsculas.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class ErroValidacao(ValueError):
    """Erro de entrada do operador (a API deve responder com HTTP 400)."""


def corpo_objeto(corpo) -> dict:
    if not isinstance(corpo, dict):
        raise ErroValidacao("O CORPO JSON DEVE SER UM OBJETO.")
    return corpo


def booleano(valor, campo: str, padrao: bool = False) -> bool:
    if valor is None:
        return padrao
    if type(valor) is not bool:
        raise ErroValidacao(f"{campo.upper()}: INFORME VERDADEIRO OU FALSO.")
    return valor


def inteiro_positivo(valor, campo: str) -> int:
    valido = False
    if type(valor) is int:
        numero = valor
        valido = True
    elif type(valor) is float and math.isfinite(valor) and valor.is_integer():
        numero = int(valor)
        valido = True
    elif isinstance(valor, str) and re.fullmatch(r"[0-9]+", valor.strip()):
        numero = int(valor.strip())
        valido = True
    if not valido or numero <= 0:
        raise ErroValidacao(f"{campo.upper()}: INFORME UM INTEIRO POSITIVO.")
    return numero


def numero_finito(valor, campo: str, negativo: bool = False) -> float:
    if valor is None or isinstance(valor, bool) or not isinstance(valor, (str, int, float, Decimal)):
        raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
    if isinstance(valor, str):
        s = valor.strip().replace(" ", "")
        if not s:
            raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
        # Formato brasileiro com separador de milhar e vírgula decimal.
        if "," in s and "." in s:
            if not re.fullmatch(r"-?[0-9]{1,3}(\.[0-9]{3})+,[0-9]+", s):
                raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            if not re.fullmatch(r"-?[0-9]+(,[0-9]+)?", s):
                raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
            s = s.replace(",", ".")
        elif not re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", s):
            raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
    else:
        s = str(valor)
    try:
        d = Decimal(s)
        n = float(d)
    except (InvalidOperation, OverflowError, ValueError):
        raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.") from None
    if not d.is_finite() or not math.isfinite(n) or (n < 0 and not negativo):
        raise ErroValidacao(f"{campo.upper()}: NÚMERO INVÁLIDO.")
    return n


def motivo_obrigatorio(valor, campo: str = "MOTIVO") -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroValidacao(f"INFORME O {campo.upper()}.")
    texto = valor.strip()
    if len(texto) > 200:
        raise ErroValidacao(f"{campo.upper()}: MÁXIMO DE 200 CARACTERES.")
    return texto


def data_iso(valor, campo: str) -> str | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if not isinstance(valor, str):
        raise ErroValidacao(f"{campo.upper()}: DATA INVÁLIDA.")
    texto = valor.strip()
    if not texto:
        return None
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", texto):
            return date.fromisoformat(texto).isoformat()
        if re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", texto):
            return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
    except ValueError:
        pass
    raise ErroValidacao(f"{campo.upper()}: DATA INVÁLIDA.")


def data_legada(valor) -> date | None:
    try:
        normal = data_iso(valor, "DATA")
        return date.fromisoformat(normal) if normal else None
    except (ErroValidacao, ValueError, TypeError):
        return None


def _texto(valor, campo: str, limite: int) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ErroValidacao(f"{campo.upper()}: TEXTO INVÁLIDO.")
    texto = valor.strip()
    if len(texto) > limite:
        raise ErroValidacao(f"{campo.upper()}: MÁXIMO DE {limite} CARACTERES.")
    return texto


def valor_acompanhamento(campo: str, valor) -> str:
    permitidos = {
        "status_instalacao": {"", "OK", "CANCELADO", "CANCELADA", "DUPLICADO"},
        "material_obra": {"", "OK", "CANCELADO", "DUPLICADO"},
        "fotografico": {"", "OK"},
    }
    if campo == "obs":
        return _texto(valor, "OBS", 2000)
    if campo == "entrega_atualizada":
        texto = _texto(valor, campo, 40).upper()
        if texto in {"", "OK", "FALTA"}:
            return texto
        return data_iso(texto, campo) or ""
    if campo not in permitidos:
        raise ErroValidacao(f"CAMPO DE ACOMPANHAMENTO INVÁLIDO: {campo}.")
    texto = _texto(valor, campo, 40).upper()
    if texto not in permitidos[campo]:
        raise ErroValidacao(f"{campo.upper()}: VALOR INVÁLIDO.")
    return texto


def itens_op(itens) -> list[dict]:
    if not isinstance(itens, list):
        raise ErroValidacao("ITENS DA O.P.: INFORME UMA LISTA.")
    vistos: set[int] = set()
    resultado: list[dict] = []
    for indice, item in enumerate(itens, 1):
        if not isinstance(item, dict):
            raise ErroValidacao(f"ITEM {indice}: INFORME UM OBJETO.")
        linha = inteiro_positivo(item.get("linha"), f"LINHA DO ITEM {indice}")
        if linha in vistos:
            raise ErroValidacao(f"LINHA {linha} REPETIDA NA O.P.")
        vistos.add(linha)
        bruto = item.get("quantidade")
        if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
            continue
        quantidade = numero_finito(bruto, f"QUANTIDADE DA LINHA {linha}")
        if quantidade == 0:
            continue
        resultado.append({
            "linha": linha,
            "quantidade": quantidade,
            "inauguracao": _texto(item.get("inauguracao"), "INAUGURAÇÃO", 40),
            "observacao": _texto(item.get("observacao"), "OBSERVAÇÃO", 200),
        })
    return resultado
