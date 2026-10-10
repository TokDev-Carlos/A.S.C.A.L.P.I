"""G2 — paginação pela altura real das linhas (funções puras sobre o XML da aba já preenchida).

Regra (PLANO_POS_BASELINE, G2): os equipamentos entram na página **em ordem** enquanto o próximo couber **inteiro**;
se não couber, a quebra manual vai **antes** dele. Nada é redimensionado, reordenado ou dividido. A área útil sai do
papel, das margens e da escala de "ajustar à largura" (fitToWidth=1) que o Excel aplica — a mesma para XLSX e PDF.
"""
from __future__ import annotations

import math
import re

# papel (pontos, retrato) por código paperSize do OOXML; sem código, A4 (padrão das impressoras no Brasil)
PAPEIS = {1: (612.0, 792.0), 5: (612.0, 1008.0), 8: (841.89, 1190.55), 9: (595.28, 841.89), 11: (419.53, 595.28)}
LARGURA_DIGITO_PX = 7          # fonte padrão do Excel (Calibri 11 / Arial 10): largura do dígito em pixels
FOLGA_PT = 4.0                 # margem de segurança entre o cálculo OOXML e a impressão real (arredondamento de pixel)
EMU_POR_PT = 12700


def _num(texto: str | None, padrao: float) -> float:
    try:
        return float(texto) if texto not in (None, "") else padrao
    except ValueError:
        return padrao


def _col_num(letras: str) -> int:
    n = 0
    for ch in letras.upper():
        n = n * 26 + ord(ch) - 64
    return n


def largura_coluna_pt(largura: float) -> float:
    """Largura OOXML (caracteres, já com o preenchimento) → pontos, como o Excel converte para pixels."""
    px = math.trunc(((256 * largura + math.trunc(128 / LARGURA_DIGITO_PX)) / 256) * LARGURA_DIGITO_PX)
    return px * 0.75


def larguras_colunas(xml: str) -> tuple[dict[int, float], float]:
    """{coluna: largura em pt} das colunas declaradas e a largura padrão das demais."""
    fmt = re.search(r"<sheetFormatPr\b([^>]*)/?>", xml)
    attrs = fmt.group(1) if fmt else ""
    padrao_attr = re.search(r'\bdefaultColWidth="([^"]+)"', attrs)
    if padrao_attr:
        padrao = largura_coluna_pt(_num(padrao_attr.group(1), 8.43))
    else:
        base = _num((re.search(r'\bbaseColWidth="([^"]+)"', attrs) or [None, "8"])[1], 8)
        padrao = math.ceil((base * LARGURA_DIGITO_PX + 5) / 8) * 8 * 0.75   # Excel arredonda a múltiplos de 8 px
    cols: dict[int, float] = {}
    for m in re.finditer(r"<col\b([^>]*)/?>", xml):
        a = m.group(1)
        ini, fim = int(_num((re.search(r'\bmin="(\d+)"', a) or [None, "0"])[1], 0)), int(_num((re.search(r'\bmax="(\d+)"', a) or [None, "0"])[1], 0))
        oculta = re.search(r'\bhidden="(1|true)"', a)
        w = 0.0 if oculta else largura_coluna_pt(_num((re.search(r'\bwidth="([^"]+)"', a) or [None, None])[1], 8.43))
        for c in range(ini, fim + 1):
            cols[c] = w
    return cols, padrao


def alturas_linhas(xml: str) -> tuple[dict[int, float], set[int], float]:
    """Altura explícita (pt) por linha, linhas ocultas e a altura padrão da aba."""
    fmt = re.search(r'<sheetFormatPr\b[^>]*\bdefaultRowHeight="([^"]+)"', xml)
    padrao = _num(fmt.group(1) if fmt else None, 15.0)
    alturas: dict[int, float] = {}
    ocultas: set[int] = set()
    for m in re.finditer(r"<row\b([^>]*?)/?>", xml):
        a = m.group(1)
        r = re.search(r'\br="(\d+)"', a)
        if not r:
            continue
        n = int(r.group(1))
        ht = re.search(r'\bht="([^"]+)"', a)
        if ht:
            alturas[n] = _num(ht.group(1), padrao)
        if re.search(r'\bhidden="(1|true)"', a):
            ocultas.add(n)
    return alturas, ocultas, padrao


