# ASCALPI Produção — instruções do projeto

Leia este arquivo inteiro, depois `docs/producao/releases/BASE_INICIAL.md` (versão congelada `producao-base-inicial-v1`), `PLANO_AJUSTES.md` e `PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md` (o que fazer a partir da base), `CONTINUAR.md` (estado atual, API, teste local) e `Codex_Plano_para_Claude.md` (achados R01–R09 e divisão Claude ⇄ Codex) antes de qualquer ação.

## 1. Objetivo

Módulo independente de **Ordens de Produção** do sistema **ASCALPI** (esse é o único nome; nunca usar outro). Substitui o legado VBA (`MOD_GERAR_OP V2.4.22`, 27 livros `OK-<CIDADE>_O.P.xlsm` + Controle). Depois de validado sozinho, será integrado ao núcleo ASCALPI (reuso do núcleo CJL) e, mais tarde, 100% nuvem.

## 2. Decisões fechadas (não rediscutir)

- O **sistema controla tudo**: numeração `NNN-AA` (reinicia por ano), contratos/saldo, histórico, revisões.
- Edição só no sistema (quantidades, datas, observações). Os `.xlsx` publicados ficam **100% bloqueados** (só visualizar). Edição nos setores está fora de escopo.
- Documento (xlsx/PDF) gerado sob demanda no **padrão visual exato do legado**. PDF via Excel no Windows; LibreOffice só para teste na nuvem.
- Regras da O.P.: (a) modelo por Prefeitura; (b) modelo por ATA; (c) informações e logo de cada O.P.; (d) só equipamentos com quantidade aparecem; (e) data pode ser texto, ex. "DEFINIR"; (f) observação por item.
- Saldo: `0` se montante ≤ 0, senão `montante − (quant + previsão)`; "ACABOU" em zero; negativo exige confirmação; códigos `0.x` são bônus/ignorados; `2.1` conta como base `2`.
- Modelo válido = aba cujo nome contém "OP-" (pontos ignorados). Cópias com dígitos finais ligam ao contrato da ATA base.
- Ambiente oficial Windows (como UStracker): `C:\Program Files\ASCALPI`, `C:\ProgramData\ASCALPI\UserData`, `%LOCALAPPDATA%\ASCALPI`; caminhos de negócio definidos na instalação.

## 3. Mapa da arquitetura

| Arquivo | Papel |
|---|---|
| `regras.py` | Regras puras: nomes, numeração, prazo, saldo |
| `pacote.py` | Leitura/edição do xlsx como OPC/XML (sem Excel) |
| `documento.py` | Gera o xlsx da O.P. (linhas ocultas, paginação, bloqueio) |
| `pdf.py` | PDF por Excel (COM) ou LibreOffice |
| `banco.py` | Esquema SQLite (WAL) |
| `legado.py` | Importador dos livros e do Controle |
| `imagens.py` | Fotos e logos extraídos dos desenhos das abas |
| `validacao.py` | Validação pura das entradas (antes de qualquer gravação) |
| `modelos_edicao.py` | G1: cópia de trabalho do modelo, validação/prévia, nova versão, descarte |
| `servico.py` | Fachada e regras de aplicação: situação da O.P., saldos, salvar/cancelar/acompanhar (transação única) |
| `publicacao.py` | Publicação .xlsx/.pdf por formato, sem apagar o anterior |
| `consultas.py` | Painel, resumo, eventos e pendências (só leitura) |
| `configuracao.py` | `config.json` local (senha dos .xlsx nunca sai daqui) |
| `servidor.py` | API HTTP (stdlib `ThreadingHTTPServer`) |
| `web/` | `index.html` + `app.css` + `app.js` (módulo ES, 7 telas e gaveta) |
| `tests/`, `ferramentas/` | Testes leves e dados de demonstração (aqui pode usar openpyxl) |

## 4. Como trabalhar (ordem de raciocínio)

1. Ler `CONTINUAR.md`; confirmar o que já está pronto antes de escrever.
2. Planejar curto: o que muda, quais arquivos, como verificar. Mudança de regra de negócio → consultar as decisões da seção 2 primeiro.
3. Construir em etapas pequenas; backend antes da interface; interface por tela, na ordem do `CONTINUAR.md`.
4. Verificar: `python -m unittest discover -s tests -t .` (leve) e, para UI, servidor com `ferramentas/dados_demo.py` + capturas Playwright (desktop 1366 e celular 390). Sem testes pesados.
5. Fechar: atualizar `CONTINUAR.md` (percentual e pendências), commitar.
6. Nunca declarar pronto sem ter rodado/visto o resultado.

## 5. Convenções

- Português do Brasil; mensagens do sistema em MAIÚSCULAS como no ASCALPI.
- Só biblioteca padrão do Python no módulo; HTML/CSS/JS puros, sem build.
- Visual: tokens e padrões do Painel ASCALPI + ideias do UStracker (onda no clique, botão ocupado, barra de progresso, filtro de coluna estilo planilha, atalho `/`). Gráficos: marcas finas, legenda com 2+ séries, tooltip nunca é a única forma de ler o dado (tabela `.sr` equivalente), cores validadas para daltonismo (real teal `#0d8ba3`, previsão roxo `#7254b6`).
- Armazenamento no navegador (`localStorage`) sempre em try/catch e opcional.

## 6. Segurança (inegociável)

- Repositório **público**: nunca adicionar dados de clientes, `dados/`, bancos `.db*`, senhas, tokens ou caminhos de servidor. A senha dos `.xlsx` é gerada na primeira execução e fica só em `dados/config.json`.
- Nunca gravar em `D:\MACROS\Legacy_Modules` nem nos `.xlsm` legados: só ler, trabalhar em cópias.
- Sem gravações fora do projeto sem autorização do Carlos; desenvolvimento nasce sem dados de produção.
- Não abrir o repositório de credenciais (Chaves-Tokens).
- Instalação em Program Files exige aprovação UAC do Carlos.
- Push somente quando o Carlos pedir. Não contornar bloqueios de segurança de `rm` (usar caminhos literais ou `"${D:?}"`).

## 7. Commits

Mensagem curta em português; terminar com as linhas de coautoria e sessão exigidas pelo ambiente.

## 8. Definição de pronto (1ª etapa funcional)

- Interface (7 telas + gaveta) e correções R01–R09 com testes. ✅
- Decisões do Carlos aplicadas (datas da O.P., `0.x` extras, contratos editados no sistema prevalecem). ✅
- Testes leves passam; capturas desktop e celular conferidas. ✅
- Módulo copiado para o PC do Carlos com `Atualizar_Copia_Local.cmd` (backup de `dados`, sem copiar dados) e validado com dados reais. ⏳ Carlos

## 9. Próximos marcos

Interface completa → amostras reais de O.P. (3–5 xlsx + PDF) para comparação pixel a pixel → teste do PDF via Excel no Windows → ambiente oficial/instalador (Plano 0) → integração ao núcleo ASCALPI → nuvem → módulo Ordens de Compra.
