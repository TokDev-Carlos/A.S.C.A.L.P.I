# CJL System — Separação Definitiva — Dados do Sistema × Dados Operacionais

## Versão da política

`CJL_DATA_POLICY_V1` — regida por R-0274→R-0280 e R-0285.

## O que entra

- `App/`: código, configurações técnicas, templates e contratos do produto;
- `Host/Bridge/` e fontes `Dev/Host/` (não `Host/Bin`);
- ferramentas `Dev/Tools/`;
- `Docs/`, incluindo a Regra Mestra permanente;
- `Updates/State/` e scripts do updater;
- `Logs/System/`: **somente histórico técnico da release corrente**;
- marcadores/launcher públicos e metadados sem segredo;
- metadados de schema, regras, versão, build, compat e Master ID.

## O que não entra

- `Data/`: banco e registros operacionais;
- `Shared/`: anexos/documentos/evidências compartilhados;
- `Repo/`: repositório operacional;
- `Export/`, `Temp/`;
- `Runtime/` e `Host/Bin/` (representados por integridade/contratos, não transportados);
- credenciais, chaves privadas e estado local `%LOCALAPPDATA%`/`%ProgramData%`;
- logs/auditoria de atividade do usuário ou conteúdo de negócio.

## Regra central

**Snapshot reproduz o SISTEMA; não copia a OPERAÇÃO.** A estrutura do banco é provada por `schema_version` + hash do `SCHEMA` em `App/Core/db.py`, nunca por exportação das linhas reais.
