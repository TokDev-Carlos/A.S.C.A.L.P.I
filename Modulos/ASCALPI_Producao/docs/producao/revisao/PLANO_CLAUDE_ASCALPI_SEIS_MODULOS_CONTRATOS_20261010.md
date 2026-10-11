# ASCALPI — Plano executivo para Claude: seis módulos, Contratos separado e fonte única de Obras
**Ordem do Admin:** 10/10/2026 · **Dono da execução:** Claude / Claude Code · **Revisor independente:** Codex / GPT  
**Classe:** especificação aprovada como DIREÇÃO pelo Admin; regras novas com impacto em saldo, autorização ou migração exigem gate específico antes de entrar em produção.  
**Nome imutável:** **ASCALPI — Automation System for Logistical Advents and Industrial Processes**.  
**CJL System:** empresa/desenvolvedora; **não é** nome do produto.  
**Versão de trabalho:** `1.00.00.000`; NÃO incrementar BA/ES/IN/SE sem nova ordem do Admin. Referência vinculante: `D:\Programas\ASCALPI\Desenvolvimento\ASCALPI\version\readme.md`.  
**Entregável Windows pretendido:** `D:\Programas\ASCALPI\Desenvolvimento\ASCALPI\version\1.00.00.000`.  
**Natureza:** plano executável por etapas; a documentação NÃO constitui integração, teste, publicação nem homologação.

## 0. Leia primeiro e respeite a governança
1. `Modulos/ASCALPI_Producao/REGRAS_CENTRAIS.md`, `QUADRO_TAREFAS.md`, `AGENTS.md`, `CONTINUAR.md`, planos G1–G5.
2. Código remoto: `claude/producao` é propriedade de Claude; `codex/producao` é da revisão; `modulo/producao-op` só recebe entrega revisada (merge `--no-ff`, ou atualização documentada do quadro); `Dev-Work` somente por ordem expressa do Admin; `main` só o Admin.
3. Ponto de partida de Produção usado na candidata local: commit `0e404be0ba7732ce914ad309b1ead87eb011ba27` da linha Claude, **128 testes** na cópia. G1 integrado separadamente ao módulo; **não** introduzir G2 inadvertidamente pela mescla integral de `claude/producao` se ainda estiver em revisão.
4. A candidata local de integração não está no GitHub. Está em `D:\Programas\ASCALPI\Desenvolvimento\ASCALPI\version\1.00.00.000` e aparece como `?? version/` no worktree `codex/temp/unificacao-windows`. **Claude remoto/nuvem não pode assumir que possui esses arquivos.** Para implementar, obter conteúdo por acesso autorizado à pasta, ou receber uma cópia de código previamente saneada/revisada; NÃO publicar `Runtime/`, bancos, dados, livros ou todo `version/` no GitHub.
5. Preservar originais do CJL e da Produção, dados do usuário, O.P.s e modelo Excel emitidos. Não tocar VBA de uso real, migrar schema automaticamente nem reescrever identificadores da instalação/Host.
6. Identificar tarefas concorrentes em `web/app.js`, `servidor.py` e `servico.py` com G2/G3 antes de editar. Se houver conflito, implementar em tarefa/branch Claude isolada e registrar bloqueio; nunca misturar marcos sem autorização.

## 1. Decisão funcional do Admin — uma única aplicação, seis áreas
Menu principal SUPERIOR persistente, na ordem:
**INÍCIO | CONTRATOS | PRODUÇÃO | LOGÍSTICA | FINANCEIRO | ADMINISTRAÇÃO**.

Aba superior é **módulo**, submenu abaixo é **função**. A navegação não pode abrir outro produto, iniciar outro servidor ou criar cópia paralela de banco. A troca de módulo mantém contexto, estado de navegação e identidade do usuário. Quando serviço ainda não existir, apresentar *FUNCIONALIDADE EM PREPARAÇÃO*, com status visível e sem botões de gravação falsos. Não anunciar módulo inteiro como funcional por existir apenas a tela.

