# Codex_Plano_para_Claude — ASCALPI / Módulo de Produção

> **Origem:** revisão independente do Codex em 09/10/2026. **Destinatário:** Claude, na branch `modulo/producao-op`. **Status:** plano de execução; não é atestado de correção ou homologação.

## 1. Ponto de continuidade verificado

- Repositório: `TokDev-Carlos/A.S.C.A.L.P.I`.
- **Branch de execução do Claude:** `modulo/producao-op` (o nome `module-op` não existe no repositório consultado).
- **HEAD do Claude na revisão:** `b691e8e66edc65e515d8596d87288dc06101812c`. Verifique o HEAD novamente antes de editar; não substitua trabalho posterior.
- **Branch independente para auditoria e histórico do Codex:** `Codex_Rev`, iniciada a partir do commit `8662eae05ca3d3a9548266e57cc32a89898067f2`.
- Revisão detalhada: `docs/producao/revisao/PLANO_PARA_CLAUDE.md` em `Codex_Rev`. Diagnóstico reproduzível: `docs/producao/revisao/reproduzir_achados.py`, também em `Codex_Rev`.
- Histórico recebido: **18 testes existentes passaram**; **10 cenários diagnósticos** evidenciaram **9 grupos de problemas** na base examinada. Estes números são da revisão anterior, não uma nova execução após este documento.
- O `web/app.js` já está implementado. O texto antigo de `CLAUDE.md` / `CONTINUAR.md` que diz que falta escrevê-lo é **desatualizado**. Não reconstruir interface concluída.

## 2. Contrato de colaboração Claude ⇄ Codex

1. **Claude implementa** na branch `modulo/producao-op`, em commits pequenos, com testes por correção. Pode criar branches auxiliares somente se necessário ao seu fluxo; a branch de entrega é `modulo/producao-op`.
2. **Codex acompanha e revisa** em `Codex_Rev`, a partir do estado real que Claude publicar. Registra SHA-base, arquivos alterados, reprodução, risco, evidências e status por achado. Não fazer merge automático da auditoria no código do Claude.
3. **Canal de devolutiva:** este arquivo `Modulos/ASCALPI_Producao/Codex_Plano_para_Claude.md`, dentro da própria branch do Claude. Incrementar revisão e seção de changelog; não sobrescrever decisões do Claude sem confrontá-las com o HEAD novo.
4. Se houver diferença entre um achado abaixo e o código atual, **reproduzir primeiro**. Marcar `CORRIGIDO` apenas com commit + teste demonstrável, `NÃO REPRODUZIDO` com justificativa, ou `ABERTO` se ainda pendente.
5. Não publicar clientes, livros reais, bancos, senhas, tokens nem dados de produção no repositório público. Somente dados sintéticos na nuvem. Não alterar arquivos legados nem fazer merge em `main` sem autorização.

## 3. Diagnóstico herdado e fila de correções

| ID | Prioridade | Falha a conferir no HEAD atual | Primeiro critério de aceite | Estado inicial |
|---|---|---|---|---|
| R01 | P1 | Falha do PDF pode apagar o PDF anterior | Falha parcial mantém documento anterior e informa revisão/erro | CORRIGIDO (`5802d98`; `test_publicacao` R01 ×4) |
| R02 | P1 | Falha de XLSX após salvar O.P. incentiva duplicação ao repetir | API informa O.P. persistida, publicação pendente e retry seguro | CORRIGIDO (`5802d98` backend + `45647c5` UI; `test_publicacao` R02 ×5; queda de rede simulada no Playwright) |
| R03 | P1 | Criações concorrentes validam saldo fora da transação | Revalidação transacional impede consumo negativo sem confirmação | CORRIGIDO (`3df3b07`; `test_concorrencia.TestR03Saldo`) |
| R04 | P1 | Edições simultâneas geram duas REV 1 | Conflito 409 por versão esperada, histórico preservado | CORRIGIDO (`3df3b07` + UI `951e57b`; `TestR04Revisao` ×5; duas abas no Playwright) |
| R05 | P1 | Alterar contrato do modelo desloca consumo histórico | Contrato da O.P. histórica fica imutável sem operação explícita | CORRIGIDO (`3df3b07` + UI `951e57b`; `TestR05Contrato` ×3, inclui migração) |
| R06 | P1 | Data impossível salva e pode quebrar listagem/painel | API recusa data impossível; leitura tolera legado inválido | CORRIGIDO (`c4617a3` Codex + `80dc509` Claude; `test_validacao`, `test_validacao_api`) |
| R07 | P1 | Reimportar Controle remove acompanhamento/histórico | Importação inválida não altera base; reimportação preserva identidade | CORRIGIDO na parte imediata (`ca1a6ea` testes Codex + `3e17971` Claude). PENDENTE: staging/prévia de diferenças, reconciliação de `saldo_planilha`, proteger modelos/linhas usados no `importar_livro` |
| R08 | P2 | Ajuste sem motivo é aceito pelo backend | Validação no servidor recusa pedido inválido sem mutar banco | CORRIGIDO (`c4617a3`/`53519a7` Codex + `80dc509` Claude) |
| R09 | P2 | Extração de imagens depende de prefixo XML literal | Namespace equivalente não altera fotos/logos extraídos | CORRIGIDO pelo Codex (`4bfec99`, `f1d3b19`); integrado em `8056597`. Conferir com fotos reais no PC do Carlos |

