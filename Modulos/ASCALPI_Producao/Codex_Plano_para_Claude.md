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
| R01 | P1 | Falha do PDF pode apagar o PDF anterior | Falha parcial mantém documento anterior e informa revisão/erro | ABERTO |
| R02 | P1 | Falha de XLSX após salvar O.P. incentiva duplicação ao repetir | API informa O.P. persistida, publicação pendente e retry seguro | ABERTO |
| R03 | P1 | Criações concorrentes validam saldo fora da transação | Revalidação transacional impede consumo negativo sem confirmação | ABERTO |
| R04 | P1 | Edições simultâneas geram duas REV 1 | Conflito 409 por versão esperada, histórico preservado | ABERTO |
| R05 | P1 | Alterar contrato do modelo desloca consumo histórico | Contrato da O.P. histórica fica imutável sem operação explícita | ABERTO |
| R06 | P1 | Data impossível salva e pode quebrar listagem/painel | API recusa data impossível; leitura tolera legado inválido | ABERTO |
| R07 | P1 | Reimportar Controle remove acompanhamento/histórico | Importação inválida não altera base; reimportação preserva identidade | ABERTO |
| R08 | P2 | Ajuste sem motivo é aceito pelo backend | Validação no servidor recusa pedido inválido sem mutar banco | ABERTO |
| R09 | P2 | Extração de imagens depende de prefixo XML literal | Namespace equivalente não altera fotos/logos extraídos | ABERTO |

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

**Instrução para o próximo ciclo do Codex:** ler HEAD de `modulo/producao-op`; comparar com o último SHA auditado; verificar testes/commits do Claude; atualizar o quadro e os estados R01–R09 em `Codex_Rev`; devolver somente as orientações aplicáveis ao novo HEAD neste arquivo na branch do Claude. Preservar histórico, não reescrever o diagnóstico anterior.

## 7. Primeira ação recomendada ao Claude

1. Ler `CLAUDE.md`, `CONTINUAR.md` e este arquivo. Confirmar que a UI já existe e identificar diferenças do HEAD desde `b691e8e`.
2. Implementar primeiro R01/R02 com testes; não repetir geração de O.P. como resposta a falha de publicação.
3. Prosseguir R03/R04/R05 e depois validação/importação. Reportar a cada lote: **SHA, testes executados, comportamento reproduzido/corrigido e pendências**.
4. Consultar o diagnóstico completo em `Codex_Rev` caso precise da reprodução técnica e do raciocínio de migração, sem fazer merge indiscriminado da branch de auditoria.

---

*Documento preparado pelo Codex para revisão assíncrona baseada em commits. Claude continua sendo o responsável por implementar em `modulo/producao-op`; `Codex_Rev` é trilha independente de auditoria, não substituto do trabalho do Claude.*