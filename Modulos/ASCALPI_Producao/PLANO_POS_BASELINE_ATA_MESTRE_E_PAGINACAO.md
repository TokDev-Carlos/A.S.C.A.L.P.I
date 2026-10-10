# Plano de evolução pós-base inicial — ASCALPI Produção

> **Destinatário e responsável técnico:** Claude, branch `modulo/producao-op`.  
> **Solicitante:** Carlos. **Planejamento:** Codex, 09/10/2026.  
> **Estado deste documento:** PLANEJADO / **EXECUÇÃO BLOQUEADA PELO MARCO G0**.  
> **Código de referência observado na elaboração:** `fb96a584fb848679d02e6f46e8010cc90f1c92cd`. Este SHA é referência de exame, **não** uma versão declarada estável nem uma tag criada.  
> **Escopo da presente entrega:** somente documentação. Não implementar mudanças nem migrar dados em decorrência da publicação deste plano.

## 0. Ordem imperativa e decisões do Carlos

**Regra de precedência:** antes de escrever qualquer funcionalidade deste plano, Claude **DEVE** validar formalmente a versão atual, identificá-la como a **BASE INICIAL** do ASCALPI Produção, preservar seu SHA imutável e obter o aceite do Carlos para iniciar a evolução. Os testes e a avaliação positiva do Carlos são evidências para G0, mas **não substituem** o registro formal. Não interpretar a publicação deste plano como autorização para executar G1–G5.

Decisões funcionais já acordadas:

1. **Modelo Excel editável pelo Carlos:** na tela Modelos, opção explícita de abrir uma **cópia de trabalho** no Excel, modificar fotos, textos e alturas originais, salvar e publicar como **nova versão** do modelo. O modelo publicado e documentos das O.P. anteriores nunca são modificados in-place.
2. **Uma biblioteca mestre por ATA:** cada ATA possuirá catálogo completo dos equipamentos, compartilhado pelas prefeituras/clientes que aderirem. A prefeitura pode aderir a somente parte do catálogo; não replicar, para cada cliente, a manutenção de fotos/textos de toda a ATA.
3. **Código-base = equipamento físico:** `1` é o item físico. `1.1`, `1.2` etc. são **variações de apresentação** do mesmo item (foto diferente e, opcionalmente, nome diferente; o nome pode ser idêntico). Não criar uma identidade física, um saldo ou um estoque novo só por existir variante.
4. **Saldo separado por contrato:** em cada contrato, quantidades de `1` + `1.1` + `1.2` consomem o mesmo código-base `1`. Contratos de clientes diferentes nunca misturam saldos. `2.1` segue agregado ao código `2`. `0.x` permanece **extra sem saldo/sem exigência de item no contrato**, sem entrar indevidamente na semântica de variantes.
5. **Paginação por dimensão efetiva:** nenhuma altura de linha será inventada, reescalada ou padronizada. Preservar altura, imagem, fontes, margens, largura de colunas e ordem originais. Calcular o espaço vertical usado pela linha existente; se o próximo equipamento não couber inteiro, quebrar antes dele e colocá-lo no início da próxima página, **mesmo que sobre espaço na anterior**. Nunca puxar itens menores para tapar o espaço. Eliminar os limites fixos de 13/15 **somente quando o novo mecanismo tiver sido aprovado**.
6. **Histórico imutável:** uma O.P. já emitida conserva contrato, código/variante, texto, imagem, versão do modelo, revisão e documentos da emissão. A edição de um modelo mestre não altera silenciosamente o passado.
7. **Excel do modelo ≠ XLSX de O.P.:** o Excel de manutenção de modelos deve ser editável; o XLSX gerado de uma Ordem de Produção segue a política de documento emitido/protegido. Verificar separadamente a observação do Carlos de que conseguiu editar um XLSX emitido.
8. Claude executa a evolução. Codex atua em **revisão e testes de validação após as entregas**, não em modificações paralelas de código sem novo acordo.

## G0 — Validação, congelamento e identificação da BASE INICIAL (obrigatório antes de tudo)

### G0.1. Identificar a versão exata

