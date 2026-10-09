# ASCALPI v1 — Módulo Produção (Ordens de Produção) — Desenho

- **Data:** 09/10/2026 — revisão 2 (direção do Carlos às 12:31)
- **Status:** para revisão
- **Decisões do usuário:**
  1. Base: núcleo do CJL System reaproveitado em `D:\PROGRAMAS\ASCALPI_Project`.
  2. Escopo da v1: Ordens de Produção (Compras na versão seguinte).
  3. PDF gerado pelo próprio Excel.
  4. **O sistema controla tudo**: cadastro e numeração das O.P., contratos, saldo e histórico ficam no ASCALPI. O `.xlsx` e o PDF são **gerados sob demanda** (baixar/enviar), mantendo **exatamente o padrão visual atual**.

## 1. Objetivo

Criar e controlar as Ordens de Produção dentro do ASCALPI. A O.P. é um registro do sistema; o documento (`.xlsx`/PDF) é uma "impressão" desse registro, gerada quando alguém pede, idêntica à que o VBA produz hoje.

## 2. Fora do escopo da v1 (v1.1)

- Etapas por setor (colunas G:R: corte, dobra, …, montagem) e sessão com tempo por setor.
- Notificação no WhatsApp.
- Medições/instalação lançadas no sistema (na v1 o saldo = linha de base importada + O.P. do sistema; a tela permite marcar O.P. como instalada).
- Ordens de Compra.

## 3. Fontes legadas (referência)

- Motor `MOD_GERAR_OP` V2.4.22 nas 27 planilhas `OK-<CIDADE>_O.P.xlsm` — referência de **layout, impressão e regras de saldo**.
- Controle `2_Controle_Ordens_De_Producao_Novo_Carlos.xlsm` — referência das **colunas da lista de O.P.** e fonte do histórico a importar.
- As planilhas legadas deixam de ser usadas para gerar O.P. depois da migração; o ASCALPI só as lê na importação.

## 4. Decisões de desenho

- **D1 — Modelo de documento por contrato.** Cada aba de O.P. (`OP_<ID>`) dos `.xlsm` vira um **modelo do sistema** (`.xlsx` com uma aba só), extraído pelo próprio Excel (`Worksheet.Copy`, preserva formatação, mesclas e imagens). Fica guardado no ASCALPI, com hash e versão. Trocar o modelo = enviar novo `.xlsx` pela tela de Modelos.
- **D2 — Documento idêntico por construção.** Um worker PowerShell controla uma instância nova e isolada do Excel e repete a sequência do VBA (seção 5.1), usando o `CountA` do próprio Excel.
- **D3 — Sistema é a fonte da verdade.** Número da O.P., itens, quantidades, prazo, solicitante, obra, status e saldo vivem no banco do CJL (repositório transacional com `write_scope`). Nada depende das pastas do servidor PCP nem dos logs legados.
- **D4 — Numeração no sistema.** Formato `NNN-AA` (mínimo 3 dígitos, reinicia a cada ano), contador no banco, reservado dentro do `write_scope` (sem duplicidade entre estações). Na migração o contador do ano começa no maior número já usado (histórico importado) + 1.
- **D5 — Documento sob demanda.** "Baixar XLSX", "Baixar PDF" e "Enviar" geram na hora a partir do registro atual. Cada geração fica registrada (data, usuário, revisão da O.P., hash) e o arquivo gerado é guardado como evidência na área de documentos do sistema (padrão já usado pela Exportação do CJL). O carimbo "Hoje" do modelo é a hora da geração, como no legado.
- **D6 — Revisão.** Editar uma O.P. já emitida incrementa `REV` (célula `U2` do documento) e mantém o histórico.
- **D7 — Saldo no sistema.** Na migração importa-se a linha de base de cada item da `TAB_SALDO_<ID>` (MONTANTE, QUANT., PREVISÃO, SALDO). Saldo atual = MONTANTE − (QUANT. + PREVISÃO da base + O.P. do sistema). Regras de código e avisos idênticas ao VBA (seção 5.4).
- **D8 — Onde roda.** Geração de documento na estação Windows com Excel 16. Sem Excel, a O.P. pode ser criada e consultada; só o download fica indisponível com mensagem clara.
- **D9 — Regras do CJL respeitadas.** R-0287: o ambiente de desenvolvimento nasce sem dados de produção (`Data`, `Shared`, `Repo`, `Logs`, `Temp`, `Export` vazios). R-0264: nada é gravado fora do projeto sem autorização da etapa.
- **D10 — Pasta do servidor opcional.** Se desejado, uma configuração "copiar PDF emitido para pasta" (ex.: pasta de rede do PCP) pode ser ligada depois; não faz parte do controle.

