# CJL System — Atualizações

Existe um único caminho: solicitação → worker externo → encerramento de processos CJL → validação → staging → aplicação → validação → snapshot → reinício. O estado da operação é persistido em Updates/State e o resultado não depende da permanência de uma janela PowerShell.
