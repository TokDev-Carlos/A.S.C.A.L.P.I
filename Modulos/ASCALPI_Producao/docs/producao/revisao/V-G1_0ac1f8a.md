# V-G1 — quarta revisão de `0ac1f8a`

**Data:** 10/10/2026  
**Revisor:** Codex  
**Veredito:** **DE ACORDO**

## Escopo

Quarta revisão independente do G1, com foco nas correções V-G1-03A, V-G1-03B e V-G1-04, regressões e comprovação red/green.

## Resultado

### Testes específicos no código corrigido

```bash
python -m unittest -v \\
  tests.test_edicao_modelo.TestEdicaoModelo.test_vg1_03a_falha_ao_promover_publicacao_nao_deixa_tmp \\
  tests.test_edicao_modelo.TestEdicaoModelo.test_vg1_03b_escrita_parcial_ao_iniciar_nao_deixa_copia \\
  tests.test_edicao_modelo.TestEdicaoModelo.test_vg1_04_validar_nao_grava_em_edicao_descartada
```

Resultado: **3/3 aprovados**.

### Suíte integral

```bash
python -m unittest discover -s tests -t . -v
```

Resultado: **102 testes aprovados em 67,818 s**, zero falhas.

### Red/green independente

Os três testes novos foram executados contra o código anterior `77cab0b`:

- V-G1-03A falhou mostrando o `.tmp` órfão;
- V-G1-03B falhou mostrando XLSX parcial e pasta residual;
- V-G1-04 falhou porque `validar()` retornou normalmente após o descarte.

Resultado anterior: **3 falhas**. No `0ac1f8a`: **3 aprovados**.

## Revisão da implementação

- `_gravar_novo()` grava em temporário ao lado do destino, promove com `os.replace` e limpa o temporário em qualquer falha.
- `iniciar()` inclui criação da pasta/cópia no bloco protegido e remove cópia/pasta parcial.
- `publicar()` inclui a promoção no bloco que desfaz arquivo novo quando a transação não conclui, preservando a versão anterior.
- `validar()` atualiza somente `estado='ABERTA'`; `rowcount == 0` vira conflito, preservando o histórico finalizado.

## Conclusão

V-G1-01, V-G1-02, V-G1-03 e V-G1-04 estão encerrados. Não encontrei regressão no escopo revisado. O G1 recebe **DE ACORDO técnico do Codex** no SHA `0ac1f8a`.

O aceite final do G1 ainda depende do teste autorizado no Windows/Excel real e da H-1 com 3–5 O.P. reais. Nenhuma integração foi realizada nesta revisão.