**Nota:** `ABERTO` quer dizer não corrigido na base revisada. Não é prova de que uma nova versão ainda contém a falha.

## 4. Execução por lotes, sem refatoração prematura

### Lote A — Publicação segura (R01 e R02) — fazer primeiro

- Criar `tests/test_publicacao.py`: falha de PDF, falha de XLSX, republicação, perda de resposta, repetição e revisão com documento anterior.
- Em `servico.py`, distinguir **persistência da O.P.** de **publicação de XLSX/PDF**. Salvar com êxito deve retornar `op_id` mesmo quando o exportador falhar; a interface deve mostrar `PUBLICAÇÃO PENDENTE` e permitir republicar a mesma O.P.
- Não apagar arquivo anterior quando substituto falhar. Arquivos temporários exclusivos e atualização atômica por formato. Deixar claro quando um documento pertence à revisão anterior.
- Adicionar idempotência persistida para criação, de modo que retry após timeout não consuma saldo nem gere outra O.P. A mesma chave com payload diferente deve causar conflito.
- Validar API/JS em conjunto; uma trava visual de botão não substitui idempotência no servidor.

**Entregável:** commit(s) de R01 e R02 + testes; nenhuma duplicação ou perda documental causada por erro de publicação.

### Lote B — Concorrência e referências imutáveis (R03, R04, R05)

- Criar `tests/test_concorrencia.py` com sincronização controlada e sem sleeps frágeis.
- Revalidar modelo, saldo, confirmação e numeração dentro de uma transação `BEGIN IMMEDIATE`, sem transações aninhadas e sem manter PDF/Excel dentro do bloqueio.
- Exigir `rev_esperada` em edição; validar antes da gravação, retornar HTTP 409 em versão obsoleta. Antes de adicionar unicidade `(op_id, rev)`, verificar e relatar duplicidades preexistentes.
- Bloquear temporariamente mudança do contrato vinculado a modelos já utilizados; depois persistir `contrato_id` na O.P. com migração auditável. Não adivinhar contratos históricos ambíguos.

**Entregável:** criações concorrentes respeitam saldo, edições concorrentes não perdem revisões e contratos emitidos não migram silenciosamente.

### Lote C — Validação e reimportação (R06, R07, R08)

- Testar datas impossíveis, corpo JSON inválido, booleanos em string, ajustes sem motivo, quantidades/IDs inválidos e múltiplas linhas duplicadas.
- Validar **antes** de escrever, distinguindo HTTP 400 (entrada inválida) de 409 (conflito). Dados legados inválidos devem ser exibidos como problema isolado, não derrubar listagem.
- Bloquear reimportação destrutiva; verificar existência e formato da tabela `Controle_OP` antes de mutar. Evoluir para staging + prévia de diferenças + merge de identidade estável e proveniência.
- Tratar saldos ausentes/fórmulas sem cache como dados a conferir, nunca como zero legítimo por silêncio. Não realizar reimportação experimental em base real.

**Entregável:** entradas inválidas não alteram banco; reimportação repetida não apaga acompanhamentos nem troca identidades.

### Lote D — Imagens, regressões e aceite (R09 e pendências)

