# ASCALPI Produção (módulo independente)

Ordens de Produção controladas pelo sistema. Este módulo roda sozinho para teste e depois entra no ASCALPI.

- **Tudo é editado no sistema**: quantidades, datas (ou "DEFINIR"), observações, obra, solicitante, tipo.
- **Arquivos são só para ver**: o `.xlsx` publicado sai com todas as células bloqueadas, planilha e estrutura protegidas por senha (SHA-512, gerada na instalação e guardada só no `dados\config.json`); o `.pdf` sai junto.
- **Mesma aparência do VBA (MOD_GERAR_OP V2.4.22)**: o modelo é a própria aba da ATA da prefeitura (logo, imagens, cores), só aparecem os equipamentos com quantidade, retrato, 1 página de largura, 13 linhas na 1ª página e as demais equilibradas até 15, margens iguais, nome `NNN-AA - CLIENTE - OBRA - TIPO - MATERIAL`.
- **Saldo por contrato**: saldo = MONTANTE − (QUANT. + PREVISÃO). Na importação entram os números atuais da planilha; cada O.P. nova consome; O.P. com instalação "OK" conta em QUANT., as demais em PREVISÃO. Saldo negativo pede confirmação; zerar só avisa; códigos `0.x` não são checados; `2.1` conta no item `2`.
- **Numeração** `NNN-AA` reinicia todo ano e continua depois do histórico importado do Controle.
- **REV**: cada edição gera nova revisão (com histórico) e republica os arquivos. Cancelar devolve o saldo.

Não precisa instalar nada além do Python (só biblioteca padrão). PDF: Excel no Windows (igual ao atual) ou LibreOffice.

## Uso

1. `Importar_Legado.cmd` → informe a pasta com os `OK-*.xlsm` e o `2_Controle_...xlsm`. Os arquivos de origem são apenas lidos.
2. `Iniciar_ASCALPI_Producao.cmd` → abre `http://127.0.0.1:8765/`.
3. Em **Configuração** escolha as pastas onde os `.xlsx`/`.pdf` são publicados (padrão: `dados\Documentos`).

Linha de comando:

```
python -m ascalpi_producao --dados <pasta> importar --origem <pasta legado>
python -m ascalpi_producao --dados <pasta> servir [--porta 8765] [--abrir]
python -m ascalpi_producao --dados <pasta> documento --op 258-26 --formato pdf
```

## Pastas

| Caminho | Conteúdo |
|---|---|
| `ascalpi_producao/regras.py` | regras do VBA (nome, material, prazo, numeração, códigos, saldo) |
| `ascalpi_producao/pacote.py` | extrai a aba da ATA como modelo `.xlsx` independente, sem Excel |
| `ascalpi_producao/documento.py` | preenche o modelo, oculta linhas sem quantidade, impressão e bloqueio |
| `ascalpi_producao/pdf.py` | PDF pelo Excel (Windows) ou LibreOffice |
| `ascalpi_producao/legado.py` | importação dos livros das prefeituras e do Controle |
| `ascalpi_producao/banco.py` · `servico.py` · `servidor.py` · `web/` | banco SQLite, regras de uso, API e telas |
| `dados/` | banco, modelos e documentos (fora do git) |

## Testes

`Testar.cmd` (ou `python -m unittest discover -s tests -t .`). Os testes criam um livro sintético; não usam dados reais. Precisam de `openpyxl` só para montar e conferir as planilhas de teste.

## Diferenças conscientes em relação ao VBA

- "Hoje ..." (B2) e o dia da entrega (S6) saem como texto fixo do momento da emissão, em vez de fórmula que muda a cada abertura.
- V2/U2 também ficam bloqueados (no VBA ficavam livres).
- O botão de macro da aba some (o `.xlsx` não tem macro); o ícone do topo continua.
