# ASCALPI v1 — Plano 1: Motor de documento e regras da O.P. — Implementation Plan

> **Contexto atualizado em 09/10/2026:** este documento preserva o planejamento histórico de integração/ambiente. O módulo atual é independente e sua interface já está implementada. Para a próxima etapa, leia [a revisão e o plano de estabilização](../../revisao/PLANO_PARA_CLAUDE.md) e as instruções vigentes em `Modulos/ASCALPI_Producao/CLAUDE.md`. Não reaplicar tarefas antigas como se fossem lacunas atuais; bloqueio total do XLSX e edição só no sistema são decisões vigentes. Integração ao núcleo e instalador ficam após estabilização e aceite operacional.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ter, sem interface, tudo o que o módulo Produção precisa para o sistema controlar as O.P.: regras (nome, número, saldo), importação dos `.xlsm` legados (contratos, itens, saldo base, histórico), extração dos modelos e geração sob demanda do `.xlsx`/PDF idênticos ao VBA V2.4.22.

**Architecture:** Pacote Python `Modulos/Producao` dentro do núcleo CJL copiado para `D:\PROGRAMAS\ASCALPI_Project\System`. Regras e importação são Python puro (qualquer SO); um worker PowerShell controla uma instância isolada do Excel para extrair modelos e gerar documentos; `cli.py` expõe tudo para teste e aceite. O Plano 2 liga isso ao banco, à API e às telas.

**Tech Stack:** Python 3.13/3.14 (stdlib + openpyxl 3.1), PowerShell 5.1 + Excel 16 via COM, unittest (padrão do CJL), poppler + Pillow só na ferramenta de aceite.

**Spec:** `docs/producao/superpowers/specs/2026-10-09-ascalpi-v1-producao-design.md` (revisão 2; seção 5 = contrato de fidelidade).

## Global Constraints

- Código em `System\App\Modulos\Producao\`; testes em `System\Tests\test_producao_*.py` inserindo `System/App` no `sys.path` (padrão CJL); fixtures em `System\Tests\producao_fixtures.py`.
- Python no Windows: `$PY = "C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe"` (3.14.6, openpyxl 3.1.5). Só stdlib + openpyxl; nada de pywin32.
- Comando de teste (raiz do projeto): `& $PY -m unittest discover -s System\Tests -p "test_producao_<nome>.py" -v`.
- Nunca gravar em `D:\MACROS\Legacy_Modules` nem nos `.xlsm`; testes trabalham em cópias temporárias. R-0287: o projeto nasce sem `Data`, `Shared`, `Repo`, `Logs`, `Temp`, `Export` do CJL.
- Excel: instância nova (`New-Object -ComObject Excel.Application`), `AutomationSecurity = 3`, arquivos de origem abertos somente leitura, `Quit()` garantido, PID gravado em `<result>.pid` logo após criar a instância.
- Mensagens ao usuário em português e MAIÚSCULAS (padrão CJL).
- Testes dependentes de Windows/Excel/arquivos legados usam `skipUnless`: `EXCEL_OK = os.name == "nt"` e existe `HKEY_CLASSES_ROOT\Excel.Application` (`winreg`); `MODELO_CAXIAS` = env `ASCALPI_MODELO_CAXIAS` ou `D:\MACROS\Legacy_Modules\Ordens_De_Producao\OK-CAXIAS_O.P.xlsm`; `CONTROLE_LEGADO` = env `ASCALPI_CONTROLE` ou `D:\MACROS\Legacy_Modules\Ordens_De_Producao\2_Controle_Ordens_De_Producao_Novo_Carlos.xlsm`.
- Um commit por tarefa, `feat(producao): ...`.

## Review Focus

1. **Excel órfão**: falha ou tempo esgotado não deixa `EXCEL.EXE` rodando nem fecha o Excel do usuário — Task 7 `test_excel_nao_fica_aberto`.
2. **Origem intocada**: extrair modelo e gerar documento não alteram o `.xlsm`/modelo (hash igual) — Task 7 `test_origem_nao_e_alterada`.
3. **Acentos e símbolos** em obra/cliente (`ç`, `ã`, `/`, `:`, `+`): nome do arquivo sanitizado igual ao legado, documento com o texto original — Task 8 `test_acentos_no_nome_e_no_documento`.
4. **Virada de ano e números legados** (`037`, `258-25`): próximo número correto — Task 3 `test_proximo_numero`.
5. **Muitos itens e linhas salteadas**: plano 13/15, quebras e linhas ocultas idênticos — Task 7 `test_plano_paginas` e `test_quebras_de_pagina_com_30_itens`.

---

### Task 1: Fundação do projeto

**Files:**
- Create (cópia de `C:\.Dev CJL\1-Dev\System`): `System\App`, `System\Dev`, `System\Docs`, `System\Tests`, `System\Updates`, `System\VERSION.json`, `System\CJL.root.json`, `System\CJL.branch.json`, `System\COPYRIGHT.txt`, `System\LICENSE.txt`. **Não copiar** `CJL.exe`, `Host`, `Data`, `Shared`, `Repo`, `Logs`, `Temp`, `Export` (R-0287).
- Create: `README.md`, `.gitignore`, `docs\INVENTARIO_LEGADO_2026-10-09.md`

- [ ] **Step 1: Copiar** os itens listados (shell Linux do dispositivo, `cp -r --preserve=timestamps`).
- [ ] **Step 2: Conferir o manifesto** — `& $PY -c "import sys; sys.path.insert(0,'System/App'); from pathlib import Path; from Core.release import verify_manifest; print('OK', verify_manifest(Path('System'))['version'])"` → `OK 1.05.01.007`.
- [ ] **Step 3: Fumaça do painel** — `CJL_BROWSER_MANAGED=1`, iniciar `& $PY System\App\painel.py`, esperar `http://127.0.0.1:<porta>`, `GET /` → 200 com `<html`; encerrar. Banco novo nasce em `%LOCALAPPDATA%\CJL\Instancias\<id>`.
- [ ] **Step 4: Linha de base** — `& $PY -m unittest discover -s System\Tests -v`; anotar no README ("Estado conhecido") os testes que já falham (ex.: `test_version_foundation` espera `1.05.00.006`).
- [ ] **Step 5: README, .gitignore, inventário** — `.gitignore`: `_sandbox/`, `__pycache__/`, `*.pyc`, `System/Data/`, `System/Shared/`, `System/Repo/`, `System/Logs/`, `System/Temp/`, `System/Export/`, `Legacy_modules/**/*.xls*`, `Legacy_modules/**/*.pdf` (dados de cliente não entram no git).
- [ ] **Step 6: Commit** — `git init && git add -A && git commit -m "chore: fundação do ASCALPI_Project com núcleo CJL 1.05.01.007"`

