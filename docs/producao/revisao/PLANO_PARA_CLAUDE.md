# ASCALPI Produção — revisão técnica e plano de estabilização

Data: 09/10/2026, horário de referência America/Sao_Paulo.
Revisor: Codex. Destinatário: Claude e Carlos.
Repositório: `TokDev-Carlos/A.S.C.A.L.P.I`.
Branch de origem: `modulo/producao-op` (não `module-op`).
Base efetivamente revisada: `b691e8e66edc65e515d8596d87288dc06101812c`.
Branch desta entrega: `codex/revisao-plano-op-2026-10-09`.

## 1. Leia isto primeiro

Esta entrega contém **revisão, reproduções e plano**, além de correções do contexto documental. **As falhas da aplicação ainda não foram corrigidas.** Não apresentar esta branch como versão homologada.

Claude: preserve o trabalho de interface já concluído. Comece pelos erros de integridade abaixo, em commits pequenos. A interface não precisa ser reescrita. Não execute os planos históricos de integração como se os seus caminhos e componentes já existissem neste módulo.

Antes de implementar, compare o HEAD atual de `modulo/producao-op` com a base acima. Se Carlos/Claude já corrigiu um achado, confirme o comportamento e marque-o como resolvido; não sobrescreva alterações recentes nem reverta código. Trabalhe em branch de correção derivada do HEAD atual e direcione a integração para `modulo/producao-op`.

### Contexto vigente

- Produto: **ASCALPI**. O módulo independente está em `Modulos/ASCALPI_Producao`.
- Runtime: Python, biblioteca padrão, SQLite, servidor HTTP local, HTML/CSS/JS sem build. `openpyxl` fica em testes/ferramentas; Pillow é usado apenas no diagnóstico opcional de imagem desta revisão.
- O sistema é a fonte da verdade; edição de dados acontece no sistema. XLSX é protegido e PDF é saída documental.
- Preservar numeração anual, regras `2.1 → 2`, bônus `0.x`, confirmação de saldo negativo, nomes de arquivo e layout legado.
- Excel/Windows é o motor de aceite visual; LibreOffice permite testes, mas não prova identidade visual com o legado.
- A interface já existe: seis telas principais, rota de edição e gaveta. Integração ao núcleo, instalador e hospedagem do produto são marcos posteriores.
- Uma sessão do Claude executar na nuvem não significa que o produto ASCALPI esteja hospedado em produção na nuvem.
- Dados e caminhos reais mencionados em documentos anteriores são contexto histórico, não evidência coletada nesta revisão. Os cenários abaixo usam exclusivamente dados fictícios temporários.

### Ordem de leitura

1. `Modulos/ASCALPI_Producao/CLAUDE.md` — decisões e restrições atuais.
2. `Modulos/ASCALPI_Producao/CONTINUAR.md` — estado da interface e pendências operacionais.
3. Este plano — diagnóstico e ordem proposta de correção.
4. Especificação e Planos 0/1 — histórico e marcos de integração; reconciliar divergências, não transformar implementação atual em decisão de negócio por inferência.

## 2. Evidências e limites

| Verificação | Resultado nesta revisão |
|---|---|
| Suíte existente `python -m unittest discover -s tests -t .` | **18 testes, OK, 20,860 s**, sem skips reportados |
| Diagnóstico adicional | **10 cenários executados**, agrupados em 9 achados; menos de 1 segundo no ambiente da revisão |
| PDF nos diagnósticos de falha | Motor substituído por mock; nenhum Excel é iniciado pelo script de diagnóstico |
| Código examinado | Módulos Python, fluxo/API, esquema SQLite, interface JS, partes relevantes do CSS, instruções, especificação e estrutura dos planos |
| Não validado aqui | Sessão ativa do Claude, banco real, livros reais, comparação visual no Excel/Windows, capturas completas da interface |

A suíte original verde não cobre os cenários concorrentes, falhas de publicação, reimportação e imagens abaixo. Ela não certifica prontidão operacional.

Para repetir o diagnóstico **da raiz do repositório**:

```bash
python docs/producao/revisao/reproduzir_achados.py
```

