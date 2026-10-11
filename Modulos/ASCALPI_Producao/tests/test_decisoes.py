"""Decisões do Carlos (09/10/2026): datas da O.P. e itens 0.x como extras. Dados sintéticos."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl

from ascalpi_producao import legado
from ascalpi_producao.servico import Servico
from tests.apoio import criar_controle, criar_livro


class Base(unittest.TestCase):
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

    def dados(self, itens=None, **extra):
        d = {"modelo_id": self.modelo["id"], "obra": "praça", "solicitante": "ana", "prazo": "definir",
             "itens": itens or [{"linha": 10, "quantidade": 1}]}
        d.update(extra)
        return d

    def b2(self, oid):
        _, xlsx = self.s.gerar_documento(oid, "xlsx")
        return openpyxl.load_workbook(io.BytesIO(xlsx)).active["B2"].value


class TestDatasDaOP(Base):
    """1 — data de criação imutável; cada revisão registra a sua data."""

    def test_criacao_imutavel_e_data_da_revisao(self):
        with patch("ascalpi_producao.servico.agora", return_value="2026-10-01T08:05:00"):
            oid = self.s.salvar_op(self.dados())["op_id"]
        o = self.s.op(oid)
        self.assertEqual((o["criado_em"], o["revisado_em"]), ("2026-10-01T08:05:00", "2026-10-01T08:05:00"))
        self.assertEqual(self.b2(oid), "Hoje 01/10/2026 8:05-quinta-feira")         # REV 0: igual ao legado

        with patch("ascalpi_producao.servico.agora", return_value="2026-10-07T14:30:00"):
            self.s.salvar_op(self.dados(obra="outra", rev_esperada=0), op_id=oid)
        o = self.s.op(oid)
        self.assertEqual(o["criado_em"], "2026-10-01T08:05:00")
        self.assertEqual(o["solicitado_em"], "2026-10-01T08:05:00")
        self.assertEqual(o["revisado_em"], "2026-10-07T14:30:00")
        self.assertEqual([r["momento"] for r in o["revisoes"]], ["2026-10-01T08:05:00", "2026-10-07T14:30:00"])
        self.assertEqual(self.b2(oid), "Hoje 01/10/2026 8:05-quinta-feira · REV 1 07/10/2026")

    def test_acompanhamento_nao_muda_as_datas_do_documento(self):
        with patch("ascalpi_producao.servico.agora", return_value="2026-10-01T08:05:00"):
            oid = self.s.salvar_op(self.dados())["op_id"]
        antes = self.b2(oid)
        with patch("ascalpi_producao.servico.agora", return_value="2026-10-20T10:00:00"):
            self.s.acompanhar(oid, {"material_obra": "OK"})
        self.assertEqual(self.b2(oid), antes)
        self.assertEqual(self.s.op(oid)["revisado_em"], "2026-10-01T08:05:00")


class TestItensExtras(Base):
    """2 — itens 0.x são extras: contam na O.P., não têm saldo."""

    def test_extra_fora_do_contrato_e_aceito_sem_saldo(self):
        with self.s.banco.transacao() as con:
            con.execute("DELETE FROM contrato_itens WHERE codigo = '0.1'")
        r = self.s.salvar_op(self.dados([{"linha": 10, "quantidade": 1}, {"linha": 14, "quantidade": 3}]))
        self.assertTrue(r["ok"])
        self.assertEqual(r["simulacao"]["status"], "SALDO_OK")
        o = self.s.op(r["op_id"])
        self.assertEqual((len(o["itens"]), sum(i["quantidade"] for i in o["itens"])), (2, 4))
        lista = next(x for x in self.s.listar_ops() if x["id"] == r["op_id"])
        self.assertEqual((lista["itens"], lista["pecas"]), (2, 4))

    def test_extra_no_contrato_nao_gera_alerta_nem_saldo(self):
        self.s.salvar_op(self.dados([{"linha": 14, "quantidade": 5}]))
        item = next(i for i in self.s.saldo_contrato(self.modelo["contrato_id"]) if i["codigo"] == "0.1")
        self.assertTrue(item["extra"])
        self.assertFalse(any(a["codigo"].startswith("0.") for a in self.s.painel()["alertas_saldo"]))
        normal = next(i for i in self.s.saldo_contrato(self.modelo["contrato_id"]) if i["codigo"] == "1")
        self.assertFalse(normal["extra"])


if __name__ == "__main__":
    unittest.main()