### Task 2: Texto, nome de arquivo, tipo e material (`nomes.py`)

**Files:** Create `System\App\Modulos\Producao\__init__.py`, `nomes.py`; Test `System\Tests\test_producao_nomes.py`

**Interfaces — Produces:**
`normalizar_nome(texto: str) -> str`, `normalizar_chave(texto: str) -> str`, `sanitizar_nome(texto: str) -> str`, `montar_nome_base(seq: str, cliente: str, obra: str, tipo: str, material: str) -> str`, `tipo_arquivo(tipo_b8: str) -> str`, `detectar_material(itens_coluna_b: Sequence[str], tipo_b8: str) -> str`, `formatar_quantidade(qtd: float) -> str`, `formatar_data_br(valor: date) -> str`

- [ ] **Step 1: Testes**

```python
self.assertEqual(normalizar_nome("  Praça  São João "), "praca sao joao")
self.assertEqual(normalizar_nome("ÁÉÍÓÚ Ññ Ýÿ"), "aeiou nn yy")
self.assertEqual(normalizar_chave("OP_CIMASP"), "OPCIMASP")
self.assertEqual(sanitizar_nome("OBRA: X/Y"), "OBRA X Y")
self.assertEqual(sanitizar_nome("CARBONO+INOX"), "CARBONO INOX")
self.assertEqual(sanitizar_nome("..Praça São João.."), "Praca Sao Joao")
self.assertEqual(sanitizar_nome("ÇÃO [teste]"), "CAO teste")
self.assertEqual(sanitizar_nome("   "), "SEM_NOME")
self.assertEqual(montar_nome_base("258-26", "CAXIAS-RJ", "CAMPO BOSSA NOVA", "MOB", "CARBONO+INOX"),
                 "258-26 - CAXIAS-RJ - CAMPO BOSSA NOVA - MOB - CARBONO INOX")
self.assertEqual(montar_nome_base("258-26", "", "OBRA", "MOB", ""), "258-26 - OBRA - MOB")
self.assertEqual(len(montar_nome_base("1", "C", "X" * 300, "MOB", "INOX")), 180)
self.assertEqual([tipo_arquivo(t) for t in ("ABRIGO ÔNIBUS", "placas", "GRADIL", "")], ["ABRIGO", "PLACA", "MOB", "MOB"])
self.assertEqual(detectar_material(["ESQUI - PEAD", "TOTEM"], "MOB"), "CARBONO")
self.assertEqual(detectar_material(["MASTRO - INOX", "TOTEM"], "MOB"), "CARBONO+INOX")
self.assertEqual(detectar_material(["MASTRO - Inox"], "MOB"), "INOX")
self.assertEqual(detectar_material(["ESQUI"], "MOB INOX"), "CARBONO+INOX")
self.assertEqual(detectar_material(["", "  "], "MOB"), "CARBONO")
self.assertEqual((formatar_quantidade(2.0), formatar_quantidade(1.5)), ("2", "1,5"))
self.assertEqual(formatar_data_br(date(2026, 10, 20)), "20/10/2026")
```

