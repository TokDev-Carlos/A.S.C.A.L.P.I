# ASCALPI — Plano 0: Ambiente oficial no Windows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (escolhido: execução nativa). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o núcleo CJL copiado em um ASCALPI instalável no padrão do UStracker: programa em `C:\Program Files\ASCALPI`, dados em `C:\ProgramData\ASCALPI\UserData` (junção), estado por usuário em `%LOCALAPPDATA%\ASCALPI`, caminhos de negócio escolhidos na instalação.

**Architecture:** Um módulo de caminhos do produto (`Core/produto.py`) passa a ser a única fonte de pastas; `Core/config.py` e o layout usam esse módulo. Scripts PowerShell (`setup-data.ps1`, `remove-data.ps1`) e um instalador NSIS (`installer/ASCALPI.nsi`) repetem o desenho já validado do UStracker.

**Tech Stack:** Python 3.14 (Runtime assinado do CJL), PowerShell 5.1, NSIS 3 (`C:\Program Files (x86)\NSIS\makensis.exe`), unittest.

**Spec:** `docs/superpowers/specs/2026-10-09-ascalpi-v1-producao-design.md` seção 12. Referência: UStracker `installer/UStracker.nsi`, `installer/setup-data.ps1`, `installer/remove-data.ps1`, `src/ustracker/paths.py`.

**Ordem:** Plano 0 primeiro (a Task 1 daqui substitui a Task 1 do Plano 1); depois Plano 1 a partir da Task 2.

## Global Constraints

- Mesmas regras do Plano 1 (`$PY`, unittest, commits, mensagens em MAIÚSCULAS, nada gravado em `D:\MACROS`).
- Nenhum caminho absoluto fixo no código Python: raiz do programa = pasta que contém `App`; dados = `<raiz>\UserData` (junção na instalação, pasta comum no desenvolvimento); estado local = `%LOCALAPPDATA%\ASCALPI\Instancias\<id>`.
- Variáveis de ambiente internas continuam com prefixo `CJL_` (compatibilidade do núcleo); nome exibido e pastas = `ASCALPI`.
- Instalação real neste PC só com o aviso do Windows (UAC) aprovado pelo Carlos (R-0264).
- R-0287: instalação nasce sem dados de desenvolvimento.

## Review Focus

1. **Junção seguida como "fuga" do Mestre**: `layout` com `UserData\...` não pode falhar na checagem "ESCAPA DO MESTRE" quando `UserData` é junção — Task 3 `test_dados_via_juncao`.
2. **Reinstalar/atualizar sem perder dados**: reinstalação mantém `ProgramData\ASCALPI\UserData` e recria só a junção — Task 6 `test_reinstalacao_mantem_dados` (roteiro manual com checagem).
3. **Usuário comum sem permissão de escrita**: banco e documentos ficam onde usuários gravam; programa continua protegido — Task 4 checa ACL (`BUILTIN\Users:(OI)(CI)M` em `UserData`).
4. **Remover tudo apaga sem backup**: "Remover tudo" só apaga depois de a cópia em `Documentos\ASCALPI_Backups` existir — Task 4 `remove-data.ps1` com saída 10 se a cópia falhar.
5. **Caminho de rede indisponível na instalação**: pasta opcional de PDF inválida não impede instalar; fica registrada como desativada — Task 5 `test_instalacao_json_pasta_invalida`.

---

### Task 1: Fundação do projeto
Igual à Task 1 do Plano 1 (cópia sem `CJL.exe`, `Host`, `Data`, `Shared`, `Repo`, `Logs`, `Temp`, `Export`; manifesto; fumaça; linha de base; README; `.gitignore`; inventário; `git init` + commit).

### Task 2: Identidade ASCALPI

**Files:** Modify `System\App\Core\config.py` (`APP_NAME`), títulos em `System\App\Painel\index.html`, mensagem de início em `System\App\painel.py`; Test `System\Tests\test_ascalpi_identidade.py`

