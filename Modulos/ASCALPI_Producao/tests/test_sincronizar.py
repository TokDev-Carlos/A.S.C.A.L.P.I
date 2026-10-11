"""INT-G1-01/02 (Codex): sincronizar só com o SHA EXATO autorizado, provado antes de mexer no checkout."""
import io
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ferramentas import sincronizar as sinc

BRANCH = "modulo/producao-op"


def git(pasta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(pasta), *args], check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(shutil.which("git"), "git indisponível")
class TestSincronizar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.origem, self.autor, self.clone = base / "origem.git", base / "autor", base / "Programas" / "ASCALPI_Project"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origem)], check=True)
        subprocess.run(["git", "init", "-q", "-b", BRANCH, str(self.autor)], check=True)
        for p in (self.autor,):
            git(p, "config", "user.email", "t@t"), git(p, "config", "user.name", "t")
        (self.autor / ".gitignore").write_text("Modulos/ASCALPI_Producao/dados/\n")
        self.a = self._commit("a.txt", "A")
        git(self.autor, "remote", "add", "origin", str(self.origem))
        git(self.autor, "push", "-q", "origin", BRANCH)
        self.clone.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", "-q", "-b", BRANCH, str(self.origem), str(self.clone)], check=True)
        git(self.clone, "config", "user.email", "t@t"), git(self.clone, "config", "user.name", "t")
        self.dados = self.clone / "Modulos" / "ASCALPI_Producao" / "dados"
        self.dados.mkdir(parents=True)
        (self.dados / "ascalpi_producao.db").write_bytes(b"banco de homologacao")
        (self.dados / "Modelos").mkdir()
        (self.dados / "Modelos" / "m.xlsx").write_bytes(b"x" * 100)
        self.b = self._commit("b.txt", "B", empurrar=True)          # origin/modulo avança para B
        self.arquivo = base / "Programas" / "ASCALPI_Local_Archive" / "snapshots_dados"
        self.porta = self._porta_livre()

    def tearDown(self):
        self.tmp.cleanup()

    def _commit(self, nome, texto, empurrar=False):
        (self.autor / nome).write_text(texto)
        git(self.autor, "add", "-A")
        git(self.autor, "commit", "-q", "-m", texto)
        if empurrar:
            git(self.autor, "push", "-q", "origin", BRANCH)
        return git(self.autor, "rev-parse", "HEAD")

    @staticmethod
    def _porta_livre():
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _rodar(self, *args):
        saida, erro = io.StringIO(), io.StringIO()
        with redirect_stdout(saida), redirect_stderr(erro):
            codigo = sinc.main(["--raiz", str(self.clone), "--arquivo", str(self.arquivo),
                                "--porta", str(self.porta), "--sim", *args])
        return codigo, saida.getvalue() + erro.getvalue()

    def _head(self):
        return git(self.clone, "rev-parse", "HEAD")

    def _sem_copia(self):
        self.assertFalse(self.arquivo.exists() and any(self.arquivo.iterdir()))

    # (a) ancestral ≠ HEAD remoto → recusa ANTES do pull, checkout intocado
    def test_a_sha_ancestral_e_recusado_antes_do_pull(self):
        codigo, texto = self._rodar("--sha", self.a[:7])
        self.assertEqual(codigo, sinc.SAIDA_RECUSADO, texto)
        self.assertIn("SÓ O SHA EXATO É ACEITO", texto)
        self.assertEqual(self._head(), self.a)
        self._sem_copia()
        self.assertNotIn("SINCRONIZADO", texto)

    # (b) SHA ausente ou que não existe → recusa
    def test_b_sha_ausente_ou_inexistente_e_recusado(self):
        for args in ((), ("--sha", "0123abc"), ("--sha", "e" * 40)):
            codigo, texto = self._rodar(*args)
            self.assertEqual(codigo, sinc.SAIDA_RECUSADO, (args, texto))
            self.assertEqual(self._head(), self.a)
        self._sem_copia()

    # (c) SHA exato, checkout limpo, servidor fechado → cópia conferida, avança e confere HEAD
    def test_c_sha_exato_sincroniza_e_guarda_copia_dos_dados(self):
        codigo, texto = self._rodar("--sha", self.b[:7])
        self.assertEqual(codigo, sinc.SAIDA_OK, texto)
        self.assertEqual(self._head(), self.b)
        self.assertIn(f"SINCRONIZADO: {self.a[:7]} -> {self.b[:7]}", texto)
        copias = list(self.arquivo.iterdir())
        self.assertEqual(len(copias), 1)
        self.assertTrue(copias[0].name.endswith("_" + self.a[:7]))
        self.assertEqual((copias[0] / "ascalpi_producao.db").read_bytes(), b"banco de homologacao")
        self.assertEqual((self.dados / "ascalpi_producao.db").read_bytes(), b"banco de homologacao")  # dados intocados
        codigo, texto = self._rodar("--sha", self.b)                  # de novo: nada a fazer
        self.assertEqual(codigo, sinc.SAIDA_OK)
        self.assertIn("JÁ ESTÁ NO SHA AUTORIZADO", texto)

    # (d) pull falha → nunca anuncia sucesso
    def test_d_pull_que_falha_nunca_anuncia_sincronizacao(self):
        (self.clone / "local.txt").write_text("divergente")              # commit local não publicado
        git(self.clone, "add", "local.txt")
        git(self.clone, "commit", "-q", "-m", "local")
        codigo, texto = self._rodar("--sha", self.b)
        self.assertEqual(codigo, sinc.SAIDA_FALHA, texto)
        self.assertNotIn("SINCRONIZADO", texto)
        self.assertIn("pull --ff-only", texto)

    def test_alteracao_local_versionada_e_recusada(self):
        (self.clone / "a.txt").write_text("mexido")
        codigo, texto = self._rodar("--sha", self.b)
        self.assertEqual(codigo, sinc.SAIDA_RECUSADO)
        self.assertIn("ALTERAÇÕES LOCAIS", texto)
        self._sem_copia()

    def test_ascalpi_aberto_na_porta_e_recusado(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", self.porta))
            s.listen()
            codigo, texto = self._rodar("--sha", self.b)
        self.assertEqual(codigo, sinc.SAIDA_RECUSADO)
        self.assertIn("PORTA", texto)
        self.assertEqual(self._head(), self.a)

    def test_outra_branch_so_com_ordem_do_admin(self):
        codigo, texto = self._rodar("--sha", self.b, "--branch", "claude/producao")
        self.assertEqual(codigo, sinc.SAIDA_RECUSADO)
        self.assertIn("ORDEM DO ADMIN", texto)

    def test_primeiro_uso_pela_copia_do_commit_revisado(self):
        """INT-G1-02: rodar o arquivo tirado do commit (fora do clone) com --raiz faz a cópia antes do pull."""
        externo = Path(self.tmp.name) / "temp" / "sincronizar.py"
        externo.parent.mkdir()
        shutil.copy(Path(sinc.__file__), externo)
        r = subprocess.run([sys.executable, str(externo),   # o mesmo Python da suíte (no Windows, "python" do PATH pode ser o atalho da Store)
                             "--raiz", str(self.clone),
                            "--arquivo", str(self.arquivo), "--porta", str(self.porta), "--sha", self.b, "--sim"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CÓPIA DE DADOS", r.stdout)
        self.assertEqual(self._head(), self.b)


if __name__ == "__main__":
    unittest.main()