### 1.1 Domínios e autoridade de escrita
| Domínio | Autoridade de criação/edição | Quem consulta/solicita | Regra |
|---|---|---|---|
| Núcleo | Core ASCALPI | Todos os módulos | Identidade, sessão, RBAC/permissões, auditoria, configurações, atualização, versão, backup |
| Clientes/prefeituras | Cadastro corporativo canônico, **apresentado por Contratos** para gestão comercial; única API comum | Produção, Logística, Financeiro | Sem segundo cadastro; compatibilizar registros de `clientes` CJL e `prefeituras` Produção por IDs/mapeamento revisado |
| ATAs, contratos, adesões, vigências, aditivos | **Contratos** | Produção, Financeiro | Registro oficial e histórico imutável de alterações; não confundir ATA-mestre com contrato específico |
| Equipamentos contratados / catálogo da ATA | **Contratos** (catálogo/adesão contratual); Produção consume especificações da versão liberada | Produção | G3/G4 continuam marcos próprios; não simular implementação do catálogo mestre |
| Saldo contratual de itens e ajustes | **Contratos** (motor canônico e livro de movimentos) | Produção (valida e compromete mediante O.P.) | Uma regra de saldo, um evento de comprometimento; sem débito extra por expedição/entrega |
| Obras | **Produção** (API/cadastro oficial) | Logística, Financeiro | Obra pode existir sem O.P.; mesma obra reutilizada em múltiplas O.P.s e cargas |
| O.P. e revisões | **Produção** | Contratos (consumo), Logística (itens elegíveis) | O.P. emitida, numeração, documento, histórico e revisão imutáveis; Logística nunca publica/edita/cancela O.P. |
| Carregamentos, descarregamentos, veículos, motoristas, viagens, rotas, custos operacionais, anexos, evidências, entregas | **Logística** | Produção, Financeiro | Reaproveitar serviços CJL: NÃO reduzir Logística à tela de cargas simplificada da V1 |
| Finanças corporativas | **Financeiro** | Contratos/Logística | Não confundir saldo financeiro com saldo físico contratual |
| Usuários, autorização, auditoria, configurações técnicas | **Administração** usando **Core** | Todos | Permissões no servidor, não apenas esconder a aba |

**Ajuste de contexto essencial:** a frase “Logística recebe tudo que tinha no CJL menos Obras/O.P.” não deve mover autenticação, administração, auditoria, atualizador ou finanças corporativas para Logística. O que é transversal fica no Core; o financeiro é módulo próprio.

## 2. Contrato do fluxo entre módulos (não inventar uma segunda regra)
`Contratos → Produção → Logística → Financeiro` são responsabilidades, não quatro cópias dos dados.

**Saldo:** preservar fórmula e decisões atuais do módulo G0/G1: montante ≤ 0 → saldo 0; caso contrário `montante − (quant + previsão)`; código-base `2.1` consome base `2`; `0.x` é EXTRA sem saldo; negativo exige confirmação; saldo isolado por contrato; O.P. emitida preserva contrato e documentos. **Não implementar automaticamente nova semântica de reserva** (emissão vs aprovação vs publicação) sem especificar e obter aprovação formal, pois isso altera regra de negócio. No primeiro corte, Contratos muda *o lugar de apresentação e o limite de autoridade*, mantendo as funções/rotas e os resultados atuais.

**Nova obra solicitada pela Logística:**
1. Seleção de cliente/prefeitura e pesquisa de obra canônica (identidade estável, sem deduplicação automática por nome).
2. Se não existir, botão `NOVA OBRA` **dentro** do fluxo de carregamento; tela/diálogo corporativo reaproveita **o serviço Produção**; validar permissões, campos, clientes e conflitos no servidor.
3. Produção cria obra (uma única transação na fonte canônica), audita ator, origem da solicitação e ID; responde `obra_id` canônico.
4. Logística seleciona o novo `obra_id` e volta ao carregamento sem perder a edição em andamento.
5. **Criar obra NÃO cria O.P. automaticamente.** Ela pode ficar sem O.P.; somente carregar itens exige O.P. válida, contrato e elegibilidade física definidos.
6. Duplo clique/retry/duas estações não podem gerar duas obras; idempotência com chave de requisição e política verificável de duplicidades/409.
7. Falha do serviço Produção: mostrar erro, não gravar uma obra “provisória” exclusivamente no banco Logística; não iniciar carga dependente sem referência resolvida.

**O.P. e carregamento:**
- Identificar por `op_id` + `obra_id` + `contrato_id` + `item_id` ou chave estável de linha; `numero` textual não é FK global.
- Validar mesma prefeitura/cliente, vínculo da obra e estado da O.P.; não presumir que O.P. emitida significa equipamento fisicamente pronto.
- Contabilizar carregamentos parciais e múltiplas viagens sem ultrapassar quantidade elegível; definir `disponível para expedição` e política de bloqueios de O.P. revisada/cancelada.
- A V1 local usa `ascalpi_producao.db` + `integracao_ascalpi.db` separados. Transação entre eles **não é ACID**: tratar revisões e reservas com snapshots de itens, operações idempotentes e eventual reconciliação; nenhuma garantia irreal de atomicidade distribuída.
- Carregamento não debita novamente saldo contratual; entrega física e consumo por O.P. são indicadores distintos.