- [ ] **Step 2: Run** → FAIL. 
- [ ] **Step 3: Implement** — mapas por ponto de código idênticos ao VBA: `normalizar_nome` (minúsculas; 192–198/224–230→a, 199/231→c, 200–203/232–235→e, 204–207/236–239→i, 209/241→n, 210–214,216/242–246,248→o, 217–220/249–252→u, 221/253/255→y; colapsa espaços; strip). `sanitizar_nome`: proibidos → espaço; mantém 48–57, 65–90, 97–122, 32, 40, 41, 45, 46, 95; acentuadas → letra base preservando caixa; resto → espaço; colapsa; remove `.`/espaço das pontas; vazio → `SEM_NOME`. `montar_nome_base`: SEQ, CLIENTE, OBRA, TIPO, MATERIAL não vazios, `" - "`, sanitiza, corta em 180.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat(producao): regras de texto, nome, tipo e material`

### Task 3: Numeração (`numeracao.py`)

**Files:** Create `numeracao.py`; Test `test_producao_numeracao.py`

**Interfaces — Produces:** `formatar_numero(numero: int, ano: int) -> str`, `token_para_numero(token: str, ano: int) -> int`, `proximo_numero(existentes: Iterable[str], ano: int) -> int`

- [ ] **Step 1: Testes**

```python
self.assertEqual(formatar_numero(7, 2026), "007-26"); self.assertEqual(formatar_numero(1234, 2026), "1234-26")
self.assertEqual(token_para_numero("258-26", 2026), 258); self.assertEqual(token_para_numero("258-25", 2026), 0)
self.assertEqual(token_para_numero("037", 2026), 37); self.assertEqual(token_para_numero("12-2026", 2026), 12)
self.assertEqual(token_para_numero("", 2026), 0)
def test_proximo_numero(self):
    self.assertEqual(proximo_numero(["257-26", "258-25", "037", "100-26"], 2026), 258)
    self.assertEqual(proximo_numero(["257-26"], 2027), 1)
    self.assertEqual(proximo_numero([], 2026), 1)
```

- [ ] **Step 2–4:** FAIL → implementar (com `-`: número antes, ano = 2 últimos dígitos depois; ano diferente → 0; sem `-` → conta como ano atual; só dígitos) → PASS.
- [ ] **Step 5: Commit** `feat(producao): formato e próximo número de O.P.`

### Task 4: Códigos e saldo (`contrato.py`)

**Files:** Create `contrato.py`; Test `test_producao_contrato.py`

**Interfaces — Produces:**
- `STATUS_SALDO_OK = "SALDO_OK"`, `STATUS_SALDO_ENCERRADO = "SALDO_ENCERRADO"`, `STATUS_SALDO_NEGATIVO = "SALDO_NEGATIVO"`, `STATUS_SALDO_NEGATIVO_CONFIRMADO = "SALDO_NEGATIVO_CONFIRMADO"`, `STATUS_SEM_CONTRATO = "SEM_CONTRATO"`
- `normalizar_codigo(valor: object) -> str`, `codigo_valido(codigo: str) -> bool`, `codigo_base(codigo: str) -> str`, `ignora_checagem(codigo_base: str) -> bool`, `normalizar_cabecalho(texto: str) -> str`, `numero_br(valor: object) -> float | None`
- `@dataclass LinhaPedido: linha: int; codigo: object; quantidade: object`
- `agregar_por_base(linhas: Sequence[LinhaPedido]) -> tuple[dict[str, float], list[str]]`
- `@dataclass SaldoItem: codigo: str; equipamento: str; montante: float; consumido: float` com `saldo() -> float | str`
- `@dataclass AvisoSaldo: codigo: str; equipamento: str; antes: float | str; quantidade: float; depois: float | str`
- `@dataclass Simulacao: status: str; negativos: list[AvisoSaldo]; encerrados: list[AvisoSaldo]; erros: list[str]; quantidades: dict[str, float]` com `exige_confirmacao: bool` (há negativos)
- `simular_saldo(itens: Mapping[str, SaldoItem], quantidades: Mapping[str, float]) -> Simulacao`

- [ ] **Step 1: Testes**

```python
ITENS = {"1": SaldoItem("1", "A", 60, 49), "2": SaldoItem("2", "B", 10, 9), "8": SaldoItem("8", "C", 60, 115),
         "9": SaldoItem("9", "D", 5, 5), "5": SaldoItem("5", "E", 0, 0), "0.2": SaldoItem("0.2", "BONUS", 0, 0)}
