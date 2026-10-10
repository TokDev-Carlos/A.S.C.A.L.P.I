# V-INT-G1 — Parecer final do candidato 5effc0c (Windows)

**Data:** 10/10/2026  
**Revisor:** Codex/ChatGPT  
**Parecer:** **DE ACORDO PARA INTEGRAR EXCLUSIVAMENTE G1** em `modulo/producao-op` pelo Claude, seguindo `REGRAS_CENTRAIS.md` §5. **Não é aceite de G2, nem prova de edição Excel pela GUI no computador.**

## Escopo e SHA

- Candidato completo revisado: `5effc0cce09847e87654f2bdaab1633c9344df68`, branch `claude/temp/integracao-g1`.
- SHA anterior `7d6af89`: falhava no Windows no teste de bootstrap (`python` do PATH = alias Microsoft Store, exit 9009).
- Patch aplicado pelo Claude em `a12f8d2`: `tests/test_sincronizar.py` usa `sys.executable`; roteiro Angra passou a chamar o mesmo interpretador Python real dos lançadores do módulo, com orientação `py -3` se necessário; docstring do sincronizador coerente.
- Com `git merge-base --is-ancestor`, confirmei **G1 `955826a` presente** e **G2 `e800f30` ausente**. A árvore do candidato não contém `ascalpi_producao/paginacao.py`.
- A branch integrada `modulo/producao-op` continha apenas documentação/quadro mais recente; o candidato deve ser integrado pelo dono da entrega por merge `--no-ff`, seguido de suíte verde no merge, **sem mesclar o PR #5 inteiro**, que inclui o G2.

## Verificação independente realmente executada

**Ambiente:** Windows do Admin (DESKTOP-NAFCJHM), interpretador `C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe`.

**Método:** `git fetch origin --prune`, `git archive 5effc0c` em `TemporaryDirectory` descartável, execução dos testes diretamente nos arquivos exatos do SHA revisado. **Não alterei o checkout da instalação única, o banco `dados/`, os modelos de Angra nem o VBA da empresa.** A pasta temporária de teste foi removida automaticamente.

```bat
"C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe" -m unittest -v tests.test_sincronizar
"C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe" -m unittest discover -s tests -t .
```

Resultados:

- **8/8 testes do sincronizador OK**, exit 0, `Ran 8 tests in 11.489s`. Abrange gate de SHA exato, SHA inexistente, backup de dados, falha de `pull`, árvore local suja, porta ocupada, restrição de branch e bootstrap externo com Python correto.
- **117/117 testes totais OK**, exit 0, `Ran 117 tests in 58.997s`. Os 8 anteriores estão incluídos nos 117, não são adicionais.
- Conferência do clone canônico ao final: `D:\Programas\ASCALPI_Project`, branch `modulo/producao-op`, HEAD `7231955b785f6797cf53d2177a14bb6a3e682012`, **status limpo**. Apenas `git fetch` atualizou referências remotas, sem `pull` e sem migração local.
- Evidência local: `D:\Programas\ASCALPI_Local_Archive\consolidacao_20261010\revisao_final_g1_5effc0c.log`.

## Decisão e continuidade

**DE ACORDO (INT-G1):** Claude está autorizado **tecnicamente** a realizar o merge `--no-ff` de `5effc0c` para `modulo/producao-op`, reaplicando a suíte no commit resultante e publicando o SHA resultante no `QUADRO_TAREFAS.md`. O próprio Claude é o dono da entrega e realiza o merge. **Não tocar `Dev-Work`/`main` e não integrar G2**.

**MEL-G1-01 continua EM REVISÃO até o teste funcional:** após a integração, o Windows deve sincronizar o SHA autorizado com backup de `dados/` **antes da migração de esquema 6→7**, testar `O.P-ATA-ANGRA-MOB` e `O.P-ATA-ANGRA-PLACAS` com o Microsoft Excel aberto fisicamente pela interface (começar, abrir, salvar, validar, publicar/descartar), conferir O.P. antiga e a nova. Registrar resultados separados; H-1 ainda pendente.

**Limites:** testes automatizados foram executados com código isolado no Windows, não executei ainda botão real de abrir o Excel, não alterei a base de homologação e não aprovei G2.

**Parecer final:** DE ACORDO — candidato `5effc0c`.