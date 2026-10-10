# ASCALPI Produção — instruções para o Codex (e outros agentes)

Antes de qualquer ação neste módulo, leia nesta ordem:

1. `REGRAS_CENTRAIS.md` — regras comuns Claude ⇄ Codex: branches, papéis, integração, proibições. **Tem precedência sobre os demais documentos** (abaixo só das ordens do Admin).
2. `QUADRO_TAREFAS.md` — tarefas, donos, estados e mensagens entre os agentes (canal único).
3. `docs/producao/releases/BASE_INICIAL.md` — base aceita (tag `producao-base-inicial-v1`).
4. `PLANO_AJUSTES.md` e `PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md` — marcos G1–G5.
5. `CONTINUAR.md` — estado técnico, API e teste local.

Resumo (ordem ORG-2 do Admin `ToKDev-Carlos`, 10/10/2026):

- Agentes autorizados: Claude/Claude Code (implementação, `claude/producao`) e Codex/ChatGPT (validação e revisão, `codex/producao`). Nenhum outro.
- Fluxo: `temporária → executora → modulo/producao-op → Dev-Work → main`. Temporárias nascem da sua executora (`codex/tmp-<tema>`) e voltam para ela.
- Na `modulo/producao-op`: só merge da sua entrega já revisada e atualizações do `QUADRO_TAREFAS.md`. Em `Dev-Work`: só com ordem expressa do Admin. Na `main`: nunca (só o Admin).
- Após **cada commit**, responder no quadro: SHA, o que fez, arquivos, testes, limitações, estado e próxima ação.
- Não apagar, renomear ou reescrever branch, tag ou histórico sem ordem expressa do Admin.

Testes: `cd Modulos/ASCALPI_Producao && python -m unittest discover -s tests -t .` (precisa de `openpyxl` só para os testes).
