"""Regras de negócio das Ordens de Produção (paridade com o VBA MOD_GERAR_OP V2.4.22)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Mapping, Sequence

# ---------------------------------------------------------------- texto

_MAPA_MIN = {}
for faixa, letra in (((192, 198), "a"), ((224, 230), "a"), ((199, 199), "c"), ((231, 231), "c"),
                     ((200, 203), "e"), ((232, 235), "e"), ((204, 207), "i"), ((236, 239), "i"),
                     ((209, 209), "n"), ((241, 241), "n"), ((210, 214), "o"), ((216, 216), "o"),
                     ((242, 246), "o"), ((248, 248), "o"), ((217, 220), "u"), ((249, 252), "u"),
                     ((221, 221), "y"), ((253, 253), "y"), ((255, 255), "y")):
    for cp in range(faixa[0], faixa[1] + 1):
        _MAPA_MIN[cp] = letra

_MAPA_ASCII = {}
for faixa, letra in (((192, 198), "A"), ((199, 199), "C"), ((200, 203), "E"), ((204, 207), "I"),
                     ((209, 209), "N"), ((210, 214), "O"), ((216, 216), "O"), ((217, 220), "U"),
                     ((221, 221), "Y"), ((224, 230), "a"), ((231, 231), "c"), ((232, 235), "e"),
                     ((236, 239), "i"), ((241, 241), "n"), ((242, 246), "o"), ((248, 248), "o"),
                     ((249, 252), "u"), ((253, 253), "y"), ((255, 255), "y")):
    for cp in range(faixa[0], faixa[1] + 1):
        _MAPA_ASCII[cp] = letra
_PERMITIDOS = set(range(48, 58)) | set(range(65, 91)) | set(range(97, 123)) | {32, 40, 41, 45, 46, 95}


def _colapsar(texto: str) -> str:
    while "  " in texto:
        texto = texto.replace("  ", " ")
    return texto.strip()


def normalizar_nome(texto: object) -> str:
    """Minúsculas, sem acentos, espaços colapsados (VBA NormalizarNome)."""
    texto = str(texto or "").strip().lower()
    return _colapsar("".join(_MAPA_MIN.get(ord(c), c) for c in texto))


def normalizar_chave(texto: object) -> str:
    t = normalizar_nome(texto).upper()
    for ch in (" ", ".", "-", "_"):
        t = t.replace(ch, "")
    return t


def sanitizar_nome(texto: object) -> str:
    """Nome seguro para arquivo (VBA SanitizeNome)."""
    texto = str(texto or "").strip()
    for ch in '\\/:*?"<>|[]':
        texto = texto.replace(ch, " ")
    saida = []
    for c in texto:
        cp = ord(c)
        if cp in _PERMITIDOS:
            saida.append(c)
        else:
            saida.append(_MAPA_ASCII.get(cp, " "))
    texto = _colapsar("".join(saida))
    texto = texto.strip(". ")
    return texto or "SEM_NOME"


def montar_nome_base(seq: str, cliente: str, obra: str, tipo: str, material: str) -> str:
    partes = [str(p).strip() for p in (seq, cliente, obra, tipo, material) if str(p or "").strip()]
    return sanitizar_nome(" - ".join(partes))[:180]


def tipo_arquivo(tipo_b8: object) -> str:
    t = str(tipo_b8 or "").strip().upper()
    if "ABRIGO" in t:
        return "ABRIGO"
    if "PLACA" in t:
        return "PLACA"
    return "MOB"


def detectar_material(nomes_itens: Sequence[str], tipo_b8: object) -> str:
    if "INOX" in normalizar_nome(tipo_b8).upper():
        return "CARBONO+INOX"
    inox = carbono = False
    for nome in nomes_itens:
        if not str(nome or "").strip():
            continue
        if "INOX" in normalizar_nome(nome).upper():
            inox = True
        else:
            carbono = True
    if inox and carbono:
        return "CARBONO+INOX"
    if inox:
        return "INOX"
    return "CARBONO"


def formatar_quantidade(qtd: float) -> str:
    qtd = float(qtd)
    if qtd == int(qtd):
        return str(int(qtd))
    return repr(qtd).replace(".", ",")


# ---------------------------------------------------------------- prazo ("Definir")

def interpretar_prazo(valor: object) -> date | str:
    """Aceita data (aaaa-mm-dd ou dd/mm/aaaa) ou texto livre como 'DEFINIR'."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("INFORME O PRAZO (DATA OU TEXTO COMO 'DEFINIR').")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            pass
    return texto.upper()


def prazo_texto(prazo: date | str) -> str:
    return prazo.strftime("%d/%m/%Y") if isinstance(prazo, date) else str(prazo)


# ---------------------------------------------------------------- numeração

