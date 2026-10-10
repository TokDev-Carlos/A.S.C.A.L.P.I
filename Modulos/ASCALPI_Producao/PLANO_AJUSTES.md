# ASCALPI Produção — ajustes depois da base

A versão `producao-base-inicial-v1` (commit `fb96a58`) está **congelada e aceita pelo Carlos**. Registro: `docs/producao/releases/BASE_INICIAL.md`.

## Organização (10/10/2026)

Branches e regras de colaboração: `REGRAS_CENTRAIS.md`; estado das tarefas: `QUADRO_TAREFAS.md`. Fluxo (ordens ORG-2/ORG-3): `temporária → executora → modulo/producao-op → Dev-Work → main`. O G1 segue na executora `claude/producao`; a antiga branch solta foi encerrada e preservada na tag `historico/2026-10-09/g1-edicao-modelo`.

## Plano vigente

O plano de evolução é do Codex: `PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md` (nesta pasta). Este arquivo só dá a ordem de leitura e o estado.

| Marco | Conteúdo | Estado |
|---|---|---|
| G0 | Validar e congelar a base | **Aprovado**; tag `producao-base-inicial-v1` no GitHub |
| Estabilização | Proteção do XLSX emitido (ressalva 1) | Encerrada: edição foi pelo sistema (REV), comportamento previsto |
| G1 | Editar modelo no Excel (cópia de trabalho, nova versão) | **ACEITO pelo Admin** (10/10/2026); DE ACORDO do Codex (`0ac1f8a`, `955826a`). Integração no módulo: candidato `claude/temp/integracao-g1` em revisão; pendente MEL-G1-01 (fluxo pela tela na instalação única, roteiro `docs/producao/roteiros/G1_EDICAO_MODELOS_ANGRA.md`) |
| G2 | Paginação pela altura original das linhas | **EM REVISÃO** (`e800f30` na `claude/producao`, por ordem do Admin); aguarda V-G2. O aceite do G1 não aprova o G2 |
| G3 | Catálogo mestre por ATA e adesões parciais | Bloqueado (aguarda aceite do G2) |
| G4 | Variantes 1.1 / 1.2 sobre o código-base | Bloqueado |
| G5 | Integração com flags e aceite final | Bloqueado |

## Regras de execução (resumo do plano do Codex)

- Claude implementa em commits pequenos, com teste; o Codex revisa e valida depois das entregas.
- Nada de `main` nem de `dados/`, banco ou documentos de cliente no GitHub. A pasta `D:\Programas` é desenvolvimento e homologação (pode reimportar e regerar a base de teste); o legado VBA do servidor não é tocado.
- Altura de linha nunca é inventada nem reescalada; saldo nunca mistura contratos; `0.x` segue como extra sem saldo.
- A cada fase: atualizar `CONTINUAR.md`, registrar SHA e testes, pedir aceite ao Carlos.
- Fluxo até o teste: nuvem (Claude) → revisão (Codex) → hierarquia de branches → `Sincronizar_ASCALPI.cmd` no clone único → teste funcional no Windows com Excel → resultado no quadro. WSL é só laboratório (não vale como aceite).

## Material histórico

Tag histórica `historico/2026-10-09/codex-revisao-r01-r09` (`4b90e72`): revisão sobre `b691e8e` (R01–R09, já corrigidos na base). Consultar somente quando solicitado. `reproduzir_achados.py` não roda mais contra a base (código reorganizado); use a suíte em `tests/`.
