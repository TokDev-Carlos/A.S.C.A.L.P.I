param(
    [string]$Root = 'C:\CJL\System',
    [string]$PanelOperator = '',
    [string]$AdminMachine = ''
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$Dispatch = Join-Path $Root 'Dev\Tools\RemoteAdmin\CJL-Remote.ps1'
$AuditPath = Join-Path $Root 'Logs\RemoteAdmin\remote_admin_audit.jsonl'
$Operator = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$PanelOperator = ($PanelOperator -replace '[\r\n\t]',' ').Trim()
if ($PanelOperator.Length -gt 100) { $PanelOperator = $PanelOperator.Substring(0,100) }
$AdminMachine = ($AdminMachine -replace '[\r\n\t]',' ').Trim()
if ($AdminMachine.Length -gt 100) { $AdminMachine = $AdminMachine.Substring(0,100) }
$ClientIp = ''
if (-not [string]::IsNullOrWhiteSpace($env:SSH_CONNECTION)) {
    $P = @($env:SSH_CONNECTION -split '\s+')
    if ($P.Count -ge 1) { $ClientIp = [string]$P[0] }
}

function Audit-Console([string]$Event,[string]$Detail='') {
    try {
        $R = [ordered]@{format=1;product='CJL System';component='REMOTE_ADMIN_AUDIT_V1';time=(Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK');operator=$Operator;panel_operator=$PanelOperator;admin_machine=$AdminMachine;admin_client_ip=$ClientIp;action='CONSOLE_DEV';event=$Event;detail=$Detail}
        Add-Content -LiteralPath $AuditPath -Value ($R | ConvertTo-Json -Compress) -Encoding UTF8
    }
    catch {}
}

function Display-Version {
    try {
        $Cfg = Get-Content -LiteralPath (Join-Path $Root 'App\Config\sistema.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        function N([string]$V) { if($V -match '(\d+)$'){return [int]$Matches[1]} return 0 }
        return ('{0}.{1}.{2:D2}.{3:D3}' -f (N ([string]$Cfg.versioning.business_id)),(N ([string]$Cfg.versioning.structural_id)),(N ([string]$Cfg.versioning.incremental_id)),(N ([string]$Cfg.versioning.security_id)))
    }
    catch { return '?' }
}

function Header {
    Clear-Host
    Write-Host '============================================================' -ForegroundColor DarkCyan
    Write-Host ' CJL SYSTEM - CONSOLE DEV REMOTO' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor DarkCyan
    Write-Host (" Host     : {0}" -f $env:COMPUTERNAME)
    Write-Host (" Windows  : {0}" -f $Operator)
    Write-Host (" Painel   : {0}" -f $(if($PanelOperator){$PanelOperator}else{'N/A'}))
    Write-Host (" PC Admin : {0}" -f $(if($AdminMachine){$AdminMachine}else{'N/A'}))
    Write-Host (" Cliente  : {0}" -f $ClientIp)
    Write-Host (" Root     : {0}" -f $Root)
    Write-Host (" Versao   : {0}" -f (Display-Version))
    Write-Host ' Canal    : Tailscale + OpenSSH | Contrato Remoto V7'
    Write-Host '============================================================' -ForegroundColor DarkCyan
    Write-Host ''
}
function Pause-Menu { Write-Host ''; [void](Read-Host 'Pressione ENTER para continuar') }
function Run([string]$Action) {
    $InvokeArgs = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$Dispatch,'-Action',$Action,'-Root',$Root,'-PanelOperator',$PanelOperator,'-AdminMachine',$AdminMachine)
    if ($Action -in @('MaintenanceEnter','MaintenanceExit')) {
        $Who = $(if($PanelOperator){$PanelOperator}else{$Operator})
        $Where = $(if($AdminMachine){$AdminMachine}else{$ClientIp})
        $InvokeArgs += @('-Reason',("CONSOLE_DEV:{0}@{1}" -f $Who,$Where))
    }
    & powershell.exe @InvokeArgs
}
function Free-Shell {
    $TranscriptDir = Join-Path $Root 'Logs\RemoteAdmin\ConsoleDev'
    New-Item -ItemType Directory -Force -Path $TranscriptDir | Out-Null
    $Transcript = Join-Path $TranscriptDir ('console_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,8) + '.log')
    Audit-Console 'FREE_SHELL_OPEN' $Transcript
    Write-Host 'PowerShell administrativo do Mestre. Digite exit para voltar ao menu.' -ForegroundColor Yellow
    Write-Host ("Transcrição: {0}" -f $Transcript) -ForegroundColor DarkGray
    $RootEscaped = $Root.Replace("'","''")
    $TranscriptEscaped = $Transcript.Replace("'","''")
    $Command = "Set-Location '$RootEscaped'; Start-Transcript -LiteralPath '$TranscriptEscaped' -Append | Out-Null; Write-Host 'CJL System - CONSOLE DEV DO MESTRE' -ForegroundColor Cyan; Write-Host 'Comandos e saída desta sessão estão sendo transcritos.' -ForegroundColor DarkGray"
    & powershell.exe -NoLogo -NoProfile -NoExit -Command $Command
    Audit-Console 'FREE_SHELL_CLOSE' $Transcript
}

Audit-Console 'OPEN'
try {
    while ($true) {
        Header
        Write-Host ' 1  STATUS'
        Write-Host ' 2  OPEN'
        Write-Host ' 3  FOCUS'
        Write-Host ' 4  CLOSE'
        Write-Host ' 5  VALIDATE'
        Write-Host ' 6  HEALTH'
        Write-Host ' 7  LOGS'
        Write-Host ' 8  UPDATE_STATUS'
        Write-Host ' 9  MAINTENANCE_ENTER (CRITICO)'
        Write-Host '10  MAINTENANCE_EXIT'
        Write-Host '11  PowerShell livre (PRIVILEGIADO)'
        Write-Host ' 0  Sair'
        Write-Host ''
        $Choice = Read-Host 'Opcao'
        Write-Host ''
        switch ($Choice) {
            '1' { Run 'Status'; Pause-Menu }
            '2' { Run 'Open'; Pause-Menu }
            '3' { Run 'Focus'; Pause-Menu }
            '4' { Run 'Close'; Pause-Menu }
            '5' { Run 'Validate'; Pause-Menu }
            '6' { Run 'Health'; Pause-Menu }
            '7' { Run 'Logs'; Pause-Menu }
            '8' { Run 'UpdateStatus'; Pause-Menu }
            '9' {
                $Confirm = Read-Host 'Digite MANUTENCAO para confirmar'
                if ($Confirm -ceq 'MANUTENCAO') { Run 'MaintenanceEnter' } else { Write-Host 'Cancelado.' }
                Pause-Menu
            }
            '10' {
                $Confirm = Read-Host 'Digite LIBERAR para confirmar'
                if ($Confirm -ceq 'LIBERAR') { Run 'MaintenanceExit' } else { Write-Host 'Cancelado.' }
                Pause-Menu
            }
            '11' { Free-Shell; Pause-Menu }
            '0' { break }
            default { Write-Host 'Opcao invalida.' -ForegroundColor Yellow; Start-Sleep -Seconds 1 }
        }
        if ($Choice -eq '0') { break }
    }
}
finally {
    Audit-Console 'CLOSE'
}
