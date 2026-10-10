"""Sincroniza o clone ÚNICO do ASCALPI com o commit **exato** autorizado no quadro (só biblioteca padrão).

Ordem (revisão V-INT-G1 do Codex): nada no checkout muda antes de provar que `origin/<branch>` é exatamente o SHA
autorizado. Só então: cópia de `dados` (com o ASCALPI fechado) → `git pull --ff-only` → confere `HEAD == SHA`.
Qualquer divergência encerra com código ≠ 0 e nunca anuncia sincronização.

Uso no PC (Windows):
    Sincronizar_ASCALPI.cmd <SHA autorizado>                            (branch padrão: modulo/producao-op)
Primeira vez (o clone ainda não tem este arquivo): rodar a cópia do commit revisado, sem checkout:
    git -C D:\\Programas\\ASCALPI_Project fetch origin --prune
    git -C D:\\Programas\\ASCALPI_Project show <SHA>:Modulos/ASCALPI_Producao/ferramentas/sincronizar.py > "%TEMP%\\sincronizar.py"
    "C:\\.Dev CJL\\3-Git_Main\\System\\Runtime\\Python\\python.exe" "%TEMP%\\sincronizar.py" --raiz D:\\Programas\\ASCALPI_Project --sha <SHA>
(usar o Python do projeto, não "python" do PATH: no Windows pode ser o atalho da Microsoft Store, erro 9009)
"""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BRANCH_PADRAO = "modulo/producao-op"
SAIDA_OK, SAIDA_RECUSADO, SAIDA_FALHA = 0, 2, 1


class Recusado(Exception):
    """Pré-condição não atendida: nada foi alterado."""


class Falha(Exception):
    """Erro durante a sincronização (o checkout pode não estar no SHA pedido)."""


