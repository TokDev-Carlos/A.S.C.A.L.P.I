# Roteiro funcional G1 — edição dos modelos de Angra dos Reis (Windows + Microsoft Excel)

**Quem executa:** Admin (`ToKDev-Carlos`) e/ou Codex no PC, com Microsoft Excel. **Onde:** a instalação única `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao` (homologação; nada aqui é a operação da empresa). **Não** usar WSL nem pasta separada: o aceite só vale no Windows. **Modelos:** `O.P-ATA-ANGRA-MOB` e `O.P-ATA-ANGRA-PLACAS`.

Anote para cada passo: **OK** / **FALHOU** + o que apareceu na tela (texto do aviso). Fotos de tela e arquivos com dados de cliente ficam **só no PC** (não publicar no GitHub); no quadro, registrar só o resultado.

## 0. Preparar (uma vez)

1. Pegar no `QUADRO_TAREFAS.md` o **SHA exato** autorizado para o teste (o merge do G1 no `modulo/producao-op`). Só esse SHA é aceito: nem um anterior, nem um mais novo.
2. **Fechar o ASCALPI** (a janela do servidor). A sincronização recusa se a porta 8765 estiver em uso.
3. **Primeira vez** (o clone ainda está no G0 e não tem o sincronizador): rodar a cópia do sincronizador **tirada do próprio commit autorizado**, sem checkout e sem criar outra instalação. Ela confere o SHA, **guarda a cópia de `dados` antes de trazer o código** (a 1ª abertura do G1 migra o banco para o esquema 7) e só então atualiza:
   ```bat
   git -C D:\Programas\ASCALPI_Project fetch origin --prune
   git -C D:\Programas\ASCALPI_Project show <SHA>:Modulos/ASCALPI_Producao/ferramentas/sincronizar.py > "%TEMP%\sincronizar.py"
   "C:\.Dev CJL\3-Git_Main\System\Runtime\Python\python.exe" "%TEMP%\sincronizar.py" --raiz "D:\Programas\ASCALPI_Project" --sha <SHA>
   ```
   Use o **Python instalado do projeto** (o mesmo dos `.cmd`), não `python` do PATH: no Windows ele pode ser o atalho da Microsoft Store (erro 9009). Se esse caminho não existir, use `py -3` no lugar.
   **Das próximas vezes:** `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao\Sincronizar_ASCALPI.cmd <SHA>`.
   - Esperado: `AUTORIZADO: <sha> = origin/modulo/producao-op`, `CÓPIA DE DADOS: …\snapshots_dados\dados_<data>_<sha antigo> (N ARQUIVOS CONFERIDOS)` e `SINCRONIZADO: <antes> -> <SHA>`.
   - Se aparecer `RECUSADO:` ou `FALHA:`, **não testar**: anotar a mensagem no quadro. `RECUSADO` significa que nada foi alterado.
   - Conferência: `git -C D:\Programas\ASCALPI_Project rev-parse --short HEAD` deve mostrar o SHA autorizado.
4. `Testar.cmd` → anotar a linha "Ran N tests … OK".
5. `Iniciar_ASCALPI_Producao.cmd` → o navegador abre em `http://127.0.0.1:8765`. Usar **esse endereço** (ou `localhost`); nome do PC ou outro nome de domínio é recusado.
   - Na 1ª abertura o banco migra do esquema 6 para o 7 sozinho (sem perder O.P.).
6. Painel → conferir que as **234 O.P.** continuam lá.

## 1. Ligar a função

7. **Configuração** → marcar **EDITAR MODELOS NO EXCEL (CÓPIA DE TRABALHO → NOVA VERSÃO)** → **SALVAR CONFIGURAÇÃO**. Esperado: "CONFIGURAÇÃO SALVA."
8. Ainda em Configuração, conferir **PUBLICAR AUTOMATICAMENTE** e as pastas de publicação: são da homologação (`dados\Documentos\…` por padrão). Ajuste se quiser; não há risco para o legado.

