"""Fotos e logo embutidos nos desenhos OOXML dos modelos, sem Excel.

As coordenadas de âncoras oneCell/twoCell são zero-based no desenho. O logo
fica em C3:C4 e as fotos dos equipamentos nas linhas 10..100, colunas B..D.
Formatos não exibidos pelo navegador (EMF/WMF/TIFF) são ignorados.
"""
from __future__ import annotations

import hashlib
import posixpath
import zipfile
from collections.abc import Mapping
from pathlib import Path
from threading import RLock
from xml.etree import ElementTree as ET

from . import pacote

TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
         ".bmp": "image/bmp", ".webp": "image/webp"}
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
COLUNAS_FOTO = (1, 2, 3)  # B..D (às vezes a foto encosta na coluna vizinha)
LINHA_INICIO, LINHA_FIM = 10, 100


def _coordenadas(ancora: ET.Element, marcador: str) -> tuple[int, int] | None:
    origem = ancora.find(f"{{{NS_XDR}}}{marcador}")
    if origem is None:
        return None
    col = origem.findtext(f"{{{NS_XDR}}}col")
    row = origem.findtext(f"{{{NS_XDR}}}row")
    try:
        return int(col), int(row)
    except (TypeError, ValueError):
        return None


def mapa_imagens(partes: Mapping[str, bytes]) -> dict[object, str]:
    """Retorna {linha: arquivo_de_mídia, 'logo': arquivo_de_mídia}, da primeira aba."""
    abas = pacote.abas(partes)
    if not abas:
        return {}
    desenhos = [r["_alvo"] for r in pacote.ler_rels(partes, abas[0]["parte"])
                if r.get("Type", "").endswith("/drawing") and r.get("_alvo")]
    saida: dict[object, str] = {}
    for desenho in desenhos:
        if desenho not in partes:
            continue
        rels = {r["Id"]: r.get("_alvo") for r in pacote.ler_rels(partes, desenho)
                if r.get("Id") and r.get("_alvo")}
        try:
            raiz = ET.fromstring(partes[desenho])
        except ET.ParseError:
            continue
        for ancora in raiz:
            if ancora.tag not in (f"{{{NS_XDR}}}oneCellAnchor", f"{{{NS_XDR}}}twoCellAnchor"):
                continue
            de = _coordenadas(ancora, "from")
            if de is None:
                continue
            ate = _coordenadas(ancora, "to")
            col, r0 = de
            r1 = ate[1] if ate else r0
            if r0 < 0 or r1 < 0:
                continue
            linha = (r0 + r1) // 2 + 1
            if col in COLUNAS_FOTO and LINHA_INICIO <= linha <= LINHA_FIM:
                chave: object = linha
            elif col == 2 and 2 <= linha <= 4:
                chave = "logo"
            else:
                continue
            for blip in ancora.iter(f"{{{NS_A}}}blip"):
                rid = blip.get(f"{{{NS_R}}}embed")
                midia = rels.get(rid)
                if midia and midia in partes and posixpath.splitext(midia)[1].lower() in TIPOS:
                    saida.setdefault(chave, midia)
                    break
    return saida


class _PartesDoZip(Mapping):
    """Lê apenas partes utilizadas pelo desenho; imagens ficam no ZIP até solicitadas."""

    def __init__(self, z: zipfile.ZipFile):
        self._z = z
        self._nomes = set(z.namelist())

    def __getitem__(self, nome: str) -> bytes:
        if nome not in self._nomes:
            raise KeyError(nome)
        return self._z.read(nome)

    def __contains__(self, nome: object) -> bool:
        return nome in self._nomes

    def __iter__(self):
        return iter(self._nomes)

    def __len__(self) -> int:
        return len(self._nomes)


class CacheImagens:
    """Mapeia âncoras com cache por metadados de alta resolução; ETag usa hash da mídia."""

    def __init__(self):
        self._mapas: dict[tuple[str, int, int], dict] = {}
        self._trava = RLock()

    def mapa(self, arquivo: Path) -> tuple[float, dict]:
        arquivo = Path(arquivo)
        stat = arquivo.stat()
        chave = (str(arquivo.resolve()), stat.st_mtime_ns, stat.st_size)
        with self._trava:
            if chave in self._mapas:
                return stat.st_mtime, self._mapas[chave]
        with zipfile.ZipFile(arquivo) as z:
            achado = mapa_imagens(_PartesDoZip(z))
        with self._trava:
            for antiga in [k for k in self._mapas if k[0] == chave[0]]:
                del self._mapas[antiga]
            self._mapas[chave] = achado
        return stat.st_mtime, achado

    def chaves(self, arquivo: Path) -> set:
        return set(self.mapa(arquivo)[1])

    def imagem(self, arquivo: Path, chave: object) -> tuple[bytes, str, str] | None:
        """(conteúdo, MIME type, ETag) ou None."""
        _, mapa = self.mapa(arquivo)
        midia = mapa.get(chave)
        if not midia:
            return None
        with zipfile.ZipFile(arquivo) as z:
            conteudo = z.read(midia)
        identidade = f"{Path(arquivo).resolve()}\0{chave}\0{midia}".encode("utf-8")
        digest = hashlib.sha256(identidade + b"\0" + conteudo).hexdigest()
        return conteudo, TIPOS[posixpath.splitext(midia)[1].lower()], f'"{digest}"'