- Confirmar o HEAD atual da branch `modulo/producao-op` e comparar arquivos **de código** do GitHub com a implantação em `D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao`, excluindo `dados/`, backups, caches e configurações privadas. Se o HEAD mudou, documentar a diferença; **não presumir que `fb96a58` continua sendo o código final**.
- Levantar dependências reais, esquema SQLite, comandos Windows, proteção do XLSX, motor Excel de PDF, riscos de instalação, arquivos e rotas atuais; não acessar credenciais ou diretórios de outros projetos.
- Registrar que os dados reais só existem no Windows autorizado; o GitHub é público.

### G0.2. Validar a versão em uso e documentar evidências

Critérios mínimos, com relatório sem conteúdo pessoal de clientes:

- [ ] `python -m unittest discover -s tests -t . -v`: suíte integral sem falhas; informar total e SHA. A última execução independente anterior teve **78/78 OK no Windows, Python 3.14.6** (e 24 cenários direcionados, subconjunto, não testes adicionais à contagem total).
- [ ] SQLite em modo de **cópia isolada**: migração v1 → v6, `PRAGMA quick_check`, `foreign_key_check` e preservação de contagens/histórico; backup integral testado antes de qualquer ação. A validação anterior preservou 230 O.P. legadas, 27 prefeituras, 45 modelos e 1.033 itens; conferir o estado atual, que pode ter evoluído.
- [ ] Confirmar, junto ao Carlos, os testes manuais que ele já realizou: criação, edição, revisão, saldo, imagens, XLSX e PDF. Testar 3–5 amostras representativas quando for necessário e autorizado, sem copiar documentos reais para o GitHub.
- [ ] Excel COM em estação Windows: PDF sintético gerado, fechamento da instância isolada, falha/timeout e preservação do PDF anterior. Já houve smoke test positivo do PDF sintético; **comparação visual com o legado ainda depende de registro de aceite específico**.
- [ ] Verificar que o XLSX de O.P. publicado está protegido conforme requisito, distinguindo-o do futuro modelo editável; registrar discrepâncias sem corrigir silenciosamente durante o congelamento.
- [ ] Não reimportar automaticamente o Controle ou as 27 planilhas, não migrar a base operacional para fins de teste, não reinicializar contadores.

### G0.3. Instituir baseline auditável

- Criar um relatório sanitizado em `docs/producao/releases/BASE_INICIAL.md` com **SHA exato do código**, versão identificadora escolhida pelo Claude e aprovada pelo Carlos, data, ambiente, esquema, testes, evidências resumidas, ressalvas e procedimento de retorno.
- Após aprovação, criar tag de referência imutável (por exemplo `producao-base-inicial-v1`, sujeita à nomenclatura já adotada no repositório), apontando para o **commit efetivamente validado**; preferir release com changelog e artefatos sintéticos, sem bancos/modelos reais. **Não criar a tag nem anunciar versão homologada antes do aceite.**
- Se G0 revelar defeito bloqueante: corrigir **separadamente como estabilização**, revalidar, pedir aceite e somente então congelar **novo SHA**. Nenhuma melhoria G1–G5 misturada ao baseline.
- Documentar um plano de restauração testável: código por commit/tag + banco/catálogo/documentos por backup consistente, sem substituir dados operacionais sem autorização.

**Portão:** G1–G5 permanecem `BLOQUEADO` até G0 constar `APROVADO` no relatório de baseline **e** o Carlos confirmar o início das evoluções. Claude deve parar no G0 se não houver aceite formal.

---

## 1. Mapa da versão atual e implicações

Arquitetura em `fb96a58` (conferir novamente no novo HEAD):

