[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

try {
    Add-Type -AssemblyName System.Windows.Forms

    $BasePath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Server = Join-Path $BasePath "Server\ASCALPI-Control-Server.ps1"
    $ConfigPath = Join-Path $BasePath "Config\control.json"

    if (-not (Test-Path -LiteralPath $Server -PathType Leaf)) {
        throw "Servidor do painel ausente: $Server"
    }
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Configuracao do painel ausente: $ConfigPath"
    }

    $Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    $EvidenceRoot = [string]$Config.evidence_root
    if (-not (Test-Path -LiteralPath $EvidenceRoot -PathType Container)) {
        [void][IO.Directory]::CreateDirectory($EvidenceRoot)
    }
    $RuntimeFile = Join-Path $EvidenceRoot "panel-runtime.json"

    Remove-Item -LiteralPath $RuntimeFile -Force -ErrorAction SilentlyContinue

    $serverArgs = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $Server + '" -BasePath "' + $BasePath + '"'
    $serverProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $serverArgs -WindowStyle Hidden -PassThru

    $runtime = $null
    for ($i=0; $i -lt 100; $i++) {
        Start-Sleep -Milliseconds 100
        if (Test-Path -LiteralPath $RuntimeFile -PathType Leaf) {
            try {
                $runtime = Get-Content -LiteralPath $RuntimeFile -Raw | ConvertFrom-Json
                if ($runtime.url) { break }
            } catch {}
        }
        if ($serverProcess.HasExited) {
            throw "Servidor encerrou antes de publicar a interface."
        }
    }
    if (-not $runtime -or -not $runtime.url) {
        throw "Servidor local nao publicou a URL dentro do tempo esperado."
    }

    $url = [string]$runtime.url

    # Dedicated application-window host. Do not fall back to the default browser.
    $edgeCandidates = New-Object System.Collections.Generic.List[string]

    foreach ($regPath in @(
        "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        "Registry::HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
    )) {
        try {
            $item = Get-ItemProperty -LiteralPath $regPath -ErrorAction Stop
            if ($item.'(default)') { [void]$edgeCandidates.Add([string]$item.'(default)') }
            elseif ($item.PSObject.Properties.Name -contains "(default)") { [void]$edgeCandidates.Add([string]$item."(default)") }
        }
        catch {
        }
    }

    try {
        $pf86 = [Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFilesX86)
        if ($pf86) { [void]$edgeCandidates.Add((Join-Path $pf86 "Microsoft\Edge\Application\msedge.exe")) }
    }
    catch {
    }

    try {
        $pf = [Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFiles)
        if ($pf) { [void]$edgeCandidates.Add((Join-Path $pf "Microsoft\Edge\Application\msedge.exe")) }
    }
    catch {
    }

    try {
        $local = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
        if ($local) { [void]$edgeCandidates.Add((Join-Path $local "Microsoft\Edge\Application\msedge.exe")) }
    }
    catch {
    }

    $edge = @(
        $edgeCandidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -Unique -First 1
    )

    if ($edge.Count -eq 0) {
        throw "Host de aplicativo Microsoft Edge nao localizado. O PAINEL ADMIN nao abrira em navegador comum."
    }

    $windowMode = "maximized"
    try {
        if ($Config.window -and $Config.window.mode) {
            $windowMode = [string]$Config.window.mode
        }
    }
    catch {
        $windowMode = "maximized"
    }


    $browserProcess = $null
    $sessionId = [Guid]::NewGuid().ToString("N")
    $panelProfile = Join-Path $EvidenceRoot ("PanelAppProfile\" + $sessionId)
    [void][IO.Directory]::CreateDirectory($panelProfile)

    $edgeArgs = @(
        "--app=$url",
        "--user-data-dir=$panelProfile",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-extensions",
        "--disable-features=msEdgeSidebarV2",
        "--app-auto-launched"
    )

    if ($windowMode -eq "maximized") {
        $edgeArgs += "--start-maximized"
    }

    $browserProcess = Start-Process -FilePath $edge[0] -ArgumentList $edgeArgs -PassThru

    # Wait until the dedicated app-profile processes disappear.
    # This avoids opening/depending on a normal browser window and keeps lifecycle tied to PAINEL ADMIN.
    $profileToken = $panelProfile.ToLowerInvariant()
    $seenAppProcess = $false

    for ($i = 0; $i -lt 100; $i++) {
        Start-Sleep -Milliseconds 100
        try {
            $appProcesses = @(
                Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.CommandLine -and ([string]$_.CommandLine).ToLowerInvariant().Contains($profileToken)
                }
            )
            if ($appProcesses.Count -gt 0) {
                $seenAppProcess = $true
                break
            }
        }
        catch {
        }
    }

    if (-not $seenAppProcess -and $browserProcess.HasExited) {
        throw "A janela de aplicativo do PAINEL ADMIN nao iniciou."
    }

    while ($true) {
        Start-Sleep -Milliseconds 300
        try {
            $appProcesses = @(
                Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.CommandLine -and ([string]$_.CommandLine).ToLowerInvariant().Contains($profileToken)
                }
            )
            if ($appProcesses.Count -eq 0) { break }
        }
        catch {
            if ($browserProcess.HasExited) { break }
        }
    }

    # Closing PAINEL ADMIN shuts down its backend.
    try {
        Invoke-WebRequest -UseBasicParsing -Method Post -Uri ($url.TrimEnd("/") + "/api/shutdown") `
            -ContentType "application/json" -Body "{}" -TimeoutSec 2 | Out-Null
    }
    catch {
    }

    Start-Sleep -Milliseconds 350

    try {
        if (-not $serverProcess.HasExited) {
            Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
    catch {
    }

    try {
        Remove-Item -LiteralPath $RuntimeFile -Force -ErrorAction SilentlyContinue
    }
    catch {
    }

    try {
        Remove-Item -LiteralPath $panelProfile -Recurse -Force -ErrorAction SilentlyContinue
    }
    catch {
    }
}
catch {
    try {
        [System.Windows.Forms.MessageBox]::Show(
            "PAINEL ADMIN nao iniciou.`r`n`r`n$($_.Exception.Message)",
            "ASCALPI - PAINEL ADMIN",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    } catch {}
    exit 1
}
