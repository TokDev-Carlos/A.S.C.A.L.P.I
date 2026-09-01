# CJL SYSTEM — ÍNDICE MESTRE DE REGRAS

## Estado atual

- Produto corrente: **CJL System**
- Linha histórica preservada: **SIS LOGIS → CJL System**
- Última regra: **R-0296**
- Próximo ID: **R-0297**
- Volume ativo: **001**
- Limite por volume: **500 regras**
- Aviso preventivo: **450 regras**
- Regras atuais no Volume: **296**
- SHA-256 físico do Volume: `4c795940ca3dedf4bfd97b05cc81bd23c854d29f200a6eedc747b66f2f0a3d10`
- SHA-256 lógico das linhas: `4c795940ca3dedf4bfd97b05cc81bd23c854d29f200a6eedc747b66f2f0a3d10`
- Regra de imutabilidade: linhas publicadas nunca são removidas, renumeradas ou reescritas.

## Mapa dos volumes

| Volume | Intervalo reservado | Intervalo ocupado | Estado | Arquivo | SHA-256 de fechamento |
|---|---|---|---|---|---|
| 001 | R-0001 → R-0500 | R-0001 → R-0296 | ATIVO | `SIS_LOGIS_REGRAS_VOLUME_001.md` | — |
| 002 | R-0501 → R-1000 | — | FUTURO | `SIS_LOGIS_REGRAS_VOLUME_002.md` | — |

## Mapa conceitual corrente

| Domínio | Regras canônicas |
|---|---|
| Governança, patches e cumulatividade | R-0001→R-0017; R-0060→R-0085; R-0231→R-0238; R-0264→R-0269 |
| Versionamento BA/ES/IN/SE | R-0226; R-0271→R-0273; R-0283 |
| Snapshot e separação de dados | R-0274→R-0280; R-0284→R-0285 |
| Estações e compatibilidade | R-0281→R-0283 |
| MAIN/DEV e promoção de patch | R-0286→R-0296 |
| Usuários e identidade administrativa | R-0239→R-0246; R-0270 |
| Remote Admin | R-0247→R-0255; R-0293 |
| Host/build/diagnóstico | R-0258→R-0259; R-0294→R-0296 |

## Superações formais

- `R-0088` parcialmente superada por `R-0195`.
- `R-0123` parcialmente superada por `R-0148`.
- `R-0001` parcialmente superada por `R-0226` e R-0271 quanto ao versionamento corrente.
- `R-0086` e `R-0128` superadas por `R-0228` quanto ao launcher público corrente.
- `R-0058` parcialmente superada por `R-0240` exclusivamente para a credencial Mestre.
- Declarações ativas de `remote_command_contract_v1` superadas por R-0247 / Protocol 7.

## Regra de unificação

`CJL_REGRAS_CONSOLIDADAS_ATIVAS.md` é mapa operacional curto; nunca substitui nem reescreve este Volume append-only.
