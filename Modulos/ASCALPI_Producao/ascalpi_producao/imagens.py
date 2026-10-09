"""Fotos dos equipamentos e logo da prefeitura, lidos direto do desenho da aba do modelo (sem Excel).

Cada foto da coluna IMAGEM (C) fica ancorada na linha do equipamento (10..100); o logo fica em C3:C4.
Formatos que o navegador não mostra (EMF/WMF/TIFF) são ignorados: a tela usa um ícone no lugar.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
from collections.abc import Mapping
from pathlib import Path
from threading import RLock

from . import pacote

TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
         ".bmp": "image/bmp", ".webp": "image/webp"}
_ANCORA = re.compile(r"<xdr:(twoCellAnchor|oneCellAnchor)\b.*?</xdr:\1>", re.S)
_DE = re.compile(r"<xdr:from><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>", re.S)
_ATE = re.compile(r"<xdr:to><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>", re.S)
_BLIP = re.compile(r'<a:blip\b[^>]*r:embed="([^"]+)"')
COLUNAS_FOTO = (1, 2, 3)          # B..D (a foto fica na C, às vezes encostada)
LINHA_INICIO, LINHA_FIM = 10, 100


def mapa_imagens(partes: dict[str, bytes]) -> dict[object, str]:
    """{linha: parte_da_midia, 'logo': parte_da_midia} para a primeira aba do pacote."""
    aba = pacote.abas(partes)[0]
    desenhos = [r["_alvo"] for r in pacote.ler_rels(partes, aba["parte"]) if r.get("Type", "").endswith("/drawing")]
    saida: dict[object, str] = {}
    for desenho in desenhos:
        if desenho not in partes:
            continue
        rels = {r["Id"]: r.get("_alvo") for r in pacote.ler_rels(partes, desenho)}
        xml = partes[desenho].decode("utf-8", "ignore")
        for m in _ANCORA.finditer(xml):
            ancora = m.group(0)
            de, ate, blip = _DE.search(ancora), _ATE.search(ancora), _BLIP.search(ancora)
            if not (de and blip):
                continue
            midia = rels.get(blip.group(1))
            if not midia or posixpath.splitext(midia)[1].lower() not in TIPOS or midia not in partes:
                continue
            col, r0 = int(de.group(1)), int(de.group(2))
            r1 = int(ate.group(2)) if ate else r0
            linha = (r0 + r1) // 2 + 1                     # linha da planilha (1-based) no meio da foto
            if col in COLUNAS_FOTO and LINHA_INICIO <= linha <= LINHA_FIM:
                saida.setdefault(linha, midia)
            elif col == 2 and 2 <= linha <= 4:              # C3:C4 = logo da prefeitura
                saida.setdefault("logo", midia)
    return saida


class _PartesDoZip(Mapping):
    """Lê do .xlsx só as partes pedidas (o desenho e as relações), sem carregar as fotos na memória."""

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
    """Mapa linha → foto de cada modelo (pequeno, fica em memória); a foto em si é lida do .xlsx quando pedida."""

    def __init__(self):
        self._mapas: dict[tuple[str, float], dict] = {}
        self._trava = RLock()

    def mapa(self, arquivo: Path) -> tuple[float, dict]:
        mtime = arquivo.stat().st_mtime
        chave = (str(arquivo), mtime)
        with self._trava:
            if chave in self._mapas:
                return mtime, self._mapas[chave]
        with zipfile.ZipFile(arquivo) as z:
            achado = mapa_imagens(_PartesDoZip(z))
        with self._trava:
            for antiga in [k for k in self._mapas if k[0] == str(arquivo)]:
                del self._mapas[antiga]
            self._mapas[chave] = achado
        return mtime, achado

    def chaves(self, arquivo: Path) -> set:
        return set(self.mapa(arquivo)[1])

    def imagem(self, arquivo: Path, chave: object) -> tuple[bytes, str, str] | None:
        """(conteúdo, tipo, etag) ou None."""
        mtime, mapa = self.mapa(arquivo)
        midia = mapa.get(chave)
        if not midia:
            return None
        with zipfile.ZipFile(arquivo) as z:
            conteudo = z.read(midia)
        return conteudo, TIPOS[posixpath.splitext(midia)[1].lower()], f'"{int(mtime)}-{chave}"'
