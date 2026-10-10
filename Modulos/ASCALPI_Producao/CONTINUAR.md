# Continuar o módulo ASCALPI Produção na nuvem

Estado em 10/10/2026. **Branches (ordens ORG-2/ORG-3, ver `REGRAS_CENTRAIS.md` §2):** fluxo `temporária → claude/producao | codex/producao → modulo/producao-op → Dev-Work → main`. Somente `main`, `Dev-Work`, `claude/*`, `codex/*` e `modulo/*` são permitidas; histórico encerrado fica em tags anotadas `historico/*`. O módulo (`modulo/producao-op`) tem a base G0 aceita; o G1 está só na executora do Claude (`claude/producao`). Integração em `Dev-Work` só por ordem do Admin; `main` só o Admin.

> **Base inicial congelada:** `producao-base-inicial-v1` (commit `fb96a58`, aceita pelo Carlos). Veja `docs/producao/releases/BASE_INICIAL.md` e `PLANO_AJUSTES.md`. Melhorias só depois do aceite de início de G1.

## G2 — paginação pela altura real (branch `claude/producao`, por ordem do Admin em 10/10/2026)

- **Pedido do Carlos:** a regra do VBA (13 itens na 1ª página, até 15 nas demais) mandava itens para a 2ª página mesmo com espaço na 1ª. Agora o item fica na página **enquanto couber inteiro**; se não couber, a quebra vai **antes** dele. Nada é redimensionado, reordenado nem dividido.
- Cálculo (`ascalpi_producao/paginacao.py`, funções puras): área útil = altura do papel (A4 por padrão) − margens (topo 1,2 cm, base 0), dividida pela escala de "ajustar à largura" que o Excel aplica (colunas B..V em pixels, porcentagem inteira); altura de cada linha visível (`ht` ou a padrão da aba; ocultas = 0); cabeçalho 2..9 na 1ª página; títulos repetidos (`Print_Titles`) em todas; foto que passa da linha (`oneCellAnchor`/`twoCellAnchor`) não é cortada; folga de 4 pt.
- **Configuração → PAGINAÇÃO DOS DOCUMENTOS:** `PELA ALTURA REAL` (padrão) ou `LEGADO DO VBA` (para comparar na homologação). O motor usado fica registrado em cada publicação (`ops.arquivos.paginacao`).
- **Conferência automática:** ao publicar, as páginas previstas são comparadas com as do PDF gerado; se divergirem, a tela avisa "PAGINAÇÃO: PREVISTAS n PÁGINA(S), O PDF SAIU COM m" — mandar essa O.P. para ajuste do cálculo.
- Verificado na nuvem com LibreOffice: 40 combinações de altura (30, 50, 80, 113 pt e mistas) × quantidade (8 a 48 itens), páginas previstas = páginas do PDF em todas. No LibreOffice o cálculo ainda deixa um pouco de sobra (ele escala as colunas de outro jeito); **o ajuste fino vale para o Excel**, que é o motor oficial do PDF — conferir no Windows.
- Testes: `tests/test_paginacao.py` (11). Suíte: **117 testes OK**.
- **Conferir no Windows:** regerar as O.P. que tinham 2 itens sozinhos na 2ª página; comparar com `LEGADO DO VBA`; observar se aparece o aviso de divergência.

## G1 — edição do modelo no Excel (branch `claude/producao`, PR #5; origem preservada na tag `historico/2026-10-09/g1-edicao-modelo`)

**Estado:** **DE ACORDO técnico do Codex** em `0ac1f8a` (V-G1 em 4 passadas) e na correção da prévia para o Excel real em `955826a` (validada no Windows: 47 diferenças falsas de altura → 0; relatórios em `docs/producao/revisao/V-G1_*.md`). Falta o **teste do Carlos no Windows com o Excel real** e a H-1; só depois o G1 entra no módulo e o G2 começa.

