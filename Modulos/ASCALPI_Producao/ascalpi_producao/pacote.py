"""Manipulação do pacote .xlsx/.xlsm (OPC) sem Excel: extrair uma aba como modelo independente."""
from __future__ import annotations

import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_SHEET = NS_R + "/worksheet"
WB_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
MANTER_DO_LIVRO = {NS_R + "/styles", NS_R + "/theme", NS_R + "/sharedStrings"}


def _rels_path(parte: str) -> str:
    pasta, nome = posixpath.split(parte)
    return posixpath.join(pasta, "_rels", nome + ".rels")


def _resolver(origem: str, alvo: str) -> str:
    if alvo.startswith("/"):
        return alvo.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(origem), alvo))


def ler_rels(partes: dict[str, bytes], parte: str) -> list[dict]:
    caminho = _rels_path(parte) if parte else "_rels/.rels"
    if caminho not in partes:
        return []
    raiz = ET.fromstring(partes[caminho])
    saida = []
    for r in raiz:
        d = dict(r.attrib)
        if d.get("TargetMode") != "External":
            d["_alvo"] = _resolver(parte or "", d["Target"]) if parte else d["Target"].lstrip("/")
        saida.append(d)
    return saida


def abas(partes: dict[str, bytes]) -> list[dict]:
    """[{nome, estado, parte, codename}] na ordem do livro."""
    wb = partes["xl/workbook.xml"].decode("utf-8")
    rels = {r["Id"]: r for r in ler_rels(partes, "xl/workbook.xml")}
    saida = []
    for m in re.finditer(r"<sheet\b[^>]*/>", wb):
        tag = m.group(0)
        nome = _attr(tag, "name")
        rid = re.search(r'r:id="([^"]+)"', tag).group(1)
        parte = rels[rid]["_alvo"]
        xml = partes[parte][:3000].decode("utf-8", "ignore")
        cn = re.search(r'<sheetPr[^>]*codeName="([^"]+)"', xml)
        saida.append({"nome": _xml_unescape(nome), "estado": _attr(tag, "state") or "visible",
                      "parte": parte, "rid": rid, "codename": cn.group(1) if cn else ""})
    return saida


def _attr(tag: str, nome: str) -> str:
    m = re.search(r'\b' + nome + r'="([^"]*)"', tag)
    return m.group(1) if m else ""


def _xml_unescape(t: str) -> str:
    t = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), t)
    t = re.sub(r"_x([0-9A-F]{4})_", lambda m: chr(int(m.group(1), 16)), t)  # escape do Excel (ex.: _x000D_)
    return t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def carregar(origem) -> dict[str, bytes]:
    with zipfile.ZipFile(origem) as z:
        return {n: z.read(n) for n in z.namelist()}


