# ASCALPI Produção — Regras Centrais de Colaboração (Claude ⇄ Codex)

> **Versão:** 3 · 10/10/2026 · ordens administrativas **ORG-2/ORG-3** do Admin `ToKDev-Carlos`.
> **Estado:** ORG-2 entregue pelo Claude em `b9ae904`; padrão final de nomes e preservação histórica em tags aplicado pelo Codex por ordem do Admin (seção 13).
> **Vale para:** todo trabalho no módulo `Modulos/ASCALPI_Producao` e nos documentos `docs/producao/`.
> **Precedência:** ordem/decisão registrada do Admin > **este documento** > `CLAUDE.md` / `AGENTS.md` > planos de marco (`PLANO_POS_BASELINE_*`, `PLANO_AJUSTES.md`) > `CONTINUAR.md` > `Codex_Plano_para_Claude.md` (histórico). Em conflito, vale o de maior precedência, e o conflito é anotado no quadro.

## 1. Quem é quem

| Papel | Quem | Responsabilidade |
|---|---|---|
| **Admin / dono do produto** | Carlos (`ToKDev-Carlos`) | Decide regras de negócio, aprova marcos, **ordena** integrações em `Dev-Work` e decide integrações na `main`. Único que autoriza apagar, renomear ou reescrever branch, tag ou histórico, e executar ações no PC/Windows (sincronizar o clone, reorganizar pastas, testes com Excel). O legado VBA do servidor não é tocado por ninguém. |
| **Agente executor de implementação** | Claude / Claude Code | Implementa código, testes de cada correção e documentação de estado. Branch executora: `claude/producao`. |
| **Agente executor de validação e revisão** | Codex / ChatGPT | Testes de validação, revisão independente, reprodução de falhas, testes no Windows/Excel quando o Admin autorizar. Implementa código **só** quando uma tarefa do quadro for atribuída a ele pelo Admin. Branch executora: `codex/producao`. |

**Não há outros agentes autorizados.** Um agente novo só entra por ordem expressa do Admin, registrada aqui e no quadro.

## 2. Hierarquia de branches

### 2.1 Fluxo lógico (sempre nesta ordem)

```
branch temporária ──► branch da IA executora ──► branch do módulo ──► Dev-Work ──► main
 (tarefa, curta)        claude/producao            modulo/producao-op   (conjunto)   (oficial)
                        codex/producao
```

| Passo | Quem faz | Condição |
|---|---|---|
| temporária → executora | o agente dono da temporária | suíte verde; um assunto por branch |
| executora → módulo | o agente dono da entrega | revisão do outro agente registrada no quadro (seção 5) |
| módulo → `Dev-Work` | só com **ordem expressa do Admin** registrada no quadro | módulo revisado e aceito; suíte verde |
| `Dev-Work` → `main` | **somente o Admin** decide | — |

### 2.2 Classes de branch

| Classe | Branch | Papel | Quem pode dar push |
|---|---|---|---|
| **Oficial (permanente)** | `main` | Versão oficial do repositório | Só o Admin |
| **Desenvolvimento conjunto (permanente)** | `Dev-Work` | Onde chegam os trabalhos finais já integrados dos módulos. **Não criar outra branch `Dev`.** | Só por ordem expressa do Admin |
| **Módulo** | `modulo/producao-op` | Integração do módulo de Produção: junta e testa o trabalho dos dois agentes. | Claude e Codex, só por merge commit de entrega revisada (seção 5) e pelo `QUADRO_TAREFAS.md` |
| **Executora** | `claude/producao` | Linha de trabalho do Claude | Só o Claude |
| **Executora** | `codex/producao` | Linha de trabalho do Codex | Só o Codex |
| **Temporária** | `claude/temp/<tema>` · `codex/temp/<tema>` | Uma tarefa curta, criada **a partir da executora do mesmo agente** e integrada de volta **nela**. Nunca vira linha permanente nem recebe trabalho de outro agente. Depois de integrada, seu SHA final é preservado por tag quando necessário e a branch é removida com autorização do Admin. | Só o agente dono |
| **Histórico** | tag anotada `historico/AAAA-MM-DD/<nome>` | Referência imutável de trabalho encerrado. Não é branch, não recebe commits e só é consultada quando solicitada. | Ninguém move ou recria; criação/remoção só por ordem do Admin |

