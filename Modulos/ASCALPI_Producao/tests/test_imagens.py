"""R09 — imagens OOXML por URI de namespace, usando pacote .xlsx sintético."""
from __future__ import annotations

import base64
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ascalpi_producao import imagens

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def desenho_xml(prefixo: str) -> bytes:
    if prefixo == "padrao":
        raiz = f'<wsDr xmlns="{XDR}" xmlns:a="{A}" xmlns:r="{R}">'
        anch = "twoCellAnchor"
        pref = ""
    else:
        raiz = f'<d:wsDr xmlns:d="{XDR}" xmlns:z="{A}" xmlns:k="{R}">'
        anch = "d:twoCellAnchor"
        pref = "d:"
    blip = 'a:blip r:embed' if prefixo == "padrao" else 'z:blip k:embed'
    fotos = ""
    for row, rid in ((2, "rLogo"), (9, "rFoto")):
        fotos += (f'<{anch}><{pref}from><{pref}col>2</{pref}col><{pref}row>{row}</{pref}row></{pref}from>'
                  f'<{pref}to><{pref}col>2</{pref}col><{pref}row>{row}</{pref}row></{pref}to>'
                  f'<{blip}="{rid}" /></{anch}>')
    fim = "</wsDr>" if prefixo == "padrao" else "</d:wsDr>"
    return (raiz + fotos + fim).encode()


def partes_sinteticas(prefixo: str) -> dict[str, bytes]:
    return {
        "xl/drawings/drawing1.xml": desenho_xml(prefixo),
        "xl/media/logo.png": PNG,
        "xl/media/foto.png": PNG + b"DIFERENTE",
    }


class TestImagens(unittest.TestCase):
    def test_mapa_logos_e_fotos_com_prefixos_equivalentes(self):
        for prefixo in ("padrao", "alternativo"):
            partes = partes_sinteticas(prefixo)
            rels = [{"Id": "rLogo", "_alvo": "xl/media/logo.png"},
                    {"Id": "rFoto", "_alvo": "xl/media/foto.png"}]
            def ler_rels(_partes, arquivo):
                if arquivo == "xl/worksheets/sheet1.xml":
                    return [{"Type": R + "/drawing", "_alvo": "xl/drawings/drawing1.xml"}]
                return rels
            with self.subTest(prefixo=prefixo), patch.object(imagens.pacote, "abas", return_value=[{"parte": "xl/worksheets/sheet1.xml"}]), patch.object(imagens.pacote, "ler_rels", side_effect=ler_rels):
                self.assertEqual(imagens.mapa_imagens(partes), {"logo": "xl/media/logo.png", 10: "xl/media/foto.png"})

    def test_one_cell_anchor_e_ignorar_formatos_sem_suporte(self):
        xml = (f'<x:wsDr xmlns:x="{XDR}" xmlns:a="{A}" xmlns:r="{R}">'
               '<x:oneCellAnchor><x:from><x:col>2</x:col><x:row>3</x:row></x:from>'
               '<a:blip r:embed="rLogo" /></x:oneCellAnchor>'
               '<x:oneCellAnchor><x:from><x:col>2</x:col><x:row>11</x:row></x:from>'
               '<a:blip r:embed="rEmf" /></x:oneCellAnchor></x:wsDr>').encode()
        partes = {"xl/drawings/drawing1.xml": xml, "xl/media/logo.png": PNG,
                  "xl/media/foto.emf": b"EMF"}
        def rels(p, arquivo):
            if arquivo == "xl/worksheets/sheet1.xml":
                return [{"Type": R + "/drawing", "_alvo": "xl/drawings/drawing1.xml"}]
            return [{"Id": "rLogo", "_alvo": "xl/media/logo.png"},
                    {"Id": "rEmf", "_alvo": "xl/media/foto.emf"}]
        with patch.object(imagens.pacote, "abas", return_value=[{"parte": "xl/worksheets/sheet1.xml"}]), patch.object(imagens.pacote, "ler_rels", side_effect=rels):
            self.assertEqual(imagens.mapa_imagens(partes), {"logo": "xl/media/logo.png"})

    def test_etag_identifica_midia_modelo_e_conteudo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arq1 = Path(pasta) / "modelo1.xlsx"
            arq2 = Path(pasta) / "modelo2.xlsx"
            for arq in (arq1, arq2):
                with zipfile.ZipFile(arq, "w") as z:
                    z.writestr("xl/media/foto.png", PNG)
            cache = imagens.CacheImagens()
            with patch.object(cache, "mapa", side_effect=lambda a: (a.stat().st_mtime, {10: "xl/media/foto.png"})):
                etag1 = cache.imagem(arq1, 10)[2]
                etag2 = cache.imagem(arq2, 10)[2]
                self.assertNotEqual(etag1, etag2)
                with zipfile.ZipFile(arq1, "w") as z:
                    z.writestr("xl/media/foto.png", PNG + b"outro")
                etag3 = cache.imagem(arq1, 10)[2]
                self.assertNotEqual(etag1, etag3)


if __name__ == "__main__":
    unittest.main()