## 3. Telas e rotas / desenho da navegação
Proposta de rotas estáveis (escolher hash router ou path router conforme compatibilidade real do servidor):
- `/` ou `#/inicio` → indicadores gerais e atalhos; mostrar indicadores reais e estado dos serviços.
- `#/contratos` → painel contratual; submenus ATAs, Contratos, Adesões, Saldos, Vigências, Aditivos, Histórico (habilitar só o que existir).
- `#/producao` → Painel, Obras, O.P.s, Equipamentos/Modelos, Acompanhamento, Configuração de Produção.
- `#/logistica` → Painel, Novo Carregamento, Carregamentos, Descarregamentos, Frota, Motoristas, Viagens, Rotas, Custos Logísticos, Documentos/Evidências.
- `#/financeiro` → funcionalidades herdadas reais mapeadas do CJL; placeholder honesto nas ainda não integradas.
- `#/administracao` → Usuários, Perfis/Permissões, Auditoria, Configurações, Versões/Atualizações; **sem** apresentar endpoint não autenticado como administração efetiva.

Layout: marca ASCALPI (CJL System somente crédito da desenvolvedora); topo sticky sem se sobrepor ao conteúdo; seis abas clicáveis por teclado, foco/aria-current, contraste, estado ativo, atalho voltar, responsivo 1366px e 390px; no celular, menu responsivo acessível sem esconder o módulo ativo; subnavegação varia por módulo; cada ação tem loading/erro/sucesso; link para recurso existente preservado; telas sem função não expõem botões enganosos.

**Compatibilidade de rotas:** hoje a Produção usa `/`, `/api/modelos`, `/api/contratos`, `/api/contratos/{id}/saldo`, `/api/ops`, e a candidata local acrescenta `/integracao`, `/api/integracao/*`. Não quebrar chamadas e links existentes. Preferir fachada de Contratos por serviço reutilizando `Servico.contratos()`, `saldo_contrato()`, `ajustar_item()`, sem copiar a lógica para a UI. Centralizar permissões antes de habilitar gravações contratuais.

### 3.1 Fontes de código reais já identificadas
- Candidata local `...\version\1.00.00.000\iniciar.py`: servidor único e ponte Produção + Obras/Cargas.
- `...\version\1.00.00.000\integracao.py`: entidades locais `obras`, `op_obras`, `cargas`, `carga_itens`, `integracao_eventos`; **não é** fonte canônica definitiva.
- `...\version\1.00.00.000\web\integracao.html|js|css`: tela de Obras/Cargas; desmembrar responsavelmente entre Produção e Logística.
- `...\version\1.00.00.000\producao\ascalpi_producao\web\index.html|app.js|app.css`: menu atual da Produção e tela Saldos.
- `...\producao\ascalpi_producao\servidor.py`: rotas de contratos, saldos e O.P.; `servico.py`: implementação de contratos e débitos.
- CJL legado (fonte de consulta, **não sobrescrever**): `...\Desenvolvimento\CJL_Legado\System\App\Modulos\Obras\service.py`, `Carregamentos\service.py`, `Clientes`, `Custos`, `Frota`, `Rotas`, `Viagens`, `Anexos`, `Evidencias`, `Financeiro`, `Usuarios`, `Exportacao`, `Sistema`; `App\painel.py`, `Core\db.py`.
- `D:\Programas\ASCALPI\Homologacao\ASCALPI` atualmente é worktree `main` com README e metadados, **não** o software integrado; não confundir com destino da versão.

## 4. Pacotes de execução atribuídos ao Claude (ordem e critério)
**Arquivos definitivos/diffs são escolha do Claude após inspecionar o código; registrar dono único no quadro.** Toda etapa: commit pequeno, suíte verde, SHA no quadro, evidência e pedido de revisão. Critérios específicos:

