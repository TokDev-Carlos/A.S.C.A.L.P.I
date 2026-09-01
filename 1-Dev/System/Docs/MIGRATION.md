# CJL System — Migração Base 4 → Base 5

A migração ES-05/SE-005 é executada externamente ao Mestre. Ela valida a Base 4, entra em manutenção, copia o estado atual para staging, preserva historico/linhagem anterior no SM_Repo, cria checkpoint atual do Repo, aplica o payload Base 5, recompila o Host em staging, valida integralmente e somente então promove `C:\CJL\System`. O Mestre antigo permanece preservado e desativado até homologação final.