O script reutiliza as fixtures existentes, cria só dados temporários e imprime JSON. É um diagnóstico do comportamento, não uma suíte de aprovação: exit code 0 significa que os cenários executaram, não que o produto está sem falhas. Após cada correção, converta o respectivo cenário em teste que exija o resultado correto.

## 3. Achados confirmados

Prioridade P1: integridade de registros, documentos ou disponibilidade. P2: consistência de validação e compatibilidade.
Os nomes de função são as referências estáveis; as linhas podem mudar após os commits.

### R01 — P1 — Falha no PDF remove a publicação anterior

**Local:** `ascalpi_producao/servico.py`, `Servico.publicar`.

Ao falhar `pdf.gerar_pdf`, `resultado` contém `pdf_erro`, mas não `pdf`. A limpeza compara o caminho anterior com `resultado.get('pdf')`, que é `None`, e apaga o PDF anterior. Ocorre inclusive republicando a mesma O.P. sem mudar o nome.

**Reprodução:** `R01_pdf_anterior`: `pdf_anterior_preservado=false`, `erro_reportado=true`.

**Correção:** só substituir/limpar um formato depois de concluir a gravação do substituto correspondente. Preservar o PDF anterior com indicação explícita da revisão a que pertence; não o apresentar como PDF atualizado. Registrar tentativa, resultado e revisão por formato. Usar temporários exclusivos por operação e serializar publicação da mesma O.P.; o nome temporário atual é compartilhado.

**Aceite:** motor PDF falha → PDF anterior permanece íntegro; XLSX novo e erro são identificados; nenhuma publicação anterior é apagada por ausência do novo arquivo. Se revisão mudou, a UI distingue documento anterior de atual.

### R02 — P1 — Erro de publicação aparece como falha de criação após commit

**Local:** `Servico.salvar_op`, `Servico.publicar`; `servidor.py::_tratar`; `web/app.js::gerar`.

O commit da O.P. termina antes de publicar. Falha ao gerar/gravar XLSX propaga exceção; a API devolve erro genérico, embora o registro e consumo já existam. A interface mantém o formulário; nova tentativa cria outro registro.

**Reprodução:** `R02_falha_xlsx`: PermissionError, 1 O.P. persistida depois do erro, 2 depois de repetir.

**Correção mínima:** retornar sucesso de persistência com `op_id`, `op` e resultado separado da publicação (`PENDENTE`/`PARCIAL`/`PUBLICADA`, erros por formato). Mostrar “O.P. SALVA; PUBLICAÇÃO PENDENTE” e ação de republicar a mesma O.P. Não tentar rollback do banco depois que documentos externos podem ter sido gravados.

**Complemento necessário para retry de rede:** chave idempotente de criação, persistida com índice único na mesma transação. Mesma chave e mesmo pedido retornam a O.P. existente; mesma chave e conteúdo diferente retornam conflito. Chave de rascunho sobrevive a timeout/reabertura, mas uma duplicação intencional cria nova chave. Desabilitar botão no JS ajuda a UX, mas não substitui idempotência no servidor.

**Aceite:** falha de pasta/motor não induz nova numeração/consumo; repetir o mesmo pedido após resposta perdida retorna o mesmo `op_id`.

### R03 — P1 — Duas criações consomem saldo sem confirmação

**Local:** `Servico.salvar_op` chama `simular` antes de `Banco.transacao`.

**Reprodução:** saldo inicial 5, duas criações de 4 sincronizadas depois da simulação: ambas salvam sem pedir confirmação; saldo final **−3**. Os números gerados são distintos: o defeito observado é o saldo, não duplicação da numeração.

**Correção:** colocar leitura do estado, validação do modelo, simulação definitiva, decisão de confirmação, reserva do número e gravação sob a mesma transação `BEGIN IMMEDIATE`. Criar helpers que reutilizem a conexão, sem `BEGIN` aninhado. Publicação/PDF permanece fora da transação. A simulação da tela continua informativa.

**Aceite:** em duas chamadas concorrentes, uma salva e a outra recebe necessidade de confirmação baseada no saldo atualizado. Revalidar também se o modelo for desativado ou a O.P. cancelada entre leitura e escrita. Confirmar negativo não dispensa validação de versão/estado.

### R04 — P1 — Edições concorrentes criam duas REV 1

**Local:** `Servico.salvar_op`, leitura de `atual` antes da transação; `banco.py::op_revisoes`; formulário JS.

