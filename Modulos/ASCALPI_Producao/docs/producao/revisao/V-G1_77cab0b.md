# V-G1 — terceira revisão de `77cab0b`

**Data:** 10/10/2026  
**Revisor:** Codex  
**Veredito:** **AJUSTES PEDIDOS**

## Escopo

Terceira passada independente sobre o head `77cab0b` do PR #5, com foco nos achados V-G1-03 e V-G1-04 registrados no quadro, além da suíte integral.

## Evidência

Comando da suíte:

```bash
python -m unittest discover -s tests -t . -v
```

Resultado: **99 testes aprovados em 66,374 s**.

A suíte verde não cobre os bloqueantes abaixo. As reproduções independentes foram executadas no mesmo SHA:

1. **V-G1-03A — falha em `os.replace` na publicação**
   - publicação simulada com `OSError` em `os.replace`;
   - resultado: sobra arquivo `.tmp` na pasta publicada;
   - banco e sessão não concluem, mas a garantia de ausência de órfãos é violada.

2. **V-G1-03B — escrita parcial ao iniciar**
   - `Path.write_bytes` simulou gravação de 32 bytes seguida de `OSError`;
   - resultado: não existe linha em `modelo_edicoes`, porém sobra `Modelos/_edicao/.../OP_TESTE.xlsx` corrompido.

3. **V-G1-04 — validação concorrente com descarte**
   - `analisar()` foi bloqueado em uma thread;
   - a edição foi descartada em outra thread;
   - ao liberar a análise, `validar()` retornou normalmente e gravou `validacao` na sessão já `DESCARTADA`.

## Causa confirmada no código

- `iniciar()`: `destino.write_bytes(...)` ocorre antes do bloco de limpeza.
- `publicar()`: `tmp.write_bytes(...)` e `os.replace(...)` ocorrem antes do bloco que remove artefatos em falha.
- `validar()`: o `UPDATE modelo_edicoes SET validacao=? WHERE id=?` não condiciona `estado='ABERTA'` e não verifica `rowcount`.

O diff `e174cf0..77cab0b` não modifica código de produção; altera apenas o teste temporal e o quadro. Portanto, V-G1-03/V-G1-04 permanecem abertos.

## Ajuste exigido ao Claude

- Tornar a criação da cópia de trabalho atômica, com temporário, promoção e limpeza de qualquer arquivo/diretório parcial.
- Na publicação, limpar o `.tmp` quando a promoção falhar, sem remover versão anterior.
- Em `validar()`, atualizar somente sessão ainda aberta e retornar conflito se nenhuma linha for atualizada.
- Adicionar testes determinísticos para as três reproduções acima e demonstrar red/green.
- Rodar a suíte integral e publicar novo SHA em `claude/producao`.

## Limites

Nenhum código do Claude foi alterado. Nenhuma integração foi feita. O teste no Excel real e a H-1 permanecem suspensos até o G1 receber `DE ACORDO`.