| ID | Pacote | Entrega | Gate de aceite (Codex) |
|---|---|---|---|
| `MOD-00` | Congelar fontes e contratos | Matriz exata de APIs, tabelas, layouts, rutas, arquivos, G1/G2 e hashes; inventário das funções CJL | Sem operação em dados reais; baseline v1 arquivada; nenhuma funcionalidade existente apagada |
| `MOD-01` | **Shell e menu de seis módulos** | Layout superior comum Início/Contratos/Produção/Logística/Financeiro/Admin, submenus corretos e roteamento com deep links | Navegação teclado/móvel, ativo/foco, 1366 e 390, refresh/back/forward; não quebrar a O.P.; placeholders honestos |
| `MOD-02` | **Contratos separado visualmente** | Painel, lista de ATAs/contratos, saldos atuais, consumo, contratos por prefeitura, links de O.P. | Valores/semântica invariantes; todas as APIs existentes preservadas; nenhuma gravação contratual insegura liberada |
| `MOD-03` | **Produção com Obras oficiais** | Mover ações de Obras para o menu Produção, API única; trocar campo livre de obra por seleção vinculada **quando compatível** | O.P.s anteriores legíveis sem forçar recadastro; obra sem O.P.; duplicata 409; sem mexer em emissão Excel |
| `MOD-04` | **Logística e pedido de Nova Obra** | Novo Carregamento solicita obra ao serviço Produção; carga parcial via O.P. válida; indicar indisponibilidade física | Logística sem INSERT autônomo em obras; retry/idempotência; erro não gera registros órfãos; limite de item e vínculos validados |
| `MOD-05` | **Inventário e adaptação CJL** | Trazer funções reais de Carregamentos, Descarregamentos, Frota, Motoristas, Rotas, Viagens, Custos, Anexos, Evidências, Exportação; classificar `APROVEITAR/ADAPTAR/SUBSTITUIR/BLOQUEADO` | Para cada recurso: API, schema, testes, autorização, evidência, sem regressão; não copiar cegamente dependência de `Core`/identidade |
| `MOD-06` | **Core, Admin e Financeiro** | Core compartilhado (login, RBAC, auditoria); financeiro CJL na aba específica; telas de admin só habilitadas após autenticação | Rejeição de usuário/ação indevida no servidor, inclusive localhost; integridade de sessão, logs e privacidade |
| `MOD-07` | **Reconciliação de dados, versionamento, homologação** | Migrações compatíveis para obras/OP/cargas e contratos; snapshots, retomada e logs; documentação de execução e recuperação | Bancos reais intactos até autorização; teste com cópia, relatório de correspondência, rollback e suíte completa; Excel H-1 e Windows quando aplicável |

### Primeira entrega a apresentar para revisão (fatiamento exigido)
**MOD-00 + MOD-01 + MOD-02 com leituras**, e o fluxo de navegação Produção/Obras e Logística/Carregamentos já existentes **sem reescrever persistência**. Financeiro e Administração ficam navegáveis com indicação precisa de `EM INTEGRAÇÃO` até MOD-06. Isso valida as seis abas imediatamente e conserva a Produção funcional. **Não misturar nessa entrega a migração de dados, alteração de saldo nem alteração do G2.**

A sequência MOD-03…07 poderá prosseguir nos seus respectivos gates/revisões; funcionalidades dependentes dos marcos G3/G4 de ATA-mestre/variantes não podem ser marcadas como entregues antes de seu aceite. G2 segue em revisão, independentemente da organização do menu. Evitar concorrência em `web/app.js` sem coordenação do dono.

## 5. Matriz de testes — nenhum aceite pela aparência apenas
| Grupo | Casos mínimos de verificação |
|---|---|
| Navegação | 6 abas, clique/teclado/tab, 1366px e 390px, menu ativo, refresh, back/forward, telas internas, HTTP 200, console sem erro |
| Produção | suíte integral atual da branch executora, emissão/edição/revisão/cancelamento O.P.; números e snapshots não mudam |
| Contratos | duas prefeituras e dois contratos com mesmo código-base, saldo isolado; `0.x` extra; `1.1` base `1`; ajuste só por operação legítima; comparação bit a bit de valores pré/pós refactor |
| Obras | criação pelo módulo Produção, consulta Logística, criação pela ação “NOVA OBRA” em Logística encaminhada à API Produção; evitar obra duplicada; cliente diferente não mistura |
| Carregamentos | obra com zero O.P. não aceita carregar itens; O.P. de cliente diferente rejeita; cargas parciais, último saldo, concorrência, cancelamento, expedição, entrega, revisão da O.P. após carga |
| Identidade | endpoint de gravação sem sessão 401; perfil sem permissão 403; usuários de módulos distintos; CSRF e XSS; nenhuma senha/dados sensíveis em log |
| Financeiro/Logística CJL | caso de comparação por operação legada antes/depois: frota, rota, viagem, despesas/rateio, anexo/evidência, relatórios, com massa sintética |
| Dados | 0 perda de registros, IDs estáveis, migrações idempotentes, retorno após erro/injeção de falha, backup íntegro com banco fechado, revisão por cópia |
| Excel / Windows | modelos G1 não alterados; H-1 comparado com Excel real quando disponibilizado; checks do G2 não presumidos pelo menu |
| Release | versão `1.00.00.000`, cabeçalho/títulos ASCALPI, desenvolvedora CJL System, launcher local funciona, sem dados reais por padrão |