- `banco.py`: `prefeituras`, `contratos`, `contrato_itens`, `modelos`, `modelo_linhas`, `ops`, `op_itens`, `op_revisoes`, `eventos`, `op_chaves`; esquema v6. Modelos ligados diretamente a `prefeitura_id`; `contrato_itens` tem saldo por contrato e código; `ops.modelo_arquivo` congela o modelo da emissão.
- `servico.py`: listagem, galeria/imagens, vínculos de contrato, escolha do modelo da O.P., cálculos de saldo. `regras.codigo_base("1.2") == "1"` e `codigo_base("0.1") == "0.1"` já são conceitos úteis; ainda **não** representam entidades cadastradas de variante.
- `web/app.js`, tela Modelos: galeria, ativação e vínculo com contrato; **não** tem sessão segura de editar/salvar Excel do modelo.
- `documento.py`: `MAX_PG1 = 13`, `MAX_PG_DEMAIS = 15`; `plano_paginas(total)` e quebras por ordinal, **não por altura**; preservar emissão por pacote OOXML.
- `pdf.py`: saída via Excel COM no Windows ou LibreOffice. Excel deve ser a referência de conferência de paginação e fidelidade.
- `imagens.py`: imagens identificadas por âncoras OOXML, logo e fotos.
- `legado.py`: reimportação com prévia e modelo versionado, sem reescrever O.P. já emitida; **não reaproveitar reimportação como rotina de atualização do catálogo mestre** sem separar semânticas.

Leitura técnica local de metadados dos 45 modelos: 17 têm alguma linha de equipamento acima de 100 pt; altura máxima observada de aproximadamente 200,1 pt; 1.063 âncoras de desenhos nas linhas de equipamentos, das quais 30 atravessam mais de uma linha. São dados agregados para orientar testes, **não quotas, alturas-padrão nem autorização para subir arquivos reais à nuvem**.

## G1 — Edição segura de modelos pelo Excel (primeira evolução, somente após G0)

**Objetivo:** botão **EDITAR MODELO NO EXCEL** na tela Modelos, sem permitir sobrescrever a versão publicada ou pastas históricas.

1. Serviço cria **sessão de edição** e cópia de trabalho temporária do `.xlsx` do modelo; identifica modelo, versão de origem e hash. A cópia é editável, com bloqueios de modelo removidos **somente nela** quando necessários; nunca expor/suprimir proteção de arquivos de O.P. Emitidos.
2. Windows local: ação explicitamente iniciada pelo Carlos abre a cópia no Excel instalado. O navegador apenas solicita a operação a uma integração local autenticada/autorizada; **não** aceitar caminho arbitrário, argumentos de shell ou abertura automática de arquivos recebidos sem validação.
3. Após o Carlos salvar e fechar, ação **VALIDAR ALTERAÇÕES**: ZIP/OOXML válido, uma aba apropriada, referências e campos indispensáveis (códigos, linhas, cabeçalho, mesclas, desenhos/imagens, área de impressão), formato não macro, ausência de alterações perigosas e nenhum item-base/variante acidentalmente duplicado. Apresentar **prévia de diferenças** (nome, foto, altura original de linha, equipamento adicionado/removido, impacto em contratos) e erros antes de publicar.
4. **PUBLICAR NOVA VERSÃO** requer confirmação: persistir arquivo com nome único imutável, hash/versionamento, alteração transacional de ponteiro de modelo, auditoria (autor/data/motivo/antes/depois); gravação atômica + recuperação se arquivo ou banco falhar. Concorrência: duas sessões partindo da mesma versão devem produzir conflito 409, não sobrescrita silenciosa.
5. **DESCARTAR RASCUNHO** também precisa de ação explícita; arquivos temporários não devem ser apagados sem política de retenção/documentação/consentimento do usuário. Não modificar `.xlsm` originais nem pastas legadas.
6. Contrato de implantação: no futuro navegador/nuvem, substituí-lo por exportar/editar/importar com mesma validação, versionamento e autorização; não acoplar o domínio a `Excel.Application`.

**Arquivos candidatos:** `ascalpi_producao/modelos_edicao.py` (novo), `servico.py`, `servidor.py`, `banco.py`, `web/app.js` e `app.css`; testes isolados. Evitar executar Excel dentro de transação SQLite.

**Aceite G1:** modelo editado no Excel local, foto/nome/altura preservados, versão nova visível na galeria, O.P. antiga reproduz documento antigo, O.P. nova usa versão nova; rejeição de arquivo inválido sem dano; dupla publicação não causa perda; XLSX de O.P. permanece na política de proteção.

## G2 — Paginação inteligente por altura original (após G0; pode ser desenvolvida depois de G1)

**Não criar "slot" artificial nem estabelecer 80/160 pt como regra.** Os slots são apenas analogia funcional: usar a altura efetiva de cada linha e de objetos ancorados, tal como vêm do modelo aprovado.

