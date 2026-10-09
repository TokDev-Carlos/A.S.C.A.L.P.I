"""Lote A (R01/R02): publicação segura e criação idempotente. Dados sintéticos; PDF por mock."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from ascalpi_producao import legado
from ascalpi_producao.servico import ErroConflito, Servico
from ascalpi_producao.servidor import servir
from tests.apoio import criar_controle, criar_livro

PDF_OK = b"%PDF-1.4\nTESTE"


def pdf_ok():
    return patch("ascalpi_producao.servico.pdf.gerar_pdf", return_value=PDF_OK)


def pdf_falha():
    return patch("ascalpi_producao.servico.pdf.gerar_pdf", side_effect=RuntimeError("FALHA SINTÉTICA DO PDF"))


class TestPublicacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "legado").mkdir()
        criar_livro(base / "legado")
        criar_controle(base / "legado")
        self.s = Servico(base / "dados")
        self.s.salvar_config({"publicar": False})
        legado.importar_pasta(self.s.banco, base / "legado", base / "dados")
        self.modelo = self.s.modelos()[0]

    def tearDown(self):
        self.s.banco.fechar()
        self.tmp.cleanup()

    def _dados(self, **extra):
        d = {"modelo_id": self.modelo["id"], "obra": "praça nova", "solicitante": "ana", "prazo": "definir",
             "itens": [{"linha": 10, "quantidade": 1}]}
        d.update(extra)
        return d

    def _contar_sistema(self):
        return self.s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem = 'SISTEMA'")["n"]

    def _saldo_item1(self):
        return next(i["saldo"] for i in self.s.saldo_contrato(self.modelo["contrato_id"]) if i["codigo"] == "1")

    def _temporarios(self):
        return [p for p in Path(self.tmp.name, "dados").rglob("*") if p.name.startswith("~")]

    # ------------------------------------------------------------ R01
    def test_r01_falha_do_pdf_preserva_o_pdf_anterior(self):
        oid = self.s.salvar_op(self._dados())["op_id"]
        with pdf_ok():
            antes = self.s.publicar(oid)
        self.assertEqual(antes["estado"], "PUBLICADA")
        with pdf_falha():
            depois = self.s.publicar(oid)
        self.assertTrue(Path(antes["pdf"]).exists(), "PDF anterior foi apagado")
        self.assertEqual(Path(antes["pdf"]).read_bytes(), PDF_OK)
        self.assertEqual(depois["estado"], "PARCIAL")
        self.assertIn("FALHA SINTÉTICA", depois["pdf_erro"])
        self.assertEqual(depois["pdf"], antes["pdf"])           # continua apontando para o arquivo que existe
        self.assertEqual(self.s.op(oid)["arquivos"]["pdf"], antes["pdf"])
        self.assertEqual(self._temporarios(), [])

    def test_r01_nova_revisao_com_pdf_falhando_marca_pdf_da_revisao_anterior(self):
        oid = self.s.salvar_op(self._dados())["op_id"]
        with pdf_ok():
            rev0 = self.s.publicar(oid)
        with pdf_falha():
            r = self.s.salvar_op(self._dados(obra="outra obra"), op_id=oid, publicar=True)
        pub = r["publicacao"]
        self.assertTrue(r["ok"])
        self.assertEqual(pub["estado"], "PARCIAL")
        self.assertTrue(Path(pub["xlsx"]).exists())
        self.assertNotEqual(pub["xlsx"], rev0["xlsx"])
        self.assertFalse(Path(rev0["xlsx"]).exists(), "xlsx da REV anterior deveria ser substituído")
        self.assertTrue(Path(rev0["pdf"]).exists(), "PDF anterior não pode sumir sem substituto")
        self.assertEqual((pub["xlsx_rev"], pub["pdf_rev"]), (1, 0))

    def test_r01_falha_do_xlsx_nao_apaga_publicacao_anterior(self):
        oid = self.s.salvar_op(self._dados())["op_id"]
        with pdf_ok():
            antes = self.s.publicar(oid)
        with pdf_ok(), patch("ascalpi_producao.servico._gravar_atomico", side_effect=PermissionError("PASTA BLOQUEADA")):
            depois = self.s.publicar(oid)
        self.assertEqual(depois["estado"], "PENDENTE")
        self.assertIn("PASTA BLOQUEADA", depois["xlsx_erro"])
        self.assertTrue(Path(antes["xlsx"]).exists())
        self.assertTrue(Path(antes["pdf"]).exists())

    def test_r01_publicacoes_simultaneas_da_mesma_op_nao_colidem(self):
        oid = self.s.salvar_op(self._dados())["op_id"]
        erros = []

        def publicar():
            try:
                self.s.publicar(oid)
            except Exception as e:  # pragma: no cover - só registra
                erros.append(e)
        with pdf_ok():
            ts = [threading.Thread(target=publicar) for _ in range(3)]
            [t.start() for t in ts]
            [t.join(30) for t in ts]
        self.assertEqual(erros, [])
        self.assertEqual(self.s.op(oid)["arquivos"]["estado"], "PUBLICADA")
        self.assertEqual(self._temporarios(), [])

    # ------------------------------------------------------------ R02
    def test_r02_falha_na_publicacao_devolve_op_salva_e_pendente(self):
        with pdf_ok(), patch("ascalpi_producao.servico._gravar_atomico", side_effect=PermissionError("SEM PERMISSÃO")):
            r = self.s.salvar_op(self._dados(), publicar=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["op"]["numero"], r["op"]["numero"])
        self.assertEqual(r["publicacao"]["estado"], "PENDENTE")
        self.assertEqual(self._contar_sistema(), 1)
        with pdf_ok():
            novo = self.s.publicar(r["op_id"])      # republicar a MESMA O.P. resolve
        self.assertEqual(novo["estado"], "PUBLICADA")
        self.assertEqual(self._contar_sistema(), 1)

    def test_r02_erro_inesperado_ao_gerar_documento_nao_vira_erro_de_criacao(self):
        with patch.object(self.s, "gerar_documento", side_effect=OSError("MODELO SUMIU")):
            r = self.s.salvar_op(self._dados(), publicar=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["publicacao"]["estado"], "PENDENTE")
        self.assertIn("MODELO SUMIU", r["publicacao"]["xlsx_erro"])

    def test_r02_repetir_com_a_mesma_chave_devolve_a_mesma_op(self):
        saldo0 = self._saldo_item1()
        a = self.s.salvar_op(self._dados(chave="rascunho-123"))
        b = self.s.salvar_op(self._dados(chave="rascunho-123"))
        self.assertEqual(a["op_id"], b["op_id"])
        self.assertTrue(b.get("repetida"))
        self.assertEqual(self._contar_sistema(), 1)
        self.assertEqual(self._saldo_item1(), saldo0 - 1)
        c = self.s.salvar_op(self._dados(chave="rascunho-456"))  # duplicação intencional: chave nova
        self.assertNotEqual(c["op_id"], a["op_id"])

    def test_r02_mesma_chave_com_pedido_diferente_e_conflito(self):
        self.s.salvar_op(self._dados(chave="chave-k1-teste"))
        with self.assertRaises(ErroConflito):
            self.s.salvar_op(self._dados(chave="chave-k1-teste", obra="obra diferente"))
        self.assertEqual(self._contar_sistema(), 1)

    def test_r02_api_retry_e_conflito(self):
        httpd = servir(self.s, "127.0.0.1", 0)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def post(corpo):
            req = urllib.request.Request(base + "/api/ops", method="POST", data=json.dumps(corpo).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        try:
            s1, r1 = post(self._dados(chave="chave-api-teste-1"))
            s2, r2 = post(self._dados(chave="chave-api-teste-1"))
            s3, r3 = post(self._dados(chave="chave-api-teste-1", obra="mudou"))
            self.assertEqual((s1, s2), (200, 200))
            self.assertEqual(r1["op_id"], r2["op_id"])
            self.assertEqual(s3, 409)
            self.assertIn("CHAVE", r3["erro"])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