**Reprodução:** `R04_revisao_concorrente` produz histórico `[0, 1, 1]`. Cada edição calcula `atual['rev'] + 1` sobre a mesma versão. A última escrita pode substituir a primeira sem alertar o operador.

**Correção:** enviar `rev_esperada`, checar dentro da transação e recusar versão obsoleta com conflito HTTP 409. Incrementar apenas uma vez. Criar unicidade `(op_id, rev)` em migração transacional depois de detectar duplicações preexistentes. Nunca apagar revisões históricas automaticamente para fazer o índice passar; relatar e preparar reconciliação explícita.

**Aceite:** duas edições da mesma base → uma revisão nova, um conflito claro; itens/obra da primeira edição não são perdidos. Testar também edição concorrente com cancelamento.

### R05 — P1 — Trocar contrato do modelo transfere consumo de O.P. já criada

**Local:** `Servico.atualizar_modelo`, `_consumo_sistema`, `op`; seletor de contrato na tela Modelos.

O saldo histórico é calculado pelo contrato **atual do modelo**, em vez do contrato associado à O.P. quando foi emitida.

**Reprodução:** O.P. consome 4; mudar modelo para outra ATA restaura saldo do contrato original de 1 para 5, reduz saldo do novo de 10 para 6 e mantém a O.P. em REV 0.

**Correção imediata:** impedir troca/remoção de contrato de modelo já usado enquanto a associação da O.P. não for estabilizada. Comunicar claramente na UI; permitir ativar/desativar conforme regra vigente.

**Correção estrutural:** persistir `contrato_id` na O.P. e usar essa referência para consumo. Versionar ou congelar o modelo documental referenciado pela O.P.; reimportação não deve mudar silenciosamente documentos já emitidos. Na migração, o contrato atual do modelo é apenas candidato de preenchimento: mudanças passadas não podem ser reconstruídas com certeza sem evidência; listar casos ambíguos.

**Aceite:** alterar modelo só afeta novas O.P.; contrato/consumo/documento das anteriores continua estável. Transferência de contrato, se desejada, vira operação explícita de negócio com histórico, não consequência de editar cadastro.

### R06 — P1 — Data impossível é persistida e quebra consultas

**Local:** `Servico.acompanhar`, `estado_op`, `listar_ops`, `painel`.

O acompanhamento grava antes de interpretar a data. `2026-02-31` satisfaz a regex de formato; `date.fromisoformat` falha depois do commit. Uma O.P. pode derrubar a listagem inteira e o painel.

**Reprodução:** `R06_data_invalida`: data persistida `2026-02-31`; `listar_ops=ValueError`.

**Correção:** validar data e valores permitidos antes da escrita; API retorna 400 e mantém estado anterior. Para registros antigos inválidos, leitura deve sinalizar “DATA INVÁLIDA” sem derrubar toda a coleção, preservando o valor bruto para correção auditada. Manter suporte ao prazo textual deliberado; não confundir texto livre válido com data impossível.

**Aceite:** data inválida não entra no banco; dado legado malformado fica identificável sem indisponibilizar outras O.P.

### R07 — P1 — Reimportação apaga acompanhamento e pode zerar o histórico

**Local:** `legado.importar_controle`, `importar_livro`, `ler_saldo`.

`importar_controle` executa `DELETE FROM ops WHERE origem='LEGADO'` antes de recriar registros. Isso remove acompanhamento feito no sistema e altera/reutiliza identidades. Não exige que a tabela `Controle_OP` tenha sido encontrada.

**Reproduções:** reimportar o mesmo Controle deixa 0 anotações preservadas; fornecer livro válido sem `Controle_OP` reduz histórico de 2 para 0.

**Correção imediata:** conferir tabela/cabeçalhos e número de registros antes de mutar; bloquear reimportação destrutiva sobre base em uso. A detecção de tabela vazia exige tratamento explícito, não apagamento automático.

**Evolução:** importar para staging, mostrar diferenças e fazer merge com identidades estáveis. Não usar apenas número da O.P. como identidade, pois o legado admite duplicatas; manter chave de origem e mecanismo para resolver ambiguidades. Campos de acompanhamento alterados no ASCALPI têm precedência, com proveniência registrada. Proteger também modelos e linhas usados por O.P. existentes.