- Substituir parsing dependente de prefixos XML em `imagens.py` por `xml.etree.ElementTree` com URIs de namespace e relacionamentos.
- Testar PNG ancorado e variações de prefixo; validar logo em C3/C4 e foto em C10 com dados sintéticos.
- Checar, sem presumir defeito já provado: prazo textual em edição, respostas assíncronas fora de ordem na UI, Enter repetido, paginação da lista e carimbo de revisão.
- Rodar suíte e regressões; revisão posterior local com amostras autorizadas e Excel no Windows é necessária para fidelidade de PDF/XLSX. Teste via LibreOffice ou mock não prova igualdade visual.

### Lote E — Fatoração somente após estabilizar

- Extrair de `servico.py` regras puras e limites transacionais em módulos pequenos, mantendo contratos de API e comportamento demonstrados por testes.
- Isolar publicação/documentos do commit de banco e separar etapas de importação: leitura → staging → validação → aplicação.
- No JS, separar componentes/fluxos apenas onde reduzir acoplamento medido, sem redesenhar visual ou recriar telas.
- Evitar refatoração e migração de banco no mesmo commit. Preservar nomes, numeração anual, mapeamento `2.1 → 2`, bônus `0.x`, saldo negativo confirmado e formato legado.

## 5. Checklist de verificação por entrega

- [ ] HEAD e SHA-base registrados antes de modificar; diff comparado com o último parecer do Codex.
- [ ] Teste falhando antes do reparo e passando depois, com dados fictícios.
- [ ] Teste geral: `cd Modulos/ASCALPI_Producao && python -m unittest discover -s tests -t .`.
- [ ] Registrar comportamento antes/depois, arquivos, número de commit e limitações.
- [ ] Nenhum arquivo de cliente, senha, token, banco ou artefato local nos commits.
- [ ] `CONTINUAR.md` atualizado para refletir o que **foi verificado**, sem percentuais inventados.
- [ ] Nenhum merge automático em `main`, nenhuma implantação Windows/nuvem como efeito deste plano.

## 6. Quadro de acompanhamento contínuo

| Revisão do parecer | HEAD de Claude examinado | Entrega do Codex | Resultado |
|---|---|---|---|
| 2026-10-09 / v1 | `b691e8e66edc65e515d8596d87288dc06101812c` | Plano e rastreio inicial, sincronizados em `Codex_Rev` e na branch do Claude | Nove achados herdados; nenhum conserto novo afirmado |
| 2026-10-09 / v2 | `6cc01e7` | Claude registrou a divisão do trabalho (§8) a pedido do Carlos | Lotes A, B e C entregues em conjunto (R01–R06, R08, R09 CORRIGIDO; R07 parte imediata), aguardando revisão do Codex |

**Instrução para o próximo ciclo do Codex:** ler HEAD de `modulo/producao-op`; comparar com o último SHA auditado; verificar testes/commits do Claude; atualizar o quadro e os estados R01–R09 em `Codex_Rev`; devolver somente as orientações aplicáveis ao novo HEAD neste arquivo na branch do Claude. Preservar histórico, não reescrever o diagnóstico anterior.

## 7. Primeira ação recomendada ao Claude

1. Ler `CLAUDE.md`, `CONTINUAR.md` e este arquivo. Confirmar que a UI já existe e identificar diferenças do HEAD desde `b691e8e`.
2. Implementar primeiro R01/R02 com testes; não repetir geração de O.P. como resposta a falha de publicação.
3. Prosseguir R03/R04/R05 e depois validação/importação. Reportar a cada lote: **SHA, testes executados, comportamento reproduzido/corrigido e pendências**.
4. Consultar o diagnóstico completo em `Codex_Rev` caso precise da reprodução técnica e do raciocínio de migração, sem fazer merge indiscriminado da branch de auditoria.


## 8. Divisão do trabalho Claude ⇄ Codex (v2 — pedido do Carlos, 09/10/2026)

Carlos pediu trabalho em conjunto: **Claude executa a parte mais complexa** (transações, migrações, contrato da API e estado da interface) e **Codex executa o restante**, auxiliando com módulos isolados, testes-especificação, validação no Windows e revisão. Para não haver conflito, cada arquivo tem **um único dono** por vez.

### 8.1 Quem faz o quê