**Comandos de referência em Windows:** `...\version\1.00.00.000\VERIFICAR_ENTREGA.ps1` e `TESTAR_VERSAO.cmd`, os testes `tests/test_integracao.py` e `tests/smoke_demo.py`, além de `cd Modulos/ASCALPI_Producao && python -m unittest discover -s tests -t .`. No final entregar logs, comandos exatos e capturas. **128 + 4** foi a linha de base verificada na cópia de 10/10; não confundir com contagem da branch após novas alterações.

## 6. Segurança, estado de implantação, reversão
1. A candidata `1.00.00.000` expõe API da Produção com cabeçalho `X-ASCALPI`, mas **não tem autenticação/ACL corporativa**. `127.0.0.1` NÃO equivale a usuário autenticado (outro programa ou usuário local alcança a porta). Bloquear exposição em rede e dados reais até MOD-06.
2. Nunca replicar saldo nem obras em dois bancos como fontes graváveis independentes. O `integracao_ascalpi.db` da candidata é ponte transitória; desenhar migração/compatibilidade sem descartar relações existentes. Snapshot de carga com versão e identidade é obrigatório antes de permitir revisões concorrentes.
3. Não renomear binários/paths `CJL` no Host antigo por busca/substituição: `ProductPaths`, `master.id`, `ProgramData\CJL\Instancias` e hashing de raiz podem redefinir identidade da instalação. Marca exibida pode ser atualizada sem mudar identidade técnica; migração de identidades é uma tarefa própria.
4. Não publicar `version/` inteiro no GitHub público: há runtime e possivelmente artefatos de homologação. Código/diffs somente após saneamento; nunca `dados/`, SQLite, arquivos Excel de clientes, senhas, tokens, mídias ou caminhos de servidor.
5. Plano de rollback por pacote: snapshot/backup verificável, feature flag quando aplicável, `git revert` de entrega integrada, sem rebase/reset/force; migrações expansivas não são revertidas por DROP, preservar compatibilidade de leitura. Registrar limites: rollback de interface ≠ rollback de dados.
6. Operação em Windows e Excel real só mediante escopo/admin e preservação de H-1. Release comercial permanece BLOQUEADO sem aceite de autenticação, banco, Logística completa, instalador e H-1.
7. O usuário aprovou a **direção de arquitetura e pediu execução pelo Claude com revisão posterior**. Isso NÃO autoriza pular gates, alterar regras de saldos, converter bancos reais, lançar build comercial ou promover branches protegidas.

## 7. Formato obrigatório da entrega do Claude ao Codex
No `QUADRO_TAREFAS.md`, mensagem por pacote com:
`ID | branch | SHA exato | arquivos alterados | API/schema antes-depois | testes comando+resultado | capturas desktop/mobile | riscos conhecidos | migração/rollback | pendências | REVISÃO SOLICITADA`.
Revisor Codex classificará cada achado como **BUG REPRODUZIDO / REGRESSÃO / DIVERGÊNCIA INTENCIONAL / RISCO / MELHORIA**, com reprodução e evidência; parecer `DE ACORDO`, `AJUSTES PEDIDOS` ou `BLOQUEANTE`.
Somente Claude faz a integração da própria entrega após parecer; Carlos aprova marcos e qualquer passagem para `Dev-Work`/`main`.

## 8. Instrução direta para Claude
> **CLAUDE:** execute **MOD-00 → MOD-01 → MOD-02** como primeira entrega isolada e testável; registre o ponto de partida exato e solicite revisão do Codex antes de integrar. A interface final deverá mostrar **INÍCIO | CONTRATOS | PRODUÇÃO | LOGÍSTICA | FINANCEIRO | ADMINISTRAÇÃO**, com Obras apenas em Produção e Carregamentos apenas em Logística; botão **NOVA OBRA** na Logística chama Produção, sem base paralela de Obras. Contratos recebe visualização e autoridade sobre contratos, atas e saldos **sem modificar o motor/saldo atual**. Continue MOD-03…07 por entregas independentes após os gates, respeitando G2/G3/G4 e preservando os recursos CJL. **NÃO editar `main`, `Dev-Work`, bancos operacionais, nem publicar `version/` completo**. Informe SHA e testes; solicite revisão do Codex. A nova versão continua **1.00.00.000**.

**Ponto de corte:** documentação pronta para execução. Nenhum item deste plano deve ser marcado `INTEGRADO` ou `ACEITO` sem código, testes e revisão reais.
