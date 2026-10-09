"""Lote B (R03/R04/R05): transação única, revisão esperada e contrato da O.P. Dados sintéticos.

A concorrência é coordenada sem sleeps: a 1ª chamada, no meio do trabalho, dispara a 2ª e espera por ela com prazo
curto. No código antigo a 2ª termina nesse intervalo (corrida); no corrigido ela fica presa na transação da 1ª.
"""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ascalpi_producao import legado
from ascalpi_producao.banco import Banco
from ascalpi_producao.servico import ErroConflito, ErroValidacao, Servico
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
        self.cid = self.modelo["contrato_id"]

    def tearDown(self):
        self.s.banco.fechar()
        self.tmp.cleanup()

    def dados(self, qtd=1, **extra):
        d = {"modelo_id": self.modelo["id"], "obra": "praça", "solicitante": "ana", "prazo": "definir",
             "itens": [{"linha": 10, "quantidade": qtd}]}
        d.update(extra)
        return d

    def saldo(self, cid=None):
        return next(i["saldo"] for i in self.s.saldo_contrato(cid or self.cid) if i["codigo"] == "1")

    def corrida(self, alvo, chamada_a, chamada_b):
        """Executa A; quando A passa por `alvo`, dispara B e espera até 0,5 s. Devolve (resultado/erro de A, de B)."""
        saida = {}

        def rodar(nome, fn):
            try:
                saida[nome] = fn()
            except Exception as e:  # noqa: BLE001
                saida[nome] = e
        tb = threading.Thread(target=rodar, args=("b", chamada_b))
        original = getattr(self.s, alvo)
        disparada = []

        def espiao(*a, **k):
            r = original(*a, **k)
            if not disparada and threading.current_thread() is not tb:
                disparada.append(1)
                tb.start()
                tb.join(0.5)
            return r
        with patch.object(self.s, alvo, side_effect=espiao):
            rodar("a", chamada_a)
            tb.join(10)
        self.assertFalse(tb.is_alive(), "segunda chamada travou")
        return saida["a"], saida["b"]


class TestR03Saldo(Base):
    def test_criacoes_concorrentes_respeitam_o_saldo(self):
        self.assertEqual(self.saldo(), 5)
        a, b = self.corrida("simular", lambda: self.s.salvar_op(self.dados(4)), lambda: self.s.salvar_op(self.dados(4)))
        resultados = [a, b]
        self.assertEqual(sum(1 for r in resultados if isinstance(r, dict) and r.get("ok")), 1)
        self.assertEqual(sum(1 for r in resultados if isinstance(r, dict) and r.get("precisa_confirmacao")), 1)
        self.assertEqual(self.saldo(), 1)

    def test_modelo_desativado_no_meio_e_revalidado(self):
        a, b = self.corrida("_validar", lambda: self.s.salvar_op(self.dados(1)),
                            lambda: self.s.atualizar_modelo(self.modelo["id"], ativo=False))
        # ou a criação termina antes da desativação, ou é recusada; nunca grava com modelo inativo já lido
        self.assertTrue(isinstance(a, dict) and a.get("ok"))
        self.assertFalse(self.s._modelo(self.modelo["id"])["ativo"])
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op(self.dados(1))