def formatar_numero(numero: int, ano: int) -> str:
    return f"{int(numero):03d}-{int(ano) % 100:02d}"


def token_para_numero(token: str, ano: int) -> int:
    token = str(token or "").strip()
    if not token:
        return 0
    if "-" in token:
        numero, resto = token.split("-", 1)
        digitos_ano = re.sub(r"\D", "", resto)[-2:]
        if digitos_ano != f"{ano % 100:02d}":
            return 0
    else:
        numero = token
    digitos = re.sub(r"\D", "", numero)
    return int(digitos) if digitos else 0


def proximo_numero(existentes: Iterable[str], ano: int) -> int:
    return max((token_para_numero(t, ano) for t in existentes), default=0) + 1


# ---------------------------------------------------------------- códigos e saldo

def normalizar_codigo(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        texto = str(int(valor)) if valor.is_integer() else format(valor, "f").rstrip("0")
    else:
        texto = str(valor)
    return texto.strip().replace(",", ".").replace(" ", "")


def codigo_valido(codigo: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)*", normalizar_codigo(codigo)))


def codigo_base(codigo: str) -> str:
    codigo = normalizar_codigo(codigo)
    if codigo.startswith("0."):
        return codigo
    return codigo.split(".", 1)[0]


def ignora_checagem(base: str) -> bool:
    return normalizar_codigo(base).startswith("0.")


def normalizar_cabecalho(texto: object) -> str:
    t = normalizar_nome(texto).upper().replace(".", "").replace("_", " ").replace("-", " ")
    return _colapsar(re.sub(r"\s+", " ", t))


def numero_br(valor: object) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return float(s)


@dataclass
class SaldoItem:
    codigo: str
    equipamento: str
    montante: float
    consumido: float

    def saldo(self) -> float | str:
        if self.montante <= 0:
            return 0
        resto = self.montante - self.consumido
        return "ACABOU" if resto == 0 else resto


@dataclass
class AvisoSaldo:
    codigo: str
    equipamento: str
    antes: float | str
    quantidade: float
    depois: float | str


SALDO_OK = "SALDO_OK"
SALDO_ENCERRADO = "SALDO_ENCERRADO"
SALDO_NEGATIVO = "SALDO_NEGATIVO"
SALDO_NEGATIVO_CONFIRMADO = "SALDO_NEGATIVO_CONFIRMADO"
SEM_CONTRATO = "SEM_CONTRATO"


@dataclass
class Simulacao:
    status: str
    negativos: list[AvisoSaldo] = field(default_factory=list)
    encerrados: list[AvisoSaldo] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    quantidades: dict[str, float] = field(default_factory=dict)

    @property
    def exige_confirmacao(self) -> bool:
        return bool(self.negativos)


def agregar_por_base(linhas: Sequence[tuple[object, object]]) -> tuple[dict[str, float], list[str]]:
    """linhas = [(codigo, quantidade)] -> quantidades por código-base."""
    total: dict[str, float] = {}
    problemas: list[str] = []
    for codigo, qtd in linhas:
        q = numero_br(qtd)
        if q is None or q <= 0:
            continue
        cod = normalizar_codigo(codigo)
        if not codigo_valido(cod):
            problemas.append(f"CÓDIGO INVÁLIDO OU VAZIO: '{cod}'.")
            continue
        base = codigo_base(cod)
        total[base] = total.get(base, 0.0) + q
    return total, problemas


def simular_saldo(itens: Mapping[str, SaldoItem], quantidades: Mapping[str, float]) -> Simulacao:
    sim = Simulacao(SALDO_OK, quantidades=dict(quantidades))
    for base, qtd in quantidades.items():
        if ignora_checagem(base):           # 0.x = extra: entra na O.P. e na contagem, sem saldo nem contrato
            continue
        if base not in itens:
            sim.erros.append(f"ITEM {base} NÃO EXISTE NO CONTRATO.")
            continue
        item = itens[base]
        antes = item.saldo()
        if isinstance(antes, (int, float)):
            depois = antes - qtd
            if depois < 0:
                sim.negativos.append(AvisoSaldo(base, item.equipamento, antes, qtd, depois))
            elif depois == 0:
                sim.encerrados.append(AvisoSaldo(base, item.equipamento, antes, qtd, 0))
        elif antes == "ACABOU" and qtd > 0:
            sim.negativos.append(AvisoSaldo(base, item.equipamento, antes, qtd,
                                            f"-{formatar_quantidade(qtd)} *saldo anterior ja estava encerrado*"))
    if sim.erros:
        sim.status = "ESTRUTURA_INVALIDA"
    elif sim.negativos:
        sim.status = SALDO_NEGATIVO
    elif sim.encerrados:
        sim.status = SALDO_ENCERRADO
    return sim
