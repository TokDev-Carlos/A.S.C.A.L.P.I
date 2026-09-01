# 2-Compiler

Área informacional e de ferramentas do processo de compilação Windows do ASCALPI.

## Função

A compilação para Windows é executada na máquina local de desenvolvimento. O repositório não precisa transportar o Runtime do Compiler nem reproduzir byte a byte a instalação local.

Esta área versiona somente o que for útil para compreender e executar corretamente a compilação:

- orientação do processo;
- scripts reutilizáveis;
- configuração portátil;
- definições de toolchain;
- ferramentas pequenas e úteis que façam sentido manter no Git;
- regras de entrada, verificação e handoff.

## O que permanece local

Não versionar como conteúdo normal desta área:

- `Runtime` instalado localmente;
- histórico de builds;
- diretórios de execução temporária;
- pacotes gerados;
- Inbox/Handoff transitórios;
- caches de SDK/dependências;
- binários que podem ser reconstruídos a partir da fonte.

## Fluxo lógico

O conhecimento útil herdado do fluxo anterior é:

```text
INPUT
  -> BUILD
  -> PACKAGE
  -> VERIFY
  -> HANDOFF
```

1. **Input**: identificar exatamente a fonte aprovada que será compilada;
2. **Build**: executar a compilação com toolchain conhecida na máquina local;
3. **Package**: montar a candidata Windows;
4. **Verify**: conferir integridade e testes aplicáveis;
5. **Handoff**: entregar a candidata controlada para `3-Git_Main`.

## Regra importante

Falha de código retorna para `1-Dev`. O Compiler não deve reparar silenciosamente a fonte durante a compilação.

O sucesso de um build também não significa homologação. A homologação pertence a `3-Git_Main`.
