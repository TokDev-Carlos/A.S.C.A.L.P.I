# ORG-LOCAL-01 — Consolidação Windows ⇄ GitHub (10/10/2026)

**Responsável pela execução e verificação:** Codex/ChatGPT, sob ordem expressa do Admin.  
**Estado:** consolidação física concluída, clone local verificado e servidor testado; funcionalidade G1 **não** está na branch integrada até Claude publicar a entrega aceita.  
**SHA testado localmente:** `e4af66b889d33149daa747ae939941ab18f00c4d` de `modulo/producao-op`.

## 1. Regra de negócio e classificação do ambiente — decisão do Admin

- **O ASCALPI instalado no computador é integralmente um ambiente de desenvolvimento/testes/homologação.** As aproximadamente 260 O.P. mencionadas pelo Admin não são emissões operacionais da empresa. A base SQLite efetivamente auditada em 10/10 tinha **234 O.P.** (contagem da instalação existente naquele instante, não afirmação sobre toda a história de testes).
- **A operação real continua no legado VBA localizado no servidor da empresa**, separada do projeto Windows e do GitHub. O ASCALPI substituirá o legado futuramente, mas **nenhuma operação atual neste ambiente deve ser chamada de produção operacional**.
- A nomenclatura `dados reais` e orientações que imponham uma instalação extra para proteger a operação da empresa estão desatualizadas; corrigir isso nos runbooks e regras. **Os dados de homologação continuam privados/não versionados**, pois podem conter nomes de clientes, modelos e imagens. Não enviar bancos, planilhas ou evidências identificáveis ao GitHub público.
- Distinguir **homologação local** de **produção empresarial**. Preservar dados antes de operações destrutivas/alterações de esquema por integridade dos testes e rollback, não por risco ao legado no servidor.
- Evitar pastas isoladas para cada teste; **um clone Git funcional, uma instalação local e uma base oficial de homologação**, com arquivos históricos em um único arquivo externo.

## 2. Estrutura após a reorganização (confirmada no Windows)

```text
D:\Programas\ASCALPI_Project\           <- RAIZ ÚNICA do clone Git
├── .git\                             <- antes dentro de _git_tag_clone
├── .gitattributes / .gitignore
├── AGENTS.md / README.md
├── docs\producao\
└── Modulos\ASCALPI_Producao\
    ├── AGENTS.md / REGRAS_CENTRAIS.md / QUADRO_TAREFAS.md
    ├── ascalpi_producao\
    ├── tests\
    ├── ferramentas\
    ├── Iniciar_ASCALPI_Producao.cmd
    └── dados\                        <- UMA base canônica local, ignorada pelo Git

D:\Programas\ASCALPI_Local_Archive\consolidacao_20261010\
├── Modulos_preexistentes\            <- instalação anterior + backup original dos dados
├── docs_preexistentes\               <- docs locais anteriores
├── Legacy_modules\                  <- diretórios legados locais preservados
├── ASCALPI_Teste_G1_20261010_1452\  <- código, dados e evidências G1 preservados
├── migracao.log / scripts de conferência
└── manifesto.json
```

A pasta independente `D:\Programas\ASCALPI_Teste_G1_20261010_1452` e o clone aninhado `_git_tag_clone` foram removidos **dos locais anteriores após arquivamento/consolidação**, sem destruir a cópia de segurança. Não existem dados da operação VBA do servidor nesse processo.

**Base de referência:** `D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao\dados`, selecionada a partir da instalação anterior (234 O.P.), com cópia preservada no arquivo. A base da antiga validação G1 continha 233 O.P. e foi arquivada separadamente; uma terceira `app\dados` da antiga pasta G1 era uma base vazia e não foi escolhida.

## 3. Fluxo obrigatório para Claude e Codex

