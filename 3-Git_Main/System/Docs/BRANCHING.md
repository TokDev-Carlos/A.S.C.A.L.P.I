# CJL System — Branch Contract 1

## Branches

- MAIN: `C:\CJL\System` — produção real.
- DEV: `C:\.Dev CJL\Sistema_Dev` — laboratório técnico sem dados operacionais de produção.
- Container DEV: `C:\.Dev CJL`.
- Share administrativa DEV: `.Dev CJL$` (UNC esperado no Host atual: `\\<LOCAL_IPV4>\.Dev CJL$`).

## Regra de código

Arquivos patchable permanecem byte a byte equivalentes entre MAIN e DEV quando estão na mesma release. Identidade da branch fica apenas em arquivos gerados (`CJL.branch.json`, `CJL.root.json`, estado de Updates, logs e SM_Repo).

## Promoção

1. O ZIP do patch é aplicado primeiro na DEV.
2. DEV é validada.
3. `approve_patch.py` registra o SHA-256 exato no `SM_Repo` da MAIN.
4. O MESMO ZIP, sem recompilar/reempacotar, é aplicado na MAIN.
5. O engine da MAIN recusa patch sem recibo de aprovação do mesmo SHA-256.

## Dados

DEV não recebe `Data`, `Shared`, `Repo`, `Logs`, `Temp` ou `Export` da produção. Runtime e Host são cópias técnicas independentes para permitir build/teste isolado.
