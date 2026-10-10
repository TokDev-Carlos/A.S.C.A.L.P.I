# ASCALPI Produção — BASE INICIAL v1

**G0: APROVADO** (base aceita pelo Carlos; tag publicada). G1 liberado pelo Carlos em 09/10/2026 ("prossiga").

Registro formal do congelamento (marco **G0** de `Modulos/ASCALPI_Producao/PLANO_POS_BASELINE_ATA_MESTRE_E_PAGINACAO.md`). Sem dados de clientes: só contagens agregadas.

## Identificação

| Item | Valor |
|---|---|
| Versão | `producao-base-inicial-v1` |
| Commit validado (código) | `fb96a584fb848679d02e6f46e8010cc90f1c92cd` |
| Tag | `producao-base-inicial-v1` (anotada, criada pelo Carlos e enviada ao GitHub em 09/10/2026; aponta para `fb96a58`). **Não mover nem recriar.** |
| Branch | `modulo/producao-op` (commits posteriores à base são só documentação) |
| Data | 09/10/2026 |
| Aceite | **Carlos**, 09/10/2026: "já podemos criar essa versão do módulo como modelo base… entrega tudo que preciso"; pediu o congelamento e a execução do plano. |

## Evidências de G0

| Verificação | Resultado |
|---|---|
| Suíte leve na nuvem (Linux, Python 3.13, dados sintéticos): `python -m unittest discover -s tests -t .` | **78/78 OK** (25 s) |
| Suíte no Windows (Codex, Python 3.14.6) | 78/78 OK (informado no plano do Codex; não repetido por Claude) |
| Código instalado no PC (`D:\PROGRAMAS\ASCALPI_Project\Modulos\ASCALPI_Producao`) × commit | **Idêntico**, excluindo `dados/`, backups, caches e configuração. Única diferença: pasta residual `_teste_migracao_*` (artefato de teste, não removida) |
| Banco do PC — cópia isolada do arquivo `.db` (sem o `-wal`), migração pelo código da base | Esquema **1 → 6** sem erro; `quick_check` ok; `foreign_key_check` vazio; contagens preservadas: 27 prefeituras, 43 contratos, 1.033 itens de contrato, 45 modelos, 1.091 linhas de modelo, 231 O.P. (230 legadas + 1 criada no sistema), 31 eventos; 230 O.P. legadas sem `contrato_id` (esperado: legado) |
| Backup antes da atualização | `backup_dados_20261009-230410` ao lado do módulo no PC |
| Testes manuais do Carlos | Interface conferida por ele no PC; aprovada |
| PDF por Excel/COM | Smoke test sintético positivo (relato do Codex). Comparação visual com o legado: **pendente** |

## Ressalvas abertas (não bloqueiam a base; tratar antes ou dentro de G1)

1. ~~XLSX de O.P. editável~~ — **encerrada (09/10/2026):** o Carlos confirmou que a edição foi feita pelo próprio sistema (Editar → nova REV), que é o comportamento previsto. Os 3 XLSX emitidos no PC foram conferidos só para leitura: planilha protegida com senha (SHA-512), nenhuma célula desbloqueada e estrutura do livro travada.
2. Comparação visual de 3–5 O.P. reais (XLSX/PDF) com o legado no Excel/Windows.
3. Pasta residual `_teste_migracao_*` no PC: remover só com autorização.
4. Pontos herdados: escala acima de 3.000 O.P., Excel travando no PDF, autenticação (marco de hospedagem).

## Como voltar à base

- Código: `git checkout producao-base-inicial-v1` (ou `git diff producao-base-inicial-v1..HEAD` para ver o que mudou).
- Dados: restaurar `dados/` a partir de um `backup_dados_<data>` consistente; nunca sobrescrever dados operacionais sem autorização do Carlos.
- Rollback operacional de melhorias novas: desativar as flags de G5 (novas O.P. voltam ao comportamento da base).

## Regras para evoluir

1. A tag não se move. Ajustes em `ajustes/<tema>` criadas a partir da tag ou do HEAD aceito.
2. Um ajuste por vez, commit pequeno, teste junto; suíte inteira verde antes e depois. Nenhum teste é removido ou enfraquecido.
3. Regra de negócio só muda com decisão registrada do Carlos.
4. Dados reais, senhas e caminhos de servidor ficam fora do GitHub (repositório público).
5. G1–G5 só começam quando o Carlos confirmar o início das evoluções.