def salvar(partes: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        ordem = ["[Content_Types].xml"] + [n for n in partes if n != "[Content_Types].xml"]
        for n in ordem:
            z.writestr(n, partes[n])
    return buf.getvalue()


def extrair_aba(origem, nome_aba: str) -> bytes:
    """Gera um .xlsx que contém só a aba indicada (imagens, mesclas, estilos e impressão preservados)."""
    partes = carregar(origem)
    lista = abas(partes)
    alvo = next((a for a in lista if a["nome"] == nome_aba), None)
    if alvo is None:
        raise ValueError(f"ABA NÃO ENCONTRADA: {nome_aba}")
    indice = lista.index(alvo)

    # --- workbook.xml: só a aba alvo, nomes definidos dela, recálculo ao abrir
    wb = partes["xl/workbook.xml"].decode("utf-8")
    sheet_tags = re.findall(r"<sheet\b[^>]*/>", wb)
    novo_tag = next(t for t in sheet_tags if f'r:id="{alvo["rid"]}"' in t)
    novo_tag = re.sub(r'\sstate="[^"]*"', "", novo_tag)
    wb = re.sub(r"<sheets>.*?</sheets>", "<sheets>" + novo_tag + "</sheets>", wb, flags=re.S)

    def filtrar_nomes(m: re.Match) -> str:
        bloco = m.group(0)
        mantidos = []
        for dn in re.findall(r"<definedName\b[^>]*>.*?</definedName>|<definedName\b[^>]*/>", bloco, flags=re.S):
            local = _attr(dn.split(">", 1)[0], "localSheetId")
            if local == str(indice):
                mantidos.append(dn.replace(f'localSheetId="{indice}"', 'localSheetId="0"'))
        return "<definedNames>" + "".join(mantidos) + "</definedNames>" if mantidos else ""

    wb = re.sub(r"<definedNames>.*?</definedNames>", filtrar_nomes, wb, flags=re.S)
    wb = re.sub(r"<definedNames\s*/>", "", wb)
    wb = re.sub(r'\sactiveTab="\d+"', "", wb)
    wb = re.sub(r'\sfirstSheet="\d+"', "", wb)
    if "<calcPr" in wb:
        wb = re.sub(r"<calcPr\b([^>]*?)/?>", lambda m: "<calcPr" + re.sub(r'\sfullCalcOnLoad="[^"]*"', "", m.group(1)).rstrip("/") + ' fullCalcOnLoad="1"/>', wb, count=1)
    wb = re.sub(r"<fileVersion\b[^>]*/>", "", wb)
    wb = re.sub(r'<workbookPr\b[^>]*/>', '<workbookPr/>', wb)
    partes["xl/workbook.xml"] = wb.encode("utf-8")

    # --- rels do livro: estilos, tema, strings e a aba
    rels_wb = ler_rels(partes, "xl/workbook.xml")
    manter_rel = [r for r in rels_wb if r["Type"] in MANTER_DO_LIVRO or r.get("Id") == alvo["rid"]]
    partes["xl/_rels/workbook.xml.rels"] = _escrever_rels(manter_rel)

    # --- rels raiz: workbook + core
    raiz = [r for r in ler_rels(partes, "") if r["Type"].endswith("/officeDocument") or r["Type"].endswith("/core-properties")]
    partes["_rels/.rels"] = _escrever_rels(raiz)

    # --- partes alcançáveis
    alcancaveis: set[str] = set()
    fila = [r["_alvo"] for r in raiz]
    while fila:
        p = fila.pop()
        if p in alcancaveis or p not in partes:
            continue
        alcancaveis.add(p)
        for r in ler_rels(partes, p):
            if "_alvo" in r:
                fila.append(r["_alvo"])
    manter = {p for p in alcancaveis}
    manter |= {_rels_path(p) for p in alcancaveis if _rels_path(p) in partes}
    manter |= {"_rels/.rels", "[Content_Types].xml"}
    partes = {k: v for k, v in partes.items() if k in manter}

    # --- content types
    ct = partes["[Content_Types].xml"].decode("utf-8")

    def filtrar_override(m: re.Match) -> str:
        nome = _attr(m.group(0), "PartName").lstrip("/")
        return m.group(0) if nome in partes else ""

    ct = re.sub(r"<Override\b[^>]*/>", filtrar_override, ct)
    ct = re.sub(r'(PartName="/xl/workbook.xml" ContentType=")[^"]+"', r'\1' + WB_XLSX + '"', ct)
    partes["[Content_Types].xml"] = ct.encode("utf-8")

    # --- sem caminho do servidor no arquivo e sem botões de macro (xlsx não tem macro)
    wb = partes["xl/workbook.xml"].decode("utf-8")
    wb = re.sub(r"<mc:AlternateContent\b(?:(?!</mc:AlternateContent>).)*?absPath.*?</mc:AlternateContent>", "", wb, flags=re.S)
    partes["xl/workbook.xml"] = wb.encode("utf-8")
    for nome in [n for n in partes if n.startswith("xl/drawings/") and n.endswith(".xml") and "/_rels/" not in n]:
        partes[nome] = limpar_desenho(partes[nome].decode("utf-8")).encode("utf-8")
    return salvar(partes)


_ANCORA = re.compile(r"<xdr:(twoCellAnchor|oneCellAnchor|absoluteAnchor)\b.*?</xdr:\1>", re.S)


def limpar_desenho(xml: str) -> str:
    """Remove formas que não imprimem (botões fora da folha) e desliga as macros das que ficam."""
    xml = _ANCORA.sub(lambda m: "" if 'fPrintsWithSheet="0"' in m.group(0) else m.group(0), xml)
    return re.sub(r'\smacro="[^"]*"', "", xml)


def _escrever_rels(rels: list[dict]) -> bytes:
    linhas = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              f'<Relationships xmlns="{NS_REL}">']
    for r in rels:
        attrs = " ".join(f'{k}="{_xml_escape(v)}"' for k, v in r.items() if not k.startswith("_"))
        linhas.append(f"<Relationship {attrs}/>")
    linhas.append("</Relationships>")
    return "".join(linhas).encode("utf-8")


def _xml_escape(t: str) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---------------------------------------------------------------- leitura rápida de valores (sem openpyxl)

def strings_compartilhadas(partes: dict[str, bytes]) -> list[str]:
    if "xl/sharedStrings.xml" not in partes:
        return []
    xml = partes["xl/sharedStrings.xml"].decode("utf-8")
    saida = []
    for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
        # ignora textos fonéticos (rPh)
        si = re.sub(r"<rPh\b.*?</rPh>", "", si, flags=re.S)
        saida.append(_xml_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    return saida


_CEL = re.compile(r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S)


def ler_valores(partes: dict[str, bytes], parte: str, ss: list[str] | None = None) -> dict[str, object]:
    """{ref: valor em cache} da aba (números como float, textos como str, booleanos como bool)."""
    ss = strings_compartilhadas(partes) if ss is None else ss
    xml = partes[parte].decode("utf-8")
    valores: dict[str, object] = {}
    for ref, attrs, corpo in _CEL.findall(xml):
        if not corpo:
            continue
        t = re.search(r'\st="(\w+)"', attrs)
        t = t.group(1) if t else "n"
        if t == "inlineStr":
            valores[ref] = _xml_unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", corpo, re.S)))
            continue
        v = re.search(r"<v>(.*?)</v>", corpo, re.S)
        if not v:
            continue
        v = v.group(1)
        if t == "s":
            valores[ref] = ss[int(v)]
        elif t in ("str", "e"):
            valores[ref] = _xml_unescape(v)
        elif t == "b":
            valores[ref] = v == "1"
        else:
            try:
                valores[ref] = float(v)
            except ValueError:
                valores[ref] = v
    return valores


def tabelas(partes: dict[str, bytes], parte: str) -> list[dict]:
    """[{nome, ref}] das tabelas (ListObjects) da aba."""
    saida = []
    for r in ler_rels(partes, parte):
        if r.get("Type", "").endswith("/table") and r.get("_alvo") in partes:
            xml = partes[r["_alvo"]][:2000].decode("utf-8", "ignore")
            m = re.search(r"<table\b[^>]*>", xml)
            if m:
                saida.append({"nome": _attr(m.group(0), "name") or _attr(m.group(0), "displayName"),
                              "ref": _attr(m.group(0), "ref")})
    return saida
