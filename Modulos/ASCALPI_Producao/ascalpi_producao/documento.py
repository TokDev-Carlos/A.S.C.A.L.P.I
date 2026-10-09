"""Gera o .xlsx da O.P. a partir do modelo extraído (mesma aparência do VBA MOD_GERAR_OP V2.4.22).

Tudo é feito direto no XML do pacote, sem Excel:
- cabeçalho (P2 número, U2 revisão, D3 obra, V2 prazo, V8 solicitante, B8 tipo, B2 "Hoje ...", S6 dia do prazo);
- linhas 10..100: D quantidade, E quantidade inauguração, S observação;
- linhas sem quantidade agrupadas e ocultas (nível 1), borda inferior fina B:V na última linha visível;
- impressão: retrato, 1 página de largura, área B2:V<última>, quebras 13 + páginas equilibradas de até 15, margens;
- arquivo 100% bloqueado: nenhuma célula editável, planilha e estrutura protegidas por senha.
"""
from __future__ import annotations

import base64
import hashlib
import io
import math
import os
import re
import struct
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime

from . import pacote
from .regras import prazo_texto

LINHA_INICIO = 10
LINHA_FIM = 100
MAX_PG1 = 13
MAX_PG_DEMAIS = 15
CM_POL = 1 / 2.54
MARGENS = dict(left=0.1 * CM_POL, right=0.1 * CM_POL, top=1.2 * CM_POL, bottom=0.0, header=0.0, footer=0.0)
LIMPAR = ["D10:E100", "S10:S100", "V2", "V8", "D3:R4"]

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
_ESPACO_S6 = " " * 48


@dataclass
class LinhaOP:
    quantidade: float | None = None
    inauguracao: object = None
    observacao: str = ""


@dataclass
class DadosOP:
    numero: str
    obra: str
    prazo: date | str
    solicitante: str
    linhas: dict[int, LinhaOP]
    rev: int = 0
    tipo: str | None = None          # B8; None = mantém o do modelo
    cliente: str | None = None       # B3; None = mantém o do modelo
    emitido_em: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------- textos calculados (antes eram fórmulas)

def texto_hoje(momento: datetime) -> str:
    return f"Hoje {momento:%d/%m/%Y} {momento.hour}:{momento:%M}-{DIAS[momento.weekday()]}"


def _proper(texto: str) -> str:
    """PROPER do Excel: maiúscula após qualquer caractere que não seja letra."""
    saida, anterior_letra = [], False
    for c in texto:
        saida.append(c.lower() if anterior_letra else c.upper())
        anterior_letra = c.isalpha()
    return "".join(saida)


def texto_dia_prazo(prazo: date | str) -> str:
    if isinstance(prazo, date):
        bruto = f"{DIAS[prazo.weekday()]}{_ESPACO_S6}{prazo:%d} {MESES[prazo.month - 1]} {prazo.year}"
    else:
        bruto = str(prazo)
    return _proper(bruto)


def serial_excel(d: date) -> int:
    return (d - date(1899, 12, 30)).days


# ---------------------------------------------------------------- endereços

def col_num(letras: str) -> int:
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n


