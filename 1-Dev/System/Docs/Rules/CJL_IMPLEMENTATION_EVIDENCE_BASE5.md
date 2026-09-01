# CJL System — Evidência Regra → Implementação — 1.05.01.006

| Grupo | Estado | Evidência |
|---|---|---|
| Regras append-only | IMPLEMENTADO EM FONTE | `App/Core/cumulativity.py`, `Docs/Rules/*`, Patch/Snapshot/Validator |
| Versionamento único | IMPLEMENTADO EM FONTE | `App/Core/version.py`, `App/Core/release.py`, `sistema.json`, `ProductPaths.cs` |
| Dados Sistema × Operação | IMPLEMENTADO EM CONTRATO | `App/Config/data.policy.json`, `App/Core/data_policy.py`, `Docs/DATA_POLICY.md` |
| Snapshot | IMPLEMENTADO EM FONTE | `Dev/Tools/snapshot_export.py`; inclui `Logs/System`, exclui operação |
| Histórico técnico | IMPLEMENTADO EM FONTE | `App/Core/system_history.py`; `Logs/System/release-history.jsonl` em runtime |
| Falso bloqueio de estação | CORRIGIDO EM FONTE | `App/painel.py::_read_release_state/_station_update_status`, `App/Painel/app.js` |
| Patch futuro | IMPLEMENTADO EM FONTE | `Dev/Tools/create_patch.py` + `apply_patch.py` Format 7 |
| Usuário interno Mestre CJLAdmin | DECIDIDO / NÃO MIGRADO POR ESTE PATCH | Regras R-0239→R-0246; procedimento específico posterior |
| Painel Remote Admin | PENDENTE | próximo bloco após este patch |
