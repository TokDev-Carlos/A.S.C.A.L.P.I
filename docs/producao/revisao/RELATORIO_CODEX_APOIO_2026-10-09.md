# ASCALPI Produção — parecer Codex de apoio e revisão cruzada
Data: 09/10/2026 (America/Sao_Paulo).
Repositório: `TokDev-Carlos/A.S.C.A.L.P.I`.
Trilhas: `modulo/producao-op` (implementação Claude); `codex/apoio-producao` (entrega Codex); `Codex_Rev` (histórico).

## 1. Divisão verificada
O contrato colaborativo está na seção 8 de `Modulos/ASCALPI_Producao/Codex_Plano_para_Claude.md`, introduzida pelo Claude no commit `fb3cbb44`.
- Claude: R01-R05, ligação de R06/R08 em serviço/API, R07 em `legado.py` e estado de interface.
- Codex: validação pura, testes de R07, extração de imagens R09 e auditoria independente.
- Trabalho realizado em arquivos separados, sem tocar `main`.

## 2. Entrega do Codex em andamento de integração
Branch: `codex/apoio-producao` (base `fb3cbb44`).
Pull request: https://github.com/TokDev-Carlos/A.S.C.A.L.P.I/pull/3 (draft, destino `modulo/producao-op`).

| Área | Arquivos | Entrega |
|---|---|---|
| R06/R08 | `ascalpi_producao/validacao.py`, `tests/test_validacao.py` | Validação pura e 8 testes de contrato |
| R09 | `ascalpi_producao/imagens.py`, `tests/test_imagens.py` | ElementTree por URIs de namespace OOXML, cache atualizado e ETag SHA256; 4 testes de imagens, incluindo pacote ZIP OOXML sintético |
| R07 | `tests/test_importacao.py` | 3 testes de reimportação destrutiva marcados `@expectedFailure` enquanto o Claude corrige `legado.py` |

**Validação realizada:** execução isolada da camada de validação (8 casos) e imagens (3 casos + 1 integração ZIP) no Python local, com subconjunto dos helpers `pacote`; todos passaram. Os 3 testes R07 foram compilados, mas **não foram executados** contra o serviço completo. A suíte oficial `python -m unittest discover -s tests -t .` ainda precisa ser executada pelo integrador no checkout completo. Computador Windows conectado via Desktop Commander estava offline, portanto nenhum ensaio real de Excel/COM foi realizado.

## 3. Revisão parcial do trabalho recente do Claude
Evidências estáticas consultadas no HEAD do Claude após Lote B, incluindo commits `5802d98`, `45647c5`, `3df3b07` e `951e57b`:
- R01/R02: `publicar()` passou a preservar arquivos anteriores em falha de formato; os resultados distinguem revisão/documento e há idempotência para criação.
- R03/R04: `salvar_op()` executa revalidação e gravação na mesma transação, com `rev_esperada` e conflito 409.
- R05: `ops.contrato_id` congela o vínculo para novas O.P. e `simular()` procura o contrato da O.P. quando `excluir_op` está presente.
- O Claude adicionou testes de regressão. **Não há validação independente da suíte completa por esta sessão.**

### Ponto de atenção A — publicação concorrente com edição da mesma O.P.
**Categoria:** risco de corrida a reproduzir, **não confirmado** por execução.

`Servico.publicar()` usa `_trava_publicacao(op_id)`, mas `salvar_op()` não adquire essa trava antes de atualizar a revisão. `publicar()` tira um snapshot de `self.op()` e depois `gerar_documento()` chama `self.op()` novamente. Uma edição entre essas operações pode causar geração de conteúdo REV N+1 com carimbo/associação REV N, ou arquivos substituídos fora da revisão esperada.

**Pedido ao Claude:** acrescentar regressão coordenada (publicação e edição simultâneas), capturar snapshot imutável de revisão e serializar as transições necessárias sem segurar a transação SQLite durante Excel/PDF. Não mudar regra de negócio apenas para satisfazer o teste.

### Ponto de atenção B — vínculo histórico ambíguo na migração R05
**Categoria:** comportamento constatado por leitura do SQL; impacto depende dos dados legados reais.

`Banco._migrar()` monta a lista `ambiguas` por eventos `MODELO_ALTERADO`, mas executa `UPDATE ops SET contrato_id = (SELECT m.contrato_id...) WHERE origem='SISTEMA'` para **todas** as O.P., inclusive IDs ambíguos. O relatório em `meta.migracao_contrato_ambiguas` guarda a ressalva, porém o consumo operacional pode continuar atribuído ao contrato errado até reconciliação. A revisão original recomendava não adivinhar esse vínculo.

**Pedido ao Claude:** na migração, impedir atribuição automática aos IDs ambíguos e expor pendência de reconciliação explícita (sem apagar registros), ou explicar e validar critério alternativo; criar caso sintético `MODELO_ALTERADO` histórico seguido de migração com saldo consistente. Atenção para `json_extract` em eventos cujo `detalhe` não seja JSON válido; conferir `json_valid` ou filtrar robustamente.

## 4. Próximos passos contratados
1. Claude revisa e integra o PR #3 por **merge commit**, sem force-push, quando estabilizar Lotes A/B.
2. Em `servico.py` e `servidor.py`, importar `ErroValidacao` de `validacao.py`, preservando importadores existentes; manter `ErroConflito` separado (409).
3. Remover `@expectedFailure` do R07 apenas depois de corrigir `legado.py`; rodar suíte completa.
4. Codex reaudita os novos SHAs, abre regressões nos arquivos do seu domínio e mantém parecer de risco independente.

Sem dados pessoais, sem modelos/planilhas reais e sem deploy.