## 5. Contrato de fidelidade e regras

### 5.1 Documento `.xlsx`/PDF (ordem exata do VBA V2.4.22)

1. Abrir o modelo do contrato (somente leitura, macros desativadas). Desproteger (senha legada), limpar `D10:E100 | S10:S100 | V2 | V8 | D3:R4` (com mesclas), reexibir `9:100`, limpar outline, `ResetAllPageBreaks`, `PrintArea = ""`.
2. Preencher (1ª célula da área mesclada): `P2` = nº (`258-26`), `U2` = revisão, `B3` = cliente, `D3` = obra, `V2` = prazo (data), `V8` = solicitante, `B8` = tipo; por linha 10..100: `D` quantidade, `E` inauguração (E:F), `S` observação (S:V).
3. `Worksheet.Copy` → pasta nova com só essa aba.
4. Outline: reexibir/limpar `9:100`, `SummaryRow = xlBelow`, `SummaryColumn = xlRight`, agrupar cada linha 10..100 com `CountA(Dn) = 0`, `ShowLevels RowLevels:=1`, linha 9 visível; borda inferior fina em `B:V` da última linha visível com `CountA(Bn:Vn) > 0` (procura de 100 a 10; mínimo 10).
5. Proteção: `Cells.Locked = False`; travar `G10:S100 | B1:C100 | B1:S9`; destravar `V2 | U2`; `Protect` senha legada, `UserInterfaceOnly = True`, `AllowFormatting* = False`.
6. Impressão: N = linhas visíveis com conteúdo; N ≤ 13 → 1 página; senão 13 na 1ª e o resto em `ceil(resto/15)` páginas iguais (primeiras +1). Quebras antes da linha real do ordinal visível `acumulado + 1`. `PrintArea = B2:V<última>`, `Zoom = False`, `FitToPagesWide = 1`, `FitToPagesTall = False`, **`Orientation = 1` (retrato)**, centralizado na horizontal, margens (cm) 1,2 / 0 / 0,1 / 0,1 / 0 / 0.
7. `SaveAs` `.xlsx` (51), reabrir, reaplicar 4–6, salvar.
8. PDF: abrir o `.xlsx` só leitura, `ExportAsFixedFormat xlTypePDF, xlQualityStandard, IncludeDocProperties True, IgnorePrintAreas False`.

### 5.2 Nome do arquivo baixado

`sanitizar(SEQ - CLIENTE - OBRA - TIPO - MATERIAL)` (máx. 180), igual ao legado: `\ / : * ? " < > | [ ]` → espaço; mantém `0-9 A-Z a-z`, espaço, `( ) - . _`; acentos removidos; outros → espaço; espaços colapsados; pontas sem `.`/espaço; vazio → `SEM_NOME`. Ex.: `258-26 - CAXIAS-RJ - CAMPO BOSSA NOVA - MOB - CARBONO INOX.pdf`.

### 5.3 Tipo e material

