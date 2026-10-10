import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from ascalpi_producao import legado, pdf
from ascalpi_producao.servico import ErroValidacao, Servico
from ascalpi_producao.servidor import servir
from tests.apoio import criar_controle, criar_livro


class TestFluxo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "legado").mkdir()
        criar_livro(base / "legado")
        criar_controle(base / "legado")
        self.s = Servico(base / "dados")
        self.s.salvar_config({"publicar": False})
        self.relatorio = legado.importar_pasta(self.s.banco, base / "legado", base / "dados")
        self.modelo = self.s.modelos()[0]

    def tearDown(self):
        self.s.banco.fechar()
        self.tmp.cleanup()

    def _op(self, **extra):
        linhas = {l["codigo"]: l["linha"] for l in self.s.modelo_completo(self.modelo["id"])["linhas"]}
        dados = {"modelo_id": self.modelo["id"], "obra": "praça nova", "solicitante": "ana", "prazo": "definir",
                 "itens": [{"linha": linhas["1"], "quantidade": "2", "observacao": "azul"},
                           {"linha": linhas["2.1"], "quantidade": "1"}]}
        dados.update(extra)
        return dados

    def test_importacao(self):
        self.assertIn("  CONTRATO TESTE: 4 ITENS", self.relatorio)
        self.assertEqual(self.modelo["ata"], "TESTE")
        modelos = {m["aba"]: m for m in self.s.modelos(todos=True)}
        self.assertEqual(sorted(modelos), ["O.P-ATA-TESTE", "O.P-ATA-TESTE-COPIA"])   # "valadão" fica de fora
        self.assertEqual(modelos["O.P-ATA-TESTE-COPIA"]["contrato_id"], self.modelo["contrato_id"])
        self.assertEqual(self.s.proximo_numero(2026), "013-26")
        ops = self.s.listar_ops(ano=2026)
        self.assertEqual({o["numero"] for o in ops}, {"005-26", "012-26"})
        self.assertTrue(all(o["cliente"] for o in ops))
        b = next(o for o in ops if o["numero"] == "012-26")
        self.assertEqual(b["prazo_texto"], "DEFINIR")
        saldo = {i["codigo"]: i["saldo"] for i in self.s.saldo_contrato(self.modelo["contrato_id"])}
        self.assertEqual(saldo, {"1": 5, "2": "ACABOU", "3": 0, "0.1": 0})

    def test_criar_editar_cancelar(self):
        r = self.s.salvar_op(self._op())
        self.assertTrue(r["precisa_confirmacao"])                  # item 2 já estava ACABOU
        r = self.s.salvar_op(self._op(), confirmar_negativo=True)
        o = r["op"]
        self.assertEqual((o["numero"], o["rev"], o["obra"], o["prazo_texto"]), (f"013-{o['ano'] % 100:02d}", 0, "PRAÇA NOVA", "DEFINIR"))
        self.assertEqual(o["material"], "CARBONO+INOX")
        self.assertEqual(o["saldo_status"], "SALDO_NEGATIVO_CONFIRMADO")
        saldo = {i["codigo"]: i["saldo"] for i in self.s.saldo_contrato(self.modelo["contrato_id"])}
        self.assertEqual(saldo["1"], 3)
        self.assertEqual(saldo["2"], -1)
        # editar: quantidade e data → REV 1, saldo recalculado sem contar a versão anterior
        dados = self._op(prazo="2026-12-01", rev_esperada=0)
        dados["itens"] = dados["itens"][:1]
        dados["itens"][0]["quantidade"] = "5"
        r = self.s.salvar_op(dados, op_id=o["id"])
        self.assertEqual(r["op"]["rev"], 1)
        self.assertEqual(r["op"]["prazo_data"], "2026-12-01")
        self.assertEqual(r["simulacao"]["status"], "SALDO_ENCERRADO")
        self.assertEqual(len(r["op"]["revisoes"]), 2)
        # instalado passa para QUANT.
        self.s.acompanhar(o["id"], {"status_instalacao": "ok"})
        item1 = next(i for i in self.s.saldo_contrato(self.modelo["contrato_id"]) if i["codigo"] == "1")
        self.assertEqual((item1["quant"], item1["previsao"], item1["saldo"]), (7, 3, "ACABOU"))
        # cancelar devolve o saldo
        self.s.cancelar_op(o["id"], "teste")
        saldo = {i["codigo"]: i["saldo"] for i in self.s.saldo_contrato(self.modelo["contrato_id"])}
        self.assertEqual(saldo["1"], 5)
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op(dados, op_id=o["id"])
        self.assertEqual(self.s.proximo_numero(o["ano"]), f"014-{o['ano'] % 100:02d}")

    def test_validacoes(self):
        for extra, msg in (({"obra": ""}, "OBRA"), ({"solicitante": " "}, "SOLICITANTE"), ({"prazo": ""}, "PRAZO"),
                           ({"itens": []}, "PELO MENOS 1")):
            with self.assertRaises(ErroValidacao) as e:
                self.s.salvar_op(self._op(**extra))
            self.assertIn(msg, str(e.exception))
        legado_op = self.s.listar_ops()[0]
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op(self._op(), op_id=legado_op["id"])

    def test_documentos_e_publicacao(self):
        o = self.s.salvar_op(self._op(itens=[{"linha": 10, "quantidade": 1}]))["op"]
        nome, xlsx = self.s.gerar_documento(o["id"], "xlsx")
        self.assertTrue(nome.startswith(o["numero"] + " - CIDADE TESTE-RJ - PRACA NOVA - MOB - "))
        self.assertEqual(xlsx[:2], b"PK")
        if not pdf.libreoffice() and not pdf.excel_disponivel():
            self.skipTest("SEM MOTOR DE PDF")
        res = self.s.publicar(o["id"])
        self.assertTrue(Path(res["xlsx"]).exists())
        self.assertTrue(Path(res["pdf"]).read_bytes().startswith(b"%PDF"))
        # nova revisão com outra obra substitui os arquivos publicados
        res2 = self.s.salvar_op(self._op(obra="outra", itens=[{"linha": 10, "quantidade": 1}], rev_esperada=0), op_id=o["id"],
                                publicar=True)["publicacao"]
        self.assertFalse(Path(res["xlsx"]).exists())
        self.assertTrue(Path(res2["xlsx"]).exists())

    def test_api(self):
        httpd = servir(self.s, "127.0.0.1", 0)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            def chamar(metodo, url, corpo=None):
                req = urllib.request.Request(base + url, method=metodo, data=json.dumps(corpo).encode() if corpo else None,
                                             headers={"Content-Type": "application/json", "X-ASCALPI": "1"})
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())
            self.assertEqual(chamar("GET", "/api/resumo")[0], 200)
            st, r = chamar("POST", "/api/ops", self._op(obra=""))
            self.assertEqual((st, r["erro"]), (400, "INFORME A OBRA."))
            st, r = chamar("POST", "/api/ops", {**self._op(), "confirmar_negativo": True})
            self.assertEqual(st, 200)
            with urllib.request.urlopen(f"{base}/api/ops/{r['op_id']}/documento.xlsx") as resp:
                self.assertIn("attachment", resp.headers["Content-Disposition"])
            with urllib.request.urlopen(base + "/") as resp:
                self.assertIn(b"ASCALPI", resp.read())
            self.assertEqual(chamar("GET", "/api/nada")[0], 404)
            self.assertNotIn("senha_arquivos", chamar("GET", "/api/config")[1])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
