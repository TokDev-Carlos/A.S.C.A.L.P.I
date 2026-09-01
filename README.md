# A.S.C.A.L.P.I

Repositório oficial do ASCALPI.

Este repositório contém a representação versionada e portátil do ambiente de engenharia do sistema. O ambiente físico de desenvolvimento continua fora do GitHub, em `C:\.Dev CJL`, e pode conter Runtime, dados de máquina, caches, logs, credenciais e outros estados locais que não pertencem ao repositório.

## Branches

### `Dev-Work`

Representa o ambiente de desenvolvimento portátil do ASCALPI.

Pode conter:

- `1-Dev`: código, scripts, configuração e engenharia de desenvolvimento;
- `2-Compiler`: orientação, scripts, configuração e ferramentas úteis do processo de compilação local;
- `3-Git_Main`: corpo Windows controlado, incluindo o Runtime completo necessário à homologação;
- `4-Control`: painel de controle e sua implementação;
- `5-Docs`: documentos principais do sistema;
- `WSL`: conteúdo portátil relacionado ao ambiente Linux/WSL.

Não representa a identidade física da máquina. `Git`, discos WSL, credenciais, dados operacionais, caches e estado transitório permanecem locais.

### `main`

A `main` é a linha homologada do ASCALPI. Quando o fluxo de promoção for implantado, ela será formada pelo conteúdo aprovado de:

- `3-Git_Main`;
- `5-Docs`.

Não é área de desenvolvimento direto.

## Guia das áreas

| Área | Função |
|---|---|
| `1-Dev` | Desenvolvimento ativo, código, scripts, configuração e validação Linux. Não carrega Runtime completo. |
| `2-Compiler` | Referência e ferramentas úteis para compilar localmente a versão Windows. Runtime, builds e histórico de compilação permanecem locais. |
| `3-Git_Main` | Corpo Windows controlado para teste/homologação. É a única área que carrega o Runtime completo. |
| `4-Control` | Painel que futuramente controlará gates, patches, Git, aprovação e rollback. |
| `5-Docs` | Documentos principais e duráveis do ASCALPI. |
| `WSL` | Scripts, configuração e conteúdo Linux portátil. Nunca contém o disco virtual da distribuição. |
| `Git` | Caixa de correio local entre ambiente e GitHub. Não é versionada. |

## Política de documentação

A documentação oficial deve permanecer pequena e autoritativa.

Regras:

1. não criar documentos novos apenas para registrar cada execução, decisão ou alteração;
2. não criar cópias `V1`, `V2`, `R1`, `R2` de um mesmo guia para simular histórico;
3. o Git já preserva versões, diffs, commits, autores e datas;
4. README e guias informacionais são estáticos e só devem mudar quando a função real da área mudar;
5. logs, receipts, checkpoints, auditorias, manifests operacionais e identidade de máquina são estado/evidência, não documentação oficial;
6. documentos principais permanecem em `5-Docs` e não devem ser substituídos por documentos paralelos concorrentes.

## Documentos principais

`5-Docs` contém atualmente:

- `Execution_Contract.md`: regras e contratos operacionais do sistema;
- `Souvenir.md`: memória/orientação durável para leitura por IA e agentes;
- `Black_Book.md`: conhecimento de falhas, riscos e ocorrências relevantes;
- `White_Book.md`: conhecimento técnico comprovado e reutilizável.

## Regra de leitura

Antes de alterar o ASCALPI:

1. identificar repositório, branch e commit;
2. ler este README;
3. ler o README da área afetada;
4. consultar `5-Docs/Execution_Contract.md` quando a operação envolver gates, integração, publicação ou produção;
5. consultar Black/White Book somente quando o histórico técnico for relevante;
6. executar apenas o fluxo correspondente à área.

## Limites de segurança

O repositório não é armazenamento para:

- UserData operacional;
- credenciais, tokens ou chaves;
- identificação privada da máquina;
- WSL `.vhdx` ou imagens equivalentes;
- caches e temporários;
- bancos operacionais com dados reais;
- logs locais de execução;
- histórico transitório de builds.

O estado físico da máquina permanece sob `C:\.Dev CJL\Git` ou nas áreas locais apropriadas e não altera a autoridade do código versionado.
