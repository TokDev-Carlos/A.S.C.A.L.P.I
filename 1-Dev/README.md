# 1-Dev

Área de desenvolvimento ativo do ASCALPI.

## Função

Concentrar código, scripts, configuração, ferramentas de engenharia e suporte necessário para desenvolver e validar o sistema antes de uma candidata Windows ser preparada.

O desenvolvimento Linux/WSL parte desta área. O launcher atual é:

```text
1-Dev/INICIAR-CJL-LINUX.sh
```

## Conteúdo esperado

- fonte do sistema;
- scripts de desenvolvimento;
- configuração portátil;
- contratos e estruturas necessárias ao código;
- ferramentas reutilizáveis;
- material técnico auxiliar do desenvolvimento quando realmente necessário.

`SM_Repo` é material auxiliar de engenharia e histórico técnico; não é repositório remoto independente nem autoridade paralela ao GitHub.

## Runtime

`1-Dev` não deve carregar um Runtime Windows completo.

Ficam fora da representação versionada desta área:

- `System/Runtime`;
- `System/Host/Bin` compilado;
- `System/CJL.exe` compilado.

O Runtime completo pertence a `3-Git_Main`.

## Permitido

- desenvolvimento controlado;
- testes com dados sintéticos ou estruturas próprias para teste;
- validação Linux;
- correções e evolução de código;
- geração de candidata para o estágio seguinte.

## Não permitido

- dados operacionais reais;
- credenciais;
- caches de workstation;
- tratar `3-Git_Main/System` como fonte experimental;
- usar esta área como armazenamento de Runtime ou builds Windows finais.

## Saída

Quando uma alteração estiver pronta, ela deve seguir o fluxo de revisão/teste definido para o projeto. A compilação Windows acontece localmente na máquina de desenvolvimento e o resultado controlado é materializado em `3-Git_Main`.