## 2. Antes de editar: uma O.P. "antiga" de cada modelo

9. **Nova O.P.** → Angra dos Reis → `O.P-ATA-ANGRA-MOB` → 2 ou 3 equipamentos com quantidade → **Gerar O.P.** Anotar o número (O.P. **A**). Baixar o **PDF** e o **XLSX** de A e guardar no PC.
10. Repetir com `O.P-ATA-ANGRA-PLACAS` → O.P. **B**, PDF/XLSX guardados.

## 3. Editar `O.P-ATA-ANGRA-MOB`

11. **Modelos** → card `O.P-ATA-ANGRA-MOB` → **EDITAR NO EXCEL** → **COMEÇAR EDIÇÃO**. Esperado: a cópia de trabalho é criada (arquivo em `dados\Modelos\_edicao\…`).
12. **ABRIR NO EXCEL**. Esperado: o Microsoft Excel abre a cópia, **editável** (sem senha).
13. No Excel: (a) mudar o **nome** de um equipamento (coluna B); (b) mudar a **altura** de uma linha de equipamento; (c) trocar a **foto** de um equipamento. **Salvar** (Ctrl+B, mesmo nome, formato .xlsx) e **fechar** o Excel.
14. **VALIDAR ALTERAÇÕES**. Esperado: a prévia mostra **exatamente** as três mudanças (NOME linha x, ALTURA linha y, FOTO linha z), **nenhuma** diferença a mais, nenhum erro.
    - Extra: repetir a validação **com o Excel ainda aberto** e anotar o que aparece.
15. **PUBLICAR NOVA VERSÃO** com motivo (ex.: "teste G1 Angra MOB"). Esperado: "NOVA VERSÃO DO MODELO PUBLICADA."; a próxima abertura de EDITAR NO EXCEL mostra a versão no histórico.

## 4. Conferir as garantias

16. Abrir a O.P. **A** (antiga) → **Ver PDF** / **Baixar XLSX**. Esperado: **igual** ao guardado no passo 9 (nome, altura e foto **antigos**). A O.P. já emitida continua no arquivo do modelo da época.
17. **Nova O.P.** com `O.P-ATA-ANGRA-MOB` → O.P. **C**. Esperado: PDF/XLSX com o **nome, a altura e a foto novos**.
18. **Duplicar** ou **Editar** a O.P. A (nova REV): anotar qual modelo o documento usa (esperado: continua o da emissão de A).

## 5. Editar `O.P-ATA-ANGRA-PLACAS` (abrir e salvar sem mudar)

19. **EDITAR NO EXCEL** → **COMEÇAR EDIÇÃO** → **ABRIR NO EXCEL** → no Excel, **só salvar** e fechar.
20. **VALIDAR ALTERAÇÕES**. Esperado: "NENHUMA ALTERAÇÃO EM RELAÇÃO AO MODELO PUBLICADO." (nenhuma diferença falsa de altura/código).
21. **DESCARTAR**. Esperado: a edição fecha; a cópia continua guardada em `dados\Modelos\_edicao\`. A O.P. B e o modelo continuam iguais.

## 6. Robustez (rápido)

22. Com o ASCALPI aberto, rodar `Iniciar_ASCALPI_Producao.cmd` de novo. Esperado: aviso "JÁ EXISTE UM PROGRAMA USANDO A PORTA 8765…" e o navegador abre no sistema já aberto; **não** sobe um 2º servidor.
23. Começar uma edição, e em **outra aba** do navegador clicar **COMEÇAR EDIÇÃO** no mesmo modelo. Esperado: a mesma edição (não cria duas).

## 7. Registrar

24. No `QUADRO_TAREFAS.md` (ou para o Codex registrar): SHA testado, "Ran N tests", resultado de cada passo (OK/FALHOU + texto), versão do Excel. **Sem** anexar arquivos de cliente.
25. Se algo falhar: anotar o passo e o texto exato do aviso; o Claude corrige na `claude/producao`, o Codex revisa e o teste se repete no mesmo roteiro (sem criar outra pasta).
