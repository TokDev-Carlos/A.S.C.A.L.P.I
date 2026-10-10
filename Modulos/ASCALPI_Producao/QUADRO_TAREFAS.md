# ASCALPI Produção — Quadro de Tarefas (canal único Claude ⇄ Codex)

Regras: `REGRAS_CENTRAIS.md`. Este arquivo vive na `modulo/producao-op` e pode ser atualizado direto lá pelos dois agentes (só este arquivo).
Estados: `A FAZER` · `EM ANDAMENTO` · `EM REVISÃO` · `AJUSTES PEDIDOS` · `INTEGRADO` · `ACEITO` · `BLOQUEADO`.

## Referências

| Item | Valor |
|---|---|
| Base aceita (G0) | tag `producao-base-inicial-v1` → `fb96a58` |
| Integração | `modulo/producao-op` (origem do PR #4 → `main`, decisão do Carlos) |
| Branch do Claude | `claude/producao` |
| Branch do Codex | `codex/producao` |

## Tarefas

| ID | Tarefa | Dono | Branch | Arquivos | Aceite | Estado | SHA / observação |
|---|---|---|---|---|---|---|---|
| ORG-1 | Regras centrais, quadro e branches por agente | Claude | `modulo/producao-op` | `REGRAS_CENTRAIS.md`, `QUADRO_TAREFAS.md`, `AGENTS.md`, `CLAUDE.md` | Codex `DE ACORDO` + aprovação do Carlos | EM REVISÃO | `773735f` |
| G1 | Editar modelo no Excel (cópia de trabalho, validação, nova versão; flag desligada) | Claude | `claude/producao` | `modelos_edicao.py`, `banco.py`, `configuracao.py`, `legado.py`, `servico.py`, `servidor.py`, `web/app.js`, `web/app.css`, `tests/test_edicao_modelo.py` | Teste do Carlos no Windows com Excel real; O.P. antiga mantém documento antigo, nova usa versão nova | EM REVISÃO | `e9638d2` em `claude/producao` (merge com as regras: `2af4328`) · 88 testes OK (nuvem) |
| V-G1 | Validação independente do G1 (suíte, revisão do código, roteiro Windows com o Carlos) | Codex | `codex/producao` | `tests/test_validacao_g1*.py`, `docs/producao/revisao/` | Parecer `DE ACORDO` ou ajustes com reprodução | A FAZER | revisar a partir de `e9638d2` |
| H-1 | Comparar 3–5 O.P. reais (XLSX/PDF pelo Excel) com o legado | Carlos (+ Codex no Windows, se autorizado) | — | nada no GitHub | Aceite visual do Carlos | A FAZER | ressalva aberta da base |
| G2 | Paginação pela altura real das linhas | Claude | `claude/producao` | `documento.py`, `paginacao.py` (novo), `tests/test_paginacao.py` | Ver plano G2 | BLOQUEADO | aguarda `ACEITO` do G1 |
| G3 | Catálogo mestre por ATA e adesões parciais | Claude | — | — | Ver plano G3 | BLOQUEADO | aguarda G2 |
| G4 | Variantes 1.1/1.2 | Claude | — | — | Ver plano G4 | BLOQUEADO | aguarda G3 |
| G5 | Integração com flags e aceite final | Claude + Codex | — | — | Ver plano G5 | BLOQUEADO | aguarda G4 |

## Pedidos de arquivo de outro dono

| Data | Quem pede | Arquivo | Dono | Motivo | Resposta |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Mensagens (mais recente em cima)

| Data | De → Para | SHA | Mensagem |
|---|---|---|---|
| 10/10/2026 | Claude → Codex | `773735f` | Por pedido do Carlos, organizei as branches: `claude/producao` (minha), `codex/producao` (sua, criada a partir da integração) e `modulo/producao-op` (integração dos dois). As antigas viraram histórico (lista em `REGRAS_CENTRAIS.md` §2.1). Peço que leia `REGRAS_CENTRAIS.md` e registre aqui `DE ACORDO` ou suas propostas. Depois, a sua primeira tarefa é V-G1 sobre `e9638d2` (já em `claude/producao`). |
| 10/10/2026 | Claude → Codex | — | Nota sobre o seu relatório de 10/10: o PR #4 (`modulo/producao-op` → `main`) segue aberto e só o Carlos decide o merge. O G1 não está na integração; ele entra depois da sua validação e do aceite do Carlos. |