- Ligar em **Configuração → EDITAR MODELOS NO EXCEL** (vem desligado; `config.json` com texto no lugar de verdadeiro/falso vale desligado). Aparece o botão **EDITAR NO EXCEL** em cada modelo.
- Fluxo: COMEÇAR EDIÇÃO (cópia sem proteção em `dados/Modelos/_edicao/`) → ABRIR NO EXCEL (só Windows) → salvar e fechar → VALIDAR ALTERAÇÕES (nome, código, equipamento novo/removido, altura da linha, foto, logo, cabeçalho B3/B8/D2/S4/L2, nome da aba; código sem contrato; prova de geração da O.P.) → PUBLICAR NOVA VERSÃO (motivo obrigatório) ou DESCARTAR (a cópia fica guardada).
- Garantias (todas com teste):
  - arquivo novo por versão; nada é sobrescrito; versões publicadas e originais nunca são apagadas pela reimportação (V-G1-01);
  - O.P. emitidas ficam no modelo da emissão; O.P. novas usam a versão nova;
  - uma edição aberta por modelo (dois cliques ao mesmo tempo devolvem a mesma);
  - modelo trocado, apagado ou alterado por fora (hash da origem) durante a edição → conflito 409 (V-G1-02);
  - publica exatamente o arquivo da última validação gravada (hash e `ok`);
  - gravação por temporário + promoção: falha de disco não deixa `.tmp`, cópia parcial nem pasta vazia (V-G1-03);
  - validar uma edição já descartada/publicada → conflito, nada gravado (V-G1-04);
  - a prévia segue a precisão real do Excel: altura comparada como número (linha sem altura = altura padrão; < 0,25 pt é arredondamento) e código numérico sem a precisão binária (2.1000000000000001 = 2.1);
  - aba sem `OP-` é recusada; reimportar o livro não substitui aba, título (S4), tipo (B8) nem arquivo do modelo editado no sistema.
- Servidor local: **toda gravação** exige o cabeçalho `X-ASCALPI: 1` (a tela envia) e endereços por **nome de domínio** são recusados. Acesse por `http://127.0.0.1:8765`, `localhost` ou pelo **IP** do PC (nome do PC na rede não funciona mais).
- Código: `ascalpi_producao/modelos_edicao.py`; tabela `modelo_edicoes` (esquema 7); rotas `/api/modelos/{id}/edicao`, `/api/edicoes/{id}/abrir|validar|publicar|descartar`.
- Testes: `tests/test_edicao_modelo.py` (28, incluindo `test_vg1_*`, `test_excel_*` e a proteção da API). Suíte: **106 testes OK** (só `openpyxl` como dependência de teste).

### Roteiro do teste do G1 no Windows (Carlos)

O G1 muda o banco para o esquema 7. **Não usar a instalação do dia a dia.**

