# CJL System — Arquitetura Base 5

## Identidade
Produto visual: **CJL System**. Prefixo técnico: **CJL**. Nome institucional: **Carlos Júnior Logística Sistemas**.

## Raiz
`C:\CJL\System` contém somente o estado operacional atual. `C:\CJL\SM_Repo` contém histórico, recuperação, patches antigos, snapshots e proveniência. `System\Repo` permanece o repositório operacional transacional e nunca deve ser confundido com `SM_Repo`.

## Baseline
BA-01 / ES-05 / IN-00 / SE-005 / Version 5.00.005 / Layout 5 / Schema 15 / Runtime 001.

## Fronteiras
App = regras de negócio e dados. Host = fronteira Windows. Runtime = dependência protegida. Repo = transações atuais. SM_Repo = histórico e recuperação. Updates = estado e fila de atualização atual.

## Administração remota
Tailscale fornece rede privada; OpenSSH fornece transporte autenticado; SMB é somente acesso a arquivos; RDP permanece acesso integral ao Windows. Ações de GUI usam Broker de sessão interativa por Task Scheduler, sem CreateProcessAsUser/CreateProcessWithToken entre sessões.
