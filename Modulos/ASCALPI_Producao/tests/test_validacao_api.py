"""Lote C (R06/R08): validação ligada no serviço e na API, sempre antes de gravar. Dados sintéticos."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from ascalpi_producao import legado
from ascalpi_producao.servico import ErroValidacao, Servico
from ascalpi_producao.servidor import servir
from ascalpi_producao.validacao import ErroValidacao as ErroDaValidacao
from tests.apoio import criar_controle, criar_livro


class TestValidacaoServico(unittest.TestCase):
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
        self.oid = self.s.salvar_op({"modelo_id": self.modelo["id"], "obra": "praça", "solicitante": "ana",
                                     "prazo": "definir", "itens": [{"linha": 10, "quantidade": 1}]})["op_id"]

    def tearDown(self):
        self.s.banco.fechar()
        self.tmp.cleanup()

    def _bruto(self, campo):
        return self.s.banco.um(f"SELECT {campo} FROM ops WHERE id = ?", (self.oid,))[campo]

    def test_mesma_classe_de_erro(self):
        self.assertIs(ErroValidacao, ErroDaValidacao)

    def test_r06_data_impossivel_nao_entra_no_banco(self):
        with self.assertRaises(ErroValidacao):
            self.s.acompanhar(self.oid, {"entrega_atualizada": "2026-02-31"})
        self.assertEqual(self._bruto("entrega_atualizada"), "")
        self.s.acompanhar(self.oid, {"entrega_atualizada": "28/02/2026"})          # formato BR válido é normalizado
        self.assertEqual(self._bruto("entrega_atualizada"), "2026-02-28")

    def test_r06_valores_e_campos_de_acompanhamento(self):
        for campos in ({"material_obra": "TALVEZ"}, {"fotografico": "SIM"}, {"campo_inventado": "OK"}):
            with self.assertRaises(ErroValidacao):
                self.s.acompanhar(self.oid, campos)
        self.assertEqual(self._bruto("material_obra"), "")

    def test_r06_data_legada_invalida_nao_derruba_a_lista(self):
        with self.s.banco.transacao() as con:     # simula dado antigo já gravado com data impossível
            con.execute("UPDATE ops SET entrega_atualizada = '2026-02-31', prazo_data = '2026-13-01' WHERE id = ?", (self.oid,))
        lista = self.s.listar_ops()
        o = next(x for x in lista if x["id"] == self.oid)
        self.assertTrue(o["data_invalida"])
        self.assertEqual(o["estado"], "SEM_DATA")
        self.assertEqual(self.s.op(self.oid)["entrega_atualizada"], "2026-02-31")   # valor bruto preservado
        self.assertIn("contagem", self.s.painel())

    def test_r08_ajuste_sem_motivo_ou_numero_invalido_nao_muda_saldo(self):
        cid = self.modelo["contrato_id"]
        antes = self.s.saldo_contrato(cid)
        for kw in ({"ajuste": 2, "motivo": ""}, {"ajuste": 2, "motivo": "   "}, {"ajuste": "dois", "motivo": "X"},
                   {"montante": -1, "motivo": "X"}, {"ajuste": float("nan"), "motivo": "X"}, {"motivo": "SÓ MOTIVO"}):
            with self.assertRaises(ErroValidacao):
                self.s.ajustar_item(cid, "1", **kw)
        self.assertEqual(self.s.saldo_contrato(cid), antes)
        self.s.ajustar_item(cid, "1", ajuste=-1, motivo="DEVOLUÇÃO")                 # ajuste negativo é permitido
        self.assertEqual(next(i for i in self.s.saldo_contrato(cid) if i["codigo"] == "1")["ajuste"], -1)

    def test_r08_linha_repetida_na_op(self):
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op({"modelo_id": self.modelo["id"], "obra": "x", "solicitante": "y", "prazo": "definir",
                              "itens": [{"linha": 10, "quantidade": 1}, {"linha": 10, "quantidade": 2}]})

    def test_r08_cancelar_sem_motivo(self):
        with self.assertRaises(ErroValidacao):
            self.s.cancelar_op(self.oid, "  ")
        self.assertEqual(self._bruto("situacao"), "ATIVA")


class TestValidacaoAPI(TestValidacaoServico):
    def setUp(self):
        super().setUp()
        self.httpd = servir(self.s, "127.0.0.1", 0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def chamar(self, metodo, url, corpo=None, cru=None):
        dados = cru if cru is not None else (json.dumps(corpo).encode() if corpo is not None else None)
        req = urllib.request.Request(self.base + url, method=metodo, data=dados, headers={"Content-Type": "application/json", "X-ASCALPI": "1"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_api_entradas_invalidas_sao_400_sem_mutacao(self):
        total = self.s.banco.um("SELECT COUNT(*) n FROM ops")["n"]
        casos = [
            ("POST", "/api/ops", None, b"[1, 2]"),                                           # corpo não-objeto
            ("POST", "/api/ops", None, b"{nao e json"),
            ("POST", "/api/ops", {"modelo_id": self.modelo["id"], "obra": "x", "solicitante": "y", "prazo": "definir",
                                  "itens": [{"linha": 10, "quantidade": 9}], "confirmar_negativo": "true"}, None),
            ("POST", f"/api/ops/{self.oid}/acompanhamento", {"entrega_atualizada": "2026-02-31"}, None),
            ("POST", f"/api/contratos/{self.modelo['contrato_id']}/ajuste", {"codigo": "1", "ajuste": 1, "motivo": ""}, None),
            ("PATCH", f"/api/modelos/{self.modelo['id']}", {"ativo": "false"}, None),
            ("PATCH", f"/api/modelos/{self.modelo['id']}", {"contrato_id": "abc"}, None),
            ("POST", f"/api/ops/{self.oid}/cancelar", {"motivo": ""}, None),
        ]
        for metodo, url, corpo, cru in casos:
            st, r = self.chamar(metodo, url, corpo, cru)
            self.assertEqual(st, 400, (url, corpo, cru, r))
        self.assertEqual(self.s.banco.um("SELECT COUNT(*) n FROM ops")["n"], total)
        self.assertTrue(self.s._modelo(self.modelo["id"])["ativo"])
        self.assertEqual(self._bruto("situacao"), "ATIVA")


if __name__ == "__main__":
    unittest.main()
