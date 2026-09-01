# CJL — Recuperacao Local do 3-Git_Main

Status: CICLO 010 / RAIZ REORGANIZADA / AGUARDANDO ORDEM DO OPERADOR
Data inicial: 2026-08-26T19:36:20-03:00
Ultima atualizacao: 2026-08-27T07:35:00-03:00
Fuso: America/Sao_Paulo
Modo: RECOVERY / READ_ONLY PRECHECK
GitHub Write: NO
Production Write: NO

## Objetivo unico

Reconstruir na maquina WORK um `3-Git_Main` isolado e funcional, usando exatamente
o candidato versionado no GitHub, antes de reorganizar `1-Dev`, `2-Compiler`,
Painel de Desenvolvimento ou producao.

## Origem definida

- repositorio: `TokDev-Carlos/CJL-System`;
- branch de origem: `main`;
- commit atual: `8b63ba05b67ff594a3e9c77a26ca735462db0b51`;
- subarvore: `3-Git_Main`;
- tree SHA: `0f1aa755a0c04b3fa382ae2afae4f8ad4b5030b4`;
- tree SHA de `3-Git_Main/System`:
  `a1b450516a98f52d8334484198fa134e555ffd74`.

## Comparacao main x Dev-Work

O `3-Git_Main` e byte-identico nas duas branches. `Dev-Work` nao possui uma
variante de Git_Main com dados de teste.

As diferencas atuais de `Dev-Work` estao em evidencia, perfil WORK, auditoria e
fonte de `1-Dev`. Elas nao pertencem ao candidato Windows.

## Candidato existente

- versao: `1.05.01.006`;
- build: `20260816234116`;
- `sistema.json` e `app.integrity.json`: identidade coerente;
- launcher `CJL.exe`: Git LFS, SHA-256
  `6b4d1d3d716a4fe4b3b670c8f658f4f8eab9a1cd6c0bb24f229abaee512350ab`,
  tamanho esperado `98.995.154` bytes;
- host: .NET 10, SDK 10.0.400, win-x64, self-contained;
- runtime Python e LibreOffice: presentes na subarvore controlada;
- `Data/sistema.db`: unica semente SQLite permitida, sem UserData operacional.

## Limite importante

O `1-Dev` atual de `main` avancou para `1.05.02.007` sem atualizar corretamente o
manifesto e falhou no Linux smoke. O `3-Git_Main` nao foi recompilado com essa
mudanca; continua sendo o candidato anterior coerente `1.05.01.006`.

Assim, este ciclo recupera o candidato Windows ja existente no GitHub. Ele nao
declara que a fonte mais nova `1.05.02.007` foi compilada ou homologada.

## Dados de teste

O repositorio ativo proibe usuarios, clientes, obras e registros operacionais.
Logo, um clone correto nao trara login administrativo nem massa de teste. Esses
dados deverao ser criados depois, somente no banco local isolado de homologacao,
por procedimento auditavel.

## Sequencia autorizada

1. inventariar apenas `C:\.Dev` e `C:\.Dev CJL`;
2. comprovar Git, Git LFS, repositorios existentes e candidatos locais;
3. definir o path final exato da nova tree;
4. preservar o estado atual por renomeacao/backup;
5. clonar `main` no staging com Git LFS;
6. conferir commit, tree, LFS, manifesto e hashes;
7. materializar somente o `3-Git_Main` no path final;
8. executar o candidato sem alterar producao;
9. corrigir acesso administrativo apenas no banco local de homologacao;
10. testar inicio, login, painel, logout, reinicio e encerramento.

## Ciclo 002 — leitura de `C:\.Dev CJL`

### Evidencia recebida

- pacote: `20260826T213512461_DEV_CJL_TREE.zip`;
- SHA-256 do pacote:
  `8cd2243eec7b1476ca332da331f2846f6c6b195cb7299afe419c8b50ca45bc56`;
- captura em Sao Paulo: `2026-08-26T21:35:12.461-03:00`;
- origem: `C:\.Dev CJL`;
- modo de captura: `robocopy /L`, somente listagem;
- resultado: ZIP integro, `53.455` arquivos, `4.601` diretorios e
  `22.791.020.124` bytes visiveis;
- escrita na origem: `NO`;
- reparse points encontrados: `0`.

### Tree real observada

