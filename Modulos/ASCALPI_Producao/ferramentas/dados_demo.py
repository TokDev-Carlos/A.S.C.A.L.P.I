"""Cria uma pasta de dados de DEMONSTRAÇÃO (livro sintético, sem dados reais) para testar a tela na nuvem.

Uso:  python ferramentas/dados_demo.py <pasta_destino>
Depois: python -m ascalpi_producao --dados <pasta_destino> servir --porta 8765
Precisa de openpyxl (só para montar o livro sintético).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ascalpi_producao import legado  # noqa: E402
from ascalpi_producao.servico import Servico  # noqa: E402
from tests.apoio import criar_controle, criar_livro  # noqa: E402


def main(destino: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        origem = Path(tmp)
        criar_livro(origem, "OK-CIDADE_TESTE_O.P.xlsx", "CIDADE TESTE-RJ")
        criar_livro(origem, "OK-OUTRA_CIDADE_O.P.xlsx", "OUTRA CIDADE-SP")
        criar_controle(origem)
        s = Servico(Path(destino))
        s.salvar_config({"publicar": False})
        for linha in legado.importar_pasta(s.banco, origem, Path(destino)):
            print(linha)
        print("PRÓXIMA O.P.:", s.proximo_numero())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dados_demo")