- [ ] **Step 1: Testes** — com `LOCALAPPDATA` apontado para tmp e sem `CJL_STATE_ROOT`: `local_state_root()` == `tmp/"ASCALPI"/"Instancias"/instance_id()`; `<title>` do painel contém `ASCALPI`.
- [ ] **Step 2–4:** FAIL → `APP_NAME = "ASCALPI"`, títulos → PASS (rodar também a linha de base: nada novo quebrou).
- [ ] **Step 5: Commit** `feat(ascalpi): identidade do produto e estado local em LOCALAPPDATA\ASCALPI`

### Task 3: Caminhos do produto com `UserData`

**Files:** Create `System\App\Core\produto.py`; Modify `System\App\Core\config.py` (`_safe_master_relative`, `shared_data_root`, `repository_root`, `seed_database_path`), `System\App\Config\layout.json`; Test `System\Tests\test_ascalpi_caminhos.py`

**Interfaces — Produces:** `@dataclass(frozen=True) CaminhosProduto: raiz: Path` com propriedades `app`, `dados` (`raiz/"UserData"`), `banco_seed` (`dados/"Data"/"sistema.db"`), `repo`, `shared`, `logs`, `temp`, `export`, `backups`, `config` (`dados/"Config"`), `modelos_producao` (`shared/"Producao"/"Modelos"`), `documentos_producao` (`shared/"Producao"/"Documentos"`); `caminhos(raiz: Path | None = None) -> CaminhosProduto` (padrão: `network_root()`); `garantir_pastas(c: CaminhosProduto) -> None`.

- [ ] **Step 1: Testes** — `caminhos(tmp).repo == tmp/"UserData"/"Repo"`; `test_dados_via_juncao`: `UserData` como junção (Windows, `mklink /J`) ou symlink (Linux) para outra pasta → `shared_data_root()` e `repository_root()` resolvem sem `ESCAPA DO MESTRE`, e um caminho `../fora` no layout continua recusado.
- [ ] **Step 2–4:** FAIL → layout `shared_data: "UserData/Shared"`, `repository: "UserData/Repo"`, `seed_database: "UserData/Data/sistema.db"`, `logs`, `temp`, `export` idem; `_safe_master_relative` valida o texto relativo (sem `..`, não absoluto) e, para destinos dentro de `UserData`, compara com `(raiz/"UserData").resolve()` → PASS. Regenerar manifesto (`write_manifest`) e repetir a fumaça.
- [ ] **Step 5: Commit** `feat(ascalpi): caminhos do produto com UserData separado do programa`

### Task 4: Scripts de dados (`setup-data.ps1`, `remove-data.ps1`)

**Files:** Create `installer\setup-data.ps1`, `installer\remove-data.ps1`; Test `System\Tests\test_ascalpi_scripts.py` (Windows)

- [ ] **Step 1: Testes** (em pastas temporárias, sem admin): `setup-data.ps1 -App <tmp>\Programa -Data <tmp>\Dados -Log <tmp>\i.log` → `<tmp>\Dados\UserData\{Data,Repo,Shared,Logs,Temp,Export,Backups,Config}` existem; `<tmp>\Programa\UserData` é junção para `<tmp>\Dados\UserData`; rodar de novo não apaga nada (arquivo-teste continua lá). `remove-data.ps1 -Data <tmp>\Dados -Backup <tmp>\Docs\ASCALPI_Backups\Desinstalacao_<data> -Log ...` → backup contém o arquivo-teste e só então `Dados\UserData` some; backup inválido → código 10 e nada removido.
- [ ] **Step 2–4:** FAIL → implementar no molde do UStracker (robocopy, `cmd /c mklink /J`, `icacls <UserData> /grant *S-1-5-32-545:(OI)(CI)M` quando elevado, log com data ISO; códigos 0/10/11/12) → PASS.
- [ ] **Step 5: Commit** `feat(ascalpi): scripts de criação e remoção dos dados`