Referência imutável: tag **`producao-base-inicial-v1`** → `fb96a58` (base aceita, G0). **Nunca mover, recriar nem apagar.**

### 2.3 Padrão obrigatório de nomes

Somente estes nomes ou prefixos são permitidos:

- `main`;
- `Dev-Work`;
- `modulo/*`;
- `claude/*`;
- `codex/*`.

Não criar branches soltas como `ajustes/*`, `feature/*`, `fix/*`, `Codex_Rev` ou qualquer nome sem o responsável e o nível do fluxo. Agente novo recebe prefixo próprio somente por ordem do Admin. Branch temporária usa obrigatoriamente `claude/temp/*` ou `codex/temp/*`.

### 2.4 Preservação e encerramento de branches

Quando uma branch temporária ou histórica não for mais necessária:

1. confirmar o SHA final e que nenhum trabalho ativo depende dela;
2. confirmar a integração ou registrar por que ela é somente referência;
3. criar tag **anotada** `historico/AAAA-MM-DD/<nome>` no SHA final;
4. conferir a tag no remoto e o SHA apontado;
5. remover a branch remota somente após ordem expressa do Admin;
6. registrar tag, SHA e remoção no `QUADRO_TAREFAS.md`.

Tags históricas são somente para consulta quando solicitada. Nunca são origem de merge automático. Qualquer recuperação nasce em nova branch temporária do agente responsável, a partir do SHA exato e com autorização do Admin.

### 2.5 Inventário ativo após a ORG-3

Contagens: commits à frente (+) e atrás (−) da `main`.

| Branch | SHA | Classe | Situação | vs `main` |
|---|---|---|---|---|
| `main` | `07b3611` | Oficial | Sem o módulo de Produção; ancestral de todas as abaixo | — |
| `Dev-Work` | `3a3946c` | Desenvolvimento conjunto | 3 commits próprios (bootstrap sanitizado de 31/08 e 01/09); **ainda sem o módulo**; integração só por ordem do Admin | +3 / −0 |
| `modulo/producao-op` | atualizado pela ORG-3 | Módulo | Base G0 + documentação de organização; origem do PR #4 (ver 2.6) | consultar Git |
| `claude/producao` | `b9ae904` na entrega ORG-2 | Executora (Claude) | Contém o **G1** (`e9638d2`) + entrega ORG-2; G1 ainda não integrado no módulo | consultar Git |
| `codex/producao` | atualizado pela ORG-3 | Executora (Codex) | Validação da ORG-2 e política final de branches/tags | consultar Git |
| tag `producao-base-inicial-v1` | `fb96a58` | Tag imutável | Base G0 aceita | — |

Histórico convertido em tags por ordem do Admin:

| Tag | SHA preservado | Origem encerrada |
|---|---|---|
| `historico/2026-10-09/g1-edicao-modelo` | `e9638d2` | `ajustes/g1-edicao-modelo` |
| `historico/2026-10-09/codex-apoio-producao` | `91f2864` | `codex/apoio-producao` |
| `historico/2026-10-09/codex-revisao-r01-r09` | `4b90e72` | `Codex_Rev` |
| `historico/2026-10-09/codex-primeira-revisao-plano` | `8662eae` | `codex/revisao-plano-op-2026-10-09` |

### 2.6 Ponto para decisão do Admin: PR #4

O PR #4 está aberto como `modulo/producao-op` → `main`, o que **pula a `Dev-Work`** no fluxo da seção 2.1. Os agentes não mexem nele. Cabe ao Admin decidir se o PR fica como está, é fechado ou é refeito como `modulo/producao-op` → `Dev-Work` quando ordenar essa integração.

