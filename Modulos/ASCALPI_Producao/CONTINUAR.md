# Continuar o módulo ASCALPI Produção na nuvem

Estado registrado em 09/10/2026. Branch: `modulo/producao-op`.

## Revisão independente — 09/10/2026

- Base revisada: `b691e8e66edc65e515d8596d87288dc06101812c`.
- Suíte existente: 18 testes, OK. Diagnóstico adicional: 10 cenários reproduzidos, 9 grupos de achados.
- Próximo trabalho de código: corrigir publicação, integridade transacional, associação de contrato, validação e reimportação antes da refatoração geral.
- Plano: [`PLANO_PARA_CLAUDE.md`](../../docs/producao/revisao/PLANO_PARA_CLAUDE.md).
- A interface já foi implementada. As descrições detalhadas abaixo servem como referência; não são tarefas para reescrevê-la.
- As capturas e validações de interface abaixo foram registradas pela sessão anterior; esta revisão não refez o aceite visual real. Os defeitos do plano ainda aguardam correção.

## O que é

Módulo independente de **Ordens de Produção** do ASCALPI: tudo é editado no sistema (quantidades, datas ou "DEFINIR", observações); os arquivos `.xlsx` publicados ficam 100% bloqueados (só visualizar) e o PDF sai no padrão exato do VBA legado (`MOD_GERAR_OP V2.4.22`). Depois de validado, entra no núcleo ASCALPI.

- Só biblioteca padrão do Python (servidor HTTP + SQLite + HTML/CSS/JS sem build).
- PDF: Excel no Windows (`pdf.py`, motor `excel`) ou LibreOffice (nuvem/testes).
- Especificação e planos: `docs/producao/superpowers/`.

## Como rodar na nuvem (sem dados reais)

```bash
cd Modulos/ASCALPI_Producao
pip install openpyxl --break-system-packages      # só para testes e dados de demonstração
python -m unittest discover -s tests -t .         # 18 testes leves
python ferramentas/dados_demo.py /tmp/demo        # livro sintético (2 prefeituras fictícias)
python -m ascalpi_producao --dados /tmp/demo servir --porta 8765
```

Os dados reais (27 livros `OK-*.xlsm`, o Controle e a pasta `dados/` importada) **não vão para o GitHub**: o repositório é público e contém dados de clientes. Na máquina do Carlos eles estão em `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao\dados` (importados: 27 prefeituras, 45 modelos com o padrão "OP-" no nome da aba, 1.033 itens de contrato, 230 O.P. do histórico; próxima O.P. 258-26). Nesta revisão, os testes em nuvem usam somente dados sintéticos; a validação com arquivos reais fica para uma etapa local autorizada.

## Progresso da interface em blocos: implementada; aceite operacional pendente

| Etapa | Situação |
|---|---|
| Backend: fotos dos equipamentos e logo (`imagens.py`), situação da O.P. (`servico.estado_op`), `/api/painel`, rotas de imagem | ✅ pronto e testado |
| `web/index.html` (casca) e `web/app.css` (visual completo + bloco "complementos usados pelo app.js" no fim) | ✅ |
| `web/app.js` novo (módulo ES, ~1.950 linhas): infraestrutura + Painel (etapa 1), Nova O.P. + Ordens + gaveta (etapa 2), Saldos + Modelos + Configuração (etapa 3) | ✅ commits `fa799bb`, `b0de808`, `0331524` |
| Conferido com capturas (Playwright, 1366px e 390px), console sem erros, fluxo gerar → saldo negativo → REV → cancelar testado | ✅ (dados de demonstração, sem fotos/logos) |
| **Validação operacional posterior à estabilização:** copiar a pasta `Modulos/ASCALPI_Producao` (sem `dados/`) para `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao` no PC do Carlos e conferir com os 27 livros reais (fotos, logos, 230 O.P.) | ⏳ |

Notas da interface:
- `index.html` carrega `app.js` com `type="module"`; o `servidor.py` força `text/javascript` para `.js` (o registro do Windows às vezes diz `text/plain` e o navegador recusaria o módulo).
- A busca (global e da tela Ordens) é feita no navegador, sem acento e sem diferenciar maiúsculas (o `LIKE` do SQLite diferencia "ç/Ç"); a lista de O.P. fica em cache por 20 s e é esquecida ao salvar.
- Preferências locais (try/catch): `ascalpi.op.rascunho`, `ascalpi.ordens.vista`, `ascalpi.painel.entregas`, `ascalpi.saldos.filtro`.
- Imagens só são pedidas quando a API diz que existem (`logo`, `fotos`, `foto`), para não gerar 404 no console; se falharem viram ícone.
- Pendências conhecidas: conferir com fotos/logos reais; o seletor de data mostra o formato do Windows (pt-BR no PC do Carlos).

Pedido do Carlos: "tabelas em blocos, mais cores, fluidez, CSS e JS, no padrão do ASCALPI, misturando ideias do UStracker; sem testes pesados".

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
| `GET /api/contratos?prefeitura_id=` · `/api/contratos/{id}/saldo` · `POST .../ajuste {codigo,montante,ajuste,motivo}` | |
| `PATCH /api/modelos/{id}` `{contrato_id, ativo}` · `GET/PUT /api/config` · `GET /api/eventos` (com `op:{numero,obra}`) · `GET /api/ops/proximo` | |

Situação da O.P. (`estado_op`, pelas colunas do Controle): CANCELADA (situação ou status CANCELADO/DUPLICADO) > INSTALADA (status OK) > NA_OBRA (material obra OK ou entrega OK) > SEM_DATA > ATRASADA (prazo efetivo < hoje; entrega atualizada com data substitui o prazo) > PROXIMA (≤ 3 dias) > NO_PRAZO.

## Referência do `app.js` implementado (preservar ao corrigir/refatorar)

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
