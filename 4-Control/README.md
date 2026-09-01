# ASCALPI Control Center

Revisão visual: PROFESSIONAL R4  
Data/hora: 30/08/2026 21:22 -03:00  
Timezone: America/Sao_Paulo

Central local de operações para supervisão dos ambientes CJL, governança documental, evidências e acessos operacionais.

## Entrada

```text
INICIAR-CJL-CONTROL.vbs
```

## Arquitetura ativa

```text
INICIAR-CJL-CONTROL.vbs
  -> ASCALPI-Control-Launcher.ps1
  -> Server/ASCALPI-Control-Server.ps1
  -> UI/index.html
  -> UI/app.js
```

- Janela de aplicativo maximizada.
- Moldura e barra de título nativas.
- Sem aba/barra de endereço.
- Interface organizada por operação e governança.
- Diagnóstico consolidado com estados em linguagem profissional.
- Ações e transições discretas em JavaScript.
- Backend operacional em PowerShell 5.1.
- Backend vinculado somente a `127.0.0.1`.
- Escrita no GitHub e em produção permanece bloqueada.

## Explorer em foco

Ações de abrir pasta não executam apenas `explorer.exe`.

Elas:
1. procuram uma janela existente naquela pasta;
2. restauram a janela se estiver minimizada;
3. trazem a janela ao topo e tentam transferir foco;
4. se não existir, abrem o Explorer;
5. aguardam a janela aparecer e tentam trazê-la ao foco.

## Linux

O mecanismo foi reconstruído diretamente a partir da implementação preservada em:

```text
Legacy/CJL-Control.ps1
```

Comando operacional:

```text
wsl.exe -d Ubuntu-24.04 -- bash "/mnt/c/.Dev CJL/1-Dev/INICIAR-CJL-LINUX.sh"
```

## Segurança

```text
Compiler execution = PAUSED
GitHub write       = NO
Production write   = NO
```

## Preservação

- `Documentation/`: não alterado.
- `Legacy/`: preservado.
- R2 rejeitada: não utilizada como base.

Consulte `PATCH_HISTORY.md` para o histórico acumulativo.
