# V-INT-G1 — Patch Windows de sincronização (7d6af89)

**Data:** 10/10/2026 · **Revisor:** Codex/ChatGPT. **Situação:** AJUSTE PONTUAL de portabilidade no candidato do Claude; patch testado, pendente aplicação na branch do proprietário.

## O que aconteceu

O Admin solicitou ao Codex corrigir os problemas da integração G1. Enquanto era iniciada a revisão, Claude publicou as duas correções originais em fd7e2dd, candidato 7d6af8912d7fa3d5451b2a74beff3e07b77aa4af. Evitei editar a branch/temporária de outro agente e revisei a nova entrega antes de duplicar trabalho.

A correção do **gate de SHA exato antes do pull**, do **snapshot antes da migração**, a separação G1/G2 e os testes de porta estão DE ACORDO do ponto de vista do código. Entretanto, o teste de bootstrap quebrou no PC Windows do Admin porque chama "python" ou "python3" por PATH, enquanto o Windows resolve o alias da Microsoft Store (código 9009). O roteiro de primeira execução tem a mesma fragilidade: chama "python" em vez do interpretador que existe no Windows do Admin.

## Falha reproduzida (candidato intocado)

Candidato obtido por git archive 7d6af89, em pasta temporária removida ao fim; interpretador Windows explícito:

    "C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe" -m unittest discover -s tests -t .

**Resultado:** Ran 117 tests in 58.170s — FAILED (failures=1).

Falha única: tests.test_sincronizar.TestSincronizar.test_primeiro_uso_pela_copia_do_commit_revisado; AssertionError: 9009 != 0; mensagem: Python não foi encontrado; atalho da Microsoft Store.

## Patch 1 — portabilidade do teste (aplicar pelo Claude)

Arquivo: Modulos/ASCALPI_Producao/tests/test_sincronizar.py

    import shutil
    import socket
    import sys            # ADICIONAR
    import subprocess

Trocar a chamada que contém:

    ["python3" if shutil.which("python3") else "python", str(externo),

pela chamada:

    [sys.executable, str(externo),

Assim o subprocesso usa o mesmo Python que executa a suíte, sem depender do PATH do Windows.

## Patch 2 — bootstrap documentado no roteiro Angra (aplicar pelo Claude)

Arquivo: Modulos/ASCALPI_Producao/docs/producao/roteiros/G1_EDICAO_MODELOS_ANGRA.md, seção 0, passo 3.

Substituir a linha que chama apenas python por:

    "C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe" "%TEMP%\sincronizar.py" --raiz "D:\Programas\ASCALPI_Project" --sha SHA_AUTORIZADO

SHA_AUTORIZADO é substituído pelo commit efetivamente aprovado. Este caminho é o interpretador já referenciado nos lançadores do módulo no PC do Admin. Para outro PC, o roteiro deve apontar ao Python efetivamente instalado; não supor que o alias da Microsoft Store funciona.

## Teste independente do patch (sem tocar na branch Claude)

Na cópia temporária do exato 7d6af89, substituí somente a linha de teste por sys.executable e executei:

- Exportação real do script por git show sob cmd.exe: exit 0, código Python válido com 7.171 bytes.
- Script exportado executado pelo Python explícito com --help: exit 0.
- python -m unittest -v tests.test_sincronizar: **8/8 OK**, 11.461 s, exit 0.
- python -m unittest discover -s tests -t .: **117/117 OK**, 58.892 s, exit 0.
- Ancestralidade: 955826a (G1) presente, e800f30 (G2) ausente.
- Pasta temporária removida, sem mudar o clone único, os 234 registros locais ou o banco; Excel Angra ainda não testado.

Evidência local: D:\Programas\ASCALPI_Local_Archive\consolidacao_20261010\revisao_fix_python_windows.log.

## Próximo passo

**Claude:** aplicar os dois patches na sua branch, executar a suíte, informar o novo SHA para revisão focalizada. Com DE ACORDO no SHA realmente publicado, realizar merge --no-ff somente do G1 ao módulo, rodar novamente a suíte e registrar no quadro. Não fazer merge de G2, Dev-Work ou main.

**Estado:** INT-G1 pendente deste ajuste pequeno. As correções originais estão tecnicamente validadas, mas o candidato 7d6af89 tal como publicado falha um teste no Windows, portanto ainda não recebeu DE ACORDO final.