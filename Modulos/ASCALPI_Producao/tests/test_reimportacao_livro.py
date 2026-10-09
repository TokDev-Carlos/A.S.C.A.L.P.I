"""R07 (complemento): prévia, modelo congelado por O.P. e conferência do saldo da planilha. Dados sintéticos."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl

from ascalpi_producao import legado
from ascalpi_producao.banco import Banco
from ascalpi_producao.servico import Servico
from tests.apoio import criar_controle, criar_livro


class TestReimportacaoLivro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.origem = self.base / "legado"
        self.origem.mkdir()
        self.livro = criar_livro(self.origem)
        criar_controle(self.origem)
        self.dados = self.base / "dados"
        self.s = Servico(self.dados)
        self.s.salvar_config({"publicar": False})
        legado.importar_pasta(self.s.banco, self.origem, self.dados)
        self.modelo = self.s.modelos()[0]

    def tearDown(self):
        self.s.banco.fechar()
        self.tmp.cleanup()

    def _alterar_livro(self, celulas):
        wb = openpyxl.load_workbook(self.livro)
        for aba, ref, valor in celulas:
            wb[aba][ref] = valor
        wb.save(self.livro)

    def _retrato(self):
        b = self.s.banco
        return ([b.todos(f"SELECT * FROM {t} ORDER BY 1") for t in ("prefeituras", "contratos", "contrato_itens", "modelos",
                                                                    "modelo_linhas", "ops")],
                sorted((p.name, p.stat().st_mtime_ns) for p in (self.dados / "Modelos").rglob("*.xlsx")))

    def _l2(self, oid):
        _, xlsx = self.s.gerar_documento(oid, "xlsx")
        return openpyxl.load_workbook(io.BytesIO(xlsx)).active["L2"].value

    def test_previa_nao_altera_banco_nem_arquivos(self):
        self._alterar_livro([("O.P-ATA-TESTE", "L2", "AÇO NOVO"), ("CONTRATO TESTE", "E4", 50)])
        antes = self._retrato()
        relatorio = legado.importar_pasta(self.s.banco, self.origem, self.dados, previa=True)
        self.assertEqual(self._retrato(), antes)
        self.assertTrue(relatorio[0].startswith("PRÉVIA"))
        self.assertTrue(any("MONTANTE 10 → 50" in l for l in relatorio), relatorio)
        self.assertTrue(any("O.P. NO HISTÓRICO" in l for l in relatorio))

    def test_reimportar_livro_nao_muda_documento_de_op_ja_emitida(self):
        antiga = self.s.salvar_op({"modelo_id": self.modelo["id"], "obra": "a", "solicitante": "b", "prazo": "definir",
                                   "itens": [{"linha": 10, "quantidade": 1}]})["op_id"]
        arquivo_antigo = self.s.op(antiga)["modelo_arquivo"]
        self.assertEqual(self._l2(antiga), "AÇO")
        self._alterar_livro([("O.P-ATA-TESTE", "L2", "AÇO NOVO")])
        legado.importar_pasta(self.s.banco, self.origem, self.dados)
        self.assertTrue((self.dados / arquivo_antigo).exists(), "arquivo do modelo usado pela O.P. foi sobrescrito")
        self.assertEqual(self._l2(antiga), "AÇO")                      # O.P. já emitida: modelo congelado
        nova = self.s.salvar_op({"modelo_id": self.modelo["id"], "obra": "c", "solicitante": "d", "prazo": "definir",
                                 "itens": [{"linha": 10, "quantidade": 1}]})["op_id"]
        self.assertEqual(self._l2(nova), "AÇO NOVO")                   # novas O.P. usam o modelo atualizado
        self.assertNotEqual(self.s.op(nova)["modelo_arquivo"], arquivo_antigo)
        r = self.s.salvar_op({"obra": "a2", "solicitante": "b", "prazo": "definir", "rev_esperada": 0,
                              "itens": [{"linha": 10, "quantidade": 2}]}, op_id=antiga)
        self.assertTrue(r["ok"])
        self.assertEqual(self._l2(antiga), "AÇO")                      # a revisão continua no modelo da emissão

    def test_falha_no_banco_nao_deixa_arquivo_novo_sem_registro(self):
        self.s.salvar_op({"modelo_id": self.modelo["id"], "obra": "a", "solicitante": "b", "prazo": "definir",
                          "itens": [{"linha": 10, "quantidade": 1}]})
        self._alterar_livro([("O.P-ATA-TESTE", "L2", "AÇO NOVO")])
        antes = self._retrato()
        original = Banco.evento

        def falhar(banco, con, acao, detalhe=""):
            if acao == "IMPORTAR_LIVRO":
                raise RuntimeError("FALHA SINTÉTICA NO BANCO")
            return original(banco, con, acao, detalhe)
        with patch.object(Banco, "evento", falhar):
            relatorio = legado.importar_pasta(self.s.banco, self.origem, self.dados)
        self.assertTrue(any("FALHA SINTÉTICA" in l for l in relatorio))
        self.assertEqual(self._retrato(), antes)

    def test_conferencia_do_saldo_da_planilha(self):
        # item 1: montante 10, quant 2, previsão 3 → saldo esperado 5; a planilha diz 999
        self._alterar_livro([("CONTRATO TESTE", "J4", 999), ("CONTRATO TESTE", "J5", 0), ("CONTRATO TESTE", "I6", None)])
        relatorio = legado.importar_pasta(self.s.banco, self.origem, self.dados)
        self.assertTrue(any("CONFERIR SALDO ITEM 1" in l and "PLANILHA 999" in l and "CALCULADO 5" in l for l in relatorio), relatorio)
        self.assertFalse(any("CONFERIR SALDO ITEM 2:" in l for l in relatorio))       # 5 − (1 + 4) = 0 confere
        self.assertTrue(any("ITEM 3" in l and "QUANT." in l and "SEM VALOR" in l for l in relatorio), relatorio)
        pend = self.s.pendencias()["saldo_a_conferir"]
        self.assertIn("1", [p["codigo"] for p in pend])

    def test_montante_editado_no_sistema_prevalece_na_reimportacao(self):
        cid = self.modelo["contrato_id"]
        self.s.ajustar_item(cid, "1", montante=40, motivo="CONTRATO MONTADO NO SISTEMA")
        relatorio = legado.importar_pasta(self.s.banco, self.origem, self.dados)
        item = next(i for i in self.s.saldo_contrato(cid) if i["codigo"] == "1")
        self.assertEqual(item["montante"], 40)
        self.assertTrue(any("ITEM 1 (TESTE): MONTANTE EDITADO NO SISTEMA (40) MANTIDO; PLANILHA 10" in l for l in relatorio), relatorio)
        outro = next(i for i in self.s.saldo_contrato(cid) if i["codigo"] == "2")
        self.assertEqual(outro["montante"], 5)                      # não editado: segue a planilha


if __name__ == "__main__":
    unittest.main()