class TestR04Revisao(Base):
    def test_edicao_exige_revisao_esperada(self):
        oid = self.s.salvar_op(self.dados())["op_id"]
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op(self.dados(obra="sem rev"), op_id=oid)

    def test_edicao_com_revisao_obsoleta_e_conflito(self):
        oid = self.s.salvar_op(self.dados())["op_id"]
        self.s.salvar_op(self.dados(obra="primeira", rev_esperada=0), op_id=oid)
        with self.assertRaises(ErroConflito):
            self.s.salvar_op(self.dados(obra="segunda", rev_esperada=0), op_id=oid)
        o = self.s.op(oid)
        self.assertEqual([r["rev"] for r in o["revisoes"]], [0, 1])
        self.assertEqual(o["obra"], "PRIMEIRA")

    def test_edicoes_concorrentes_geram_uma_revisao_e_um_conflito(self):
        oid = self.s.salvar_op(self.dados())["op_id"]
        a, b = self.corrida("_validar", lambda: self.s.salvar_op(self.dados(obra="A", rev_esperada=0), op_id=oid),
                            lambda: self.s.salvar_op(self.dados(obra="B", rev_esperada=0), op_id=oid))
        self.assertEqual(sorted(type(x).__name__ for x in (a, b)), ["ErroConflito", "dict"])
        self.assertEqual([r["rev"] for r in self.s.op(oid)["revisoes"]], [0, 1])

    def test_editar_e_cancelar_ao_mesmo_tempo(self):
        oid = self.s.salvar_op(self.dados())["op_id"]
        a, b = self.corrida("_validar", lambda: self.s.salvar_op(self.dados(obra="A", rev_esperada=0), op_id=oid),
                            lambda: self.s.cancelar_op(oid, "TESTE"))
        self.assertTrue(isinstance(a, dict) and a.get("ok"))
        o = self.s.op(oid)
        self.assertEqual((o["situacao"], o["rev"]), ("CANCELADA", 1))
        with self.assertRaises(ErroValidacao):
            self.s.salvar_op(self.dados(obra="C", rev_esperada=1), op_id=oid)

    def test_revisao_unica_no_banco(self):
        oid = self.s.salvar_op(self.dados())["op_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            with self.s.banco.transacao() as con:
                con.execute("INSERT INTO op_revisoes (op_id, rev, momento, dados) VALUES (?, 0, 'x', '{}')", (oid,))


class TestR05Contrato(Base):
    def _novo_contrato(self, montante=10):
        with self.s.banco.transacao() as con:
            cid = con.execute("INSERT INTO contratos (prefeitura_id, ata) VALUES (?, 'OUTRA')",
                              (self.modelo["prefeitura_id"],)).lastrowid
            con.execute("INSERT INTO contrato_itens (contrato_id, codigo, montante) VALUES (?, '1', ?)", (cid, montante))
        return cid

    def test_trocar_contrato_do_modelo_nao_move_consumo_ja_emitido(self):
        oid = self.s.salvar_op(self.dados(4))["op_id"]
        self.assertEqual(self.saldo(), 1)
        novo = self._novo_contrato()
        self.s.atualizar_modelo(self.modelo["id"], contrato_id=novo)
        self.assertEqual(self.saldo(), 1)                 # O.P. antiga continua no contrato original
        self.assertEqual(self.saldo(novo), 10)
        self.assertEqual(self.s.op(oid)["contrato_id"], self.cid)
        nova = self.s.salvar_op(self.dados(2))["op_id"]     # novas O.P. usam o contrato novo
        self.assertEqual(self.s.op(nova)["contrato_id"], novo)
        self.assertEqual((self.saldo(), self.saldo(novo)), (1, 8))

    def test_editar_op_antiga_confere_o_contrato_dela(self):
        oid = self.s.salvar_op(self.dados(4))["op_id"]
        novo = self._novo_contrato(montante=100)
        self.s.atualizar_modelo(self.modelo["id"], contrato_id=novo)
        r = self.s.salvar_op(self.dados(6, rev_esperada=0), op_id=oid)   # 6 > saldo 5 do contrato ORIGINAL
        self.assertTrue(r.get("precisa_confirmacao"))
        linha = next(l for l in self.s.modelo_completo(self.modelo["id"], excluir_op=oid)["linhas"] if l["linha"] == 10)
        self.assertEqual((linha["montante"], linha["saldo"]), (10, 5))     # não o montante 100 do contrato novo

    def test_migracao_preenche_contrato_e_guarda_unicidade(self):
        oid = self.s.salvar_op(self.dados(1))["op_id"]
        caminho = self.s.banco.caminho
        self.s.banco.fechar()
        con = sqlite3.connect(caminho)
        con.execute("DROP INDEX IF EXISTS ix_revisoes_op_rev")
        con.execute("ALTER TABLE ops DROP COLUMN contrato_id")
        con.execute("INSERT INTO op_revisoes (op_id, rev, momento, dados) VALUES (?, 0, 'x', '{}')", (oid,))  # duplicada antiga
        con.commit()
        con.close()
        b = Banco(caminho)
        try:
            self.assertEqual(b.um("SELECT contrato_id FROM ops WHERE id = ?", (oid,))["contrato_id"], self.cid)
            self.assertEqual(b.um("SELECT COUNT(*) n FROM op_revisoes WHERE op_id = ?", (oid,))["n"], 2)  # nada apagado
            self.assertIsNone(b.um("SELECT name FROM sqlite_master WHERE name = 'ix_revisoes_op_rev'"))
            self.assertIn(str(oid), b.um("SELECT valor FROM meta WHERE chave = 'revisoes_duplicadas'")["valor"])
        finally:
            b.fechar()
        self.s.banco = Banco(caminho)   # tearDown fecha


if __name__ == "__main__":
    unittest.main()