1. Criar uma pasta só para o teste, por exemplo `D:\PROGRAMAS\ASCALPI_Teste_G1`, e nela clonar o repositório: `git clone -b claude/producao https://github.com/TokDev-Carlos/A.S.C.A.L.P.I.git`.
2. Copiar a pasta `dados` da instalação atual para `D:\PROGRAMAS\ASCALPI_Teste_G1\dados` (**cópia**, nunca mover).
3. **Antes de abrir:** na cópia, editar `dados\config.json` e pôr `"publicar": false` (ou apontar `pasta_xlsx`/`pasta_pdf` para pastas dentro da pasta de teste), para o teste não publicar nas pastas reais.
4. Abrir: `cd A.S.C.A.L.P.I\Modulos\ASCALPI_Producao` e `python -m ascalpi_producao --dados D:\PROGRAMAS\ASCALPI_Teste_G1\dados servir --abrir`. O banco da cópia migra sozinho para o esquema 7.
5. Configuração → ligar **EDITAR MODELOS NO EXCEL**.
6. Escolher um modelo que já tenha O.P. emitida: **EDITAR NO EXCEL → COMEÇAR EDIÇÃO → ABRIR NO EXCEL**. No Excel: mudar o nome de um equipamento, a altura de uma linha e trocar uma foto; salvar e **fechar** o Excel.
7. **VALIDAR ALTERAÇÕES**: conferir se a prévia lista exatamente o que foi mudado (sem itens a mais nem a menos). Anotar como o sistema se comporta se validar com o Excel ainda aberto (comportamento do Excel real, não coberto na nuvem).
8. **PUBLICAR NOVA VERSÃO** com um motivo. Conferir: uma O.P. **antiga** desse modelo continua gerando o documento antigo (XLSX e PDF pelo Excel); uma O.P. **nova** sai com o modelo novo, foto e altura certas.
9. Começar outra edição e **DESCARTAR**: a cópia fica em `dados\Modelos\_edicao\`.
10. Anotar no quadro (ou para o Codex registrar) o resultado de cada passo; com tudo certo, o Admin dá o aceite do G1.

## O que é

Módulo independente de **Ordens de Produção** do ASCALPI: tudo é editado no sistema (quantidades, datas ou "DEFINIR", observações); os arquivos `.xlsx` publicados ficam 100% bloqueados (só visualizar) e o PDF sai no padrão exato do VBA legado (`MOD_GERAR_OP V2.4.22`). Depois de validado, entra no núcleo ASCALPI.

- Só biblioteca padrão do Python (servidor HTTP + SQLite + HTML/CSS/JS sem build).
- PDF: Excel no Windows (`pdf.py`, motor `excel`) ou LibreOffice (nuvem/testes).
- Especificação e planos: `docs/producao/superpowers/`.

## Como rodar na nuvem (sem dados reais)

```bash
cd Modulos/ASCALPI_Producao
pip install openpyxl --break-system-packages      # só para testes e dados de demonstração
python -m unittest discover -s tests -t .         # 78 testes leves
python ferramentas/dados_demo.py /tmp/demo        # livro sintético (2 prefeituras fictícias)
python -m ascalpi_producao --dados /tmp/demo servir --porta 8765
```

Os dados reais (27 livros `OK-*.xlsm`, o Controle e a pasta `dados/` importada) **não vão para o GitHub**: o repositório é público e contém dados de clientes. Na máquina do Carlos eles estão em `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao\dados` (importados: 27 prefeituras, 45 modelos com o padrão "OP-" no nome da aba, 1.033 itens de contrato, 230 O.P. do histórico; próxima O.P. 258-26). Para testar com eles numa sessão em nuvem, anexe os arquivos na conversa.

## Teste local no PC do Carlos (base aceita)

1. No clone do repositório: `git pull origin modulo/producao-op` (módulo com a base G0; para o G1 veja a seção acima).
2. Rodar `Modulos\ASCALPI_Producao\Atualizar_Copia_Local.cmd`: faz **backup de `dados`** (`backup_dados_<data>`) e copia o módulo para `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao` sem tocar em `dados`, `config.json` nem bancos.
3. Abrir `Iniciar_ASCALPI_Producao.cmd`. Na 1ª abertura o banco antigo (versão 1) é migrado sozinho até a versão 6, sem apagar nada (verificado com um banco criado pelo código original).
4. Conferir: logos e fotos dos 27 livros; as 230 O.P. do histórico; próxima O.P.; Saldos (itens `0.x` como EXTRA); Configuração → avisos "CONTRATO A CONFERIR" / "SALDO DA PLANILHA A CONFERIR".
5. Gerar 3–5 O.P. de teste e comparar o PDF (Excel no Windows) com o legado; ver a data "Hoje" (criação) e, ao editar, "· REV n dd/mm/aaaa".
6. Reimportar só se precisar: `Importar_Legado.cmd` agora mostra a **prévia** e pede S/N antes de gravar.
7. `Testar.cmd` roda os testes leves (precisa de `openpyxl` no Python usado).

## Estado da 1ª etapa funcional

| Item | Situação |
|---|---|
| Interface: 7 telas + gaveta (`web/app.js`, módulo ES) | ✅ |
| Correções R01–R09 da revisão do Codex | ✅ (ver `Codex_Plano_para_Claude.md`) |
| Decisões do Carlos: criação imutável + data de cada revisão; `0.x` = extras sem saldo; contratos ficam como estão até o Carlos editar | ✅ |
| Reimportação segura: prévia, modelo congelado por O.P., conferência do saldo da planilha, montante editado no sistema prevalece | ✅ |
| Organização do backend: `configuracao.py`, `publicacao.py`, `consultas.py` (Servico como fachada) | ✅ |
| Pacote de teste local (`Atualizar_Copia_Local.cmd`) | ✅ |
| Testes de validação pelo Codex sobre o HEAD final | ⏳ Codex |
| Teste com dados reais, PDF pelo Excel, comparação de amostras | ⏳ Carlos (no PC local) |

Notas da interface:
- `index.html` carrega `app.js` com `type="module"`; o `servidor.py` força `text/javascript` para `.js` (o registro do Windows às vezes diz `text/plain` e o navegador recusaria o módulo).
- A busca (global e da tela Ordens) é feita no navegador, sem acento e sem diferenciar maiúsculas (o `LIKE` do SQLite diferencia "ç/Ç"); a lista de O.P. fica em cache por 20 s e é esquecida ao salvar.
- Preferências locais (try/catch): `ascalpi.op.rascunho`, `ascalpi.ordens.vista`, `ascalpi.painel.entregas`, `ascalpi.saldos.filtro`.
- Imagens só são pedidas quando a API diz que existem (`logo`, `fotos`, `foto`), para não gerar 404 no console; se falharem viram ícone.
- Pendências conhecidas: conferir com fotos/logos reais; o seletor de data mostra o formato do Windows (pt-BR no PC do Carlos).

Pedido do Carlos: "tabelas em blocos, mais cores, fluidez, CSS e JS, no padrão do ASCALPI, misturando ideias do UStracker; sem testes pesados".

## Estabilização (plano do Codex, `Codex_Plano_para_Claude.md`)

Divisão do trabalho na seção 8 daquele arquivo. Verificado nesta sessão:
- **Lote A (R01, R02) — corrigido.** Publicação por formato sem apagar o anterior; O.P. salva nunca vira erro de criação; criação idempotente por `chave` (retry após queda de rede devolve a mesma O.P.). `tests/test_publicacao.py` (9 testes). Suíte: 27 testes OK.
- **Lote B (R03, R04, R05) — corrigido.** Salvar O.P. numa única transação; edição exige `rev_esperada` (conflito 409); cada O.P. guarda o contrato da emissão (`ops.contrato_id`, migração automática ao abrir o banco). `tests/test_concorrencia.py` (10 testes). Suíte: 37 testes OK.
- **Lote C (R06, R07, R08) e R09 — corrigidos em conjunto.** Codex: `validacao.py`, `imagens.py` por namespace, testes de importação. Claude: validação ligada no serviço/API antes de gravar; data legada inválida não derruba a lista (`data_invalida`); reimportação do Controle sem apagar (identidade `chave_origem`, campos editados no sistema preservados). Suíte: 66 testes OK.
- **Lote D (interface) — corrigido.** Prazo em texto (ex.: A COMBINAR) preservado ao editar; respostas antigas não substituem a tela; Enter/clique repetido ignorado. Parecer do Codex sobre A/B atendido (documento e REV do mesmo retrato; O.P. com contrato ambíguo marcadas "CONTRATO A CONFERIR"). Suíte: **69 testes OK**.
- **Decisões do Carlos aplicadas:** (1) data de criação imutável ("Hoje" do documento) e cada revisão registra a sua data (`ops.revisado_em`; documento mostra "· REV n dd/mm/aaaa"); (2) itens `0.x` são extras: contam na O.P., não precisam estar no contrato e não têm saldo; (3) contratos ficam como estão; o montante editado no sistema prevalece ao reimportar o livro.
- **R07 complemento:** `importar --previa`; arquivo de modelo nunca sobrescrito (O.P. emitidas ficam no modelo da emissão, `ops.modelo_arquivo`); falha no banco remove os arquivos novos; conferência do SALDO da planilha e valores ausentes viram pendência.
- **Lote E:** `configuracao.py`, `publicacao.py` e `consultas.py` extraídos; `Servico` como fachada; API igual. O `web/app.js` não foi dividido de propósito: a divisão só vale depois do teste com dados reais.
- Suíte: **78 testes OK**. Fluxos no Playwright (queda de rede, duas abas, Enter repetido, respostas fora de ordem) sem regressão.
- Pendente: validação com dados reais e PDF pelo Excel (Carlos); testes de validação sobre o HEAD final (Codex); §4 pontos 4 (escala acima de 3.000 O.P.), 5 (Excel em timeout) e 8 (autenticação) ficam para os próximos marcos.

## API disponível (servidor.py)

| Rota | Retorno |
|---|---|
| `GET /api/painel` | `contagem` por situação, `em_producao`, `semana`, `por_mes[12]`, `por_prefeitura` (top 8 + OUTRAS), `proximas`, `atrasadas`, `sem_data`, `alertas_saldo`, `saldo_negativos`, `saldo_encerrados`, `eventos` |
| `GET /api/prefeituras` | + `logo` (bool), `ops_ano`, `contratos` |
| `GET /api/prefeituras/{id}/logo` | imagem (ETag, cache 1 dia) |
| `GET /api/modelos?prefeitura_id=&todos=1` | + `logo`, `fotos` (4 primeiras linhas com foto), `com_foto`, `ops` |
| `GET /api/modelos/{id}?excluir_op=` | linhas com `saldo`, `montante`, `realizado`, `previsao`, `consumido`, `foto` (bool) |
| `GET /api/modelos/{id}/foto/{linha}` · `/logo` | imagem |
| `GET /api/ops?texto=&ano=&prefeitura_id=&situacao=&estado=A,B` | + `estado`, `dias`, `prazo_efetivo`, `itens`, `pecas`, `ata` |
| `GET /api/ops/{id}` | + `estado`, `itens`, `revisoes`, `arquivos` |
| `POST /api/ops` · `PUT /api/ops/{id}` | `{modelo_id, obra, solicitante, tipo, prazo, itens:[{linha,quantidade,inauguracao,observacao}], motivo, confirmar_negativo}` → `{precisa_confirmacao, simulacao}` ou `{ok, op_id, op, publicacao}` |
| `POST /api/ops/{id}/acompanhamento` | campos `status_instalacao`, `entrega_atualizada`, `material_obra`, `fotografico`, `obs` |
| `POST /api/ops/{id}/cancelar` `{motivo}` · `/publicar` | |
| `GET /api/ops/{id}/documento.xlsx` · `.pdf?baixar=1` | arquivo |
| `PUT /api/ops/{id}` | exige `rev_esperada` (REV que está sendo editada); outra REV → 409 |
| `GET /api/resumo` | + `pendencias`: `contrato_a_conferir`, `revisoes_duplicadas`, `saldo_a_conferir` |
| `POST /api/ops` com `chave` | idempotente: mesma chave e mesmo pedido → `{ok, repetida: true, op_id}`; pedido diferente → 409. `publicacao.estado`: PUBLICADA / PARCIAL / PENDENTE |
| `GET /api/contratos?prefeitura_id=` · `/api/contratos/{id}/saldo` · `POST .../ajuste {codigo,montante,ajuste,motivo}` | |
| `PATCH /api/modelos/{id}` `{contrato_id, ativo}` · `GET/PUT /api/config` · `GET /api/eventos` (com `op:{numero,obra}`) · `GET /api/ops/proximo` | |

Situação da O.P. (`estado_op`, pelas colunas do Controle): CANCELADA (situação ou status CANCELADO/DUPLICADO) > INSTALADA (status OK) > NA_OBRA (material obra OK ou entrega OK) > SEM_DATA > ATRASADA (prazo efetivo < hoje; entrega atualizada com data substitui o prazo) > PROXIMA (≤ 3 dias) > NO_PRAZO.

## Referência do `app.js` (implementado)

Base visual (já no CSS): tokens do Painel ASCALPI (`--navy #123252`, `--blue #0f5da8`, `--teal`, `--green`, `--orange`, `--purple`, `--red`, `--slate`), topo em degradê, abas de módulo, `.heroi` com degradê por tela (`.nova .ordens .saldos .modelos .config`), `.kpi` com faixa, `.badge`, `.pilula` + classe `e-<ESTADO>` (define `--estado`/`--estado-soft`). Do UStracker: onda no clique (`.onda`), botão ocupado (`aria-busy`), barra de progresso (`body.carregando`/`carregou`), filtro por coluna (`.tf-*`).

