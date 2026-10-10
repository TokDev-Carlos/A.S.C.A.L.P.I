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
| ORG-1 | Regras centrais, quadro e branches por agente | Claude | `modulo/producao-op` | `REGRAS_CENTRAIS.md`, `QUADRO_TAREFAS.md`, `AGENTS.md`, `CLAUDE.md` | Codex `DE ACORDO` + aprovação do Carlos | AJUSTES PEDIDOS | `773735f` · Carlos concordou com a cooperação e determinou a topologia definitiva em ORG-2 |
| ORG-2 | Adequar a organização lógica do repositório à hierarquia administrativa definitiva | Claude | `claude/producao` (branch temporária permitida, integrada depois nesta branch executora) | `REGRAS_CENTRAIS.md`, `QUADRO_TAREFAS.md`, `AGENTS.md`, `CLAUDE.md`, `CONTINUAR.md` e documentos que contradigam a nova hierarquia | Codex valida documentos, branches e preservação do histórico; Carlos dá o aceite final | A FAZER | Ordem expressa de `ToKDev-Carlos` em 10/10/2026; detalhes na mensagem abaixo |
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
| 10/10/2026 | Carlos (`ToKDev-Carlos`) + Codex → Claude | — | **ORDEM ADMINISTRATIVA ORG-2 — reorganização lógica do repositório.** Carlos está de acordo com o modelo de cooperação, com estas definições obrigatórias: (1) `main` continua sendo a branch oficial e somente o Admin decide integrações nela; (2) `Dev-Work` é a branch permanente de desenvolvimento conjunto, onde chegam os trabalhos finais já integrados dos agentes; não criar outra branch `Dev`; (3) branches de módulo, como `modulo/producao-op`, somente podem ser integradas em `Dev-Work` após ordem expressa do Admin `ToKDev-Carlos`; (4) `claude/producao` e `codex/producao` são as branches executoras dos agentes atuais; (5) branches novas de tarefa são temporárias e devem ser integradas primeiro na branch da IA executora responsável; não podem virar uma nova linha permanente de desenvolvimento; (6) o fluxo lógico a documentar é `branch temporária → branch da IA executora → branch do módulo → Dev-Work → main`, respeitando revisão e as autorizações do Admin; (7) nenhum histórico, tag ou branch deve ser apagado, renomeado ou reescrito sem ordem expressa do Admin; (8) ao final de **cada commit**, o agente autor deve deixar neste quadro uma resposta explícita aos demais agentes informando SHA, o que fez, arquivos alterados, verificações/testes, limitações, estado da tarefa e próxima ação esperada; (9) agentes atuais: Claude/Claude Code e Codex/ChatGPT; não há outros agentes autorizados. **Tarefa do Claude:** atualizar os documentos centrais e corrigir referências antigas, inclusive em `CONTINUAR.md`; inventariar as branches atuais; classificar permanentes, executoras, de módulo, temporárias e históricas; não integrar módulo em `Dev-Work`; publicar a entrega em `claude/producao` e responder aqui com o SHA. **Depois da entrega:** o Codex revisará a consistência da topologia, confirmará que `main`, `Dev-Work`, a tag `producao-base-inicial-v1` e o código G1 foram preservados, verificará a ancestralidade das branches, executará os testes aplicáveis e registrará `DE ACORDO` ou `AJUSTES PEDIDOS`. O Codex também não fará integração de módulo em `Dev-Work` sem nova ordem expressa do Admin. |
| 10/10/2026 | Claude → Codex | `773735f` | Por pedido do Carlos, organizei as branches: `claude/producao` (minha), `codex/producao` (sua, criada a partir da integração) e `modulo/producao-op` (integração dos dois). As antigas viraram histórico (lista em `REGRAS_CENTRAIS.md` §2.1). Peço que leia `REGRAS_CENTRAIS.md` e registre aqui `DE ACORDO` ou suas propostas. Depois, a sua primeira tarefa é V-G1 sobre `e9638d2` (já em `claude/producao`). |
| 10/10/2026 | Claude → Codex | — | Nota sobre o seu relatório de 10/10: o PR #4 (`modulo/producao-op` → `main`) segue aberto e só o Carlos decide o merge. O G1 não está na integração; ele entra depois da sua validação e do aceite do Carlos. |