```text
C:\.Dev CJL
|-- Builds\                         [vazio]
|-- Compilador\
|   |-- 20260825T133302154_8b63ba05b67f\
|   |-- 20260825T160519293_8b63ba05b67f\
|   |-- 20260825T164406957_8b63ba05b67f\
|   `-- 20260825T181944779_8b63ba05b67f\
|-- Git_Main\
|   |-- Current\                    [vazio; nao e link]
|   `-- System\                     [candidato executavel]
|-- Patches\
|   `-- Inbox\
|-- Releases\
|   `-- Approved\                   [vazio]
|-- Runtime\
|   `-- Python\
`-- WSL\
    |-- CJL-Dev-Panel\              [R010 a R029]
    |-- CJL-Dev-Panel.cmd
    `-- CJL-Dev-Work\
        |-- ext4.vhdx
        `-- shortcut.ico
```

Nao existem pastas chamadas `1-Dev`, `2-Compiler` ou `3-Git_Main` nessa tree.
Tambem nao existe `3-Gi_Main`.

### Distribuicao por pasta principal

| Pasta | Arquivos | Diretorios | Bytes | GiB |
| --- | ---: | ---: | ---: | ---: |
| `WSL` | 175 | 35 | 16.359.424.763 | 15,236 |
| `Compilador` | 33.603 | 2.883 | 4.705.426.773 | 4,382 |
| `Git_Main` | 16.648 | 1.388 | 1.576.282.626 | 1,468 |
| `Runtime` | 3.028 | 289 | 149.879.583 | 0,140 |
| `Patches` | 1 | 2 | 6.379 | ~0 |
| `Builds` | 0 | 1 | 0 | 0 |
| `Releases` | 0 | 2 | 0 | 0 |

### WSL comprovado pelo Windows

- distribuicoes registradas e em execucao: `docker-desktop` e
  `Ubuntu-24.04`, ambas WSL 2;
- distribuicao padrao na captura: `docker-desktop`;
- arquivo fisico encontrado:
  `C:\.Dev CJL\WSL\CJL-Dev-Work\ext4.vhdx`;
- tamanho visivel do VHDX: `16.353.591.296` bytes (`15,230 GiB`);
- ultima modificacao observada: `2026-08-27 00:34:58`;
- nenhum link NTFS monta a raiz do Ubuntu dentro de `C:\.Dev CJL`.

A tree Windows enxerga o VHDX como um unico arquivo. Ela nao enxerga os arquivos
Linux guardados dentro dele. A associacao do VHDX com `Ubuntu-24.04` e a tree
interna de `/` continuam nao verificadas.

### Repositorios Git visiveis

Nao foi encontrado nenhum diretorio ou arquivo `.git` na parte NTFS listada.
Isso significa que o repositorio de desenvolvimento, se existir nessa estrutura,
esta dentro do `ext4.vhdx` ou em outro caminho fora de `C:\.Dev CJL`.

### `Git_Main` local

O candidato executavel esta em:

```text
C:\.Dev CJL\Git_Main\System
```

Ele possui:

- `16.648` arquivos;
- `1.576.282.626` bytes;
- `CJL.exe` real com `98.995.154` bytes;
- `Host` com oito binarios/arquivos e `669.851.363` bytes;
- `Runtime` embarcado com `16.473` arquivos e `800.149.998` bytes;
- `App` com 96 arquivos;
- `Data\sistema.db` com `344.064` bytes;
- tres logs de bootstrap, inclusive um de `2026-08-25T18:51:31-03:00`;
- `Current` vazio, sem junction, symlink ou mount point.

O tamanho local do `CJL.exe` coincide com o tamanho declarado pelo Git LFS da
branch `main` (`98.995.154` bytes). O tamanho local de
`App\Config\sistema.json` tambem coincide com o arquivo atual do GitHub
(`11.583` bytes), cuja identidade declara `1.05.01.006`, build
`20260816234116`.

Essas coincidencias comprovam alinhamento estrutural e de tamanho, mas nao
comprovam identidade byte a byte. A captura nao calculou SHA-256 dos arquivos
locais.

### Saidas do `Compilador`

| Candidato | Arquivos | Bytes | Classificacao pela tree |
| --- | ---: | ---: | --- |
| `20260825T133302154_8b63ba05b67f` | 154 | 776.818.263 | parcial |
| `20260825T160519293_8b63ba05b67f` | 153 | 776.022.655 | parcial |
| `20260825T164406957_8b63ba05b67f` | 16.648 | 1.576.292.960 | completo em quantidade |
| `20260825T181944779_8b63ba05b67f` | 16.648 | 1.576.292.895 | completo em quantidade e mais recente |