**Lacuna adicional por leitura estática:** `saldo_planilha` é coletado, mas não reconciliado; valores ausentes/fórmulas sem cache podem virar zero. Implementar prévia com diferenças, dados ausentes e critérios de corte antes de aceitar migração. Não alegar que os saldos reais foram conferidos nesta revisão.

**Aceite:** tabela ausente não altera banco; repetir importação preserva acompanhamento e identidade; falha de um modelo não deixa arquivos substituídos sem atualização correspondente no banco; dados incompletos não são convertidos silenciosamente em saldo válido.

### R08 — P2 — Motivo obrigatório só é exigido pelo navegador

**Local:** `Servico.ajustar_item`, `web/app.js::ajustar`.

**Reprodução:** ajuste de 2 sem motivo é aceito pelo serviço e muda saldo de 5 para 3.

**Correção:** validar motivo no servidor antes da transação; validar tipos e números finitos. Centralizar validação dos corpos de API para objeto JSON, booleanos reais, IDs válidos, quantidades e linhas únicas. `bool('false')` não é confirmação explícita; não converter strings arbitrárias em consentimento para saldo negativo.

**Aceite:** pedidos inválidos recebem 400 e não alteram registros; motivos obrigatórios são auditáveis também quando a chamada não vem da tela.

### R09 — P2 — Imagens dependem do prefixo XML literal

**Local:** `imagens.py::mapa_imagens` e regex `_ANCORA`, `_DE`, `_BLIP`.

O leitor depende de prefixos `xdr:` e `a:`. XML equivalente pode usar namespace padrão ou outro prefixo.

**Reprodução:** XLSX sintético válido com PNG ancorado em C10, gerado com openpyxl: 1 mídia presente e **0 imagens reconhecidas**.

**Correção:** ler desenhos com `xml.etree.ElementTree`, usando URIs de namespace e relacionamentos. Manter os formatos suportados e a regra de localização; não incluir conversão de EMF/WMF neste reparo. Adicionar fixture em namespace padrão e com prefixos diferentes, logo C3/C4 e foto C10. ETag deve distinguir modelo/mídia e alteração de conteúdo; o atual só usa segundo do mtime e chave.

**Aceite:** namespace semanticamente equivalente produz a mesma foto/logo. Este diagnóstico não comprova que todas as fotos dos livros reais falham; verificar amostras reais posteriormente.

## 4. Pontos adicionais para validar, sem tratá-los como falhas reproduzidas

1. **Prazo textual na edição:** backend aceita texto livre; `telaNova` converte qualquer prazo não-data em modo `definir` e `gerar` envia `DEFINIR`. Preservar o texto original ao editar/duplicar e oferecer campo textual conforme decisão vigente.
2. **Respostas fora de ordem na UI:** `escolherModelo`, `trocarPref`, salvar/cancelar/republicar na gaveta não usam de modo consistente geração/identidade após `await`. Validar alternância rápida A→B; uma resposta antiga não pode substituir o estado do destino atual. Em `desenharAbaGaveta`, atribuir a variável local antes de validar identidade e só então atualizar `gav.modelo`.
3. **Reentrada por teclado:** `ocupado` altera `aria-busy` e CSS bloqueia ponteiro, mas não existe trava lógica uniforme. Validar Enter repetido; desabilitar e restaurar estado do botão e impedir reentrada no handler. Coordenar com idempotência R02.
4. **Escala da listagem:** `listar_ops` limita 3.000 antes de filtrar estado; a UI/painel calculam totais sobre subconjuntos. Antes de extrapolar esse volume, separar agregações no banco de paginação e busca. Não refazer agora só por desempenho presumido.
5. **Excel em timeout:** o subprocesso PowerShell tem timeout, mas não há identificação explícita do Excel criado nem rotina dedicada de recuperação. Validar no Windows com instância isolada, sem encerrar Excel do usuário. Não declarar COM robusto só porque LibreOffice passou.
6. **Carimbo e versões documentais:** `_dados_documento` usa `atualizado_em`, que também muda no acompanhamento. Definir se “Hoje” é emissão, revisão ou geração e registrá-lo no lugar correspondente. Não alterar essa regra silenciosamente.
7. **Bônus fora da tabela:** `simular_saldo` verifica existência antes de ignorar `0.x`; o frontend mostra bônus sem conferência. Confirmar com a regra legada se bônus ausente da tabela deve ser aceito e registrar uma interpretação única antes de modificar.
8. **Fronteira de implantação:** servidor atual é local e sem autenticação de usuários. Não publicar em rede/nuvem como etapa desta estabilização. Autenticação, autorização e proteção das rotas mutáveis pertencem ao marco de hospedagem.