1. Obter linhas visíveis da O.P. **na ordem original**. Ler de OOXML `<row ht="...">` com fallback para `sheetFormatPr.defaultRowHeight` e medidas de desenho (âncoras `oneCell` / `twoCell`, offsets EMU). Considerar imagem que ultrapassa a linha, sem cobrar altura dupla se a linha já a comporta; cabeçalho e objetos fixos fora do corpo são tratados separadamente.
2. Definir área vertical imprimível conforme papel, orientação retrato, margens, cabeçalho/rodapé e escala efetiva `fitToWidth=1`. Não trocar escalas/fontes/tamanhos para fazer caber mais.
3. Atribuir equipamentos **sequencialmente** à página enquanto o próximo couber **inteiro**. Se não couber, colocar quebra manual **antes** desse equipamento; nunca dividir equipamento nem rearranjar para preencher sobra. Itens 16/17 caberão na primeira página **apenas quando o espaço realmente comportar**.
4. Prever diferença entre cálculo OOXML e impressão real: fazer simulação ou impressão temporária pelo Excel **antes da publicação oficial**, verificar páginas e eventuais cortes, ajustar somente **quebras**, mantendo estilos e dimensões. A conferência não pode criar O.P. nem consumir saldo. Se um único equipamento for maior que a área útil, sinalizar impedimento real e pedir ajuste manual do modelo — **não** redimensionar automaticamente.
5. Preservar exatamente as quebras acordadas em XLSX e PDF; exportar sempre a partir do mesmo artefato/retrato. Ter chave de configuração ou flag para voltar à paginação legada 13/15 durante a homologação; registrar qual motor foi usado por documento.
6. Considerar modelos com múltiplas alturas, fotos atravessando linhas, mesclagens, primeira página com cabeçalho, variações posteriores e margens/impressoras; driver/impressão física pode divergir, então não prometer identidade universal com todas as impressoras.

**Arquivos candidatos:** `documento.py`, eventual `paginacao.py` (funções puras), `pdf.py` somente para validação/preview Excel, `tests/test_paginacao.py`. **Sem alterar o tamanho de linha, imagem, coluna, fonte ou a ordem das O.P.**

**Aceite G2:** para cada modelo testado, itens permanecem na sequência; nenhuma imagem partida/cortada; não há 2ª página artificial quando os itens cabem integralmente na primeira; há espaço em branco legítimo quando próximo item alto não cabe; Excel e PDF têm paginação aprovada; regressões de 13/15, retrato, margens e proteção não quebram.

## G3 — Catálogo mestre por ATA e adesões parciais (após G0 e estabilização de G1/G2)

**Objetivo:** uma entidade ATA reutilizável, com catálogo integral, independentemente de quantas prefeituras tenham aderido.

### Entidades conceituais propostas (nomes são candidatos; Claude valida esquema e migrações)

| Entidade | Responsabilidade | Identidade |
|---|---|---|
| `atas_mestre` | ATA canônica, descrição, status e versão de catálogo | `ata_id` estável; não deduplicar somente por título/`codename` |
| `equipamentos_base` | Produto físico/referência de consumo; código como texto, nome principal, especificação, imagem padrão | `equipamento_id`; unicidade (`ata_id`, `codigo_base`) |
| `equipamento_variantes` | Variações de apresentação: código `1.1`/`1.2`, imagem e nome opcionais; sempre pertencem a um `equipamento_id` | `variante_id`; unicidade (`ata_id`, `codigo_variante`) |
| `atas_versoes` | Snapshot imutável da edição do catálogo/modelo e dos ativos de mídia | (`ata_id`, `versao`), hash |
| `adesoes_ata` | Prefeitura/cliente + contrato aderindo a uma ATA e a uma versão/política | `adesao_id`, vínculo por IDs |
| `adesao_itens` | Subconjunto efetivamente contratado e opção de variante padrão por cliente | (`adesao_id`, `equipamento_id`) |
| `op_itens` (evoluir) | Seleção histórica de código-base e variante efetiva + snapshot do nome/foto/modelo | IDs + snapshots por revisão |

**Invariantes:**

