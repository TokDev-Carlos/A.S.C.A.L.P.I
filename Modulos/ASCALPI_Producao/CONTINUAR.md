# Continuar o módulo ASCALPI Produção

Estado em 10/10/2026. **Branches (ordens ORG-2/ORG-3, ver `REGRAS_CENTRAIS.md` §2):** fluxo `temporária → claude/producao | codex/producao → modulo/producao-op → Dev-Work → main`. Somente `main`, `Dev-Work`, `claude/*`, `codex/*` e `modulo/*`; histórico encerrado em tags anotadas `historico/*`. Integração em `Dev-Work` só por ordem do Admin; `main` só o Admin.

> **Base inicial congelada:** `producao-base-inicial-v1` (commit `fb96a58`). Veja `docs/producao/releases/BASE_INICIAL.md` e `PLANO_AJUSTES.md`.

## Ambientes (decisão do Admin, 10/10/2026 — vale para toda a documentação)

| Onde | O que é | Pode |
|---|---|---|
| **Legado VBA no servidor da empresa** | o sistema em **uso real** hoje | **nada**: não tocar, não ler escrevendo, não testar nele |
| `D:\MACROS\Legacy_Modules` | cópia de referência do legado | **só leitura** |
| `D:\Programas\ASCALPI_Project` | **desenvolvimento e homologação** (clone Git único) | mexer, reiniciar, migrar e regerar a base à vontade |
| `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao\dados` | **base de homologação** (234 O.P., 45 modelos, 27 prefeituras de teste) | idem; backup só para recuperar testes |
| `D:\Programas\ASCALPI_Local_Archive` | arquivo morto e cópias de segurança dos testes | guardar; não é instalação |
| Nuvem (sessões do Claude/Codex) | implementação e revisão com dados sintéticos | tudo, sem dados de cliente |
| WSL (Ubuntu 24.04) no PC | laboratório de apoio: testes rápidos, git, hashes, LibreOffice | **não vale como aceite** (ver `REGRAS_CENTRAIS.md` §11.1) |

- **Uma instalação só:** `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao`, que é o próprio clone Git. Não criar outra pasta para testar marco nenhum: troca-se o commit do clone (`Sincronizar_ASCALPI.cmd <SHA>`), não a pasta.
- Nada de `dados/`, banco, documentos de cliente, senhas ou caminhos de servidor no GitHub (repositório público). As O.P. locais são de teste, mas têm nomes de clientes, modelos e fotos.

## Fluxo de uma entrega até o teste no Windows

1. Claude implementa e testa na nuvem (`claude/producao` ou `claude/temp/*`).
2. Codex revisa e valida tecnicamente no GitHub; parecer no `QUADRO_TAREFAS.md`.
3. A entrega aprovada sobe pela hierarquia (`executora → modulo/producao-op`).
4. O Admin sincroniza o clone local com o **SHA exato** autorizado: `Sincronizar_ASCALPI.cmd <SHA>` (só `modulo/producao-op`).
5. Testes funcionais no **Windows com Microsoft Excel**, na instalação única.
6. Resultado volta ao GitHub (quadro); correção segue o mesmo ciclo.

## G1 — edição do modelo no Excel

**Estado:** **ACEITO pelo Admin** (10/10/2026), com **DE ACORDO técnico do Codex** em `0ac1f8a` (V-G1, 4 passadas) e na correção da prévia para o Excel real em `955826a` (Windows: 47 diferenças falsas de altura → 0). Relatórios em `docs/producao/revisao/V-G1_*.md`. **Integração no módulo:** candidato preparado na `claude/temp/integracao-g1` (G1 sem o G2), aguardando a revisão do Codex; ver o quadro. Pendência: **MEL-G1-01** — o fluxo funcionar pela tela na instalação única (roteiro abaixo).

**Por que a edição dos modelos de Angra não funcionou (diagnóstico de 10/10):**
1. **Causa principal:** a instalação única está em `modulo/producao-op`, que ainda é G0 — o `web/app.js` não tem o botão EDITAR NO EXCEL, e o servidor não tem as rotas de edição. O G1 só existe na `claude/producao` até a integração.
2. Depois de integrar: a função **nasce desligada** (`edicao_modelo_excel=false` no `config.json` local, que não é versionado). A migração do banco não liga nada; é preciso ligar em Configuração.
3. A tela envia o cabeçalho `X-ASCALPI` em toda gravação (exigido desde `64eeed2`); abrir o sistema por **nome de domínio** é recusado — usar `http://127.0.0.1:8765` ou `http://localhost:8765`.
4. ABRIR NO EXCEL só funciona com o **servidor rodando no Windows** (o servidor abre o arquivo no programa padrão do `.xlsx`). Pelo WSL ou na nuvem, o botão avisa e mostra o caminho da cópia.
5. Nada indica problema nos modelos de Angra em si (`O.P-ATA-ANGRA-MOB` e `O.P-ATA-ANGRA-PLACAS` têm `OP-` no nome da aba; o modelo é extraído com uma aba só e sem macros). Se a validação recusar algum, a mensagem diz o motivo — anotar no roteiro.