## 3. Ciclo de uma tarefa

1. **Registrar** no `QUADRO_TAREFAS.md`: ID, dono, branch, arquivos, critério de aceite. Mudança de regra de negócio só entra com a decisão do Admin anotada.
2. **Sincronizar** a executora com o módulo antes de começar: `git merge origin/modulo/producao-op` (merge, nunca rebase de algo já publicado).
3. **Trabalhar** na executora ou numa temporária criada dela; commits pequenos, um assunto por commit, com teste junto.
4. **Responder no quadro após cada commit** (seção 7).
5. **Verificar** antes de pedir revisão: suíte inteira verde (`python -m unittest discover -s tests -t .`, dentro de `Modulos/ASCALPI_Producao`) e, se mexeu na interface, capturas 1366 px e 390 px com o console limpo.
6. **Pedir revisão**: estado `EM REVISÃO`, com SHA, testes e limitações. O outro agente revisa a partir do SHA, não da descrição.
7. **Integrar no módulo** (seção 5) e marcar `INTEGRADO`, com o SHA do merge.
8. **Aceite do Admin** quando a tarefa fecha um marco (G1, G2, …): estado `ACEITO`. Só então o marco seguinte é liberado.

Estados no quadro: `A FAZER` → `EM ANDAMENTO` → `EM REVISÃO` → `AJUSTES PEDIDOS` (volta ao dono) → `INTEGRADO` → `ACEITO`; também `BLOQUEADO` (com motivo).

## 4. Regras gerais de git

- Toda integração entre branches é por **merge commit** (`git merge --no-ff`). Nada de rebase, `--force`, `reset` ou reescrita de histórico em branch publicada.
- Branch temporária nasce da executora do mesmo agente, usa `claude/temp/*` ou `codex/temp/*` e volta para a executora. Nunca nasce de `main`, `Dev-Work` ou do módulo.
- Integração que deixa a suíte vermelha é desfeita com `git revert` do merge (nunca apagando histórico), e a tarefa volta para `AJUSTES PEDIDOS`.

## 5. Integração da executora no módulo (`modulo/producao-op`)

Condições:

1. a executora está sincronizada com o módulo (sem conflito pendente);
2. suíte verde **depois** do merge (rodar de novo no resultado);
3. revisão do outro agente registrada no quadro (`DE ACORDO` ou ajustes já feitos). Exceções: documentação pura e o próprio quadro.

Quem integra: o dono da entrega, depois da revisão; o revisor não integra a entrega do outro. Commit direto no módulo: só no `QUADRO_TAREFAS.md` e correção de texto em documentação. Código nunca.

## 6. `Dev-Work` e `main`

- `modulo/producao-op` → `Dev-Work`: **somente com ordem expressa do Admin registrada no quadro** (data, SHA de origem). O agente que receber a ordem faz o merge, roda a suíte e responde no quadro.
- `Dev-Work` → `main`: **somente o Admin**. Os agentes não fazem merge na `main`, não aprovam PR e não abrem PR novo sem pedido dele.

## 7. Comunicação

- **Canal único:** `Modulos/ASCALPI_Producao/QUADRO_TAREFAS.md` na `modulo/producao-op` (estado das tarefas + mensagens, com data, autor e SHA).
- **Resposta obrigatória após cada commit** (ordem ORG-2, item 8): o autor deixa no quadro uma mensagem aos demais agentes com:
  - SHA e branch;
  - o que fez;
  - arquivos alterados;
  - verificações e testes executados, com o resultado;
  - limitações e o que não foi verificado;
  - estado da tarefa;
  - próxima ação esperada e de quem.

  Vários commits seguidos de uma mesma entrega podem ser respondidos numa única mensagem que cite todos os SHAs. A mensagem é publicada por commit direto no quadro do módulo.