- Cada ATA pode ter 50 itens e uma prefeitura aderir a 12, sem clonar os outros 38. A escolha de variante não permite usar item não contratado.
- Não confundir `ata_id` do catálogo com `contrato_id` de saldo: dois contratos que aderem à mesma ATA mantêm montantes, previsões, instalados e ajustes **independentes**.
- Código-base é identificado **dentro da ATA**; `1` de ATAs distintas não implica automaticamente mesmo produto. Um cadastro global físico compartilhado entre várias ATAs seria evolução futura com conciliação explícita, não deduplicação heurística.
- Alterações de catálogo e variantes nunca retroagem para documentos já emitidos; cada emissão referencia versão imutável e conserva snapshot de texto, imagem, ordem e dimensão real.
- Não se apaga `modelos` / `modelo_linhas` / `contrato_itens` existentes na primeira migração. Implementar tabela de correspondência, modo compatível e migração expansiva por etapas, com relatório de ambiguidades e revisão manual.

**Aceite G3:** duas prefeituras aderem à mesma ATA com subconjuntos distintos e usam o mesmo catálogo; modificar a foto/nome base uma vez atualiza **somente novas emissões** nos destinos aplicáveis; O.P. e saldos antigos permanecem auditáveis; dados de prefeituras não se misturam.

## G4 — Variantes 1.1 / 1.2 e personalização de cliente (sobre G3)

### Regras fechadas

- `1` = equipamento físico e código de saldo; `1.1` e `1.2` = apresentação selecionada da base `1`, sem segundo estoque, identidade física ou montante.
- Cada variante pode ter imagem própria e nome substituto **opcional**. Nome ausente = herdar nome base; nome igual ao principal é válido; imagem ausente = herdar imagem base. Campos visuais nunca precisam ser artificialmente diferentes.
- Quantidade consumida no contrato por todas as variantes: `Q(1) = Q(1) + Q(1.1) + Q(1.2)`. Não confundir com `0.1`, que continua EXTRA sem saldo.
- Identificador da variante não é número decimal de cálculo: tratar `"1.10"` como texto distinto de `"1.1"` e jamais usar `float` para chave. Normalização existente deve ser revisada para evitar perda de zeros/dígitos na importação.
- Por adesão pode haver uma variante sugerida para o cliente; autor da O.P. escolhe dentre variantes válidas **dos itens contratados**, com permissão e rastreio. Mostrar nome/foto resultantes na prévia e documento.
- Uma variante pode representar altura original diferente, **se o respectivo modelo aprovado assim a tiver**; a paginação consome essa altura, não redimensiona para caber.
- Se alteração realmente cria item de especificação, composição ou obrigação contratual física distinta, exige novo cadastro físico mediante aprovação; não mascarar como mera variante.

### Migração

- Ler itens de 45 modelos e agrupar candidatos por (`ATA identificada com segurança`, código-base); **não** agrupar automaticamente por nome/foto semelhante, código igual em outra ATA ou `codename` ambíguo.
- Gerar relatório `candidatos` / `ambíguos` / `não conciliados`, mapa de correspondência reversível e prévia; nenhuma linha histórica apagada.
- Trabalhar com cópia de banco, modelo e dados de demonstração. Migrações idempotentes, recuperáveis e avaliadas antes de qualquer transformação na base real.
- O sistema antigo deve continuar legível durante rollout; manter compatibilidade de rotas existentes ou versionar API sem quebrar UI.

**Aceite G4:** mesma ATA, variações `1.1` e `1.2`, nomes iguais ou diferentes, imagens diferentes, ambas debitam `1`; outra prefeitura pode ter variante preferida distinta; um item `0.1` não gera saldo; render antigo permanece idêntico com snapshot anterior.

## G5 — Integração, habilitação gradual e aceite final

