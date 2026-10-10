# V-G1 — validação no Windows da correção `955826a`

**Data:** 10/10/2026  
**Revisor:** Codex / ChatGPT  
**Código examinado:** `955826a` (`claude/producao`; correção de normalizações do Excel)  
**Veredito no escopo da correção:** **DE ACORDO**. **G1 permanece EM REVISÃO** até H-1 e aceite do Admin.

## Ambiente e integridade

Testes executados no Windows, no ambiente já isolado da validação G1. Atualizados **somente** os dois arquivos alterados por `955826a`: `ascalpi_producao/modelos_edicao.py` e `tests/test_edicao_modelo.py`. Seus hashes Git foram comparados com os blobs exatos de `955826a`, coincidindo. As cópias anteriores foram guardadas localmente. Instalada a dependência de testes Pillow **apenas no venv isolado**. Não houve instalação na produção, nem modificação da base operacional, nem publicação de O.P./modelo.

## Quatro novos testes — Windows

`python -m unittest -v` com os quatro métodos novos de `TestEdicaoModelo`:

| Teste | Resultado |
|---|---|
| `test_excel_abrir_e_salvar_sem_editar_nao_gera_diferencas` | **OK** |
| `test_excel_normalizacao_de_altura_nao_polui_a_previa` | **OK** |
| `test_excel_alteracao_real_de_altura_continua_detectada` | **OK** |
| `test_excel_nome_e_foto_continuam_detectados` | **OK** |

**Resultado:** `Ran 4 tests in 1.407s — OK`.

A primeira tentativa encontrou `ModuleNotFoundError: PIL` somente no quarto teste. Após instalar Pillow no ambiente de teste, todos passaram; não era defeito da implementação.

## Suíte integral — Windows

`python -m unittest discover -s tests -t .`  
**Resultado:** `Ran 106 tests in 44.581s — OK` (exit code 0).

## Comparação independente com XLSX efetivamente salvos no Excel

Reutilizados quatro arquivos de evidência **já salvos pelo Excel real** no teste isolado anterior; não são arquivos simulados pela suíte. A análise foi repetida com a implementação antiga (cópia local anterior a `955826a`, equivalente a `b7c36a8`) e a nova, usando a **mesma origem publicada** da sessão de teste. Cada caso retornou `ok=True`, sem erros de validação.

| Arquivo de evidência | Prévia anterior | Prévia corrigida |
|---|---|---|
| `somente_salvar.xlsx` | 47 falsas `ALTURA` | **0 diferenças** |
| `somente_nome.xlsx` | 47 `ALTURA` + 1 `NOME` | **1 `NOME`** |
| `somente_altura.xlsx` | 47 `ALTURA` | **1 `ALTURA` (linha 11)** |
| `somente_fotos.xlsx` | 47 `ALTURA` + 2 `FOTO` | **2 `FOTO`, sem `ALTURA`** |

As duas diferenças de FOTO correspondem a imagens com dimensões distintas trocadas entre as linhas 10 e 11 (582×429 e 600×416); não são falsas diferenças de altura.

**Conclusão:** os 47 falsos positivos de altura foram eliminados nos quatro arquivos Excel, sem esconder as alterações efetivas de nome, altura ou fotos. Esta comparação é uma prova *antes/depois* com os mesmos dados, não apenas um teste de unidade.

## Limitações e próxima ação

- Esta rodada reanalisou arquivos **previamente salvos pelo Excel**, mas **não** reabriu/ressalvou os livros na interface do Excel nem executou publicação de nova versão na interface.
- Não foram comparadas 3–5 O.P. reais em XLSX/PDF com o legado (**H-1 ainda A FAZER**).
- A validação da **correção pontual** está **DE ACORDO**; o **aceite de G1** e a liberação de G2 seguem dependentes da verificação pendente e da decisão expressa do Admin.
- Evidências e logs mantidos **apenas no computador de teste**, fora do repositório público.