## 5. Plano de execução em lotes pequenos

As caixas abaixo representam trabalho futuro; não foram marcadas como feitas porque o diagnóstico passou.

### Lote A — Publicação resiliente (R01–R02)

- [ ] Criar `tests/test_publicacao.py` com falha de PDF, falha de XLSX, mudança de nome/revisão e tentativa repetida.
- [ ] Separar resultado de gravação da O.P. e resultado de publicação, mantendo compatibilidade explícita com a UI.
- [ ] Preservar documento anterior, distinguir revisões e usar temporários exclusivos.
- [ ] Implementar retry da publicação e idempotência da criação, com migração pequena e testada.
- [ ] Exibir sucesso parcial sem pedir ao usuário para criar novamente.

Arquivos: `servico.py`, `banco.py`, `servidor.py`, `web/app.js`, teste novo. Commit sugerido: `fix(producao): preservar documentos e separar falhas de publicacao` (idempotência pode ser commit seguinte).

### Lote B — Integridade transacional (R03–R05)

- [ ] Criar `tests/test_concorrencia.py` com duas operações coordenadas por barreira/evento, timeout curto e sem sleeps arbitrários.
- [ ] Refazer os testes para coordenar a entrada das requisições, não bloquear uma barreira dentro da transação corrigida (isso criaria deadlock artificial).
- [ ] Revalidar estado/saldo dentro da transação; manter número único e publicação fora da trava.
- [ ] Introduzir controle de versão esperado e resposta 409, com atualização correspondente do formulário.
- [ ] Bloquear mudança de contrato de modelo usado; preparar migração da associação de contrato por O.P.
- [ ] Detectar dados antigos inconsistentes e apresentar relatório; não apagar histórico para satisfazer constraints.

Arquivos: `servico.py`, `banco.py`, `servidor.py`, `web/app.js`, testes. Dividir em commits por achado. Uma operação de migração não deve compartilhar commit com reorganização geral de módulos.

### Lote C — Validação e importação (R06–R08)

- [ ] `tests/test_validacao_api.py`: data impossível, corpo não-objeto, booleano inválido, IDs/quantidades inválidos, motivo vazio; conferir 400/409 e ausência de mutação.
- [ ] `tests/test_importacao.py`: tabela ausente, reimportação de base em uso e acompanhamento preservado.
- [ ] Adicionar staging/prévia, reconciliação de saldo e política de identidade/proveniência antes de habilitar reimportação recorrente.
- [ ] Manter leitura tolerante a registros antigos problemáticos, com aviso explícito.

Arquivos: `servico.py`, `legado.py`, `regras.py`, `servidor.py`, testes. Não reimportar os livros reais para testar esta etapa.

### Lote D — Imagens e consistência de UI (R09 e verificações adicionais)

- [ ] Implementar leitura por namespace com fixture pequena em `tests/test_imagens.py`.
- [ ] Preservar prazo textual e proteger estado de tela/gaveta contra respostas antigas.
- [ ] Validar gerar → confirmação negativa → editar → cancelar → republicar com dados de demonstração.
- [ ] Capturas em 1366 px e 390 px; conferir fotos/logos sintéticos, foco, botões ocupados e console.

Somente esta etapa requer nova inspeção visual de interface; não repetir capturas em alterações puramente documentais.

### Lote E — Refatoração gradual, depois das correções

Evitar um “arquivo utilitário” genérico e uma reescrita com framework. Extrair responsabilidades mantendo `Servico` como fachada e URLs/contratos públicos estáveis.