- Tipo (B8): contém `ABRIGO` → `ABRIGO`; contém `PLACA` → `PLACA`; senão `MOB`.
- Material: B8 contém `INOX` → `CARBONO+INOX`; senão pelos nomes dos itens com quantidade: INOX e não-INOX → `CARBONO+INOX`; só INOX → `INOX`; senão `CARBONO`.

### 5.4 Saldo e códigos

- Código: vírgula→ponto, sem espaços; válido = dígitos com pontos isolados. Código-base = antes do 1º ponto (`1.2`→`1`), exceto `0.x` (bônus), que vale exato e não entra na checagem.
- Saldo do item = `0` se MONTANTE ≤ 0; senão `MONTANTE − consumido`, exibido `ACABOU` quando zero.
- Validação da O.P.: base inexistente → bloqueia. Antes numérico: depois = antes − qtd (`< 0` negativo, `= 0` encerrado). Antes `ACABOU` com qtd > 0 → negativo (`-<qtd> *saldo anterior ja estava encerrado*`). Negativo → exige confirmação explícita (registrada na O.P.); encerrado → aviso.

## 6. Arquitetura

```
Painel (WebView2) ──HTTP local──► painel.py (núcleo CJL)
                                   └─ Modulos/Producao/
                                       ├─ nomes.py          texto, nome de arquivo, tipo, material
                                       ├─ numeracao.py      formato NNN-AA e próximo número
                                       ├─ contrato.py       códigos, saldo, simulação
                                       ├─ modelos.py        importação dos .xlsm (contratos, itens, saldo base, linhas)
                                       ├─ historico.py      importação das O.P. do Controle legado
                                       ├─ excel_worker.ps1  Excel COM: extrair modelo / gerar documento
                                       ├─ excel.py          ponte Python→PowerShell (job/result JSON, timeout, PID)
                                       ├─ documentos.py     monta o job a partir do registro e guarda a evidência
                                       ├─ service.py        CRUD, regras, saldo (Plano 2)
                                       └─ cli.py            linha de comando (testes e aceite)
```

Criar O.P. (write_scope): validar → simular saldo → confirmar se preciso → reservar número → gravar O.P. e itens. Baixar documento: ler registro (read_scope) → gerar fora da trava (Excel) → registrar a emissão (write_scope) → entregar o arquivo.

## 7. Modelo de dados (Plano 2)

- `prod_contratos` — id, cliente_id → `clientes`, contrato_id (`CIMASP`), numero_contrato (`FOR-29/2025`), descrição, tipo_b8 padrão, ativo.
- `prod_modelos` — id, contrato_id, versão, arquivo, sha256, origem, ativo.
- `prod_modelo_linhas` — modelo_id, linha (10..100), codigo, equipamento.
- `prod_contrato_itens` — contrato_id, codigo, equipamento, valor_unitario, montante, quant_base, previsao_base.
- `prod_ops` — id, seq, numero, ano, revisao, cliente_id, contrato_id, obra, solicitante, prazo, tipo_b8, tipo, material, status (`ABERTA`, `EMITIDA`, `INSTALADA`, `CANCELADA`), saldo_status, confirmou_saldo_negativo, campos do Controle (entrega atualizada, material obra, status instalação, fotográfico, obs.), origem (`ASCALPI`/`LEGADO`), criado_por/em.
- `prod_op_itens` — op_id, linha, codigo, codigo_base, equipamento, quantidade, inauguracao, observacao.
- `prod_documentos` — op_id, revisao, tipo (`XLSX`/`PDF`), arquivo, sha256, modelo_id, gerado_por/em.
- `counters` (existente) — `op_<ano>`.

## 8. Telas (Plano 2)