def capacidade_pt(xml: str, col_ini: str, col_fim: str) -> tuple[float, float]:
    """(altura útil por página em pontos **da planilha**, escala aplicada) para retrato com fitToWidth=1."""
    ps = re.search(r"<pageSetup\b([^>]*)/?>", xml)
    papel = int(_num((re.search(r'\bpaperSize="(\d+)"', ps.group(1)) or [None, "9"])[1], 9)) if ps else 9
    largura_papel, altura_papel = PAPEIS.get(papel, PAPEIS[9])
    pm = re.search(r"<pageMargins\b([^>]*)/?>", xml)
    marg = {k: _num((re.search(rf'\b{k}="([^"]+)"', pm.group(1)) or [None, None])[1], 0.0) * 72 if pm else 0.0
            for k in ("left", "right", "top", "bottom")}
    cols, padrao = larguras_colunas(xml)
    largura_area = sum(cols.get(c, padrao) for c in range(_col_num(col_ini), _col_num(col_fim) + 1))
    util_largura = largura_papel - marg["left"] - marg["right"]
    escala = 1.0 if largura_area <= util_largura else max(0.10, math.floor(util_largura / largura_area * 100) / 100)
    return (altura_papel - marg["top"] - marg["bottom"]) / escala, escala


def excesso_imagens(desenho_xml: str | None, altura_de, linha_fim) -> dict[int, float]:
    """Quanto (pt) a foto ancorada numa linha passa do fim dessa linha; a quebra não pode cortá-la."""
    if not desenho_xml:
        return {}
    saida: dict[int, float] = {}
    for anc in re.finditer(r"<(?:\w+:)?(oneCellAnchor|twoCellAnchor)\b(.*?)</(?:\w+:)?\1>", desenho_xml, re.S):
        corpo = anc.group(2)
        de = re.search(r"<(?:\w+:)?from>.*?<(?:\w+:)?row>(\d+)</(?:\w+:)?row>.*?<(?:\w+:)?rowOff>(-?\d+)</", corpo, re.S)
        if not de:
            continue
        linha, off = int(de.group(1)) + 1, int(de.group(2)) / EMU_POR_PT
        if anc.group(1) == "oneCellAnchor":
            ext = re.search(r'<(?:\w+:)?ext\b[^>]*\bcy="(\d+)"', corpo)
            if not ext:
                continue
            fundo = off + int(ext.group(1)) / EMU_POR_PT
        else:
            ate = re.search(r"<(?:\w+:)?to>.*?<(?:\w+:)?row>(\d+)</(?:\w+:)?row>.*?<(?:\w+:)?rowOff>(-?\d+)</", corpo, re.S)
            if not ate:
                continue
            fundo = sum(altura_de(r) for r in range(linha, int(ate.group(1)) + 1)) + int(ate.group(2)) / EMU_POR_PT
        sobra = fundo - altura_de(linha)
        if sobra > 0 and linha <= linha_fim:
            saida[linha] = max(saida.get(linha, 0.0), sobra)
    return saida


def quebras_por_altura(xml: str, itens: list[int], primeira_linha: int, desenho_xml: str | None = None,
                       titulos: tuple[int, int] | None = None, col_ini: str = "B", col_fim: str = "V") -> list[int]:
    """Linhas antes das quais vai a quebra manual. `itens` são as linhas visíveis dos equipamentos, em ordem."""
    alturas, ocultas, padrao = alturas_linhas(xml)

    def altura_de(r: int) -> float:
        return 0.0 if r in ocultas else alturas.get(r, padrao)
    cap, _ = capacidade_pt(xml, col_ini, col_fim)
    cap -= FOLGA_PT
    excesso = excesso_imagens(desenho_xml, altura_de, max(itens) if itens else 0)
    repetidas = sum(altura_de(r) for r in range(titulos[0], titulos[1] + 1)) if titulos else 0.0
    # página 1: o que vem antes do primeiro equipamento (cabeçalho do modelo e linhas ocultas = 0)
    usado = sum(altura_de(r) for r in range(primeira_linha, itens[0])) if itens else 0.0
    if titulos and titulos[0] < primeira_linha:
        usado += repetidas                     # títulos acima da área de impressão também saem na página 1
    quebras: list[int] = []
    na_pagina = 0
    anterior = None
    for r in itens:
        entre = sum(altura_de(x) for x in range(anterior + 1, r)) if anterior is not None else 0.0
        precisa = entre + altura_de(r) + excesso.get(r, 0.0)
        if na_pagina and usado + precisa > cap:
            quebras.append(r)
            usado, na_pagina, entre = repetidas, 0, 0.0
        usado += entre + altura_de(r)
        na_pagina += 1
        anterior = r
    return quebras


def paginas_previstas(xml_aba: str) -> int:
    """Páginas que o documento terá pelas quebras manuais gravadas na aba."""
    return len(re.findall(r"<brk\b", xml_aba)) + 1


def paginas_pdf(conteudo: bytes) -> int:
    """Conta as páginas de um PDF (objetos /Type /Page, sem /Pages)."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", conteudo))
