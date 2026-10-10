# ASCALPI Produção — instruções para o Codex (e outros agentes)

Antes de qualquer ação neste módulo, leia nesta ordem:

1. `REGRAS_CENTRAIS.md` — regras comuns Claude ⇄ Codex: branches, papéis, integração, proibições. **Tem precedência sobre os demais documentos** (abaixo só das decisões do Carlos).
2. `QUADRO_TAREFAS.md` — tarefas, donos, estados e mensagens entre os agentes (canal único).
3. `docs/producao/releases/BASE_INICIAL.md` — base aceita (tag `producao-base-inicial-v1`).
4. `PLANO_AJUSTES.md` e `PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md` — marcos G1–G5.
5. `CONTINUAR.md` — estado técnico, API e teste local.

Resumo do seu papel (decisão do Carlos de 09/10/2026): **validação e revisão**. Sua branch de trabalho é `codex/producao`; não dê push em `claude/producao` nem em `main`; na `modulo/producao-op` só merge de integração da sua própria entrega revisada e atualizações do `QUADRO_TAREFAS.md`.

Testes: `cd Modulos/ASCALPI_Producao && python -m unittest discover -s tests -t .` (precisa de `openpyxl` só para os testes).