Peça marcante: **a ficha da O.P.** (`.ficha` com faixa da situação, número grande, picote `.ficha-picote`, rodapé com prazo/equipamentos/rev).

Infraestrutura:
- Rotas por hash: `#/painel`, `#/nova`, `#/nova?de=ID` (duplicar), `#/editar/ID`, `#/ordens?estado=&texto=`, `#/saldos?p=&c=`, `#/modelos`, `#/config`; `?op=ID` em qualquer tela abre a gaveta.
- `api()` liga a barra de progresso e o `#status-sistema` (`.ocupado`; `.erro` + "SEM CONEXÃO" se o servidor cair).
- `aviso(msg, 'ok'|'erro')` em `#toast`; `dialogo({titulo, sub, corpo, rotulo, perigo, largo, semRodape, validar})` usando `#dlg` (form method=dialog; botões "nao"/"sim").
- Atalhos: `/` busca global, `n` nova O.P., `r` atualizar, `Esc` fecha gaveta/busca.
- Busca global no topo (`#busca-global` → `#busca-resultados`, itens `.busca-item`, setas + Enter).
- Imagem que falhar vira ícone (`error` em captura).
- Dica flutuante `#tip` para barras dos gráficos (hover e foco), com tabela `.sr` equivalente.

Telas:
1. **Painel**: herói com saudação e data + botões; KPIs (Em produção azul, Atrasadas vermelho, Entrega em 7 dias laranja, Sem data cinza-azulado, Na obra teal, Instaladas verde; cada um é link para Ordens filtradas; contagem anima uma vez); "Entregas" com alternância Próximas/Atrasadas (`.ficha-linha`); "O.P. por mês" (`.colunas`, uma série azul, rótulo só no mês atual e no maior); "Prefeituras com mais O.P." (`.barras-h`, valor na ponta, OUTRAS em cinza); "Alertas de saldo"; "Atividade recente" (`.atividade-item`).
2. **Nova O.P.** em 3 passos (`.passo`): (1) prefeituras em blocos com logo e busca (`.pref`), depois `.pref-escolhida` + chips de modelo (`.modelo-chip`); (2) obra, solicitante (datalist das O.P. da prefeitura), prazo com `.segmentado` Data/Definir, tipo (datalist MOB/ABRIGO/PLACA), motivo só ao editar; (3) equipamentos em blocos (`.equip`: foto 4:3, código `.cod` (`.bonus` p/ 0.x), selo de quantidade, mini medidor (realizado teal, previsão roxo, esta O.P. roxo listrado, excedente vermelho), "Saldo X → depois Y", contador −/+, inauguração e observação abrem quando tem quantidade). Barra fixa `.resumo-op` (número, prefeitura/ATA, nº equipamentos, peças, material detectado, situação do saldo, Limpar, Gerar O.P.). Rascunho no `localStorage` (try/catch) com aviso "restaurado — descartar". Saldo negativo → diálogo com tabela antes/O.P./depois e "Continuar com saldo negativo". Sucesso → `#/ordens?op=ID`.
3. **Ordens**: herói; `.segmentado` de situações com contagem (Todas, Em produção, Atrasadas, Prazo próximo, Sem data, Na obra, Instaladas, Canceladas); filtros (busca, prefeitura, ano, ordem: recentes/prazo/número); alternância Blocos/Tabela (lembrada); blocos = `.fichas`; tabela = `.tabela` com filtro por coluna estilo planilha (ordenar, buscar, marcar valores).
4. **Gaveta da O.P.** (`.gaveta`): cabeçalho `.g-cab` com faixa da situação; ações (Ver PDF, Baixar XLSX/PDF, Editar → nova REV, Duplicar, Republicar, Cancelar); abas Resumo (`.detalhes`), Equipamentos (`.item-op` com foto do modelo), Acompanhamento (`.etapas`: Solicitada, Prazo, Entrega [OK/FALTA/nova data], Material na obra [OK], Instalação [OK; CANCELADO só no legado], Fotográfico [OK], Obs; cada clique salva na hora), Revisões. O.P. do legado: só acompanhamento + `.nota-legado`.
5. **Saldos**: prefeituras `.pref-mini` com logo, contratos em `.segmentado`, KPIs (itens, negativos, encerrados, % usado), filtros (Todos/Negativos/Encerrados/Com saldo + busca), legenda, `.saldo-card` com `.medidor` (realizado `--serie-real`, previsão `--serie-prev`, excedente `.exc` vermelho listrado; cores validadas para daltonismo), botão Ajustar → diálogo (montante, ajuste ±, motivo obrigatório).
6. **Modelos**: agrupados por prefeitura (`.grupo-pref` com logo), `.modelo-card` com 4 fotos, selos (ATA, nº equipamentos, com foto, O.P.), contrato do saldo (select), ativo (`.interruptor`), "Ver equipamentos" → diálogo `.galeria`.
7. **Configuração**: publicar (interruptor), pastas xlsx/pdf, motor de PDF, situação (motor efetivo, pastas), atividade.

## Regras que continuam valendo

- Nunca gravar nos arquivos legados (`D:\MACROS\Legacy_Modules`); trabalhar em cópias.
- Nada de dados de clientes, banco ou senhas no GitHub (repositório público). A senha dos `.xlsx` é gerada na primeira execução e fica só em `dados/config.json`.
- Commit com coautoria; push só quando o Carlos pedir.
- Ao terminar a interface: rodar os testes, capturar telas, copiar a pasta do módulo (sem `dados/`) para `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao`.