- Relatórios longos de revisão: arquivo em `docs/producao/revisao/` na `codex/producao`, com link no quadro.
- Ao começar uma sessão, cada agente lê este documento, o quadro e o `git log` do módulo desde o último SHA que conhece.
- Toda afirmação de "feito" ou "passou" traz o SHA e o comando executado. O que não foi verificado é dito como não verificado.

## 8. Propriedade de arquivos

- Cada tarefa do quadro lista os arquivos que vai alterar. **Um arquivo de código tem um único dono por vez.**
- Para mexer em arquivo de outro dono: pedido no quadro; o dono faz, ou os dois combinam a troca no quadro.
- Testes novos do Codex ficam em `tests/` com nomes próprios (ex.: `tests/test_validacao_<tema>.py`). Testes de algo ainda não implementado entram com `@unittest.expectedFailure` e o ID da tarefa no nome; o Claude remove a marcação quando entrega.
- **Nenhum teste é apagado ou enfraquecido** para fazer a suíte passar. Teste errado é corrigido com justificativa no commit e anotado no quadro.

## 9. Regras do produto que nenhum dos dois muda sozinho

- Nome do sistema: **ASCALPI**. Português do Brasil; mensagens do sistema em MAIÚSCULAS.
- Só biblioteca padrão do Python no módulo; HTML/CSS/JS puros, sem build. `openpyxl` só em `tests/` e `ferramentas/`.
- O sistema controla tudo: numeração `NNN-AA` (reinicia por ano), contratos/saldo, histórico, revisões.
- `.xlsx` de O.P. emitida é 100% bloqueado; o **modelo** editável (G1) é outra coisa e nunca se confunde com O.P. emitida.
- Saldo: `0` se montante ≤ 0, senão `montante − (quant + previsão)`; `ACABOU` em zero; negativo exige confirmação; `2.1` conta na base `2`; saldos de contratos diferentes nunca se misturam.
- `0.x` = extra: conta na O.P., não precisa estar no contrato, não tem saldo.
- Data de criação da O.P. é imutável; cada revisão registra a sua data.
- Histórico imutável: O.P. emitida conserva contrato, modelo, textos, fotos e documentos da emissão; nada é sobrescrito no lugar.
- Paginação (G2): altura de linha, fonte, imagem e ordem nunca são inventadas, reescaladas ou reordenadas.
- Migrações de banco: só expansivas e auditáveis; nunca apagam histórico para satisfazer restrição; ambiguidade vira pendência para o Admin.
- Contratos: o montante editado no sistema prevalece sobre a planilha na reimportação; contrato de O.P. ambígua só o Admin decide.

## 10. Segurança e dados

- Repositório **público**: nunca commitar dados de clientes, livros reais, `dados/`, bancos `.db*`, `config.json`, senhas, tokens, hashes de senha, caminhos de servidor ou mídias reais. Só dados sintéticos.
- Nunca gravar em `D:\MACROS\Legacy_Modules` nem nos `.xlsm` legados.
- **Classificação dos ambientes (Admin, 10/10/2026):** o uso real da empresa é o **legado VBA no servidor** — nenhum agente toca nele. Tudo em `D:\Programas` é **desenvolvimento e homologação**: a instalação única `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao` (clone Git) e a base `dados` de teste podem ser reiniciadas, migradas e regeradas; backup (em `D:\Programas\ASCALPI_Local_Archive`) só para recuperar testes. Não criar outra pasta de instalação para testar um marco: sincronizar o clone com o commit autorizado (`Sincronizar_ASCALPI.cmd`). Reorganizar pastas locais ou remover arquivos do PC continua dependendo de autorização do Admin.
- A base de homologação continua **fora do GitHub** (tem nomes de clientes, modelos e fotos).
- Não acessar o repositório de credenciais (Chaves-Tokens) nem diretórios de outros projetos.

## 11. Testes, evidências e commits