1. Integrar ao fluxo Nova/Editar O.P., seleção de prefeitura, ATA, adesão, equipamento físico, variante, saldo, fotos, XLSX, PDF e paginação. **Não criar uma segunda numeração ou duplicar O.P.**; manter `rev_esperada` / 409, idempotência, proteção contra dupla publicação e `BEGIN IMMEDIATE` no escopo curto da gravação.
2. Entregar em flags controladas, **desabilitadas por padrão**: `edicao_modelo_excel`, `paginacao_altura`, `catalogo_ata`, `variantes_apresentacao`. Ativar primeiro para cenários sintéticos e uma amostra autorizada, depois ampliar após aceite.
3. Garantir rollback **operacional**: desativar flags e retornar renderização antiga para novas O.P. sem descartar schema/arquivos históricos; restauração de backup somente com autorização e plano explícito. Nunca rodar downgrade destrutivo em banco com novos dados.
4. Homologar em Windows/Excel com modelos de altura variável e casos de uma/deduas páginas, PDF vs XLSX, fontes/imagens, 27 origens legadas, contratos parciais e usuário sem Excel; manter aviso de indisponibilidade claro se necessário.
5. Garantir compatibilidade com a futura arquitetura de servidor na nuvem: edição no Excel é um **adaptador da estação**; cadastro, versões, contratos e PDFs são conceitos do domínio, não dependências de `COM` ou de caminhos `D:\`.
6. Atualizar `CLAUDE.md` / `CONTINUAR.md` e uma ADR de domínio (biblioteca de ATAs, variantes e snapshots) a cada fase; criar changelog de migrações, manual de edição no Excel e de desfazer sessão, riscos e aceites assinados pelo Carlos.

### Matriz mínima de testes automatizados e validação

| Conjunto | Casos exigidos |
|---|---|
| G0 baseline | 78 testes vigentes (ou total novo justificado), suíte e hashes auditados, migração de cópia, PDF Excel sintético e aceite manual |
| G1 editor Excel | cópia sem tocar no original; salvar/fechar; erro/arquivo malformado; concorrência 409; foto, mescla, altura e proteção; publicar/rollback; O.P. emitida congelada |
| G2 paginação | 13/15 e 16/17 conforme altura *real*, itens altos, desenhos atravessando linhas, cabeçalho/margens, evitar cortes, nenhuma reordenação; páginas iguais no XLSX/PDF |
| G3 ATA mestre | uma ATA/várias prefeituras, adesão parcial, versão, reimportação independente, isolamento de saldo, O.P. antiga imutável |
| G4 variantes | `1`/`1.1`/`1.2` consomem base `1`; `1.10` não conflita com `1.1`; `0.x` extra; fallback de nome/foto, seleção válida, snapshot por REV |
| G5 E2E | criar, revisar, publicar, cancelar, retry de criação, dois usuários, duas versões simultâneas, alternar flag e recuperar saída antiga |

### Condições de parada / não fazer

- **Nunca começar G1–G5 antes do aceite da base inicial G0.**
- Não dar `git push` em `main`, não instalar nada no Windows, não reimportar 27 livros ou mexer no banco real por efeito de um plano.
- Não publicar exemplos de clientes, modelos reais, mídias, hashes de senhas ou pastas privadas no GitHub público. Usar massa sintética.
- Não transformar variantes em equipamentos físicos duplicados e não misturar saldos entre contratos.
- Não ajustar altura/fonte/zoom/imagem para colocar mais itens na página; apenas detectar o espaço e inserir quebras.
- Não substituir versões antigas de modelos ou documentos de O.P.; alterar somente ponteiro de versão futura sob confirmação.
- Nenhuma migração ambígua automática, nenhuma correção automática de contratos ou código-base sem conferência do Carlos.

## Checklist do Claude para início da próxima sessão

- [ ] Confirmar HEAD e ler `CLAUDE.md`, `CONTINUAR.md`, `Codex_Plano_para_Claude.md` e este plano.
- [ ] Executar **somente G0** e produzir evidência sanitizada; apresentar ao Carlos a versão proposta para baseline e solicitar aceite.
- [ ] Após aceite: registrar tag/release no SHA validado, manter snapshot do schema e atualizar o histórico.
- [ ] Só então abrir G1, depois G2, G3, G4 e G5, com commits pequenos, testes e aceite por fase.
- [ ] Devolver ao Codex apenas as tarefas de **validação independente**, conforme instrução atual do Carlos.

**Situação em 09/10/2026: plano registrado; baseline formal ainda NÃO declarada por este documento; nenhuma implementação nova autorizada ou realizada.**
