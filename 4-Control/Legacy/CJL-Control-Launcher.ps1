$ErrorActionPreference = "Stop"

try {
    Add-Type -AssemblyName System.Windows.Forms

    $base = Split-Path -Parent $MyInvocation.MyCommand.Path
    $panel = Join-Path $base "CJL-Control.ps1"
    $logRoot = "C:\CJL_Work_Evidence\Control"
    $log = Join-Path $logRoot "startup-error.txt"

    if (-not (Test-Path -LiteralPath $panel)) {
        throw "CJL-Control.ps1 ausente: $panel"
    }

    & $panel
}
catch {
    try {
        if (-not (Test-Path -LiteralPath $logRoot)) {
            New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
        }

        $content = @(
            "CJL CONTROL STARTUP ERROR v1.1.2"
            "Timestamp=$((Get-Date).ToString('o'))"
            "Message=$($_.Exception.Message)"
            "Position=$($_.InvocationInfo.PositionMessage)"
            "ScriptStackTrace=$($_.ScriptStackTrace)"
        ) -join [Environment]::NewLine

        [System.IO.File]::WriteAllText($log, $content, (New-Object System.Text.UTF8Encoding($false)))
    }
    catch {
    }

    try {
        [System.Windows.Forms.MessageBox]::Show(
            "CJL Control nao iniciou.`r`n`r`n$($_.Exception.Message)`r`n`r`nLog: C:\CJL_Work_Evidence\Control\startup-error.txt",
            "CJL Control - Erro",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }
    catch {
    }
}