Comparacao por path e tamanho entre o candidato mais recente e o `Git_Main`:

- ambos possuem `16.648` arquivos;
- `16.643` paths comuns possuem o mesmo tamanho;
- tres arquivos existem somente no candidato do Compilador:
  `README.md`, `SOURCE_ORIGIN.md` e
  `Docs\Homologation\R022_PIPELINE_HOMOLOGATION.md`;
- tres logs de bootstrap existem somente no `Git_Main`;
- dois paths comuns possuem tamanho diferente:
  `App\Config\sistema.json` e `Updates\State\atual.json`;
- o candidato mais recente e `10.269` bytes maior no total.

Portanto, `Git_Main\System` nao e uma copia direta do ultimo candidato do
Compilador. Ele e uma tree anterior que ja foi executada e acumulou logs.

### Painel e residuos do fluxo anterior

- o Painel local esta fora do repositorio visivel, em
  `C:\.Dev CJL\WSL\CJL-Dev-Panel`;
- existem 172 arquivos ativos/historicos, revisoes de R010 a R029 e
  `CJL-Dev-Panel.ps1` com `226.733` bytes;
- o estado registrado do Painel tem timestamp anterior ao script R029;
- ha um patch R022 em `Patches\Inbox`;
- `Builds` e `Releases\Approved` estao vazios;
- ha um Python separado em `Runtime\Python`, alem do Python embarcado nos
  candidatos completos e no `Git_Main`.

### Veredito do ciclo 002

`CONFLICT / INCOMPLETE`.

A tree confirma que o fluxo anterior criou uma estrutura operacional diferente
da combinada e duplicou candidatos completos. Entretanto, ela tambem confirma
que ja existe um `Git_Main\System` substancial, com launcher, Host, Runtime,
App e banco. Ele deve ser preservado e validado antes de qualquer reorganizacao.

Nao e seguro mover, renomear, apagar ou substituir pastas ainda. Faltam dois
gates de leitura:

1. tree interna do `Ubuntu-24.04`, explicitamente nessa distribuicao e no mesmo
   filesystem do VHDX;
2. hashes e manifests do `Git_Main\System` local para comparar byte a byte com
   `3-Git_Main/System` do GitHub.

## Gate atual

PENDENTE: identidade Git e hashes criticos de `/cjl/Sistema_Dev`, executados
diretamente no terminal `Ubuntu-24.04`.

Nenhuma pasta local deve ser apagada, movida ou sobrescrita antes desse gate.

## Ciclo 003 — falha da primeira coleta interna WSL

### Veredito

`REPROVADO / DEBUG`.

O bloco PowerShell 5.1 entregou um here-string multilinha diretamente como
argumento de `bash -lc`. A fronteira PowerShell 5.1 -> `wsl.exe` -> Bash nao
preservou o comando como uma unica unidade. O Bash recebeu trechos sem o valor
de `out`.

### Evidencia observada

