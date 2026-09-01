# WSL

Área de conteúdo portátil relacionado ao ambiente Linux/WSL usado no desenvolvimento do ASCALPI.

## Função

Manter scripts, configuração, estrutura e outros arquivos Linux que façam sentido reconstruir ou compartilhar pelo Git.

A distribuição utilizada atualmente no ambiente de desenvolvimento é `Ubuntu-24.04`.

O fluxo de desenvolvimento Linux é acionado a partir de `1-Dev`, atualmente por:

```text
1-Dev/INICIAR-CJL-LINUX.sh
```

## O que pode ser versionado

- scripts Linux;
- arquivos de configuração portáveis;
- estrutura necessária ao ambiente de desenvolvimento;
- orientação de bootstrap/reconstrução;
- conteúdo técnico que não dependa da identidade física da máquina.

## O que permanece local

Nunca versionar:

- `ext4.vhdx`;
- `.vhd`, `.vhdx`, `.qcow2`, `.img` ou discos equivalentes;
- estado interno completo da distribuição;
- caches;
- credenciais;
- informações privadas do usuário;
- estado Docker/containers quando for apenas materialização local.

O Git deve permitir reconstruir o ambiente; não deve clonar o disco físico da máquina.
