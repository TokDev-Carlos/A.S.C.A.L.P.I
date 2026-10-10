"""G2 — paginação pela altura real: o item fica na página enquanto couber inteiro (pedido do Carlos, 10/10/2026)."""
import io
import re
import tempfile
import unittest
from pathlib import Path

from ascalpi_producao import documento as d, pacote, paginacao as pg
from ascalpi_producao.configuracao import Configuracao
from ascalpi_producao.validacao import ErroValidacao
from tests.apoio import criar_livro

ABA = re.compile(r"xl/worksheets/sheet\d+\.xml")


def _aba(conteudo: bytes) -> str:
    partes = pacote.carregar(io.BytesIO(conteudo))
    return next(v for k, v in partes.items() if ABA.fullmatch(k)).decode("utf-8")


def _com_alturas(modelo: bytes, altura) -> bytes:
    """Modelo com altura explícita nas linhas 10..100 (altura(r) → pt), como os modelos reais com foto."""
    partes = pacote.carregar(io.BytesIO(modelo))
    nome = next(k for k in partes if ABA.fullmatch(k))
    xml = re.sub(r'<row r="(\d+)"',
                 lambda m: (f'<row r="{m.group(1)}" ht="{altura(int(m.group(1)))}" customHeight="1"'
                            if 10 <= int(m.group(1)) <= 100 else m.group(0)), partes[nome].decode("utf-8"))
    partes[nome] = xml.encode("utf-8")
    return pacote.salvar(partes)