```text
awk: fatal: cannot open file `/TREE_UBUNTU_ROOT.tsv'
mkdir: missing operand
WSL_EXIT_CODE=1
LinuxOut=NULL
wslpath: Invalid argument
```

As falhas de `wslpath`, ZIP, `OpenRead`, hash e a mensagem final falsa de PASS
sao efeitos em cascata. Nenhum ZIP valido foi produzido.

### Risco de residuo

Como o comando foi executado como `root` e `out` ficou vazio, redirecionamentos
podem ter criado arquivos de evidencia diretamente em `/`. A existencia desses
arquivos ainda nao foi comprovada. Nenhuma limpeza e autorizada antes de uma
listagem explicita e somente leitura da raiz.

### Correcao de desenho autorizavel depois do gate

Nao voltar a transportar script multilinha como argumento de `bash -lc`.
Materializar o Bash em arquivo UTF-8 sem BOM num diretorio de evidencia Windows,
converter somente o path desse arquivo e executa-lo por caminho com argumentos
separados. O wrapper devera terminar imediatamente em qualquer falha e nunca
imprimir PASS sem ZIP existente e hash calculado.

## Ciclo 004 — tree interna do Ubuntu

### Regra operacional aprovada pelo operador

- comandos e scripts Linux: terminal `Ubuntu-24.04`, usando Bash;
- comandos e scripts Windows: Windows PowerShell, usando paths Windows;
- CMD: somente wrapper minimo quando necessario;
- proibido transportar blocos Bash multilinha por `bash -lc` via PowerShell.

### Evidencia recebida

- pacote: `20260826T231156_UBUNTU_ROOT_TREE.tar.gz`;
- SHA-256:
  `a521b4e64d3251802e40cac4db62ad206554c73f424b92078792fbef627c2016`;
- timestamp Sao Paulo: `2026-08-26T23:11:56-03:00`;
- gzip integro;
- 11 membros: um diretorio e dez arquivos;
- nenhum path traversal, path absoluto, symlink ou hardlink no pacote;
- todos os quatro coletores terminaram com exit code zero;
- source, GitHub e producao: `WRITE=NO`.

### Ubuntu e filesystem

- sistema: Ubuntu `24.04.4 LTS`;
- kernel: `6.18.33.1-microsoft-standard-WSL2`;
- root: `/dev/sdf`, `ext4`;
- capacidade logica: `1.081.101.176.832` bytes;
- uso: `12.099.964.928` bytes, aproximadamente 2%;
- tree: `83.630` arquivos e `14.190` diretorios, alem de outros tipos;
- repositorio Git unico encontrado: `/cjl/Sistema_Dev/.git`.

### Estrutura real no WSL

```text
/cjl
|-- Sistema_Dev/          [repositorio Git]
|   |-- 1-Dev/
|   |-- 2-Compiler/
|   |-- 3-Git_Main/
|   |-- Knowledge/
|   |-- Machine/
|   `-- .git/
|-- .venv-cjl-dev-work/
|-- Compilador/           [vazio]
|-- Evidence/
|-- Patches/
`-- SM_Repo/
```

Portanto, a tree canonica combinada ja existe dentro do repositorio WSL. A tree
Windows paralela foi criada fora desse modelo.

### Dimensoes de `/cjl/Sistema_Dev`

| Subtree | Arquivos | Bytes observados |
| --- | ---: | ---: |
| `3-Git_Main` | 16.663 | 1.576.318.249 |
| `.git` | 199 | 1.218.642.406 |
| `1-Dev` | 385 | 165.033.625 |
| `2-Compiler` | 12 | 11.677 |
| `Knowledge` | 6 | 49.820 |
| `Machine` | 5 | 38.195 |

O `3-Git_Main/System` possui exatamente `16.645` arquivos e
`1.576.281.489` bytes. Os demais 18 arquivos de `3-Git_Main` pertencem a
README, Steps, Evidence e Receipt.

### Comparacao WSL versus Windows

Origem WSL:

```text
/cjl/Sistema_Dev/3-Git_Main/System
```

Alvo Windows observado:

```text
C:\.Dev CJL\Git_Main\System
```

Resultado por path e tamanho:

- `16.645` arquivos comuns;
- todos os `16.645` possuem o mesmo tamanho;
- nenhum arquivo existe somente no WSL;
- nenhum arquivo comum possui tamanho diferente;
- Windows possui apenas tres arquivos extras, todos em `Logs\Bootstrap`;
- diferenca total: `1.137` bytes, exatamente os tres logs de `379` bytes.

Assim, a evidencia atual indica que o `Git_Main\System` Windows e a mesma
estrutura materializada do candidato WSL, acrescida somente de logs de tres
execucoes. A identidade byte a byte ainda depende de hashes.

### Residuos e organizacao

- `/tmp` ocupa `5.408.964.608` bytes;
- existem 37 diretorios `cjl-linux-dev-*`, muitos com aproximadamente 166 MB;
- `/home/carlos_alberto` possui caches .NET/NuGet e um diretorio
  `cjl-reconcile`;
- existem duas entradas de diretorio na raiz do repositorio cujo nome comeca
  por `# CJL Documentation Reconciliation Recovery Evidence` e contem quebras
  de linha; o status Git ainda dira se sao rastreadas ou residuos locais;
- `1-Dev` contem `bin/Release` locais; o status Git ainda dira se sao ignorados,
  nao rastreados ou rastreados.

Nenhuma limpeza esta autorizada neste ciclo.

### Classificacao

`INCOMPLETE`, com forte alinhamento estrutural do candidato Windows.

Proximo gate: branch, commit, remote, status, Git LFS e hashes criticos do
repositorio WSL. Depois: hashes correspondentes do Windows em PowerShell.