1. **Nuvem primeiro:** Claude implementa em `claude/producao`; Codex revisa código, regras e suíte no GitHub; registra resultado no `QUADRO_TAREFAS.md` antes do teste local.
2. **Git versionado:** após revisão, a entrega passa pela hierarquia da `REGRAS_CENTRAIS.md`. O clone local acompanha a **mesma branch e o mesmo SHA** explicitamente escolhido no GitHub; por padrão, a branch integrada `modulo/producao-op`. Não integrar `Dev-Work` ou `main` sem ordem do Admin.
3. **Windows/Excel depois:** validar a tela funcional, modelos e O.P. na **mesma instalação** `D:\Programas\ASCALPI_Project`, usando o Microsoft Excel para abertura/edição e PDF. Não executar testes de escrita sobre o servidor legado VBA.
4. **Fechamento:** registrar SHA, evidências, resultado, pendências e próxima ação no GitHub. Falha local implica correção na branch executora e nova revisão, não criação de mais uma cópia de sistema.
5. **Backup pontual:** antes de alterações de esquema ou operações destrutivas, preservar um snapshot recuperável da base de homologação no arquivo local. **Não sincronizar `dados\` ou arquivos de backup no GitHub**.
6. Evitar iniciar duas instâncias na porta 8765; usar o `Iniciar_ASCALPI_Producao.cmd` do módulo presente **na raiz clonada**, que aponta `--dados` para `%~dp0dados`. Descontinuar o roteiro antigo `Atualizar_Copia_Local.cmd` que copia código para uma segunda instalação (Claude deve adaptar o documento/launcher numa entrega revisada, não executá-lo sem necessidade).

## 4. Verificações realmente executadas

- Git remoto: `https://github.com/TokDev-Carlos/A.S.C.A.L.P.I.git`. Clone principal: `modulo/producao-op`, commit `e4af66b889d33149daa747ae939941ab18f00c4d`, sem mudanças locais versionadas; `git status --porcelain=v1 --untracked-files=all` limpo no fim da migração.
- `dados\` ignorado pelo Git (`git check-ignore` conferido). Base: **234 O.P., 45 modelos, 27 prefeituras**.
- A antiga base G1 e suas evidências: **1.685 arquivos, 188.338.456 bytes** antes e depois do arquivamento, com contagem/bytes idênticos; 233 O.P. na base G1 arquivada.
- Processos antigos: havia **duas instâncias ASCALPI usando a porta 8765**, uma apontava para uma `app\dados` vazia. Os dois servidores e os inicializadores CMD antigos foram encerrados para desbloquear e consolidar as pastas; nenhum processo do servidor VBA empresarial foi tocado.
- Suíte no clone final: `python -m unittest discover -s tests -t .` → **78/78 OK**, exit 0, com avisos `ResourceWarning` não bloqueantes.
- Smoke funcional em porta temporária **18765**: GUI `GET /` HTTP 200; API `/api/modelos?todos=1` (45) e `/api/prefeituras` (27), além de `/api/config`, OK. Base canônica continuou com 234 O.P. Servidor temporário encerrado ao fim.
- Houve bloqueio de renomeação de diretórios por processos Windows ainda abertos. Resolvido por **cópia preservada/arquivamento e encerramento dos inicializadores antigos**, sem perda de dados. Evidência local: `migracao.log`.

## 5. Pendências reais e trabalho do Claude

**MEL-G1-01 (prioritária):** embora o Admin tenha aceitado o G1, em 10/10 a branch integrada `modulo/producao-op` (`e4af66b`) ainda contém **G0** no `app.js`; nela **não há** `EDITAR NO EXCEL`, `COMEÇAR EDIÇÃO` nem `edicao_modelo_excel`. Esses controles estão na executora `claude/producao`, que já contém também o **G2 em revisão** (não promover automaticamente sem V-G2/aceite). Depois do merge/autorização apropriados e nova sincronização, repetir o teste de ponta a ponta com `O.P-ATA-ANGRA-MOB` ou `O.P-ATA-ANGRA-PLACAS`: selecionar o **modelo**, abrir cópia editável no Excel, salvar, validar alterações, publicar nova versão e verificar a O.P. antiga. **Não confundir edição de modelo com desbloqueio manual do XLSX emitido**, cuja imutabilidade é requisito.

**V-G2:** código do G2 no Claude em `e800f30` sob revisão; não inclui nesta migração qualquer aceite funcional do G2.

**Documentos desatualizados:** corrigir em `CONTINUAR.md`, `README.md`, `PLANO_AJUSTES.md`, `PLANO_POS_BASELINE_*` e orientações aplicáveis: ambiente Windows não é operação real; não exigir novas pastas de instalação G1; referências à publicação/produção real devem apontar apenas ao legado VBA do servidor. O formulário H-1 deve mencionar **O.P. de homologação** comparadas ao padrão legado sem manipular o ambiente empresarial.

**Integração:** o Admin aprovou reorganização física e espelhamento; **não ordenou merge em `Dev-Work`/`main`**. Cada agente permanece responsável por sua branch.

## 6. Comandos de operação

```bat
git -C "D:\Programas\ASCALPI_Project" status -sb
git -C "D:\Programas\ASCALPI_Project" fetch origin --prune
git -C "D:\Programas\ASCALPI_Project" pull --ff-only origin modulo/producao-op

cd /d "D:\Programas\ASCALPI_Project\Modulos\ASCALPI_Producao"
python -m unittest discover -s tests -t .
Iniciar_ASCALPI_Producao.cmd
```

Antes de usar `pull --ff-only`, verificar que a branch atual é `modulo/producao-op` e não há alterações versionadas locais. Registrar SHA antes/depois; `dados\` não faz parte do clone Git e é mantido durante sincronização. A revisão em nuvem precede novas atualizações de código local.