### Task 5: Configuração escolhida na instalação (`instalacao.json`)

**Files:** Create `System\App\Core\instalacao.py`; Test `System\Tests\test_ascalpi_instalacao.py`

**Interfaces — Produces:** `ler_instalacao(c: CaminhosProduto) -> dict` (padrões quando ausente), `gravar_instalacao(c, dados: dict) -> dict`; chaves: `formato: 1`, `pasta_dados`, `copiar_pdf_para` (`""` = desligado), `copiar_pdf_ativo: bool`, `instalado_em`, `versao`.

- [ ] **Step 1: Testes** — sem arquivo → padrões; gravar e ler de volta; `test_instalacao_json_pasta_invalida`: `copiar_pdf_para` inexistente → gravado com `copiar_pdf_ativo = False` e aviso, sem exceção.
- [ ] **Step 2–4:** FAIL → implementar (escrita atômica com `Core.atomic.atomic_write_json`) → PASS.
- [ ] **Step 5: Commit** `feat(ascalpi): configuração de caminhos escolhidos na instalação`

### Task 6: Instalador NSIS e instalação de validação

**Files:** Create `installer\ASCALPI.nsi`, `installer\LEIA-ME.txt`, `installer\README.md`, `System\Dev\Tools\montar_pacote.py`

- [ ] **Step 1: Pacote** — `montar_pacote.py <saida>` monta a pasta do programa: `App` (sem `__pycache__`), `Runtime\Python` (cópia de `C:\.Dev CJL\3-Git_Main\System\Runtime\Python`), `VERSION.json`, `CJL.root.json` (role `PRODUCTION`, environment `MAIN`), `COPYRIGHT.txt`, `LICENSE.txt`, `Iniciar ASCALPI.cmd`/atalho (`Runtime\Python\pythonw.exe App\Inicializacao\iniciar.py`). Teste: a pasta gerada passa em `verify_manifest`.
- [ ] **Step 2: `ASCALPI.nsi`** no molde do UStracker: `RequestExecutionLevel admin`, `InstallDir $PROGRAMFILES64\ASCALPI`, página para escolher a pasta de dados (padrão `%PROGRAMDATA%\ASCALPI`) e a pasta opcional de cópia de PDF, fecha o ASCALPI aberto, copia o programa (exceto `UserData`), roda `setup-data.ps1`, grava `instalacao.json`, atalhos no Menu Iniciar/Área de Trabalho, desinstalador com **Manter dados** / **Remover tudo** (`/REMOVERTUDO`), `/S` silencioso, log em `UserData\Logs\instalacao.log`.
- [ ] **Step 3: Compilar** — `& "C:\Program Files (x86)\NSIS\makensis.exe" -INPUTCHARSET UTF8 -DSRC=<pacote> -DVERSION=1.05.01.007 installer\ASCALPI.nsi` → `ASCALPI_install_x64.exe`.
- [ ] **Step 4: Instalação de validação neste PC** (precisa da aprovação no UAC): instalar; conferir `C:\Program Files\ASCALPI`, junção `UserData` → `C:\ProgramData\ASCALPI\UserData`, ACL de usuários, atalho abre o painel; reinstalar e conferir que um arquivo-teste em `UserData\Shared` continua (`test_reinstalacao_mantem_dados`); desinstalar com **Manter dados** e conferir que `ProgramData\ASCALPI` ficou.
- [ ] **Step 5: Commit** `feat(ascalpi): instalador oficial no padrão Program Files + ProgramData`

## Depois deste plano

- Janela própria (Host .NET + WebView2, como o `UStracker.exe`) com marca ASCALPI.
- Plano 1 a partir da Task 2 (modelos e documentos passam a viver em `UserData\Shared\Producao`).
- Nuvem: servidor como o do UStracker, estações como clientes.