def col_letras(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def separar_ref(ref: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def expandir(faixa: str) -> list[str]:
    if ":" not in faixa:
        return [faixa]
    a, b = faixa.split(":")
    ca, ra = separar_ref(a)
    cb, rb = separar_ref(b)
    return [f"{col_letras(c)}{r}" for r in range(ra, rb + 1) for c in range(col_num(ca), col_num(cb) + 1)]


def _esc(t: object) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- planilha (XML)

_CELULA = re.compile(r'<c r="([A-Z]+)(\d+)"[^>]*?/>|<c r="([A-Z]+)(\d+)"[^>]*>.*?</c>', re.S)


class Planilha:
    def __init__(self, xml: str):
        self.xml = xml

    # linhas
    def _linha(self, r: int) -> re.Match | None:
        return re.search(r'<row r="%d"[^>]*?(?:/>|>.*?</row>)' % r, self.xml, re.S)

    def _trocar_linha(self, m: re.Match, novo: str) -> None:
        self.xml = self.xml[:m.start()] + novo + self.xml[m.end():]

    def _garantir_linha(self, r: int) -> re.Match:
        m = self._linha(r)
        if m:
            if m.group(0).endswith("/>") and not m.group(0).endswith("</row>"):
                self._trocar_linha(m, m.group(0)[:-2] + "></row>")
                m = self._linha(r)
            return m
        pos = None
        for mm in re.finditer(r'<row r="(\d+)"', self.xml):
            if int(mm.group(1)) > r:
                pos = mm.start()
                break
        if pos is None:
            pos = self.xml.index("</sheetData>")
        self.xml = self.xml[:pos] + f'<row r="{r}"></row>' + self.xml[pos:]
        return self._linha(r)

    def atributo_linha(self, r: int, nome: str, valor: str | None) -> None:
        m = self._garantir_linha(r)
        bloco = m.group(0)
        abertura = bloco[:bloco.index(">") + 1]
        nova = re.sub(r'\s%s="[^"]*"' % nome, "", abertura)
        if valor is not None:
            nova = nova[:-1] + f' {nome}="{valor}">'
        self._trocar_linha(m, nova + bloco[len(abertura):])

    def linha_oculta(self, r: int) -> bool:
        m = self._linha(r)
        return bool(m and 'hidden="1"' in m.group(0)[:m.group(0).index(">")])

    # células
    def _celula(self, ref: str) -> tuple[re.Match, re.Match | None]:
        col, r = separar_ref(ref)
        linha = self._garantir_linha(r)
        for c in _CELULA.finditer(linha.group(0)):
            if (c.group(1) or c.group(3)) == col:
                return linha, c
        return linha, None

    def estilo(self, ref: str) -> str | None:
        _, c = self._celula(ref)
        if c is None:
            return None
        m = re.match(r'<c\b[^>]*\ss="(\d+)"', c.group(0))
        return m.group(1) if m else None

    def valor_texto(self, ref: str, compartilhadas: list[str]) -> str:
        _, c = self._celula(ref)
        if c is None:
            return ""
        x = c.group(0)
        if 't="s"' in x:
            v = re.search(r"<v>(\d+)</v>", x)
            return compartilhadas[int(v.group(1))] if v else ""
        t = re.search(r"<t[^>]*>(.*?)</t>", x, re.S)
        if t:
            return pacote._xml_unescape(t.group(1))
        v = re.search(r"<v>(.*?)</v>", x, re.S)
        return pacote._xml_unescape(v.group(1)) if v else ""

    def definir(self, ref: str, valor: object, estilo: str | None = "manter") -> None:
        linha, c = self._celula(ref)
        s = self.estilo(ref) if estilo == "manter" else estilo
        attr_s = f' s="{s}"' if s is not None else ""
        if valor is None or valor == "":
            nova = f'<c r="{ref}"{attr_s}/>'
        elif isinstance(valor, bool):
            nova = f'<c r="{ref}"{attr_s} t="b"><v>{int(valor)}</v></c>'
        elif isinstance(valor, (int, float)):
            v = int(valor) if float(valor).is_integer() else valor
            nova = f'<c r="{ref}"{attr_s}><v>{v}</v></c>'
        else:
            texto = str(valor)
            esp = ' xml:space="preserve"' if texto != texto.strip() or "  " in texto else ""
            nova = f'<c r="{ref}"{attr_s} t="inlineStr"><is><t{esp}>{_esc(texto)}</t></is></c>'
        bloco = linha.group(0)
        if c is not None:
            bloco = bloco[:c.start()] + nova + bloco[c.end():]
        else:
            col = col_num(separar_ref(ref)[0])
            pos = None
            for cc in _CELULA.finditer(bloco):
                if col_num(cc.group(1) or cc.group(3)) > col:
                    pos = cc.start()
                    break
            if pos is None:
                pos = bloco.rindex("</row>")
            bloco = bloco[:pos] + nova + bloco[pos:]
        self._trocar_linha(linha, bloco)

    def tem_conteudo(self, ref: str) -> bool:
        _, c = self._celula(ref)
        return bool(c and ("<v>" in c.group(0) or "<t" in c.group(0) or "<f" in c.group(0)))


# ---------------------------------------------------------------- estilos

class Estilos:
    def __init__(self, xml: str):
        self.xml = xml

    def _bloco(self, tag: str) -> re.Match:
        return re.search(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), self.xml, re.S)

    def _itens(self, tag: str, item: str) -> list[str]:
        return re.findall(r"<%s\b[^>]*/>|<%s\b[^>]*>.*?</%s>" % (item, item, item), self._bloco(tag).group(1), re.S)

    def _anexar(self, tag: str, item_xml: str) -> int:
        m = self._bloco(tag)
        n = len(self._itens(tag, tag[:-1] if tag != "cellXfs" else "xf"))
        abertura = self.xml[m.start():m.start(1)]
        abertura_nova = re.sub(r'count="\d+"', f'count="{n + 1}"', abertura)
        self.xml = self.xml[:m.start()] + abertura_nova + m.group(1) + item_xml + self.xml[m.end(1):]
        return n

    def com_borda_inferior_fina(self, s: str | None) -> str:
        xfs = self._itens("cellXfs", "xf")
        xf = xfs[int(s or 0)]
        bid = int(re.search(r'borderId="(\d+)"', xf).group(1)) if 'borderId="' in xf else 0
        borda = self._itens("borders", "border")[bid]
        nova_borda = re.sub(r"<bottom\b[^>]*/>|<bottom\b[^>]*>.*?</bottom>",
                            '<bottom style="thin"><color indexed="64"/></bottom>', borda, flags=re.S)
        if "<bottom" not in nova_borda:
            nova_borda = nova_borda.replace("<diagonal", '<bottom style="thin"><color indexed="64"/></bottom><diagonal', 1)
        novo_bid = self._anexar("borders", nova_borda)
        if 'borderId="' in xf:
            novo_xf = re.sub(r'borderId="\d+"', f'borderId="{novo_bid}"', xf, count=1)
        else:
            novo_xf = xf.replace("<xf ", f'<xf borderId="{novo_bid}" ', 1)
        if "applyBorder" not in novo_xf:
            novo_xf = novo_xf.replace("<xf ", '<xf applyBorder="1" ', 1)
        return str(self._anexar("cellXfs", novo_xf))

    def bloquear_tudo(self) -> None:
        self.xml = re.sub(r'\slocked="0"', "", self.xml)


# ---------------------------------------------------------------- senha (algoritmo SHA-512 do Office)

def hash_senha(senha: str, sal: bytes | None = None, giros: int = 100000) -> dict[str, str]:
    sal = sal or os.urandom(16)
    h = hashlib.sha512(sal + senha.encode("utf-16-le")).digest()
    for i in range(giros):
        h = hashlib.sha512(h + struct.pack("<I", i)).digest()
    return {"algorithmName": "SHA-512", "hashValue": base64.b64encode(h).decode(),
            "saltValue": base64.b64encode(sal).decode(), "spinCount": str(giros)}


# ---------------------------------------------------------------- paginação (OP_CalcularPlanoPaginas)

def plano_paginas(total: int) -> list[int]:
    if total <= 0:
        return [1]
    if total <= MAX_PG1:
        return [total]
    resto = total - MAX_PG1
    demais = math.ceil(resto / MAX_PG_DEMAIS)
    base, sobra = divmod(resto, demais)
    return [MAX_PG1] + [base + (1 if i < sobra else 0) for i in range(demais)]


# ---------------------------------------------------------------- geração

def _sheet_part(partes: dict[str, bytes]) -> tuple[str, str]:
    aba = pacote.abas(partes)[0]
    return aba["parte"], aba["nome"]


def _compartilhadas(partes: dict[str, bytes]) -> list[str]:
    if "xl/sharedStrings.xml" not in partes:
        return []
    xml = partes["xl/sharedStrings.xml"].decode("utf-8")
    saida = []
    for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
        saida.append(pacote._xml_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    return saida


def linhas_do_modelo(modelo: bytes) -> list[dict]:
    """Linhas 10..100 do modelo com equipamento: [{linha, codigo, equipamento}]."""
    partes = pacote.carregar(io.BytesIO(modelo))
    parte, _ = _sheet_part(partes)
    ws = Planilha(partes[parte].decode("utf-8"))
    ss = _compartilhadas(partes)
    saida = []
    for r in range(LINHA_INICIO, LINHA_FIM + 1):
        nome = ws.valor_texto(f"B{r}", ss).strip()
        if nome:
            saida.append({"linha": r, "codigo": ws.valor_texto(f"A{r}", ss).strip(), "equipamento": nome})
    return saida


def cabecalho_do_modelo(modelo: bytes) -> dict:
    partes = pacote.carregar(io.BytesIO(modelo))
    parte, nome = _sheet_part(partes)
    ws = Planilha(partes[parte].decode("utf-8"))
    ss = _compartilhadas(partes)
    return {"aba": nome, "cliente": ws.valor_texto("B3", ss).strip(), "tipo": ws.valor_texto("B8", ss).strip(),
            "titulo": ws.valor_texto("D2", ss).strip(), "empresa": ws.valor_texto("L2", ss).strip()}


def _inserir_antes(xml: str, novo: str, candidatos: list[str]) -> str:
    for tag in candidatos:
        i = xml.find(tag)
        if i >= 0:
            return xml[:i] + novo + xml[i:]
    raise ValueError("PONTO DE INSERÇÃO NÃO ENCONTRADO")


_DEPOIS_DE_PAGESETUP = ["<colBreaks", "<customProperties", "<cellWatches", "<ignoredErrors", "<smartTags",
                        "<drawing", "<legacyDrawing", "<legacyDrawingHF", "<picture", "<oleObjects", "<controls",
                        "<webPublishItems", "<tableParts", "<extLst", "</worksheet>"]


def gerar_xlsx(modelo: bytes, dados: DadosOP, senha: str) -> bytes:
    partes = pacote.carregar(io.BytesIO(modelo))
    parte, nome_aba = _sheet_part(partes)
    ws = Planilha(partes[parte].decode("utf-8"))
    st = Estilos(partes["xl/styles.xml"].decode("utf-8"))

    # 1) limpar entradas do modelo
    for faixa in LIMPAR:
        for ref in expandir(faixa):
            if ws.tem_conteudo(ref):
                ws.definir(ref, None)

    # 2) cabeçalho
    ws.definir("B2", texto_hoje(dados.emitido_em))
    ws.definir("P2", dados.numero)
    ws.definir("U2", int(dados.rev))
    ws.definir("D3", dados.obra)
    ws.definir("V2", serial_excel(dados.prazo) if isinstance(dados.prazo, date) else prazo_texto(dados.prazo))
    ws.definir("S6", texto_dia_prazo(dados.prazo))
    ws.definir("V8", dados.solicitante)
    if dados.tipo is not None:
        ws.definir("B8", dados.tipo)
    if dados.cliente is not None:
        ws.definir("B3", dados.cliente)

    # 3) itens
    visiveis = []
    for r in range(LINHA_INICIO, LINHA_FIM + 1):
        item = dados.linhas.get(r)
        qtd = item.quantidade if item else None
        if item and qtd:
            ws.definir(f"D{r}", float(qtd))
            ws.definir(f"E{r}", item.inauguracao if item.inauguracao not in (None, "") else None)
            ws.definir(f"S{r}", item.observacao or None)
            ws.atributo_linha(r, "hidden", None)
            ws.atributo_linha(r, "outlineLevel", None)
            visiveis.append(r)
        else:
            ws.atributo_linha(r, "hidden", "1")
            ws.atributo_linha(r, "outlineLevel", "1")
    if not visiveis:
        raise ValueError("A O.P. PRECISA DE PELO MENOS 1 EQUIPAMENTO COM QUANTIDADE.")
    # linha-resumo abaixo de cada grupo recolhido (Outline.SummaryRow = xlBelow)
    for r in range(LINHA_INICIO, LINHA_FIM + 1):
        if ws.linha_oculta(r) and not ws.linha_oculta(r + 1):
            ws.atributo_linha(r + 1, "collapsed", "1")
    ultima = max(visiveis)

    # 4) borda inferior fina B:V na última linha visível
    cache: dict[str | None, str] = {}
    for c in range(col_num("B"), col_num("V") + 1):
        ref = f"{col_letras(c)}{ultima}"
        s = ws.estilo(ref)
        if s not in cache:
            cache[s] = st.com_borda_inferior_fina(s)
        linha, cel = ws._celula(ref)
        if cel is None:
            ws.definir(ref, None, estilo=cache[s])
        else:
            x = cel.group(0)
            novo = re.sub(r'\ss="\d+"', f' s="{cache[s]}"', x, count=1) if ' s="' in x else x.replace("<c ", f'<c s="{cache[s]}" ', 1)
            bloco = linha.group(0)
            ws._trocar_linha(linha, bloco[:cel.start()] + novo + bloco[cel.end():])

    # 5) agrupamento, visão e impressão
    x = ws.xml
    x = re.sub(r"<sheetFormatPr\b([^>]*?)\s*/>",
               lambda m: "<sheetFormatPr" + re.sub(r'\soutlineLevelRow="\d+"', "", m.group(1)) + ' outlineLevelRow="1"/>', x, count=1)
    x = re.sub(r'(<pane\b[^>]*?)\stopLeftCell="[^"]*"', r'\1 topLeftCell="A10"', x)
    x = re.sub(r"<selection\b[^>]*/>", "", x)
    x = re.sub(r'\s*<pageSetUpPr\b[^>]*/>', "", x)
    x = re.sub(r'\s*<outlinePr\b[^>]*/>', "", x)
    sheetpr_extra = '<outlinePr summaryBelow="1" summaryRight="1"/><pageSetUpPr fitToPage="1"/>'
    if re.search(r"<sheetPr\b[^>]*/>", x):
        x = re.sub(r"<sheetPr\b([^>]*)/>", r"<sheetPr\1>" + sheetpr_extra + "</sheetPr>", x, count=1)
    elif "<sheetPr" in x:
        x = x.replace("</sheetPr>", sheetpr_extra + "</sheetPr>", 1)
    else:
        x = x.replace("<dimension", "<sheetPr>" + sheetpr_extra + "</sheetPr><dimension", 1)
    if "<pageMargins" not in x:
        x = _inserir_antes(x, "<pageMargins/>", ["<pageSetup", "<headerFooter", "<rowBreaks"] + _DEPOIS_DE_PAGESETUP)
    if "<pageSetup" not in x:
        i = x.index("<pageMargins")
        i = x.index("/>", i) + 2
        x = x[:i] + '<pageSetup paperSize="9"/>' + x[i:]
    x = re.sub(r"<printOptions\b[^>]*/>", '<printOptions horizontalCentered="1"/>', x)
    if "<printOptions" not in x:
        x = x.replace("<pageMargins", '<printOptions horizontalCentered="1"/><pageMargins', 1)
    margens = " ".join(f'{k}="{v!r}"' for k, v in MARGENS.items())
    x = re.sub(r"<pageMargins\b[^>]*/>", f"<pageMargins {margens}/>", x)
    def _ps(m: re.Match) -> str:
        attrs = m.group(1)
        for a in ("orientation", "fitToWidth", "fitToHeight", "scale"):
            attrs = re.sub(r'\s%s="[^"]*"' % a, "", attrs)
        return f'<pageSetup{attrs} fitToWidth="1" fitToHeight="0" orientation="portrait"/>'
    x = re.sub(r"<pageSetup\b([^>]*?)\s*/>", _ps, x, count=1)

    # quebras: 13 linhas na página 1, depois páginas equilibradas de até 15
    x = re.sub(r"<rowBreaks\b.*?</rowBreaks>|<rowBreaks\b[^>]*/>", "", x, flags=re.S)
    plano = plano_paginas(len(visiveis))
    quebras, acumulado = [], 0
    for n in plano[:-1]:
        acumulado += n
        quebras.append(visiveis[acumulado])          # linha real do ordinal acumulado+1
    if quebras:
        brks = "".join(f'<brk id="{r - 1}" max="16383" man="1"/>' for r in quebras)
        x = _inserir_antes(x, f'<rowBreaks count="{len(quebras)}" manualBreakCount="{len(quebras)}">{brks}</rowBreaks>',
                           _DEPOIS_DE_PAGESETUP)

    # 6) proteção total da planilha (somente visualizar)
    h = hash_senha(senha)
    prot = (f'<sheetProtection algorithmName="{h["algorithmName"]}" hashValue="{h["hashValue"]}" '
            f'saltValue="{h["saltValue"]}" spinCount="{h["spinCount"]}" sheet="1" objects="1" scenarios="1" '
            'formatCells="0" formatColumns="0" formatRows="0" insertColumns="0" insertRows="0" '
            'insertHyperlinks="0" deleteColumns="0" deleteRows="0" sort="0" autoFilter="0" pivotTables="0"/>')
    prot = prot.replace('formatCells="0" formatColumns="0" formatRows="0" insertColumns="0" insertRows="0" '
                        'insertHyperlinks="0" deleteColumns="0" deleteRows="0" sort="0" autoFilter="0" pivotTables="0"', "")
    x = re.sub(r"<sheetProtection\b[^>]*/>", "", x)
    x = _inserir_antes(x, prot.replace("  ", " ").replace(" />", "/>"),
                       ["<protectedRanges", "<scenarios", "<autoFilter", "<sortState", "<dataConsolidate",
                        "<customSheetViews", "<mergeCells", "<phoneticPr", "<conditionalFormatting",
                        "<dataValidations", "<hyperlinks", "<printOptions", "<pageMargins"])
    x = re.sub(r"<protectedRanges\b.*?</protectedRanges>", "", x, flags=re.S)
    ws.xml = x
    st.bloquear_tudo()

    # 7) livro: área de impressão e estrutura protegida
    wb = partes["xl/workbook.xml"].decode("utf-8")
    nome_ref = "'" + nome_aba.replace("'", "''") + "'"
    area = f'<definedName name="_xlnm.Print_Area" localSheetId="0">{_esc(nome_ref)}!$B$2:$V${ultima}</definedName>'
    wb = re.sub(r'<definedName name="_xlnm.Print_Area"[^>]*>.*?</definedName>', "", wb)
    wb = re.sub(r"<definedNames\s*/>", "", wb)
    if "<definedNames>" in wb:
        wb = wb.replace("<definedNames>", "<definedNames>" + area, 1)
    else:
        wb = wb.replace("</sheets>", "</sheets><definedNames>" + area + "</definedNames>", 1)
    wb = re.sub(r"<definedNames></definedNames>", "", wb)
    hw = hash_senha(senha)
    wb = re.sub(r"<workbookProtection\b[^>]*/>", "", wb)
    wb = wb.replace("<bookViews>", f'<workbookProtection workbookAlgorithmName="SHA-512" workbookHashValue="{hw["hashValue"]}" '
                                   f'workbookSaltValue="{hw["saltValue"]}" workbookSpinCount="{hw["spinCount"]}" '
                                   'lockStructure="1"/><bookViews>', 1)
    wb = re.sub(r'(<workbookView\b[^>]*?)\sactiveTab="\d+"', r"\1", wb)

    partes[parte] = ws.xml.encode("utf-8")
    partes["xl/styles.xml"] = st.xml.encode("utf-8")
    partes["xl/workbook.xml"] = wb.encode("utf-8")
    partes.pop("xl/calcChain.xml", None)
    return pacote.salvar(partes)