self.assertEqual(normalizar_codigo(" 1,2 "), "1.2"); self.assertEqual(normalizar_codigo(3.0), "3")
self.assertEqual(normalizar_codigo(1.2), "1.2"); self.assertEqual(normalizar_codigo(None), "")
for ok in ("1", "1.2", "0.1"): self.assertTrue(codigo_valido(ok))
for ruim in ("1..2", ".1", "1.", "A1", ""): self.assertFalse(codigo_valido(ruim))
self.assertEqual((codigo_base("1.2"), codigo_base("0.3")), ("1", "0.3"))
self.assertEqual(normalizar_cabecalho("VALOR UN."), "VALOR UN"); self.assertEqual(normalizar_cabecalho("PREVISÃO"), "PREVISAO")
self.assertEqual(agregar_por_base([LinhaPedido(10, "1", 2), LinhaPedido(11, "1.1", 1), LinhaPedido(12, "0.2", 3),
                                   LinhaPedido(13, "", None), LinhaPedido(14, "5", "0")]), ({"1": 3.0, "0.2": 3.0}, []))
self.assertEqual(agregar_por_base([LinhaPedido(10, "1,5", "2,5")]), ({"1": 2.5}, []))
self.assertIn("linha 10", agregar_por_base([LinhaPedido(10, "", 2)])[1][0])
self.assertTrue(agregar_por_base([LinhaPedido(10, "1", "abc")])[1])
self.assertEqual([ITENS[k].saldo() for k in ("1", "9", "5", "8")], [11, "ACABOU", 0, -55])
self.assertEqual(simular_saldo(ITENS, {"1": 2}).status, "SALDO_OK")
enc = simular_saldo(ITENS, {"2": 1}); self.assertEqual(enc.encerrados, [AvisoSaldo("2", "B", 1, 1, 0)])
neg = simular_saldo(ITENS, {"8": 1}); self.assertEqual(neg.negativos, [AvisoSaldo("8", "C", -55, 1, -56)])
self.assertTrue(neg.exige_confirmacao)
self.assertEqual(simular_saldo(ITENS, {"9": 2}).negativos,
                 [AvisoSaldo("9", "D", "ACABOU", 2, "-2 *saldo anterior ja estava encerrado*")])
