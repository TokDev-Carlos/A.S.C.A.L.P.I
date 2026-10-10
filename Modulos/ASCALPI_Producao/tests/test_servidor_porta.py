"""Instância única: uma 2ª abertura do servidor na mesma porta não sobe outro processo sobre a mesma base."""
import io
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from ascalpi_producao import __main__ as principal
from ascalpi_producao.servico import Servico
from ascalpi_producao.servidor import ServidorExclusivo, servir


class TestPortaExclusiva(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Servico(Path(self.tmp.name) / "dados")
        self.httpd = servir(self.s, porta=0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.porta = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.s.banco.fechar()
        self.tmp.cleanup()

    def test_segunda_instancia_na_mesma_porta_falha(self):
        with self.assertRaises(OSError):
            servir(self.s, porta=self.porta)

    def test_no_windows_pede_a_porta_exclusiva(self):
        pedidos = []

        class Soquete:
            def setsockopt(self, nivel, opcao, valor):
                pedidos.append((opcao, valor))
        falso = ServidorExclusivo.__new__(ServidorExclusivo)
        falso.socket = Soquete()
        with patch("ascalpi_producao.servidor.os.name", "nt"), \
                patch("ascalpi_producao.servidor.socket.SO_EXCLUSIVEADDRUSE", -5, create=True), \
                patch("ascalpi_producao.servidor.ThreadingHTTPServer.server_bind") as bind:
            falso.server_bind()
        self.assertEqual(pedidos, [(-5, 1)])
        bind.assert_called_once()

    def test_comando_servir_avisa_e_nao_abre_outro_servidor(self):
        erro = io.StringIO()
        with redirect_stderr(erro), patch("webbrowser.open") as abrir:
            codigo = principal.main(["--dados", str(Path(self.tmp.name) / "outra"), "servir",
                                     "--porta", str(self.porta), "--abrir"])
        self.assertEqual(codigo, 3)
        self.assertIn("JÁ EXISTE UM PROGRAMA USANDO A PORTA", erro.getvalue())
        abrir.assert_called_once_with(f"http://127.0.0.1:{self.porta}/")


if __name__ == "__main__":
    unittest.main()