1. **Ordens de Produção** — lista no formato do Controle (Nº, Cliente, Obra, Solicitante, Equipamentos, Material, Solicitação, Entrega, Entrega atualizada, Material obra, Status instalação, Fotográfico, Obs.), filtros, botões Baixar XLSX/PDF.
2. **Nova/Editar O.P.** — cliente → contrato → obra, prazo, solicitante, tipo → grade com as linhas do modelo e saldo antes/depois ao vivo → confirmação de saldo negativo → salvar.
3. **Saldos de contrato** — por contrato, colunas como a `TAB_SALDO`, O.P. por item, marcar instalada.
4. **Modelos e contratos** — importar `.xlsm` legado, ver/atualizar modelo de cada contrato, itens e montantes.
5. Permissões: `PRODUCAO_OP_CRIAR` (PCP), `PRODUCAO_OP_CONSULTAR` (todos), `PRODUCAO_ADMIN`.

## 9. Migração

1. Importar dos 27 `.xlsm`: clientes, contratos, modelos (extraídos pelo Excel), itens e saldo base.
2. Importar o histórico de O.P. da tabela do Controle (origem `LEGADO`, sem itens detalhados quando não houver) e ajustar o contador do ano.
3. A partir do corte, as O.P. passam a ser criadas só no ASCALPI.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Excel preso após falha | worker grava PID; ponte encerra no tempo-limite; instância sempre nova |
| Política de execução do PowerShell | `-ExecutionPolicy Bypass` só no processo |
| Modelo extraído diferente do original | aceite pixel a pixel contra PDFs reais emitidos pelo legado |
| Saldo divergente na migração | importação confere SALDO recalculado = SALDO da planilha item a item |

## 11. Planos

- **Plano 1 — Motor de documento e regras**: fundação, regras puras, importação de modelos, extração de modelos e geração de documento pelo Excel, linha de comando, aceite de fidelidade.
- **Plano 2 — Produção no ASCALPI**: banco, serviço, API, telas, histórico, permissões, corte.
- **Plano 3 — v1.1**: setores, WhatsApp, medições, Compras.

## 12. Ambiente oficial do ASCALPI (Windows) — decisão de 09/10/2026 12:39

Igual ao UStracker instalado neste computador:

| O quê | Onde | Quem grava |
|---|---|---|
| Programa (App, Runtime Python assinado, Host, modelos padrão) | `C:\Program Files\ASCALPI` | só administradores (instalador) |
| Dados (banco/seed, `Repo`, `Shared` com modelos e documentos emitidos, `Logs`, `Temp`, `Export`, `Backups`, `Config`) | `C:\ProgramData\ASCALPI\UserData` | usuários do Windows (permissão Modificar) |
| Ligação | junção `C:\Program Files\ASCALPI\UserData` → `C:\ProgramData\ASCALPI\UserData` | instalador |
| Estado por usuário (cache SQLite local, sessão, preferências, WebView2) | `%LOCALAPPDATA%\ASCALPI\Instancias\<id>` | o próprio usuário |
| Caminhos de negócio (pasta de dados, pasta opcional para cópia de PDF, futuro Mestre em rede) | escolhidos **na instalação** e gravados em `UserData\Config\instalacao.json` | instalador / administrador |

- Desinstalar: **Manter dados** ou **Remover tudo** (antes copia para `Documentos\ASCALPI_Backups\Desinstalacao_<data>`).
- Nenhum caminho fixo no código: tudo deriva da raiz do programa, da junção `UserData` e do `instalacao.json`.
- Isso oficializa no ASCALPI o que as regras R-0286/R-0287 do CJL deixavam por raiz escolhida; uma regra nova deve registrar o ambiente oficial nos documentos mestres (5-Docs).
- Etapa seguinte (depois de validar): servidor na nuvem como o UStracker, com as estações como clientes.

## 13. Aceite da v1

1. Para 3–5 O.P. reais, o PDF gerado pelo ASCALPI tem o mesmo número de páginas, o mesmo texto e diferença de pixels só na área do carimbo "Hoje".
2. Duas estações criando O.P. ao mesmo tempo nunca repetem número.
3. Saldo importado confere com a planilha no corte.