self.assertEqual(simular_saldo(ITENS, {"5": 1}).negativos, [AvisoSaldo("5", "E", 0, 1, -1)])
self.assertEqual(simular_saldo(ITENS, {"0.2": 5}).status, "SALDO_OK")
self.assertTrue(simular_saldo(ITENS, {"7": 1}).erros)
```

- [ ] **Step 2–4:** FAIL → implementar conforme spec 5.4 (`numero_br`: `,` e `.` → remove `.` e troca `,`; só `,` → `.`; `-` só no início) → PASS.
- [ ] **Step 5: Commit** `feat(producao): códigos e simulação de saldo do VBA`

### Task 5: Importação dos modelos `.xlsm` (`modelos.py`)

**Files:** Create `modelos.py`, `System\Tests\producao_fixtures.py`; Test `test_producao_modelos.py`

**Interfaces:**
- Consumes: `contrato.normalizar_codigo`, `contrato.normalizar_cabecalho`, `contrato.SaldoItem`
- Produces: `LinhaModelo(linha: int, codigo: str, equipamento: str)`; `ItemSaldoPlanilha(codigo, equipamento, valor_unitario: float | None, montante: float, quant: float, previsao: float, saldo_planilha: float | str | None)` com `para_saldo_item() -> SaldoItem` (`consumido = quant + previsao`); `ContratoModelo(contrato_id, aba_op, codename_op, aba_saldo: str | None, tabela_saldo: str | None, numero_contrato, tipo_b8, cliente_b3, linhas: list[LinhaModelo], itens_saldo: list[ItemSaldoPlanilha], colunas_op: list[str], problemas: list[str])`; `Modelo(caminho: Path, sha256: str, cliente_oficial: str, contratos: list[ContratoModelo])` com `contrato(id) -> ContratoModelo`; `ler_modelo(caminho: Path) -> Modelo`.
- Fixture `criar_modelo_sintetico(caminho: Path) -> Path` (openpyxl): aba `O.P-TESTE` (codeName `OP_TESTE`, B3 `CLIENTE TESTE`, B8 `MOB`, linhas 10/11/12 = `1 ITEM A`, `2 ITEM B`, `3 ITEM C`); aba `CONTRATO TESTE` (codeName `Saldo_TESTE`, E2 `"Contrato: \nFOR-1/2026"`, tabela `TAB_SALDO_TESTE` `A3:I7`, cabeçalhos `COD, EQUIPAMENTOS, VALOR UN., MONTANTE, ACUMULADO, QUANT., SALDO, O.P 001-26, PREVISÃO`, `totalsRowCount=1`; itens COD/MONTANTE/QUANT./SALDO/PREVISÃO: `1` 10/2/5/3, `2` 4/4/"ACABOU"/0, `3` 20/0/19/1; linha 7 `TOTAL DO CONTRATO:`); aba `O.P-SEM` (codeName `OP_SEMSALDO`, linha 10 `1 ITEM S`); aba `DB` (codeName `DB_`, tabela `TAB_CLIENTE` `B2:B3`).

- [ ] **Step 1: Testes**

```python
m = ler_modelo(criar_modelo_sintetico(tmp / "m.xlsx"))
self.assertEqual(m.cliente_oficial, "CLIENTE TESTE")
c = m.contrato("TESTE")
self.assertEqual(c.linhas[:2], [LinhaModelo(10, "1", "ITEM A"), LinhaModelo(11, "2", "ITEM B")])
self.assertEqual([i.codigo for i in c.itens_saldo], ["1", "2", "3"]); self.assertEqual(c.colunas_op, ["O.P 001-26"])
self.assertIsNone(m.contrato("SEMSALDO").aba_saldo)
@skipUnless(MODELO_CAXIAS.is_file(), "modelo legado indisponível")
def test_modelo_caxias(self):
    m = ler_modelo(MODELO_CAXIAS)
    self.assertEqual(m.cliente_oficial, "CAXIAS-RJ")
    self.assertEqual([c.contrato_id for c in m.contratos], ["CIMASP", "CIOP", "GYM", "CIMASP1"])
    c = m.contrato("CIMASP")
    self.assertEqual((c.aba_op, c.aba_saldo, c.tabela_saldo, c.numero_contrato, c.tipo_b8),
                     ("O.P-ATA-CIMASP", "CONTRATO CIMASP", "TAB_SALDO_CIMASP", "FOR-29/2025", "MOB"))
    self.assertEqual(c.linhas[0], LinhaModelo(10, "1", "ESQUI - PEAD"))
    i1 = next(i for i in c.itens_saldo if i.codigo == "1")
    self.assertEqual((i1.montante, i1.quant, i1.previsao, i1.saldo_planilha), (60, 13, 36, 11))
    self.assertEqual(m.contrato("CIOP").numero_contrato, "FOR-181/2024")
    for ct in m.contratos:
        for it in ct.itens_saldo:
            if it.saldo_planilha is not None and it.montante > 0:
                self.assertEqual(it.para_saldo_item().saldo(), it.saldo_planilha, (ct.contrato_id, it.codigo))