| Área atual | Extração proposta | Limite da responsabilidade |
|---|---|---|
| `servico.py`: publicar/gerar | `publicacao.py` | Snapshot da O.P., arquivos, resultados e tentativas; não reserva números |
| `servico.py`: config | `configuracao.py` | Validação e gravação atômica; preserva senha fora das respostas |
| `servico.py`: estado/painel | `consultas.py` | Consultas e agregações; não altera O.P. |
| `servico.py`: salvar/cancelar/acompanhar | Manter inicialmente na fachada | Dono explícito da transação; extrair só quando isso simplificar o código |
| `web/app.js`: API/cache/DOM | `web/core/api.js`, `estado.js`, `dom.js` | Rede, invalidação, escape e ciclo de vida; sem conhecer telas específicas |
| `web/app.js`: telas | `web/telas/*.js` | Renderizar/montar/desmontar cada tela com contexto explícito |
| `web/app.js`: gaveta/dialogo | `web/componentes/*.js` | Componentes e descarte de listeners/requisições |
| `web/app.css` | Manter primeiro; extrair depois | Preservar tokens e classes; eliminar duplicação só com conferência visual |

- [ ] Uma extração por commit; não mudar regra de negócio junto com mover código.
- [ ] Dependências em uma direção: rotas → aplicação → regras/infraestrutura; tela → componentes/core. Sem imports circulares.
- [ ] Evitar globais compartilhadas entre telas; cada montagem retorna uma função de descarte.
- [ ] Reutilizar helpers de regras onde houver duplicação; cálculo do navegador é prévia, servidor decide.
- [ ] Executar a suíte leve e apenas os testes afetados após cada extração; não adicionar testes que apenas repetem o código movido.

## 6. Contextos corrigidos e decisões a preservar

| Divergência | Tratamento |
|---|---|
| `CLAUDE.md` diz “app.js a escrever” | Corrigido para interface implementada e validação pendente |
| `CONTINUAR.md` chama referência de “o que escrever” | Renomeada para referência da implementação existente |
| README da raiz diz que estrutura funcional ainda será incorporada | Contextualizado nesta branch; `main` continua com sua própria fundação |
| Spec antiga prevê extração Excel/integração CJL e células desbloqueadas | Mantida como histórico com aviso; decisão vigente é módulo independente e bloqueio total |
| Plano 0 diz para começar pelo instalador/núcleo | Marcado como marco futuro, após estabilização/aceite do módulo |
| Caminhos `docs/superpowers` dos planos não batem com o repo | Referências documentais ajustadas para `docs/producao/superpowers` |
| “100% pronto” versus validação real pendente | Separar código implementado, diagnóstico automatizado e aceite operacional |

Questões que exigem decisão específica antes de mudar comportamento: carimbo “Hoje”, bônus ausente da tabela, recuperação de associação histórica ambígua e política de corte/reimportação. Não são motivo para bloquear as correções inequívocas R01–R04/R06/R08/R09.

## 7. Critério de encerramento para o Claude

1. Atualizar esta lista com commit e teste por achado, sem substituir evidência por porcentagem estimada.
2. Suíte original e regressões relevantes verdes; testes sem dados de clientes.
3. Nenhuma perda de documento em falha parcial; retry não duplica O.P.
4. Concorrência preserva saldo, cancelamento, numeração e revisão; migrações preservam histórico.
5. Reimportação inválida não muta a base e fotos sintéticas aparecem.
6. Após revisão do código: validação autorizada em cópia local de dados reais, PDF no Excel/Windows e comparação de 3–5 amostras. Não afirmar identidade visual com base apenas em mocks/LibreOffice.
7. Atualizar `CONTINUAR.md` com concluído, pendente, testes e limitações; integrar com revisão. Não copiar módulo para a instalação operacional nem fazer merge em `main` como efeito automático deste plano.

## 8. Mensagem de entrada para a próxima sessão

Leia `Modulos/ASCALPI_Producao/CLAUDE.md`, `CONTINUAR.md` e `docs/producao/revisao/PLANO_PARA_CLAUDE.md`. Compare o HEAD com `b691e8e`. A interface já está implementada. Execute os lotes A–D em commits pequenos, começando pela preservação do PDF anterior e pela separação entre salvar O.P. e publicar documentos. Converta as reproduções em regressões com comportamento correto. Faça a refatoração do lote E somente após estabilizar as regras. Informe achado, correção, testes e pendências reais a cada lote. Use apenas dados sintéticos na nuvem e preserve as alterações concorrentes do projeto.