- Fluxo: Configuração → EDITAR MODELOS NO EXCEL → Modelos → EDITAR NO EXCEL → COMEÇAR EDIÇÃO (cópia sem proteção em `dados\Modelos\_edicao\`) → ABRIR NO EXCEL → salvar e fechar → VALIDAR ALTERAÇÕES (nome, código, equipamento novo/removido, altura, foto, logo, cabeçalho B3/B8/D2/S4/L2, nome da aba; código sem contrato; prova de geração) → PUBLICAR NOVA VERSÃO (motivo obrigatório) ou DESCARTAR (a cópia fica guardada).
- Garantias (todas com teste):
  - arquivo novo por versão; nada é sobrescrito; versões publicadas e originais nunca são apagadas pela reimportação (V-G1-01);
  - **O.P. já emitida continua ligada ao arquivo do modelo da época; só as novas usam a versão nova**;
  - uma edição aberta por modelo (dois cliques ao mesmo tempo devolvem a mesma);
  - modelo trocado, apagado ou alterado por fora (hash da origem) durante a edição → conflito 409 (V-G1-02);
  - publica exatamente o arquivo da última validação gravada (hash e `ok`);
  - gravação por temporário + promoção: falha de disco não deixa `.tmp`, cópia parcial nem pasta vazia (V-G1-03);
  - validar uma edição já descartada/publicada → conflito, nada gravado (V-G1-04);
  - a prévia segue a precisão real do Excel (altura numérica com tolerância de 0,25 pt; código sem a precisão binária);
  - aba sem `OP-` é recusada; reimportar o livro não substitui aba, título (S4), tipo (B8) nem arquivo do modelo editado no sistema.
- Banco: o G1 leva o esquema de 6 para **7** sozinho na 1ª abertura (verificado com base criada pelo código G0, com O.P.: nada perdido, edição completa funciona depois). `Sincronizar_ASCALPI.cmd` guarda uma cópia da base antes.
- Servidor: porta de uso **exclusivo** — uma 2ª abertura na 8765 não sobe outro servidor sobre a mesma base (no Windows o `SO_REUSEADDR` deixava; foi assim que apareceram duas instâncias); ela avisa e abre o navegador no que já está rodando.
- Código: `ascalpi_producao/modelos_edicao.py`; tabela `modelo_edicoes`; rotas `/api/modelos/{id}/edicao`, `/api/edicoes/{id}/abrir|validar|publicar|descartar`. Testes: `tests/test_edicao_modelo.py`, `tests/test_servidor_porta.py`.
- **Roteiro do teste funcional com os modelos de Angra:** `docs/producao/roteiros/G1_EDICAO_MODELOS_ANGRA.md`.

## G2 — paginação pela altura real

**EM REVISÃO** na `claude/producao` (`e800f30`), aguardando o V-G2. Não está no candidato de integração do G1 e **o aceite do G1 não aprova o G2**. G3, G4 e G5 seguem bloqueados.

## O que é

Módulo independente de **Ordens de Produção** do ASCALPI: tudo é editado no sistema (quantidades, datas ou "DEFINIR", observações); os arquivos `.xlsx` publicados ficam 100% bloqueados (só visualizar) e o PDF sai no padrão exato do VBA legado (`MOD_GERAR_OP V2.4.22`). Depois de validado, entra no núcleo ASCALPI e substitui o legado do servidor.

- Só biblioteca padrão do Python (servidor HTTP + SQLite + HTML/CSS/JS sem build).
- PDF: Excel no Windows (`pdf.py`, motor `excel`) ou LibreOffice (nuvem/WSL, só para teste).
- Especificação e planos: `docs/producao/superpowers/`.

## Como rodar na nuvem (dados sintéticos)

```bash
cd Modulos/ASCALPI_Producao
pip install openpyxl --break-system-packages      # só para testes e dados de demonstração
python -m unittest discover -s tests -t .         # testes leves
python ferramentas/dados_demo.py /tmp/demo        # livro sintético (2 prefeituras fictícias)
python -m ascalpi_producao --dados /tmp/demo servir --porta 8765
```

A base de homologação (importada dos 27 livros `OK-*.xlsm` e do Controle: 27 prefeituras, 45 modelos, 234 O.P. de teste) fica só no PC, em `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao\dados`, ignorada pelo Git. Para usar algum arquivo dela numa sessão em nuvem, anexar na conversa (sem publicar no GitHub).

## Instalação única no PC do Admin (homologação)

Tudo roda de `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao`:

| Comando | Faz |
|---|---|
| `Sincronizar_ASCALPI.cmd <SHA>` | atalho para `ferramentas\sincronizar.py` (com testes): exige o **SHA exato** autorizado no quadro e prova, **antes de mexer no código**, que `origin/modulo/producao-op` é esse SHA (ancestral ou mais novo é recusado); recusa com mudança local versionada ou com o ASCALPI aberto na 8765; guarda e confere uma cópia de `dados` em `D:\Programas\ASCALPI_Local_Archive\snapshots_dados\`; `git pull --ff-only`; confere `HEAD == SHA`. Outra branch só com `--autorizado-admin`. Primeira vez: rodar a cópia do commit revisado (roteiro de Angra, passo 3). Substitui o antigo `Atualizar_Copia_Local.cmd`. |
| `Iniciar_ASCALPI_Producao.cmd` | abre o sistema com a base `dados` do próprio módulo; se já estiver aberto, só abre o navegador. |
| `Testar.cmd` | testes leves (precisa de `openpyxl` no Python usado). |
| `Importar_Legado.cmd` | reimporta os livros (da cópia de referência, só leitura) com **prévia** e confirmação S/N. |

Conferências da base G0 (continuam valendo): logos e fotos dos 27 livros; O.P. do histórico; próxima O.P.; Saldos (itens `0.x` como EXTRA); Configuração → avisos "CONTRATO A CONFERIR" / "SALDO DA PLANILHA A CONFERIR"; data "Hoje" (criação) e, ao editar, "· REV n dd/mm/aaaa".

## Estado da 1ª etapa funcional

| Item | Situação |
|---|---|
| Interface: 7 telas + gaveta (`web/app.js`, módulo ES) | ✅ |
| Correções R01–R09 da revisão do Codex | ✅ (ver `Codex_Plano_para_Claude.md`) |
| Decisões do Carlos: criação imutável + data de cada revisão; `0.x` = extras sem saldo; contratos ficam como estão até o Carlos editar | ✅ |
| Reimportação segura: prévia, modelo congelado por O.P., conferência do saldo da planilha, montante editado no sistema prevalece | ✅ |
| Organização do backend: `configuracao.py`, `publicacao.py`, `consultas.py` (Servico como fachada) | ✅ |
| Instalação única + `Sincronizar_ASCALPI.cmd` (substitui `Atualizar_Copia_Local.cmd`) | ✅ (em revisão no candidato G1) |
| Testes de validação pelo Codex sobre o HEAD final | ⏳ Codex |
| H-1: O.P. de homologação, PDF pelo Excel, comparação com o padrão do legado | ⏳ Admin (no PC, instalação única) |

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
- **Lote E:** `configuracao.py`, `publicacao.py` e `consultas.py` extraídos; `Servico` como fachada; API igual. O `web/app.js` não foi dividido de propósito: a divisão só vale depois da homologação no Windows.
- Suíte: **78 testes OK**. Fluxos no Playwright (queda de rede, duas abas, Enter repetido, respostas fora de ordem) sem regressão.
- Pendente: homologação no Windows e PDF pelo Excel (Admin); testes de validação sobre o HEAD final (Codex); §4 pontos 4 (escala acima de 3.000 O.P.), 5 (Excel em timeout) e 8 (autenticação) ficam para os próximos marcos.

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

- Nunca gravar nos arquivos legados (`D:\MACROS\Legacy_Modules`, só leitura) nem tocar no legado VBA do servidor.
- Nada de dados de clientes, banco, `dados/`, senhas ou caminhos de servidor no GitHub (repositório público). A senha dos `.xlsx` é gerada na primeira execução e fica só em `dados/config.json`.
- Commit com coautoria; resposta no quadro após cada commit.
- Ao terminar uma entrega: rodar os testes, capturar telas, registrar o SHA no quadro; o clone do PC é atualizado pelo Admin com `Sincronizar_ASCALPI.cmd` (nunca copiando pastas).
