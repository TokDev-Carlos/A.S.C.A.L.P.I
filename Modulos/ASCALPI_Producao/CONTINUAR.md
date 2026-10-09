# Continuar o módulo ASCALPI Produção na nuvem

Estado em 09/10/2026 (fim da sessão). Branch: `modulo/producao-op`. **1ª etapa funcional pronta para o teste local.**

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

## Teste local no PC do Carlos (próximo passo)

1. No clone do repositório: `git pull origin modulo/producao-op`.
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