```

- [ ] **Step 2–4:** FAIL → implementar (estrutura por `zipfile`: `workbook.xml` + rels, `codeName` em `<sheetPr>`, tabelas com `ref`/`totalsRowCount`; valores com `openpyxl.load_workbook(read_only=True, data_only=True, keep_links=False)`; colunas por `normalizar_cabecalho` — exatas `COD`, `EQUIPAMENTOS`, `VALOR UN`, `MONTANTE`, `QUANT`, `SALDO`; `PREVISAO` por "contém"; `colunas_op` = cabeçalhos entre SALDO e PREVISÃO começando com `O.P `; `numero_contrato` = E2 após `Contrato:`; cliente oficial = `TAB_CLIENTE` na aba `DB_`, senão B3) → PASS.
- [ ] **Step 5: Commit** `feat(producao): importação de contratos, itens e saldo base dos .xlsm`

### Task 6: Importação do histórico do Controle (`historico.py`)

**Files:** Create `historico.py`; Test `test_producao_historico.py`

**Interfaces — Produces:** `@dataclass OpHistorico: seq: str; cliente: str; obra: str; solicitante: str; equipamentos: str; material: str; solicitacao: datetime | None; entrega: date | None; entrega_atualizada: date | None; material_obra: str; status_instalacao: str; fotografico: str; obs: str`; `ler_controle(caminho: Path) -> list[OpHistorico]` (tabela `Controle_OP` da aba `CONTROLE_ORDENS_DE_PRODUÇÃO`, colunas por cabeçalho normalizado; linhas sem Nº ignoradas; Nº sempre texto).

- [ ] **Step 1: Testes** — fixture sintética `criar_controle_sintetico(caminho)` com 2 linhas (`257-26`, `CAXIAS-RJ`, `CAMPO BOSSA NOVA`, `LUIS`, `MOB`, `CARBONO+INOX`, `2026-10-01 08:30:22`, `2026-10-01`) e uma linha vazia → `len == 2`, campos iguais; `@skipUnless(CONTROLE_LEGADO.is_file())`: `ler_controle(CONTROLE_LEGADO)[0].seq == "257-26"` e todos os `seq` casam `^\d{3,}-\d{2}$|^\d+$`.
- [ ] **Step 2–4:** FAIL → implementar → PASS.
- [ ] **Step 5: Commit** `feat(producao): importação do histórico do Controle legado`

### Task 7: Worker Excel (`excel_worker.ps1`) e ponte (`excel.py`)

**Files:** Create `excel_worker.ps1`, `excel.py`; Test `test_producao_excel.py`

**Interfaces — Produces:**
- Job JSON (`formato: 1`) com `acao`:
  - `"extrair_modelo"`: `{"acao":"extrair_modelo","origem":"<xlsm>","codename":"OP_CIMASP","saida_xlsx":"<modelo.xlsx>"}` → abre a origem só leitura, `Worksheet.Copy` da aba, `SaveAs` 51.
  - `"gerar_documento"`: `{"acao":"gerar_documento","modelo":"<modelo.xlsx>","senhas":["<senha>"],"cabecalho":{"P2":"258-26","U2":0,"B3":"CAXIAS-RJ","D3":"OBRA","V2":"2026-10-20","V8":"LUIS","B8":"MOB"},"linhas":[{"linha":10,"D":2,"E":null,"S":""}],"saida_xlsx":"...","saida_pdf":"..."}` → spec 5.1 passos 1–8.
- Result JSON: `{"ok", "erro", "excel_pid", "xlsx", "pdf", "area_impressao", "linhas_ocultas", "quebras", "paginas_planejadas", "duracao_ms"}`
- `ExcelIndisponivelError`, `ExcelFalhouError`, `WORKER: Path`, `plano_paginas(total_visiveis: int) -> list[int]`, `executar_job(job: dict, *, pasta_trabalho: Path, timeout_s: float = 300.0, executar=subprocess.run, encerrar_pid: Callable[[int], None] | None = None) -> dict`

- [ ] **Step 1: Testes**

```python
def test_plano_paginas(self):
    for n, esperado in ((0, [1]), (13, [13]), (14, [13, 1]), (28, [13, 15]), (29, [13, 8, 8]), (30, [13, 9, 8]),
                        (60, [13, 12, 12, 12, 11])):
        self.assertEqual(plano_paginas(n), esperado)
def test_ponte_monta_comando_e_le_resultado(self):  # executar falso; qualquer SO
    # comando: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <WORKER> -Job <job.json> -Result <result.json>