## Ciclo 005 — identidade Git e topologia definitiva

### Decisao final do operador

A raiz visivel de trabalho devera conter somente tres entradas:

```text
C:\.Dev CJL\
|-- 1-Dev
|-- 2-Compiler
`-- 3-Git_Main
```

Mapeamento operacional obrigatorio:

- `1-Dev`: fonte e sistema Linux, fisicamente no Ubuntu/WSL;
- `2-Compiler`: estagio intermediario controlado no Ubuntu/WSL, responsavel por
  compilar a identidade aprovada para Windows/.NET;
- `3-Git_Main`: sistema Windows completo de pre-producao e homologacao, com
  recursos reais, dados de teste locais isolados e rollback;
- Painel: somente controlador de estados, testes, aprovacao, reprovacao e
  rollback; nunca fonte canonica do codigo.

Links, atalhos ou portais podem representar os dois estagios Linux no Windows,
desde que a operacao Linux ocorra diretamente no terminal `Ubuntu-24.04` e a
operacao Windows diretamente no PowerShell.

### Evidencia Git recebida

- arquivo: `Texto colado(20260827-022549).txt`;
- SHA-256: `83666042ab4317675022a0d2ec554cb0fd470b742b7fa65bee8a00c2964b2b67`;
- repositorio: `/cjl/Sistema_Dev`;
- branch: `Dev-Work`;
- HEAD: `529953acfabeb44a2b29bacc2301fc4c520abfcf`;
- upstream: `origin/Dev-Work`;
- status: limpo e alinhado ao upstream segundo as referencias locais;
- arquivos rastreados: `16.885`;
- nao rastreados: `0`;
- ignorados: `195`;
- Git LFS `3.7.1`, sem objetos pendentes.

Hashes criticos do candidato WSL:

| Arquivo | SHA-256 |
| --- | --- |
| `3-Git_Main/System/CJL.exe` | `6b4d1d3d716a4fe4b3b670c8f658f4f8eab9a1cd6c0bb24f229abaee512350ab` |
| `App/Config/sistema.json` | `c9bc10a32e70b360aad9fefeabbbbfd78e1f16473ccfc5a0bf1fabee55a7ea0c` |
| `App/Config/app.integrity.json` | `d67a9b6353139e0e581cb9ad8aeca2e0629d03b81f5ebb4e430286dd4a0c21be` |
| `Data/sistema.db` | `d5ab9e4e389d6b026ba90d22e21bb1d93d20b1ace2f1b2451ea7ddfda6b98213` |

O HEAD local coincide com o HEAD atual conhecido de `Dev-Work`. O candidato
`3-Git_Main` continua equivalente entre `Dev-Work` e `main`; os dados de teste
nao fazem parte da branch e deverao existir somente no ambiente Windows local.

### Estrategia de recuperacao

Nao recompilar a fonte `main` vermelha antes de recuperar o candidato coerente
ja materializado. A ordem passa a ser:

1. comparar os quatro hashes criticos do Windows com o candidato WSL/GitHub;
2. preservar o `Git_Main` Windows atual e seus logs;
3. transformar/adotar esse candidato como `3-Git_Main`;
4. iniciar e diagnosticar Host, backend, banco e acesso administrativo;
5. criar dados administrativos somente no banco local isolado, se necessario;
6. homologar inicio, login, painel, logout, reinicio e rollback;
7. somente depois reorganizar a raiz, relocar o VHDX e materializar os portais
   `1-Dev` e `2-Compiler`;
8. somente depois reabilitar o Painel como controlador do fluxo.

### Gate atual

PENDENTE: SHA-256 dos quatro arquivos criticos em
`C:\.Dev CJL\Git_Main\System`, executado exclusivamente no Windows PowerShell
e sem escrita.

Nenhuma pasta sera movida, renomeada, apagada ou sobrescrita antes desse gate.

## Ciclo 006 — gate de identidade Windows aprovado

### Resultado recebido

```text
FAILURES=0
SOURCE_WRITE=NO
PRODUCTION_WRITE=NO
[PASS] WINDOWS_HASH_GATE=PASS
```

Os quatro arquivos criticos em `C:\.Dev CJL\Git_Main\System` possuem os mesmos
SHA-256 do candidato `3-Git_Main/System` em `/cjl/Sistema_Dev`, incluindo o
launcher, os dois manifests e a semente SQLite.

### Conclusao

O candidato Windows existente pode ser adotado sem copia ou recompilacao. Os
tres logs de bootstrap locais sao evidencia de execucao e nao alteram a
identidade dos arquivos criticos.

### Proximo gate

ADOPTION_RENAME:

1. comprovar ausencia de processos executando a partir de `Git_Main`;
2. salvar os arquivos mutaveis em evidencia externa;
3. renomear reversivelmente `Git_Main` para `3-Git_Main`;
4. comprovar origem ausente, destino presente e identidade preservada.

O WSL, GitHub, producao e demais pastas de `C:\.Dev CJL` permanecem intocados.

## Ciclo 007 — adocao concluida e causa do login comprovada

### Evidencias recebidas

- transcript: `Texto colado(20260827-025303).txt`;
- SHA-256 do transcript:
  `bc17a264d428275c011ec46da1a9d2f696a6e95b8daf1d826d9fb7d31616726b`;
- rollback: `20260826T235220278_BEFORE_3-GIT_MAIN_ADOPTION.zip`;
- SHA-256 do ZIP:
  `be9c21ce5e1216109b705b47ac08448c5219b27ce176b993f28a82eb3597c006`;
- ZIP sem erro de CRC, com quatro arquivos mutaveis e receipt;
- nenhum processo bloqueador;
- renomeacao concluida para `C:\.Dev CJL\3-Git_Main`;
- quatro hashes pos-renomeacao aprovados;
- WSL, GitHub e producao sem escrita.

### Banco preservado

`PRAGMA integrity_check=ok`. Todas as tabelas operacionais possuem zero linhas,
inclusive `usuarios=0`. A semente e limpa e nao contem credencial ou massa de
teste.

### Causa comprovada do acesso administrativo

Existe um defeito de bootstrap na baseline `1.05.01.006`:

1. `Core.bootstrap.bootstrap()` cria `ADMIN` apenas no banco local da instancia;
2. `Host/Bridge/host_bridge.py::cmd_recover_admin()` recupera apenas o banco
   semente do Mestre;
3. o banco semente versionado possui zero usuarios;
4. o recuperador para com `CONTA ADMIN PRINCIPAL AUSENTE` quando `ADMIN` nao
   existe.

Assim, a recuperacao oficial nao consegue inicializar sua propria pre-condicao.
Isso explica a impossibilidade de acesso e nao e erro de senha do operador.

### Isolamento do caminho final

O codigo de `Core.config` comprova que a execucao direta usa a pasta fisica que
contem `App`, isto e, `C:\.Dev CJL\3-Git_Main\System`. Os defaults
`C:\CJL\System` presentes em manifests nao redirecionam a execucao direta. O
estado local e isolado em `%LOCALAPPDATA%\CJL\Instancias\<master+hash-do-path>`.

### Correcao local controlada proposta

1. exigir PowerShell elevado e ausencia de processos CJL;
2. validar novamente integridade e `usuarios=0`;
3. inserir somente a identidade `ADMIN` sem PIN, em `BEGIN IMMEDIATE`;
4. atualizar contador e flag `admin_provisioning_required=1`;
5. validar integridade e invariantes; rollback transacional em falha;
6. abrir o Bootstrap oficial e escolher `RECUPERAR`;
7. o Bootstrap solicita o novo PIN de forma oculta e registra a recuperacao;
8. autenticar e abrir o Mestre no caminho final.

O PIN nunca sera escrito em script, chat, transcript ou arquivo de evidencia.

## Ciclo 008 — substituicao do bloco interativo por pacote fechado

### Falha operacional evitada

O bloco PowerShell anterior continha um here-string Python longo. A colagem
parcial deixou o console no prompt de continuacao `>>`, antes de fechar a
atribuicao. Nenhum Python foi executado e o banco nao foi alterado nesse ponto.

Correcao: cancelar com `Ctrl+C` e nao continuar a colagem. A fronteira foi
substituida por arquivos separados e versionados.

### Pacote

- nome: `CJL-Admin-Recovery-v1.0.0.zip`;
- SHA-256:
  `873129328dae7c8bd22d2af32f1ca6056f2090a06cbdabc89b70972cfe556c21`;
- CMD: wrapper minimo, parser PowerShell nativo e propagacao do exit code;
- PowerShell: elevacao, processos, paths, evidencias e Bootstrap Windows;
- Python: backup SQLite, transacao e invariantes;
- PIN: nunca presente ou capturado pelo kit.

### Gates executados

- AST Python: PASS;
- primeira execucao sobre copia da semente real: PASS;
- repeticao idempotente: PASS;
- backup via SQLite API e integridade: PASS;
- banco divergente bloqueado sem alterar o SHA-256: PASS;
- `integrity_check` e `foreign_key_check`: PASS;
- ausencia de `__pycache__`/`*.pyc`: PASS;
- hashes internos e ZIP reextraido: PASS;
- estrutura PowerShell: PASS por varredura local;
- parser nativo Windows PowerShell 5.1: gate automatico ainda pendente na
  maquina do operador antes de qualquer escrita.

### Proximo gate

Executar `ATIVAR-RECUPERACAO-ADMIN.cmd`, confirmar
`ADMIN_IDENTITY_GATE=PASS`, usar `RECUPERAR` no Bootstrap oficial, definir PIN
local oculto, autenticar e abrir a opcao 1.

## Ciclo 009 — reinicio dirigido pelo operador

### Decisao humana mais recente

O fluxo de recuperacao administrativa e a reorganizacao anterior foram
interrompidos. Nenhuma continuacao sera inferida. Cada etapa futura dependera de
comando explicito do operador.

Raiz Windows final exigida:

```text
C:\.Dev CJL\
|-- 1-Dev\
|-- 2-Compiler\
|-- 3-Git_Main\
`-- WSL\
```