- Toda correção ou funcionalidade nasce com teste que falha antes e passa depois. Suíte leve completa verde antes de pedir revisão e depois de integrar. Sem testes pesados.
- Interface: capturas 1366 px e 390 px, console limpo; erros esperados, como o conflito 409 simulado, são citados no quadro.
- Excel/Windows é a referência para PDF e paginação; LibreOffice ou mock não provam igualdade visual.

### 11.1 Onde cada verificação vale (Admin, 10/10/2026)

| Ambiente | Serve para | Vale como aceite? |
|---|---|---|
| Nuvem (sessões Claude/Codex, Linux) | implementação, suíte, revisão, LibreOffice | não para Excel/PDF/Windows |
| **WSL (Ubuntu 24.04) no PC** | laboratório de apoio: testes rápidos, git, hashes, comparação com LibreOffice | **não** — Excel, PDF, caminhos do Windows, travas de arquivo e instalador só contam testados no Windows |
| **Windows + Microsoft Excel** (instalação única) | teste funcional, PDF oficial, paginação, abrir no Excel | **sim** |

- **Não rodar o banco em `/mnt/d` pelo WSL:** SQLite em modo WAL sobre o disco do Windows dá erro de I/O. No WSL, usar uma **cópia** da base dentro do Linux (ex.: `~/ascalpi_dados`), nunca a `dados` da instalação única aberta ao mesmo tempo pelo Windows.
- Fluxo definitivo: (1) Claude implementa e testa na nuvem; (2) Codex revisa e valida tecnicamente; (3) a entrega aprovada segue a hierarquia de branches; (4) o clone local é sincronizado com o commit autorizado; (5) testes funcionais no Windows com Excel; (6) resultados voltam ao GitHub e as correções seguem o mesmo ciclo.
- Ação no PC (git pull, Excel real) é pedida ao Admin com o comando exato; nenhum agente presume que foi feita.
- Revisão do Codex registra: SHA examinado, testes rodados, achados com reprodução e risco, veredito (`DE ACORDO`, `AJUSTES PEDIDOS` ou `BLOQUEANTE`).
- Commits: mensagem curta em português, prefixo `feat|fix|test|docs|refactor(producao): …`, terminando com as linhas de coautoria/sessão que o ambiente de cada agente exige. Sem identificador de modelo de IA em mensagens, código ou documentos.

## 12. Proibido para os dois agentes

- Push ou merge na `main`; abrir ou aprovar PR sem pedido do Admin.
- Integrar qualquer módulo na `Dev-Work` sem ordem expressa do Admin; criar outra branch `Dev`.
- Push na executora ou numa temporária do outro agente.
- Criar temporária fora da própria executora, ou mantê-la como linha permanente.
- Criar branch fora de `main`, `Dev-Work`, `modulo/*`, `claude/*` ou `codex/*`.
- Usar branch como arquivo histórico; trabalho encerrado é preservado por tag anotada e registrado no quadro.
- `push --force`, rebase ou reset de qualquer branch publicada.
- Apagar, renomear ou reescrever branch, tag ou histórico sem ordem expressa do Admin; mover ou recriar a tag `producao-base-inicial-v1`.
- Apagar ou enfraquecer teste.
- Começar o marco seguinte sem o `ACEITO` do Admin no anterior.
- Mudar regra de negócio sem decisão do Admin registrada no quadro.

## 13. Aceite deste documento

| Quem | Situação | Data | Observações |
|---|---|---|---|
| Admin (`ToKDev-Carlos`) | APROVOU a topologia e o padrão final de branches/tags (ORG-2/ORG-3) | 10/10/2026 | Somente cinco grupos: `main`, `Dev-Work`, `claude/*`, `codex/*`, `modulo/*` |
| Claude | Entregou a versão 2 | 10/10/2026 | `b9ae904` em `claude/producao` |
| Codex | DE ACORDO COM AJUSTE APLICADO | 10/10/2026 | Versão 3: nomes padronizados e histórico preservado em tags anotadas |

Mudanças neste documento: proposta no quadro → acordo dos dois agentes → aprovação do Admin → nova versão aqui (número e data).
