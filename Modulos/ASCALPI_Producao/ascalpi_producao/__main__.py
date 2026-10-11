"""ASCALPI Produção — módulo independente de Ordens de Produção.

Uso:
  python -m ascalpi_producao importar --origem <pasta com OK-*.xlsm e Controle> [--previa] [--dados <pasta>]
  python -m ascalpi_producao servir [--dados <pasta>] [--porta 8765] [--abrir]
  python -m ascalpi_producao documento --op 258-26 --formato pdf --saida <arquivo> [--dados <pasta>]
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from . import __version__


def pasta_dados_padrao() -> Path:
    if os.environ.get("ASCALPI_PRODUCAO_DADOS"):
        return Path(os.environ["ASCALPI_PRODUCAO_DADOS"])
    return Path(__file__).resolve().parent.parent / "dados"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ascalpi_producao", description="ASCALPI Produção " + __version__)
    ap.add_argument("--dados", type=Path, default=None, help="pasta de dados (banco, modelos, documentos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("importar", help="importa modelos, contratos/saldos e histórico dos arquivos legados")
    imp.add_argument("--origem", type=Path, required=True)
    imp.add_argument("--previa", action="store_true", help="mostra o que mudaria, sem gravar nada")
    sv = sub.add_parser("servir", help="abre o sistema no navegador")
    sv.add_argument("--porta", type=int, default=8765)
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--abrir", action="store_true")
    dc = sub.add_parser("documento", help="gera o xlsx/pdf de uma O.P.")
    dc.add_argument("--op", required=True, help="número (ex.: 258-26) ou id")
    dc.add_argument("--formato", choices=("xlsx", "pdf"), default="pdf")
    dc.add_argument("--saida", type=Path)
    args = ap.parse_args(argv)

    from .servico import Servico
    dados = (args.dados or pasta_dados_padrao()).resolve()
    servico = Servico(dados)

    if args.cmd == "importar":
        from .legado import importar_pasta
        if not args.origem.is_dir():
            print(f"PASTA DE ORIGEM NÃO ENCONTRADA: {args.origem}", file=sys.stderr)
            return 2
        for linha in importar_pasta(servico.banco, args.origem, dados, previa=args.previa):
            print(linha)
        if not args.previa:
            print(f"PRÓXIMA O.P.: {servico.proximo_numero()}")
        return 0

    if args.cmd == "documento":
        alvo = servico.banco.um("SELECT id FROM ops WHERE numero = ? AND origem = 'SISTEMA' ORDER BY id DESC",
                                (args.op,)) or ({"id": int(args.op)} if args.op.isdigit() else None)
        if not alvo:
            print("O.P. NÃO ENCONTRADA.", file=sys.stderr)
            return 2
        nome, conteudo = servico.gerar_documento(alvo["id"], args.formato)
        destino = args.saida or Path(nome)
        destino.write_bytes(conteudo)
        print(destino)
        return 0

    from .servidor import servir
    url = f"http://{args.host}:{args.porta}/"
    try:
        httpd = servir(servico, args.host, args.porta)
    except OSError:
        # já existe um ASCALPI (ou outro programa) nesta porta: não abre um 2º servidor sobre a mesma base
        print(f"JÁ EXISTE UM PROGRAMA USANDO A PORTA {args.porta}. SE FOR O ASCALPI, ELE JÁ ESTÁ ABERTO: {url}",
              file=sys.stderr)
        if args.abrir:
            webbrowser.open(url)
        servico.banco.fechar()
        return 3
    print(f"ASCALPI Produção {__version__} — {url}  (dados: {dados})  Ctrl+C para sair")
    if args.abrir:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        servico.banco.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