Conteudo pretendido:

- `1-Dev`: futuro Painel e portais/atalhos para o CJL Linux no Ubuntu;
- `2-Compiler`: todo material antigo de build, compilacao, patches, releases e
  runtime, guardado e sem execucao ate nova ordem;
- `3-Git_Main`: futura materializacao limpa da branch `main`, seguida de
  credencial local de homologacao;
- `WSL`: armazenamento Linux preservado nesta etapa.

### Etapa autorizada agora

Somente reorganizar a raiz NTFS:

- criar `1-Dev` e `2-Compiler`;
- mover `Builds`, `Compilador`, `Patches`, `Releases`/`Realeses` e `Runtime`
  para dentro de `2-Compiler`;
- nao alterar `3-Git_Main`;
- nao alterar `WSL` nem o VHDX;
- nao apagar nada;
- registrar receipt externo e executar rollback automatico se uma movimentacao
  falhar.

### Conflito pendente para a etapa 3-Git_Main

A branch `main` atual usa PIN numerico e nao carrega credencial padrao. Portanto,
os requisitos `clone byte-identico da main` e `senha textual inicial admin`
nao podem ser verdadeiros simultaneamente sem um patch de autenticacao. O
operador devera escolher posteriormente entre:

1. clone identico + PIN temporario local com troca obrigatoria; ou
2. patch DEV que implemente senha textual temporaria, nova compilacao e novo
   candidato, deixando de ser clone identico da main atual.

