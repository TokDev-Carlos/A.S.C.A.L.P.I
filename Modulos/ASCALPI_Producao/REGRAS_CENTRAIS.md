# ASCALPI Produção — Regras Centrais de Colaboração (Claude ⇄ Codex)

> **Versão:** 1 · 10/10/2026 · **Estado:** PROPOSTA DO CLAUDE, aguardando o "DE ACORDO" do Codex e a aprovação do Carlos (seção 12).
> **Vale para:** todo trabalho no módulo `Modulos/ASCALPI_Producao` e nos documentos `docs/producao/`.
> **Precedência:** decisão registrada do Carlos > **este documento** > `CLAUDE.md` / `AGENTS.md` > planos de marco (`PLANO_POS_BASELINE_*`, `PLANO_AJUSTES.md`) > `Codex_Plano_para_Claude.md` (histórico). Em conflito entre documentos, vale o de maior precedência e o conflito é anotado no `QUADRO_TAREFAS.md`.

## 1. Quem é quem

| Papel | Quem | Responsabilidade |
|---|---|---|
| **Dono do produto** | Carlos | Decide regras de negócio, aprova marcos, libera a próxima etapa, é o único que integra na `main` e o único que autoriza mexer em dados reais ou no PC/Windows. |
| **Implementação** | Claude (Claude Code) | Escreve e corrige o código do módulo, os testes de cada correção e a documentação de estado (`CONTINUAR.md`). |
| **Validação e revisão** | Codex (GPT) | Testes de validação, revisão técnica independente, reprodução de falhas, testes no Windows/Excel quando o Carlos autorizar. Implementa código **só** quando uma tarefa do quadro for atribuída a ele pelo Carlos. |

Decisão vigente do Carlos (09/10/2026): Claude implementa; Codex faz testes de validação e revisão depois de cada entrega.

## 2. Mapa das branches

Três branches de trabalho. Todo o resto é histórico.

