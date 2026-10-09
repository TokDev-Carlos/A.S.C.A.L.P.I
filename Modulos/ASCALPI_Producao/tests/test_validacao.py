"""Contrato da validação pura; independente do backend de mutação do Claude."""
import unittest
from datetime import date

from ascalpi_producao.validacao import (ErroValidacao, booleano, corpo_objeto, data_iso,
    data_legada, inteiro_positivo, itens_op, motivo_obrigatorio, numero_finito, valor_acompanhamento)


class TestValidacao(unittest.TestCase):
    def test_corpo_objeto(self):
        self.assertEqual(corpo_objeto({"x": 1}), {"x": 1})
        for entrada in ([], None, "{}", 123, True):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                corpo_objeto(entrada)

    def test_booleano_estrito(self):
        self.assertTrue(booleano(True, "CONFIRMAR"))
        self.assertFalse(booleano(False, "CONFIRMAR"))
        self.assertTrue(booleano(None, "CONFIRMAR", True))
        for entrada in ("false", "true", "0", "1", 0, 1, [], {}):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                booleano(entrada, "CONFIRMAR")

    def test_inteiro_positivo(self):
        self.assertEqual(inteiro_positivo("010", "ID"), 10)
        self.assertEqual(inteiro_positivo(2.0, "LINHA"), 2)
        for entrada in (0, -1, True, False, 2.4, "2.5", "x", None, float("inf")):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                inteiro_positivo(entrada, "LINHA")

    def test_numero_finito_brasileiro(self):
        self.assertEqual(numero_finito("2,5", "QTD"), 2.5)
        self.assertEqual(numero_finito("1.234,50", "QTD"), 1234.5)
        self.assertEqual(numero_finito("12.5", "QTD"), 12.5)
        self.assertEqual(numero_finito("-2", "AJUSTE", negativo=True), -2)
        for entrada in (None, "", "   ", "NaN", "Infinity", float("inf"), float("nan"), True,
                        -1, "1,2,3", "1.23,5", [], {}):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                numero_finito(entrada, "QTD")

    def test_motivo_obrigatorio(self):
        self.assertEqual(motivo_obrigatorio("  ajuste justificado  "), "ajuste justificado")
        for entrada in (None, " ", 123, "a" * 201):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                motivo_obrigatorio(entrada)

    def test_data_iso_e_leitura_legada(self):
        self.assertEqual(data_iso("09/10/2026", "ENTREGA"), "2026-10-09")
        self.assertEqual(data_iso("2026-10-09", "ENTREGA"), "2026-10-09")
        self.assertIsNone(data_iso("", "ENTREGA"))
        self.assertEqual(data_legada("09/10/2026"), date(2026, 10, 9))
        for valor in ("2026-02-31", "31/02/2026", "DEFINIR", "2026/10/09", 123):
            with self.subTest(valor=valor), self.assertRaises(ErroValidacao):
                data_iso(valor, "ENTREGA")
            self.assertIsNone(data_legada(valor))

    def test_valor_acompanhamento(self):
        self.assertEqual(valor_acompanhamento("status_instalacao", "ok"), "OK")
        self.assertEqual(valor_acompanhamento("entrega_atualizada", "10/10/2026"), "2026-10-10")
        self.assertEqual(valor_acompanhamento("entrega_atualizada", "falta"), "FALTA")
        self.assertEqual(valor_acompanhamento("obs", " texto "), "texto")
        for campo, valor in (("status_instalacao", "CONCLUÍDO"), ("fotografico", "FALTA"),
                             ("material_obra", "CANCELADA"), ("entrega_atualizada", "2026-02-31"),
                             ("inexistente", "OK"), ("obs", "x" * 2001), ("fotografico", True)):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ErroValidacao):
                valor_acompanhamento(campo, valor)

    def test_itens_op_sem_repeticao(self):
        self.assertEqual(itens_op([{"linha": 10, "quantidade": "2,5", "observacao": " az "},
                                   {"linha": 11, "quantidade": 0},
                                   {"linha": 12, "quantidade": ""}]),
                         [{"linha": 10, "quantidade": 2.5, "inauguracao": "", "observacao": "az"}])
        for entrada in (None, {}, "a", [{"linha": 10, "quantidade": 1}, {"linha": 10, "quantidade": 2}],
                        [{"linha": True, "quantidade": 1}], [{"linha": 10, "quantidade": -1}],
                        [{"linha": 10, "quantidade": "NaN"}], [{"linha": 10, "quantidade": 1, "observacao": "x" * 201}],
                        [3]):
            with self.subTest(entrada=entrada), self.assertRaises(ErroValidacao):
                itens_op(entrada)


if __name__ == "__main__":
    unittest.main()