Nenhuma escolha foi presumida.

## Ciclo 010 — reorganizacao da raiz aprovada

### Resultado observado

```text
[PASS] MOVIDO=Builds
[PASS] MOVIDO=Compilador
[PASS] MOVIDO=Patches
[PASS] MOVIDO=Releases
[PASS] MOVIDO=Runtime
[PASS] ROOT_REORGANIZATION=PASS
FINAL_ROOT_ENTRIES=1-Dev|2-Compiler|3-Git_Main|WSL
```

### Receipt

- arquivo: `ROOT_REORGANIZATION_RECEIPT.txt`;
- SHA-256:
  `15c847baf0e2e53cb6994ee4b5258015f7b9502f7ef58ec72ecb2708c17018ea`;
- timestamp: `2026-08-27T07:27:29.1412055-03:00`;
- pastas movidas: `5`;
- delete: `NO`;
- WSL write: `NO`;
- Git_Main write: `NO`;
- production write: `NO`.

### Estado homologado desta etapa

```text
C:\.Dev CJL\
|-- 1-Dev\
|-- 2-Compiler\
|-- 3-Git_Main\
`-- WSL\
```

Somente a organizacao da raiz esta homologada. Conteudo de `1-Dev`, ambiente
Linux/containers, material de `2-Compiler`, clone limpo de `3-Git_Main`,
credenciais e Painel permanecem pendentes e nao serao executados sem nova ordem
do operador.
