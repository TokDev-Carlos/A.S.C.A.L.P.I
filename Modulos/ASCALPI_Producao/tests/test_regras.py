import unittest
from datetime import date

from ascalpi_producao import regras as r


class TestRegras(unittest.TestCase):
    def test_nome_arquivo(self):
        self.assertEqual(r.montar_nome_base("007-26", "CAXIAS-RJ", "PRAÇA São João/2", "MOB", "CARBONO"),
                         "007-26 - CAXIAS-RJ - PRACA Sao Joao 2 - MOB - CARBONO")
        self.assertLessEqual(len(r.montar_nome_base("1", "C", "X" * 400, "MOB", "INOX")), 180)

    def test_tipo_material(self):
        self.assertEqual(r.tipo_arquivo("abrigo de ônibus"), "ABRIGO")
        self.assertEqual(r.tipo_arquivo("PLACAS"), "PLACA")
        self.assertEqual(r.tipo_arquivo("MOB"), "MOB")
        self.assertEqual(r.detectar_material(["BALANÇO INOX", "GANGORRA"], "MOB"), "CARBONO+INOX")
        self.assertEqual(r.detectar_material(["BALANÇO INOX"], "MOB"), "INOX")
        self.assertEqual(r.detectar_material(["GANGORRA"], "MOB INOX"), "CARBONO+INOX")
        self.assertEqual(r.detectar_material(["GANGORRA"], "MOB"), "CARBONO")

    def test_prazo(self):
        self.assertEqual(r.interpretar_prazo("2026-10-30"), date(2026, 10, 30))
        self.assertEqual(r.interpretar_prazo("30/10/2026"), date(2026, 10, 30))
        self.assertEqual(r.interpretar_prazo("definir"), "DEFINIR")
        with self.assertRaises(ValueError):
            r.interpretar_prazo("")

    def test_numeracao(self):
        self.assertEqual(r.formatar_numero(7, 2026), "007-26")
        self.assertEqual(r.proximo_numero(["255-26", "023", "300-25"], 2026), 256)
        self.assertEqual(r.proximo_numero([], 2027), 1)

    def test_codigos(self):
        self.assertEqual(r.codigo_base("2.1"), "2")
        self.assertEqual(r.codigo_base("0.3"), "0.3")
        self.assertEqual(r.normalizar_codigo(2.0), "2")
        self.assertEqual(r.normalizar_codigo("8,1"), "8.1")
        self.assertTrue(r.ignora_checagem("0.1"))
        self.assertEqual(r.normalizar_cabecalho("DATA ENTREGA\r\nATUALIZADA"), "DATA ENTREGA ATUALIZADA")

    def test_saldo(self):
        itens = {"1": r.SaldoItem("1", "A", 60, 49), "8": r.SaldoItem("8", "B", 60, 115),
                 "3": r.SaldoItem("3", "C", 10, 10), "4": r.SaldoItem("4", "D", 0, 5)}
        self.assertEqual(itens["1"].saldo(), 11)
        self.assertEqual(itens["8"].saldo(), -55)
        self.assertEqual(itens["3"].saldo(), "ACABOU")
        self.assertEqual(itens["4"].saldo(), 0)
        sim = r.simular_saldo(itens, {"1": 11})
        self.assertEqual(sim.status, r.SALDO_ENCERRADO)
        sim = r.simular_saldo(itens, {"1": 2, "3": 1})
        self.assertEqual(sim.status, r.SALDO_NEGATIVO)
        self.assertTrue(sim.exige_confirmacao)
        self.assertIn("encerrado", sim.negativos[0].depois)
        self.assertEqual(r.simular_saldo(itens, {"9": 1}).status, "ESTRUTURA_INVALIDA")
        self.assertEqual(r.agregar_por_base([("2", "1"), ("2.1", "1,5"), ("x", 1), ("3", "")]),
                         ({"2": 2.5}, ["CÓDIGO INVÁLIDO OU VAZIO: 'x'."]))


if __name__ == "__main__":
    unittest.main()
