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
## Git e branches oficiais

O módulo Git do Painel usa a caixa local `C:\.Dev CJL\Git\Repository\A.S.C.A.L.P.I` como repositório operacional. `1-Dev` e `3-Git_Main` não são mais procurados como raízes Git principais.

Nesta revisão, Git permanece em modo **somente leitura** no Painel:

```text
GitHub write = NO
Force push   = NO
main write   = NO
```

### Dev-Work

Representa o ambiente portátil de engenharia e pode conter:

- `1-Dev`;
- `2-Compiler` informacional/ferramentas úteis, sem Runtime local;
- `3-Git_Main`, incluindo o Runtime Windows homologável;
- `4-Control`;
- `5-Docs`;
- conteúdo portátil de `WSL`.

### main

A linha homologada é formada somente por:

- `3-Git_Main`;
- `5-Docs`.

Promover `main` não significa fazer merge integral da `Dev-Work`.

### Informação útil

O Painel deve encaminhar informação durável para os documentos já existentes, sem criar documentação paralela:

- função de pasta -> README existente da área;
- regra operacional -> `5-Docs\Execution_Contract.md`;
- memória durável para IA -> `5-Docs\Souvenir.md`;
- falha ou risco reutilizável -> `5-Docs\Black_Book.md`;
- solução técnica comprovada -> `5-Docs\White_Book.md`;
- ativo técnico útil -> área técnica correspondente;
- logs, receipts, checkpoints e evidência transitória -> `C:\.Dev CJL\Git`, somente local;
- informação sem valor futuro -> descartar.

A configuração executável destas regras fica em `Config\control.json`.