class TestPaginacaoPorAltura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.modelo = pacote.extrair_aba(criar_livro(Path(cls.tmp.name)), "O.P-ATA-TESTE")
        # A4 retrato, margens do legado (topo 1,2 cm, base 0), 21 colunas B..V de 48 pt → escala 58% (fitToWidth):
        # área útil = (841,89 − 34,02) / 0,58 = 1392,9 pt − folga 4 → 1388,9; cabeçalho 2..9 = 8 × 15 = 120 pt.
        cls.m80 = _com_alturas(cls.modelo, lambda r: 80)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _quebras(self, modelo: bytes, n: int, motor: str = "altura", inicio: int = 10) -> list[int]:
        dados = d.DadosOP("010-26", "OBRA", "DEFINIR", "ANA", {r: d.LinhaOP(1) for r in range(inicio, inicio + n)})
        return [int(x) + 1 for x in re.findall(r'<brk id="(\d+)"', _aba(d.gerar_xlsx(modelo, dados, "s", motor)))]

    def test_capacidade_da_pagina(self):
        dados = d.DadosOP("010-26", "OBRA", "DEFINIR", "ANA", {10: d.LinhaOP(1)})
        cap, escala = pg.capacidade_pt(_aba(d.gerar_xlsx(self.m80, dados, "s")), "B", "V")
        self.assertEqual(escala, 0.58)                                  # porcentagem inteira, como o Excel
        self.assertAlmostEqual(cap, (841.89 - 1.2 / 2.54 * 72) / 0.58, places=3)

    def test_itens_que_cabem_nao_vao_para_a_segunda_pagina(self):
        # (1388,9 − 120) / 80 = 15,8 → 15 itens de 80 pt cabem na 1ª página; o VBA quebrava no 14º
        self.assertEqual(self._quebras(self.m80, 14, "legado"), [23])
        self.assertEqual(self._quebras(self.m80, 15), [])
        self.assertEqual(self._quebras(self.m80, 14), [])

    def test_quebra_antes_do_primeiro_item_que_nao_cabe(self):
        self.assertEqual(self._quebras(self.m80, 16), [25])             # o 16º (linha 25) abre a página 2
        # páginas seguintes sem cabeçalho: 1388,9 / 80 = 17 itens
        self.assertEqual(self._quebras(self.m80, 15 + 17 + 1), [25, 42])

    def test_item_alto_deixa_espaco_legitimo_e_ordem_mantida(self):
        # linhas de 60 pt e uma de 400 pt na posição 20: o alto não cabe no que sobra e abre a página 2 inteiro
        alto = _com_alturas(self.modelo, lambda r: 400 if r == 30 else 60)
        quebras = self._quebras(alto, 25)
        usado = 120 + 60 * 20                                           # linhas 10..29 = 1320 pt
        self.assertGreater(usado + 400, 1388.9)
        self.assertEqual(quebras, [30])                                 # nunca reordena para preencher a sobra

    def test_linhas_mistas_seguem_a_altura_de_cada_uma(self):
        mista = _com_alturas(self.modelo, lambda r: [24, 80, 113, 45][r % 4])
        alt = {r: [24, 80, 113, 45][r % 4] for r in range(10, 60)}
        quebras = self._quebras(mista, 30)
        usado, esperado = 120.0, []
        for r in range(10, 40):                                         # simulação independente da regra
            if usado + alt[r] > 1392.887 - pg.FOLGA_PT and r != 10:
                esperado.append(r)
                usado = 0.0
            usado += alt[r]
        self.assertEqual(quebras, esperado)
        self.assertTrue(quebras)

    def test_foto_que_passa_da_linha_nao_e_cortada(self):
        xml = ('<worksheet><sheetFormatPr defaultRowHeight="15"/><sheetData>'
               + "".join(f'<row r="{r}" ht="100" customHeight="1"/>' for r in range(10, 30)) + "</sheetData>"
               '<pageMargins left="0" right="0" top="0" bottom="0"/><pageSetup paperSize="9"/></worksheet>')
        # 21 colunas padrão de 64 px = 1008 pt > 595,28 → escala 59%; 841,89 / 0,59 − 4 = 1422,9 pt
        sem_foto = pg.quebras_por_altura(xml, list(range(10, 30)), 10)
        self.assertEqual(sem_foto, [24])                                # 14 × 100 = 1400 cabe; o 15º não
        desenho = ('<xdr:wsDr xmlns:xdr="x"><xdr:oneCellAnchor><xdr:from><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff>'
                   '<xdr:row>22</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:ext cx="1" cy="1905000"/>'
                   '</xdr:oneCellAnchor></xdr:wsDr>')                  # foto de 150 pt na linha 23 (passa 50 pt)
        self.assertEqual(pg.quebras_por_altura(xml, list(range(10, 30)), 10, desenho), [23])   # 23 vai inteira à pág. 2

    def test_titulos_repetidos_contam_em_todas_as_paginas(self):
        xml = ('<worksheet><sheetFormatPr defaultRowHeight="15"/><sheetData>'
               + "".join(f'<row r="{r}" ht="100" customHeight="1"/>' for r in range(10, 60)) + "</sheetData>"
               '<pageMargins left="0" right="0" top="0" bottom="0"/><pageSetup paperSize="9"/></worksheet>')
        sem = pg.quebras_por_altura(xml, list(range(10, 60)), 10)
        com = pg.quebras_por_altura(xml, list(range(10, 60)), 10, titulos=(2, 9))   # 8 × 15 = 120 pt por página
        self.assertEqual(sem[:2], [24, 38])
        self.assertEqual(com[:2], [23, 36])

    def test_largura_de_coluna_como_o_excel(self):
        # largura gravada no arquivo (com o preenchimento de 5 px), não a mostrada na tela
        self.assertEqual(pg.largura_coluna_pt(9.140625), 48.0)          # 64 px (8,43 na tela)
        self.assertEqual(pg.largura_coluna_pt(11.42578125), 60.0)       # 80 px (10,71 na tela)

    def test_paginas_previstas_e_do_pdf(self):
        self.assertEqual(pg.paginas_previstas('<rowBreaks count="2"><brk id="1"/><brk id="2"/></rowBreaks>'), 3)
        self.assertEqual(pg.paginas_pdf(b"<< /Type /Pages /Count 2 >> << /Type /Page >> << /Type/Page>>"), 2)


class TestConfiguracaoDaPaginacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Configuracao(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_padrao_e_altura_e_legado_continua_disponivel(self):
        self.assertEqual(self.cfg.ler()["paginacao"], "altura")
        self.assertEqual(self.cfg.salvar({"paginacao": "legado"})["paginacao"], "legado")
        with self.assertRaises(ErroValidacao):
            self.cfg.salvar({"paginacao": "16"})

    def test_valor_invalido_no_arquivo_vale_o_padrao(self):
        self.cfg.arquivo.write_text('{"paginacao": "qualquer"}', encoding="utf-8")
        self.assertEqual(self.cfg.ler()["paginacao"], "altura")


if __name__ == "__main__":
    unittest.main()