def test_ponte_tempo_esgotado_encerra_excel(self):  # TimeoutExpired + <result>.pid "4321" -> encerrar_pid(4321), ExcelFalhouError com "TEMPO"
@skipUnless(EXCEL_OK and MODELO_CAXIAS.is_file(), "requer Windows + Excel + modelo")
class ExcelReal(unittest.TestCase):
    # setUpClass: copia o .xlsm para tmp e extrai OP_CIMASP -> modelo.xlsx
    def test_extrair_modelo(self):  # modelo.xlsx tem 1 aba "O.P-ATA-CIMASP", A10 == 1, B10 == "ESQUI - PEAD"
    def test_gera_documento_igual_ao_vba(self):  # linhas 10 (D=2), 12 (D=1,E=1), 14 (D=3,S="OBS")
        ws = openpyxl.load_workbook(r["xlsx"]).active
        self.assertEqual((ws.title, ws["P2"].value), ("O.P-ATA-CIMASP", "258-26")); self.assertTrue(ws.protection.sheet)
        self.assertEqual({n for n, d in ws.row_dimensions.items() if d.hidden and 10 <= n <= 100}, set(range(10, 101)) - {10, 12, 14})
        self.assertEqual(ws.print_area, "'O.P-ATA-CIMASP'!$B$2:$V$14")
        self.assertEqual((ws.page_setup.orientation, ws.page_setup.fitToWidth, ws.page_setup.fitToHeight), ("portrait", 1, 0))
        self.assertAlmostEqual(ws.page_margins.top, 1.2 / 2.54, places=3)
        self.assertTrue(Path(r["pdf"]).read_bytes().startswith(b"%PDF")); self.assertEqual(contar_paginas_pdf(r["pdf"]), 1)
    def test_quebras_de_pagina_com_30_itens(self):
        self.assertEqual(r["paginas_planejadas"], 3); self.assertEqual(contar_paginas_pdf(r["pdf"]), 3)
        self.assertEqual(r["quebras"], [linhas_com_d[13], linhas_com_d[22]])
    def test_excel_nao_fica_aberto(self):  # após sucesso e após falha forçada; PIDs de Excel do usuário inalterados
    def test_origem_nao_e_alterada(self):  # sha256 do .xlsm e do modelo.xlsx antes == depois
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `excel.py`** — `plano_paginas` (spec 5.1 passo 6); ponte grava `job.json`, executa com timeout, lê `result.json`; timeout → lê `<result>.pid`, `encerrar_pid` (padrão `taskkill /PID <pid> /T /F`), `ExcelFalhouError("TEMPO ESGOTADO NA GERAÇÃO DO EXCEL.")`; `ok == False` → `ExcelFalhouError(erro)`.
- [ ] **Step 4: Implement `excel_worker.ps1`** (`-Job`, `-Result`), spec 5.1 à risca, `try/finally` com `Close($false)`, `Quit()`, `ReleaseComObject`, `[GC]::Collect()` e encerramento do PID se ainda vivo após 5 s. PID via `GetWindowThreadProcessId` (Add-Type) sobre `$excel.Hwnd`. Chamadas posicionais (`$m = [Type]::Missing`):
  ```powershell
  $wb = $excel.Workbooks.Open($arquivo, 0, $true, $m, $m, $m, $true, $m, $m, $false, $false, $m, $false)
  $ws.Protect($senha, $true, $true, $true, $true, $false, $false, $false)
  $ws.Outline.ShowLevels(1, $m)
  $wbPdf.ExportAsFixedFormat(0, $pdf, 0, $true, $false, $m, $m, $false)
  ```
- [ ] **Step 5: Run** no Windows → PASS. **Step 6: Commit** `feat(producao): worker Excel para extrair modelos e gerar documentos`

### Task 8: Documento da O.P. e linha de comando (`documentos.py`, `cli.py`)

**Files:** Create `documentos.py`, `cli.py`; Modify `System\App\Config\app.integrity.json` (regenerado); Test `test_producao_documentos.py`

**Interfaces:**
- Consumes: Tasks 2–7.
- Produces:
  - `@dataclass ItemOP: linha: int; codigo: str; equipamento: str; quantidade: float; inauguracao: float | None = None; observacao: str = ""`
  - `@dataclass OrdemProducao: seq: str; revisao: int; cliente: str; obra: str; prazo: date; solicitante: str; tipo_b8: str; itens: list[ItemOP]`
  - `class OrdemInvalidaError(ValueError)`
  - `validar_ordem(op: OrdemProducao) -> None` (obra/cliente/solicitante não vazios, ≥ 1 item com quantidade > 0, linhas entre 10 e 100 sem repetição)
  - `nome_documento(op: OrdemProducao) -> str` (= `montar_nome_base(seq, cliente, sanitizar_nome(obra), tipo_arquivo(tipo_b8), detectar_material(nomes com qtd, tipo_b8))`)
  - `montar_job(op: OrdemProducao, modelo_xlsx: Path, saida_dir: Path) -> dict`
  - `gerar_documentos(op: OrdemProducao, modelo_xlsx: Path, saida_dir: Path, *, executar=excel.executar_job) -> tuple[Path, Path]`
  - `cli.main(argv) -> int`: `ler-modelo --modelo`, `extrair-modelos --origem <xlsm> --destino <pasta>` (um `.xlsx` por contrato), `gerar --modelo <xlsx> --seq --cliente --obra --prazo --solicitante [--tipo MOB] [--rev 0] --item LINHA=QTD[:INAUG][:OBS] --saida <pasta>`; `cli.parse_item(texto) -> ItemOP` (código/equipamento preenchidos a partir do modelo pela linha).

- [ ] **Step 1: Testes**

