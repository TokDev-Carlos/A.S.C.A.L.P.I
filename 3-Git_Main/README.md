# 3-Git_Main

Corpo Windows controlado do ASCALPI para teste e homologação.

## Função

Receber uma candidata Windows produzida a partir do desenvolvimento aprovado e validar o sistema antes de qualquer promoção para `main` ou uso operacional.

Esta área não é fonte experimental. Alterações de código devem voltar para `1-Dev`, ser testadas e passar novamente pelo fluxo de compilação.

## Conteúdo principal

`System` representa o corpo portátil/executável controlado da candidata Windows.

Diferentemente de `1-Dev` e `2-Compiler`, esta é a única área da `Dev-Work` que deve conter o Runtime completo necessário ao sistema, incluindo quando aplicável:

```text
System/Runtime
System/Host/Bin
System/CJL.exe
```

Binários grandes podem ser transportados por Git LFS.

## Estado local que não pertence ao repositório

Não usar esta área versionada para armazenar:

- UserData real;
- dados de clientes, obras ou operação;
- credenciais;
- logs mutáveis;
- exportações temporárias;
- caches;
- evidências locais transitórias;
- rollback local;
- bancos operacionais preenchidos.

## Homologação

O fluxo conceitual preservado é:

```text
LOAD
  -> RUN
  -> TEST
  -> APPROVE
  -> PROMOTE
```

A promoção nunca é consequência automática de um build bem-sucedido. Ela exige candidata identificada, testes aplicáveis e aprovação do fluxo de controle.

## Relação com `main`

Quando o fluxo de promoção estiver implantado, o conteúdo homologado desta área, junto com `5-Docs`, formará a linha oficial `main` do ASCALPI.