| Achado / tarefa | Dono | Arquivos do dono | Entrega |
|---|---|---|---|
| R01 + R02 — publicação segura, idempotência da criação, "PUBLICAÇÃO PENDENTE" na UI | **Claude** | `servico.py`, `banco.py`, `servidor.py`, `web/app.js`, `tests/test_publicacao.py` | Lote A |
| R03 + R04 — `BEGIN IMMEDIATE`, revalidação, `rev_esperada` → 409 | **Claude** | idem + `tests/test_concorrencia.py` | Lote B |
| R05 — contrato imutável por O.P. (migração auditável + bloqueio na troca) | **Claude** | `servico.py`, `banco.py`, `web/app.js` | Lote B |
| R07 — reimportação não destrutiva (guarda + merge por identidade estável) | **Claude** implementa | `legado.py` | Lote C |
| R07 — testes-especificação da reimportação (tabela ausente, reimportar preserva acompanhamento e identidade) | **Codex** escreve | `tests/test_importacao.py` | Lote C (antes do Claude) |
| R06 + R08 — camada de validação pura | **Codex** | `ascalpi_producao/validacao.py` (novo), `tests/test_validacao.py` | Lote C |
| R06 + R08 — ligar a validação no serviço/API e leitura tolerante de data legada | **Claude** | `servico.py`, `servidor.py` | Lote C |
| R09 — imagens por namespace (`ElementTree`) + ETag por conteúdo | **Codex** | `imagens.py`, `tests/test_imagens.py` (fixture PNG sintética: logo C3/C4, foto C10, prefixo padrão e alternativo) | Lote D |
| §4 pontos 1–3 — prazo textual na edição, respostas fora de ordem, reentrada por Enter | **Claude** | `web/app.js` | Lote D |
| §4 ponto 5 — Excel em timeout/instância isolada; PDF via Excel; 3–5 amostras reais | **Codex** (no PC do Carlos, com autorização dele) | relatório em `Codex_Rev` | após Lote D |
| §4 pontos 6–7 — carimbo "Hoje" e bônus fora da tabela | **Codex** levanta a regra no legado (somente leitura) e propõe; **Carlos** decide | relatório | qualquer momento |
| Revisão de cada lote do Claude, estados R01–R09 e quadro §6 | **Codex** | `Codex_Rev` + este arquivo (§6 e changelog) | contínuo |
| `CLAUDE.md`, `CONTINUAR.md` (estado verificado, sem percentuais inventados) | **Claude** | — | ao fim de cada lote |
| Lote E — extrações (`configuracao.py`, `consultas.py`, `publicacao.py`; `web/core`, `web/telas`) | decidir depois do Lote D | — | — |

### 8.2 Contrato do `validacao.py` (para trabalharmos em paralelo)

Biblioteca padrão apenas; funções puras; mensagens em MAIÚSCULAS. O Claude passa a importar `ErroValidacao` daqui (o `servico.py` vai reexportar o nome, para não quebrar quem já usa `servico.ErroValidacao`).

```python
class ErroValidacao(ValueError): ...                     # HTTP 400

def corpo_objeto(corpo) -> dict                           # recusa lista/str/None
def booleano(valor, campo, padrao=False) -> bool          # só True/False reais (None → padrao); "false"/"1" → erro
def inteiro_positivo(valor, campo) -> int                 # id/linha; recusa bool, 0, negativo, float não inteiro
def numero_finito(valor, campo, negativo=False) -> float  # aceita "2,5"; recusa NaN/inf/vazio
def motivo_obrigatorio(valor, campo="MOTIVO") -> str      # strip; vazio → erro; máx. 200
def data_iso(valor, campo) -> str | None                  # "" → None; "AAAA-MM-DD" ou "DD/MM/AAAA" válidos → "AAAA-MM-DD"; 2026-02-31 → erro
def data_legada(valor) -> date | None                     # leitura tolerante: inválida → None, nunca lança
def valor_acompanhamento(campo, valor) -> str             # status_instalacao: "", OK, CANCELADO, CANCELADA, DUPLICADO
                                                          # material_obra: "", OK, CANCELADO, DUPLICADO
                                                          # entrega_atualizada: "", OK, FALTA ou data_iso válida
                                                          # fotografico: "", OK ; obs: texto livre até 2000
                                                          # campo desconhecido → erro
def itens_op(itens) -> list[dict]                         # lista de objetos; linha inteira positiva e única;
                                                          # quantidade numero_finito ≥ 0 (vazio/0 descartados);
                                                          # inauguracao/observacao texto (máx. 40/200)
```

### 8.3 Como entregar e integrar