| Branch | Dono | Para quê | Quem pode dar push |
|---|---|---|---|
| **`claude/producao`** | Claude | Trabalho do Claude (implementação dos marcos G1–G5 e correções). | Só o Claude |
| **`codex/producao`** | Codex | Trabalho do Codex (testes de validação, relatórios de revisão, reproduções, tarefas que o Carlos atribuir a ele). | Só o Codex |
| **`modulo/producao-op`** | Compartilhada | **Desenvolvimento integrado**: onde o trabalho dos dois se junta e é testado em conjunto. É a origem do PR #4 para a `main`. | Claude e Codex, **só** por merge commit de integração (seção 4) e pelo `QUADRO_TAREFAS.md` |
| `main` | Carlos | Versão oficial do repositório. | Só o Carlos (merge do PR #4 ou de PRs futuros) |

Referência imutável: tag **`producao-base-inicial-v1`** → `fb96a58` (base aceita, G0). **Nunca mover nem recriar.**

### 2.1 Branches antigas (somente leitura)

Ficam no repositório como histórico. **Ninguém trabalha nelas.** Apagar só com autorização do Carlos.

| Branch | Situação |
|---|---|
| `ajustes/g1-edicao-modelo` | G1 do Claude; conteúdo levado para `claude/producao` (mesmo commit `e9638d2`). |
| `codex/apoio-producao` | Entrega do Codex (R06/R08/R09, testes R07); já integrada na `modulo/producao-op` (PR #3). |
| `Codex_Rev` | Auditoria histórica do Codex sobre `b691e8e` (R01–R09). Fica como registro; novos pareceres vão para `codex/producao`. |
| `codex/revisao-plano-op-2026-10-09` | Primeira entrega da revisão do Codex; substituída por `Codex_Rev`. |
| `Dev-Work` | Fora deste acordo (trabalho anterior do Carlos, não é do módulo de Produção). Não tocar. |

## 3. Ciclo de uma tarefa

1. **Registrar** a tarefa no `QUADRO_TAREFAS.md` (na `modulo/producao-op`): ID, dono, branch, arquivos que vai tocar, critério de aceite. Tarefa que muda regra de negócio só entra com a decisão do Carlos anotada.
2. **Sincronizar** a branch própria com a integração antes de começar: `git merge origin/modulo/producao-op` (merge, nunca rebase de algo já publicado).
3. **Trabalhar** só na branch própria, em commits pequenos, um assunto por commit, com teste junto.
4. **Verificar** antes de pedir integração: suíte inteira verde (`python -m unittest discover -s tests -t .`, dentro de `Modulos/ASCALPI_Producao`) e, se mexeu na interface, capturas 1366 px e 390 px com o console do navegador limpo.
5. **Pedir revisão**: mudar o estado no quadro para `EM REVISÃO`, com SHA, testes executados e limitações. O outro agente revisa a partir do SHA (não da descrição).
6. **Integrar** (seção 4) e marcar `INTEGRADO` no quadro com o SHA do merge.
7. **Aceite do Carlos** quando a tarefa fecha um marco (G1, G2, …): estado `ACEITO`. Só então o marco seguinte é liberado.

Estados possíveis no quadro: `A FAZER` → `EM ANDAMENTO` → `EM REVISÃO` → `AJUSTES PEDIDOS` (volta para o dono) → `INTEGRADO` → `ACEITO`. Também `BLOQUEADO` (com o motivo).

## 4. Regras de integração na `modulo/producao-op`

- Entrada **só por merge commit** (`git merge --no-ff`) de `claude/producao` ou `codex/producao`. Nada de rebase, `--force`, `reset` ou reescrever histórico em branch compartilhada.
- Condições para integrar uma entrega:
  1. a branch de origem está sincronizada com a integração (sem conflito pendente);
  2. suíte inteira verde **depois** do merge (rodar de novo no resultado);
  3. revisão do outro agente registrada no quadro (`DE ACORDO` ou ajustes já feitos). Exceção: documentação pura e o próprio quadro.
- **Quem integra:** o dono da entrega, depois da revisão. O revisor não integra a entrega do outro.
- Commit direto na `modulo/producao-op` só para: o `QUADRO_TAREFAS.md` e correção de texto em documentação. Código nunca.
- Integração que deixa a suíte vermelha é desfeita com `git revert` do merge (nunca apagando histórico) e a tarefa volta para `AJUSTES PEDIDOS`.
- **`main`:** só o Carlos. Os agentes não fazem merge na `main`, não aprovam PR e não abrem PR novo sem pedido dele. O PR #4 continua aberto até o Carlos decidir.

## 5. Propriedade de arquivos

- Cada tarefa do quadro lista os arquivos que vai alterar. **Um arquivo de código tem um único dono por vez** (o dono da tarefa ativa que o lista).
- Precisa mexer num arquivo de outro dono: anotar o pedido no quadro; o dono faz, ou os dois combinam a troca no quadro.
- Arquivos novos de teste do Codex ficam em `tests/` com nomes próprios (ex.: `tests/test_validacao_<tema>.py`). Testes de algo ainda não implementado entram com `@unittest.expectedFailure` e o ID da tarefa no nome; o Claude remove a marcação quando entrega.
- **Nenhum teste é apagado ou enfraquecido** para fazer a suíte passar. Teste errado é corrigido com justificativa no commit e anotado no quadro.

## 6. Comunicação

- **Canal único:** `Modulos/ASCALPI_Producao/QUADRO_TAREFAS.md` na `modulo/producao-op` (estado das tarefas + registro de mensagens entre os agentes, com data, autor e SHA).
- Relatórios longos de revisão: arquivo em `docs/producao/revisao/` na `codex/producao`, com link no quadro.
- `Codex_Plano_para_Claude.md` fica como histórico (R01–R09 e changelog até 09/10/2026). Novas mensagens vão para o quadro.
- Cada agente, ao começar uma sessão: ler este documento, o quadro e o `git log` da integração desde o último SHA que conhece.
- Toda afirmação de "feito" ou "passou" traz o SHA e o comando executado. O que não foi verificado é dito como não verificado.

## 7. Regras do produto que nenhum dos dois muda sozinho

- Nome do sistema: **ASCALPI**. Português do Brasil; mensagens do sistema em MAIÚSCULAS.
- Só biblioteca padrão do Python no módulo; HTML/CSS/JS puros, sem build. `openpyxl` só em `tests/` e `ferramentas/`.
- O sistema controla tudo: numeração `NNN-AA` (reinicia por ano), contratos/saldo, histórico, revisões.
- `.xlsx` de O.P. emitida é 100% bloqueado; o **modelo** editável (G1) é outra coisa e nunca se confunde com O.P. emitida.
- Saldo: `0` se montante ≤ 0, senão `montante − (quant + previsão)`; `ACABOU` em zero; negativo exige confirmação; `2.1` conta na base `2`; saldos de contratos diferentes nunca se misturam.
- `0.x` = extra: conta na O.P., não precisa estar no contrato, não tem saldo.
- Data de criação da O.P. é imutável; cada revisão registra a sua data.
- Histórico imutável: O.P. emitida conserva contrato, modelo, textos, fotos e documentos da emissão; nada é sobrescrito no lugar.
- Paginação (G2): altura de linha, fonte, imagem e ordem nunca são inventadas, reescaladas ou reordenadas.
- Migrações de banco: só expansivas e auditáveis; nunca apagam histórico para satisfazer restrição; ambiguidade vira pendência para o Carlos.
- Contratos: o montante editado no sistema prevalece sobre a planilha na reimportação; contrato de O.P. ambígua só o Carlos decide.

## 8. Segurança e dados

- Repositório **público**: nunca commitar dados de clientes, livros reais, `dados/`, bancos `.db*`, `config.json`, senhas, tokens, hashes de senha, caminhos de servidor ou mídias reais. Só dados sintéticos.
- Nunca gravar em `D:\MACROS\Legacy_Modules` nem nos `.xlsm` legados.
- PC/Windows do Carlos: instalação, reimportação de livros reais, alteração do banco operacional e remoção de arquivos só com autorização explícita dele, caso a caso. Sempre backup antes.
- Não acessar o repositório de credenciais (Chaves-Tokens) nem diretórios de outros projetos.

## 9. Testes e evidências

- Toda correção ou funcionalidade nasce com teste que falha antes e passa depois.
- Suíte leve completa verde antes de pedir revisão e depois de integrar. Sem testes pesados.
- Interface: capturas 1366 px e 390 px, console limpo (erros esperados, como conflito 409 simulado, são citados no quadro).
- Excel/Windows é a referência para PDF e paginação; LibreOffice ou mock não provam igualdade visual.
- Revisão do Codex registra: SHA examinado, testes rodados, achados com reprodução e risco, veredito (`DE ACORDO`, `AJUSTES PEDIDOS` ou `BLOQUEANTE`).

## 10. Commits

- Mensagem curta em português, prefixo `feat|fix|test|docs|refactor(producao): …`.
- Terminar com as linhas de coautoria e sessão que o ambiente de cada agente exige.
- Não incluir identificador de modelo de IA em mensagens de commit, código ou documentos.

## 11. Proibido para os dois agentes

- Push na `main`; merge na `main`; mover ou recriar a tag `producao-base-inicial-v1`.
- Push na branch do outro agente.
- `push --force`, rebase ou reset de qualquer branch publicada.
- Apagar branch, tag ou teste sem autorização do Carlos.
- Começar o marco seguinte sem o `ACEITO` do Carlos no anterior.
- Mudar regra de negócio sem decisão do Carlos registrada no quadro.

## 12. Aceite deste documento

| Quem | Situação | Data | Observações |
|---|---|---|---|
| Claude | PROPOSTO | 10/10/2026 | Versão 1 |
| Codex | PENDENTE | — | Ler e registrar `DE ACORDO` ou propostas de mudança (no quadro, seção "Mensagens") |
| Carlos | PENDENTE | — | Aprovar a versão final |

Mudanças neste documento: proposta no quadro → acordo dos dois agentes → aprovação do Carlos → nova versão aqui (com número e data).
