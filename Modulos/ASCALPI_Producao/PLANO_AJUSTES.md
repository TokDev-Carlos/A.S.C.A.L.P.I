# ASCALPI Produção — ajustes depois da base

A versão `producao-base-inicial-v1` (commit `fb96a58`) está **congelada e aceita pelo Carlos**. Registro: `docs/producao/releases/BASE_INICIAL.md`.

## Organização (10/10/2026)

Branches e regras de colaboração: `REGRAS_CENTRAIS.md`; estado das tarefas: `QUADRO_TAREFAS.md`. O G1 segue na branch `claude/producao` (a `ajustes/g1-edicao-modelo` virou histórico).

## Plano vigente

O plano de evolução é do Codex: `PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md` (nesta pasta). Este arquivo só dá a ordem de leitura e o estado.

| Marco | Conteúdo | Estado |
|---|---|---|
| G0 | Validar e congelar a base | **Aprovado**; tag `producao-base-inicial-v1` no GitHub |
| Estabilização | Proteção do XLSX emitido (ressalva 1) | Encerrada: edição foi pelo sistema (REV), comportamento previsto |
| G1 | Editar modelo no Excel (cópia de trabalho, nova versão) | **Implementado** na branch `claude/producao` (antes `ajustes/g1-edicao-modelo`) (flag desligada por padrão); aguardando teste do Carlos no Windows e revisão do Codex |
| G2 | Paginação pela altura original das linhas | Bloqueado |
| G3 | Catálogo mestre por ATA e adesões parciais | Bloqueado |
| G4 | Variantes 1.1 / 1.2 sobre o código-base | Bloqueado |
| G5 | Integração com flags e aceite final | Bloqueado |

## Regras de execução (resumo do plano do Codex)

- Claude implementa em commits pequenos, com teste; o Codex revisa e valida depois das entregas.
- Nada de `main`, instalação no Windows, reimportação dos livros reais ou dados reais no GitHub.
- Altura de linha nunca é inventada nem reescalada; saldo nunca mistura contratos; `0.x` segue como extra sem saldo.
- A cada fase: atualizar `CONTINUAR.md`, registrar SHA e testes, pedir aceite ao Carlos.

## Material histórico

Branch `Codex_Rev`: revisão sobre `b691e8e` (R01–R09, já corrigidos na base). `reproduzir_achados.py` não roda mais contra a base (código reorganizado); use a suíte em `tests/`.