def _git(raiz: Path, *args: str, checar: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True)
    if checar and r.returncode != 0:
        raise Falha(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def _commit(raiz: Path, ref: str) -> str | None:
    r = subprocess.run(["git", "-C", str(raiz), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def porta_em_uso(porta: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, porta)) == 0


def _conferir_copia(origem: Path, destino: Path) -> int:
    def mapa(p: Path) -> dict[str, int]:
        return {str(f.relative_to(p)): f.stat().st_size for f in p.rglob("*") if f.is_file()}
    a, b = mapa(origem), mapa(destino)
    if a != b:
        raise Falha(f"CÓPIA DE DADOS INCOMPLETA ({len(b)} DE {len(a)} ARQUIVOS). NADA FOI SINCRONIZADO.")
    return len(a)


def sincronizar(raiz: Path, sha: str, branch: str = BRANCH_PADRAO, dados: Path | None = None,
                arquivo: Path | None = None, porta: int = 8765, autorizado_admin: bool = False,
                confirmar=input, falar=print) -> str:
    """Devolve o SHA completo sincronizado. Levanta Recusado (nada mudou) ou Falha."""
    raiz = Path(raiz).resolve()
    dados = Path(dados) if dados else raiz / "Modulos" / "ASCALPI_Producao" / "dados"
    arquivo = Path(arquivo) if arquivo else raiz.parent / "ASCALPI_Local_Archive" / "snapshots_dados"
    if not sha:
        raise Recusado("INFORME O SHA AUTORIZADO NO QUADRO (--sha). SEM SHA NADA É SINCRONIZADO.")
    if branch != BRANCH_PADRAO and not autorizado_admin:
        raise Recusado(f"SÓ A BRANCH {BRANCH_PADRAO} É SINCRONIZADA SEM ORDEM DO ADMIN (--autorizado-admin).")
    if _git(raiz, "rev-parse", "--is-inside-work-tree", checar=False) != "true":
        raise Recusado(f"{raiz} NÃO É UM CLONE GIT.")
    antes = _git(raiz, "rev-parse", "HEAD")
    atual = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD")
    falar(f"CLONE  : {raiz}\nBRANCH : {atual} -> {branch}\nHEAD   : {antes[:7]}")
    sujo = _git(raiz, "status", "--porcelain", "--untracked-files=no")
    if sujo:
        raise Recusado("HÁ ALTERAÇÕES LOCAIS EM ARQUIVOS DO GIT. NADA FOI FEITO:\n" + sujo)
    if porta_em_uso(porta):
        raise Recusado(f"O ASCALPI (OU OUTRO PROGRAMA) ESTÁ ABERTO NA PORTA {porta}. FECHE E RODE DE NOVO.")

    # 1) provar o SHA ANTES de mexer no checkout (fetch só atualiza refs remotas)
    _git(raiz, "fetch", "origin", "--prune")
    remoto = _commit(raiz, f"origin/{branch}")
    if not remoto:
        raise Recusado(f"A BRANCH origin/{branch} NÃO EXISTE.")
    pedido = _commit(raiz, sha)
    if not pedido:
        raise Recusado(f"O SHA {sha} NÃO EXISTE NO REPOSITÓRIO. CONFIRA NO QUADRO.")
    if pedido != remoto:
        raise Recusado(f"origin/{branch} ESTÁ EM {remoto[:7]}, NÃO NO SHA AUTORIZADO {pedido[:7]}. "
                       "SÓ O SHA EXATO É ACEITO (ANCESTRAL OU MAIS NOVO NÃO). NADA FOI ALTERADO.")
    falar(f"AUTORIZADO: {pedido[:7]} = origin/{branch}")
    if pedido == antes:
        falar("O CLONE JÁ ESTÁ NO SHA AUTORIZADO. NADA A FAZER.")
        return pedido
    if confirmar("Guardar cópia de dados e sincronizar agora? (S/N) ").strip().upper() not in ("S", "SIM"):
        raise Recusado("CANCELADO PELO USUÁRIO. NADA FOI ALTERADO.")

    # 2) cópia da base de homologação (ASCALPI fechado → arquivos do SQLite consistentes)
    if dados.exists():
        destino = arquivo / f"dados_{datetime.now():%Y%m%d-%H%M%S}_{antes[:7]}"
        shutil.copytree(dados, destino)
        n = _conferir_copia(dados, destino)
        falar(f"CÓPIA DE DADOS: {destino} ({n} ARQUIVOS CONFERIDOS)")
    else:
        falar(f"SEM PASTA DE DADOS EM {dados} (NADA A COPIAR).")

    # 3) avançar só por fast-forward e conferir o resultado
    if atual != branch:
        _git(raiz, "switch", branch)
    _git(raiz, "pull", "--ff-only", "origin", branch)
    depois = _git(raiz, "rev-parse", "HEAD")
    if depois != pedido:
        raise Falha(f"DEPOIS DO PULL O CLONE ESTÁ EM {depois[:7]}, NÃO EM {pedido[:7]}. NÃO TESTE; AVISE NO QUADRO.")
    falar(f"SINCRONIZADO: {antes[:7]} -> {depois[:7]} ({branch}). REGISTRE ESTE SHA NO QUADRO.")
    return depois


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sincroniza o clone único do ASCALPI com o SHA autorizado.")
    ap.add_argument("--sha", default="", help="SHA autorizado no QUADRO_TAREFAS.md (obrigatório)")
    ap.add_argument("--branch", default=BRANCH_PADRAO)
    ap.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument("--dados", type=Path, default=None)
    ap.add_argument("--arquivo", type=Path, default=None)
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--autorizado-admin", action="store_true", help="outra branch, por ordem expressa do Admin")
    ap.add_argument("--sim", action="store_true", help="não perguntar (uso em teste)")
    a = ap.parse_args(argv)
    try:
        sincronizar(a.raiz, a.sha, a.branch, a.dados, a.arquivo, a.porta, a.autorizado_admin,
                    confirmar=(lambda _m: "S") if a.sim else input)
        return SAIDA_OK
    except Recusado as e:
        print(f"RECUSADO: {e}", file=sys.stderr)
        return SAIDA_RECUSADO
    except Falha as e:
        print(f"FALHA: {e}", file=sys.stderr)
        return SAIDA_FALHA


if __name__ == "__main__":
    sys.exit(main())