```python
OP = OrdemProducao("258-26", 0, "CAXIAS-RJ", "CAMPO BOSSA NOVA", date(2026, 10, 20), "LUIS", "MOB",
                   [ItemOP(10, "1", "ESQUI - PEAD", 2), ItemOP(14, "5", "MASTRO - INOX", 1, None, "OBS")])
def test_nome_documento(self):
    self.assertEqual(nome_documento(OP), "258-26 - CAXIAS-RJ - CAMPO BOSSA NOVA - MOB - CARBONO INOX")
def test_montar_job(self):
    job = montar_job(OP, Path("m.xlsx"), Path("out"))
    self.assertEqual(job["acao"], "gerar_documento")
    self.assertEqual(job["cabecalho"], {"P2": "258-26", "U2": 0, "B3": "CAXIAS-RJ", "D3": "CAMPO BOSSA NOVA",
                                        "V2": "2026-10-20", "V8": "LUIS", "B8": "MOB"})
    self.assertEqual(job["linhas"], [{"linha": 10, "D": 2.0, "E": None, "S": ""}, {"linha": 14, "D": 1.0, "E": None, "S": "OBS"}])
    self.assertTrue(job["saida_pdf"].endswith("258-26 - CAXIAS-RJ - CAMPO BOSSA NOVA - MOB - CARBONO INOX.pdf"))
def test_acentos_no_nome_e_no_documento(self):
    op = replace(OP, obra="Praça São João / Lote 2")
    self.assertIn("Praca Sao Joao Lote 2", nome_documento(op))
    self.assertEqual(montar_job(op, Path("m.xlsx"), Path("o"))["cabecalho"]["D3"], "Praça São João / Lote 2")
def test_validar_ordem(self):  # obra vazia, sem itens, linha 9, linha repetida -> OrdemInvalidaError
def test_cli_parse_item(self):  # "10=2:1:OBS" -> linha 10, qtd 2.0, inaug 1.0, obs "OBS"
@skipUnless(EXCEL_OK and MODELO_CAXIAS.is_file(), "requer Windows + Excel + modelo")
def test_cli_e2e(self):  # extrair-modelos da cópia -> gerar para CIMASP -> xlsx e pdf existem, pdf começa com %PDF
```

- [ ] **Step 2–4:** FAIL → implementar → PASS (Windows inclui o e2e).
- [ ] **Step 5: Manifesto e painel** — `& $PY -c "import sys; sys.path.insert(0,'System/App'); from pathlib import Path; from Core.release import write_manifest; write_manifest(Path('System'))"`; repetir a fumaça da Task 1 (painel abre). Versão fica `1.05.01.007` até o fechamento do Plano 2.
- [ ] **Step 6: Commit** `feat(producao): documento da O.P. sob demanda e linha de comando`

### Task 9: Aceite de fidelidade

**Files:** Create `System\Dev\Tools\extrair_pedido.py`, `System\Dev\Tools\comparar_pdf.py`, `docs\ACEITE_PDF.md`; Test `test_producao_aceite.py`

**Interfaces — Produces:** `extrair_pedido(xlsx_legado: Path) -> dict` (P2, U2, B3, D3, V2, V8, B8, aba, linhas 10..100 com D preenchido → formato aceito por `cli gerar`); `comparar(pdf_a: Path, pdf_b: Path, *, dpi: int = 100, mascaras=((1, 0.0, 0.0, 0.35, 0.12),), tolerancia: float = 0.001) -> dict` → `{"paginas_a", "paginas_b", "tamanhos_iguais", "texto_igual", "diferenca_max", "ok"}` (texto via `pdftotext -layout` ignorando a linha que começa com `Hoje`).

- [ ] **Step 1: Testes** — PDFs feitos com Pillow: idênticos → `ok`; com retângulo → não `ok`; retângulo dentro da máscara → `ok`. `extrair_pedido` sobre xlsx sintético → `seq "258-26"`, `obra "OBRA X"`, `prazo "2026-10-20"`, itens `[{"linha": 10, "quantidade": 2.0, "inauguracao": None, "observacao": ""}]`.
- [ ] **Step 2–4:** FAIL → implementar (`pdftoppm`, `pdftotext`, `ImageChops.difference`) → PASS (Linux com poppler).
- [ ] **Step 5: Aceite com amostras** (precisa de 3–5 O.P. reais `.xlsx` + `.pdf` em `Legacy_modules\Ordens_De_Producao\amostras\`): `extrair_pedido` → modelo do contrato extraído do `.xlsm` do cliente → `cli gerar` no Windows → `comparar(pdf_legado, pdf_novo)` → tabela em `docs\ACEITE_PDF.md`. Critério: todas `ok`.
- [ ] **Step 6: Commit** `test(producao): aceite de fidelidade do PDF`