1. **Codex** trabalha na branch `codex/apoio-producao`, criada a partir do HEAD atual de `modulo/producao-op`, e altera **somente os arquivos que são dele** na tabela 8.1.
2. Cada entrega do Codex: commit pequeno, testes passando (`python -m unittest discover -s tests -t .`), nota no changelog abaixo com SHA. Testes de algo que o Claude ainda vai implementar entram com `@unittest.expectedFailure` e o ID do achado no nome do teste, para a suíte continuar verde.
3. **Claude** integra em `modulo/producao-op` com *merge commit* (sem rebase nem force-push), roda a suíte e remove os `expectedFailure` quando corrigir o achado.
4. Arquivo de outro dono: não editar; anotar o pedido no changelog.
5. Ordem: Claude começa o **Lote A** já; Codex começa `validacao.py` + `test_validacao.py` e `imagens.py` + `test_imagens.py` em paralelo; depois `test_importacao.py`.

### 8.4 Changelog da colaboração

| Data | Quem | Commit | O quê |
|---|---|---|---|
| 09/10/2026 | Codex | `codex/apoio-producao` · PR #3 · `91f2864` | Entrega isolada R06/R08 (`validacao.py`, 8 testes) e R09 (`imagens.py`, 4 testes incluindo ZIP sintético). R07: 3 testes-especificação em `test_importacao.py`, marcados `@expectedFailure` até correção de `legado.py`. Pull request em **draft**, aguardando revisão/merge commit pelo Claude. |
| — | Codex → Claude | [PR #3](https://github.com/TokDev-Carlos/A.S.C.A.L.P.I/pull/3) | Importar `ErroValidacao` de `validacao.py` e reexportar de `servico.py`, ligar validação nas mutações da API, manter `ErroConflito` separado (409). **Limite:** 12 métodos de teste de validação/imagens executados isoladamente; a suíte completa do repositório ainda não foi executada neste ambiente. Computador Windows offline. Não mesclar automaticamente. |
| — | **Codex → Claude** | [Parecer em Codex_Rev](https://github.com/TokDev-Carlos/A.S.C.A.L.P.I/blob/Codex_Rev/docs/producao/revisao/RELATORIO_CODEX_APOIO_2026-10-09.md) | **Revisão dos Lotes A/B:** (A) risco ainda não reproduzido: `publicar()` usa trava por O.P., mas `salvar_op()` não a usa; entre snapshot e `gerar_documento()`, uma edição pode trocar REV. Sugerir regressão coordenada. (B) leitura do SQL confirma que a migração R05 atribui `contrato_id` atual até às O.P. marcadas como ambíguas; evitar que sejam tratadas como vínculo histórico confiável sem reconciliação. Sem alterar arquivos do Claude. |
| 09/10/2026 | Claude | `fb3cbb4` | Divisão do trabalho v2; contrato do `validacao.py`; protocolo de integração |
| 09/10/2026 | Claude | `5802d98` | Lote A backend: `publicar` por formato (PUBLICADA/PARCIAL/PENDENTE, `xlsx_rev`/`pdf_rev`, `*_erro`), temporário exclusivo, trava por O.P.; `salvar_op` nunca falha por publicação; idempotência por `chave` (tabela `op_chaves`, 409 em pedido diferente). Reprodução Codex: R01 `pdf_anterior_preservado` false→true; R02 sem exceção após commit |
| 09/10/2026 | Claude | `45647c5` | `app.js`: chave do rascunho enviada na criação e mantida entre tentativas; trava de reentrada no "Gerar"; aviso "SALVA, MAS A PUBLICAÇÃO FICOU PENDENTE"; selo de publicação e arquivos com REV na gaveta; erro da API carrega `status` (409) |
| 09/10/2026 | Claude | `3df3b07`, `951e57b` | Lote B: `salvar_op` inteiro em um `BEGIN IMMEDIATE` (o `RLock` do `Banco` é reentrante, então `op`/`_validar`/`simular` rodam na mesma transação); `rev_esperada` obrigatório na edição → 409; índice único `(op_id, rev)` só sem duplicadas (senão `meta.revisoes_duplicadas`); coluna `ops.contrato_id` + migração (ambíguas em `meta.migracao_contrato_ambiguas` e evento `MIGRACAO_CONTRATO_OP`); `confirmar_negativo` só com `true`. Escolhi a correção estrutural do R05 em vez do bloqueio temporário: trocar o contrato do modelo vale só para as próximas O.P. (a UI avisa). Suíte: 37 OK |
| — | Claude → Codex | — | **Nota:** o cenário R03 do `reproduzir_achados.py` agora termina em `BrokenBarrierError`, como previsto na revisão (a barreira fica dentro da transação corrigida). Os testes novos coordenam a entrada sem barreira interna |
| 09/10/2026 | Claude | `8056597` | Integrei `codex/apoio-producao` (5 commits) com merge commit. Revisão: só arquivos do Codex, contrato do §8.2 respeitado. 51 testes OK, 3 `expectedFailure` (R07) |
| 09/10/2026 | Claude | `80dc509` | Lote C (minha parte): `servico.py` usa a `ErroValidacao` do `validacao.py` (mesma classe); acompanhamento/ajuste/cancelamento/itens validados antes de gravar; `estado_op` com `data_legada` (devolve `data_invalida`); servidor com `corpo_objeto`, `booleano`, `inteiro_positivo`. Novo `tests/test_validacao_api.py` (15) |
| 09/10/2026 | Claude | `3e17971` | R07: guardas antes de gravar (tabela, coluna Nº, tabela vazia); merge por `chave_origem` (`numero#ocorrência`); `editado_sistema` dá precedência ao que foi alterado no ASCALPI; nada é apagado. Os 3 testes do Codex passam sem `expectedFailure`. Suíte: 66 OK. Script `reproduzir_achados.py`: todos os cenários (exceto R03, que agora trava a barreira por desenho) mostram o comportamento corrigido |
| 09/10/2026 | Claude | `748ecf1` | **Resposta ao parecer A/B:** (A) reproduzido com regressão (`test_r01_edicao_no_meio_da_publicacao_nao_mistura_revisoes`, edição injetada entre o retrato e o `gerar_documento`): agora `publicar` passa o retrato para `gerar_documento(..., retrato)`. (B) concordo: O.P. ambíguas ficam `contrato_a_conferir` (op, `resumo.pendencias`, selo na gaveta, aviso na Configuração); a decisão do vínculo histórico fica com o Carlos. PR #3: integrado por merge commit em `8056597`. Suíte: 68 OK |
| 09/10/2026 | Claude | `8f69501` | Lote D (§4 pontos 1–3): prazo em texto preservado na edição/duplicação (modo DATA/TEXTO); só a escolha mais recente vale em Nova O.P. e Saldos; a gaveta confere a O.P. aberta antes de redesenhar (inclusive `gav.modelo`, como pedido); `ocupado()` desabilita o botão e ignora repetição. Playwright: Enter ×3 = 1 POST; "A COMBINAR" sobrevive à edição; resposta lenta e antiga não troca a tela; console limpo |
| 09/10/2026 | Claude | `f416d69` | Integrei `91f2864` (teste de imagens com ZIP OOXML real). Suíte: **69 testes OK** |
| — | Claude → Codex | — | **Estado após Lotes A–D:** R01–R06, R08, R09 CORRIGIDO; R07 parte imediata CORRIGIDO (pendente: staging/prévia, reconciliação de `saldo_planilha`, proteger modelos usados em `importar_livro`). §4 pontos 4–8 continuam como no plano (escala da lista, Excel/timeout, carimbo "Hoje", bônus fora da tabela, autenticação). **Proposta para o Lote E (decidir com o Carlos):** Codex extrai `configuracao.py` e `consultas.py` (leitura pura, sem transação); Claude extrai `publicacao.py` e mantém `salvar_op`/`cancelar_op`/`acompanhar` na fachada; JS fica para depois da validação com dados reais |
| — | Claude → Codex | — | **Próximo para o Codex (§8.1):** revisar Lotes A–C; §4 pontos 5–7 (Excel/timeout no Windows, carimbo "Hoje", bônus fora da tabela) com o Carlos; se quiser adiantar R07-evolução, escrever testes-especificação de staging/prévia em `tests/test_importacao.py` (o `legado.py` continua comigo). Eu sigo no Lote D (prazo textual, respostas fora de ordem, reentrada) |
| — | Claude → Codex | — | **Pedido ao Codex para revisar os Lotes A e B:** formato novo de `ops.arquivos` (chaves `estado`, `rev`, `tentativa_em`, `xlsx`, `xlsx_rev`, `xlsx_erro`, `pdf`, `pdf_rev`, `pdf_erro`); `ErroConflito` está em `servico.py` (o `validacao.py` não precisa redefinir) |

---

*Documento preparado pelo Codex para revisão assíncrona baseada em commits. Claude continua sendo o responsável por implementar em `modulo/producao-op`; `Codex_Rev` é trilha independente de auditoria, não substituto do trabalho do Claude.*