# CJL System — Regras Consolidadas Ativas

> Mapa operacional. Não é append-only e não substitui o Volume Mestre. A finalidade é UNIFICAR leitura de regras equivalentes sem apagar história.

## G-01 — Governança e cumulatividade
**Origem:** R-0001→R-0017, R-0060→R-0085.  
**Atual:** R-0226, R-0231→R-0236, R-0264→R-0269.

- Release oficial nasce de baseline comprovada.
- Regra Mestra é append-only.
- Hash é necessário, mas não substitui auditoria semântica.
- Mudança incompatível exige superação declarada.
- Patch, Snapshot e validação carregam metadados de regras.
- Desenvolvimento não vira produção sem release/homologação.

## G-02 — Interface protegida
**Origem:** R-0018→R-0023, R-0097, R-0125, R-0153, R-0167, R-0174, R-0180, R-0190.  
**Atual:** R-0260.

A interface é conceito persistente. Mudança visual/funcional precisa ser intencional, auditável e não pode desaparecer por efeito colateral.

## G-03 — Dados e componentes protegidos
**Origem:** R-0024→R-0027 e correlatas.  
**Atual:** R-0257.

Banco/Data/Shared/Repo/Runtime/documentos/evidências/backups não são payload comum de patch. Migração exige backup, gate, validação e rollback.

## G-04 — Fluxo logístico
**Origem vigente:** R-0046→R-0057.

Rotas/Frota iniciam o mesmo Carregamento PLANEJADO; rota, veículo, paradas e custos pertencem ao mesmo registro. Geolocalização é normalizada e valores sem informação permanecem vazios.

## G-05 — Usuários e Mestre
**Origem:** R-0058→R-0059, R-0090, R-0195→R-0199.  
**Atual:** R-0239→R-0246, R-0263, R-0270.

- Mestre = `CJLAdmin`, perfil `ADMIN`; operações administrativas Windows também convergem para `CJLAdmin`.
- Credencial Mestre = 6 alfanuméricos + `.`.
- Usuários comuns continuam com PIN numérico 4–32.
- Credenciais ficam somente em Scrypt+salt.
- `ADMIN` legado é migrado preservando ID/hash; histórico não é reescrito.

## G-06 — Layout e Mestre Base 5
**Origem histórica:** R-0086→R-0133.  
**Atual:** R-0227→R-0230, R-0262.

- Mestre: `C:\CJL\System`.
- Histórico/recuperação: `C:\CJL\SM_Repo`.
- Launcher público: `CJL.exe`.
- Layout 5: App/Host/Runtime/Data/Shared/Repo/Updates/Logs/Temp/Docs/Dev/Export.
- Literais de layout antigo são permitidos somente em histórico/proveniência/compatibilidade declarada.

## G-07 — Host, build e diagnóstico
**Origem:** R-0134→R-0192, R-0204→R-0206, R-0220→R-0224.  
**Atual:** R-0258→R-0259.

Host/Bin só é promovido após staging, hashes, manifesto e self-tests. Falha mantém evidência e Bin anterior recuperável.

## G-08 — Remote Admin
**Atual:** R-0245→R-0255, R-0270.

- Identidade Windows administrativa e executora: `CJLAdmin`; autoridade elevada é explícita quando a ação exige.
- Tailscale = rede; OpenSSH = transporte; SMB = arquivos; RDP = desktop.
- Remote Command Contract = Protocol 7.
- Painel conhece comandos lógicos, não Task Scheduler/Broker interno.
- OPEN/FOCUS/CLOSE precisam atuar na sessão CJLAdmin correta.
- Status leve; Health/Validate profundos.
- Painel nativo, instalável, responsivo e com log humano.

## G-09 — Regras históricas de patch
**Origem:** R-0152, R-0158, R-0173, R-0179, R-0189, R-0207, R-0209, R-0225 e regras de aceite específicas relacionadas.  
**Atual:** R-0261.

Essas linhas continuam como prova do escopo das releases antigas, mas não devem ser usadas como versão corrente do produto.


## G-10 — Versionamento único da release
**Atual:** R-0271→R-0273, R-0283.

- Versão pública: `B.EE.II.SSS`.
- Fonte de verdade: componentes BA/ES/IN/SE + build + compat_sequence.
- Alias `ES.IN.SE` existe somente para handshake legado e deve ser derivado/validado.
- Nenhuma tela, log, relatório ou novo manifesto pode inventar versão independente.

## G-11 — Snapshot e classes de dados
**Atual:** R-0274→R-0280, R-0284→R-0285.

- **Dados do Sistema:** fonte, configuração técnica, regras, schema/contratos, templates, manifests, documentação corrente e logs técnicos da release.
- **Dados Operacionais de Usuários:** banco com linhas, registros de negócio, anexos/evidências, documentos gerados, Shared/Repo operacional, credenciais, caches e estado local.
- Snapshot inclui a primeira classe e exclui a segunda.
- `Logs/System` é técnico e snapshotável; logs de atividade/negócio não são.

## G-12 — Compatibilidade de estação
**Atual:** R-0281→R-0283.

A estação lê componentes e compatibilidade no nível JSON correto, compara versão/compat/schema/runtime e apresenta o motivo real do bloqueio. Igualdade de release e piso não pode produzir bloqueio falso.

## MAIN / DEV — contrato ativo

- **R-0286→R-0296**: MAIN é produção; DEV é laboratório isolado; patches são root-relative e o mesmo ZIP/SHA aprovado em DEV é o único pacote aceito na MAIN.
- DEV: `C:\.Dev CJL\Sistema_Dev`; share administrativa: `.Dev CJL$`.
- Dados operacionais de produção não são copiados para DEV.

