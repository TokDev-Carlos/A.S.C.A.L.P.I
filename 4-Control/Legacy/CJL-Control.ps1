# CJL Control v1.1.2
# Windows PowerShell 5.1 / WinForms
# Purpose: single operator panel for 1-Dev, 2-Compiler (paused), and 3-Git_Main.
# This panel does not edit source, databases, repository revisions, or Compiler state.

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$DevRoot = "C:\.Dev CJL"
$LinuxRoot = Join-Path $DevRoot "1-Dev"
$CompilerRoot = Join-Path $DevRoot "2-Compiler"
$GitMainRoot = Join-Path $DevRoot "3-Git_Main"

$LinuxLauncher = Join-Path $LinuxRoot "INICIAR-CJL-LINUX.sh"
$LinuxInstance = "C:\CJL_Work_Evidence\Runtime-State\1-Dev\Instancia\instance.json"

$GitMainSystem = Join-Path $GitMainRoot "System"
$GitMainBootstrap = Join-Path $GitMainSystem "Host\Bin\CJL.Bootstrap.exe"

$EvidenceRoot = "C:\CJL_Work_Evidence\Control"
$EventFile = Join-Path $EvidenceRoot "events.jsonl"
$StateRoot = Join-Path $EvidenceRoot "state"
$SelectedPatchFile = Join-Path $StateRoot "selected-patch.json"

function Ensure-EvidenceRoot {
    try {
        if (-not (Test-Path -LiteralPath $EvidenceRoot)) {
            New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
        }
    }
    catch {
        # Logging must never block the control panel.
    }
}

function Write-ControlEvent {
    param(
        [Parameter(Mandatory=$true)][string]$Event,
        [string]$Target = "",
        [string]$Result = "INFO",
        [string]$Detail = ""
    )

    try {
        Ensure-EvidenceRoot
        $payload = [ordered]@{
            timestamp = (Get-Date).ToString("o")
            event = $Event
            target = $Target
            result = $Result
            detail = $Detail
        }
        $line = ($payload | ConvertTo-Json -Compress) + [Environment]::NewLine
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::AppendAllText($EventFile, $line, $utf8NoBom)
    }
    catch {
        # Logging must never block the control panel.
    }
}

function Write-JsonNoBom {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)]$Value
    )

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $json = ($Value | ConvertTo-Json -Depth 8) + [Environment]::NewLine
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}

function Get-Sha256Portable {
    param([Parameter(Mandatory=$true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha.ComputeHash($stream)
        }
        finally {
            $sha.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }

    return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}

function Show-PanelError {
    param([string]$Message)
    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        "CJL Control",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Start-HiddenProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FileName,
        [Parameter(Mandatory=$true)][string]$Arguments,
        [string]$WorkingDirectory = ""
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FileName
    $psi.Arguments = $Arguments
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    if ($WorkingDirectory) {
        $psi.WorkingDirectory = $WorkingDirectory
    }

    return [System.Diagnostics.Process]::Start($psi)
}

function Test-WslPid {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $false
    }

    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "wsl.exe"
        $psi.Arguments = "-d Ubuntu-24.04 -- ps -p $ProcessId -o pid="
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true

        $process = [System.Diagnostics.Process]::Start($psi)
        $stdout = $process.StandardOutput.ReadToEnd()
        $null = $process.StandardError.ReadToEnd()
        $process.WaitForExit()

        if ($process.ExitCode -ne 0) {
            return $false
        }

        return ($stdout.Trim() -eq [string]$ProcessId)
    }
    catch {
        return $false
    }
}

function Get-LinuxState {
    $state = [ordered]@{
        status = "OFFLINE"
        detail = "Nenhuma instancia Linux registrada."
        pid = 0
        url = ""
    }

    if (-not (Test-Path -LiteralPath $LinuxRoot)) {
        $state.status = "AUSENTE"
        $state.detail = "1-Dev nao encontrado."
        return [pscustomobject]$state
    }

    if (-not (Test-Path -LiteralPath $LinuxLauncher)) {
        $state.status = "INCOMPLETO"
        $state.detail = "Launcher Linux ausente."
        return [pscustomobject]$state
    }

    if (Test-Path -LiteralPath $LinuxInstance) {
        try {
            $instance = Get-Content -LiteralPath $LinuxInstance -Raw | ConvertFrom-Json
            $processId = [int]$instance.pid
            $port = [int]$instance.port

            if (Test-WslPid -ProcessId $processId) {
                $state.status = "ONLINE"
                $state.pid = $processId
                $state.url = "http://127.0.0.1:$port"
                $state.detail = "PID $processId | Porta $port"
            }
            else {
                $state.status = "REGISTRO ORFAO"
                $state.pid = $processId
                $state.detail = "instance.json existe, mas o PID nao esta ativo."
            }
        }
        catch {
            $state.status = "REGISTRO INVALIDO"
            $state.detail = $_.Exception.Message
        }
    }

    return [pscustomobject]$state
}

function Get-GitMainState {
    $state = [ordered]@{
        status = "OFFLINE"
        detail = "Nenhum processo Git_Main detectado."
        count = 0
    }

    if (-not (Test-Path -LiteralPath $GitMainSystem)) {
        $state.status = "AUSENTE"
        $state.detail = "3-Git_Main\System nao encontrado."
        return [pscustomobject]$state
    }

    try {
        $rows = @(
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                ([string]$_.ExecutablePath).StartsWith($GitMainSystem, [System.StringComparison]::OrdinalIgnoreCase) -or
                ([string]$_.CommandLine).IndexOf($GitMainSystem, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
        )

        $state.count = $rows.Count

        if ($rows.Count -gt 0) {
            $state.status = "ONLINE"
            $state.detail = "$($rows.Count) processo(s) associado(s) ao Git_Main."
        }
        else {
            $state.status = "PRONTO"
            $state.detail = "Sistema disponivel para abertura."
        }
    }
    catch {
        $state.status = "STATUS INDISPONIVEL"
        $state.detail = $_.Exception.Message
    }

    return [pscustomobject]$state
}

function Open-Linux {
    if (-not (Test-Path -LiteralPath $LinuxLauncher)) {
        Show-PanelError "Launcher ausente:`r`n$LinuxLauncher"
        Write-ControlEvent -Event "LINUX_OPEN_REQUEST" -Target "1-Dev" -Result "FAIL" -Detail "Launcher ausente."
        return
    }

    try {
        $linuxLauncherWsl = "/mnt/c/.Dev CJL/1-Dev/INICIAR-CJL-LINUX.sh"
        $arguments = '-d Ubuntu-24.04 -- bash "' + $linuxLauncherWsl + '"'
        $null = Start-HiddenProcess -FileName "wsl.exe" -Arguments $arguments
        Write-ControlEvent -Event "LINUX_OPEN_REQUEST" -Target "1-Dev" -Result "REQUESTED" -Detail $linuxLauncherWsl
    }
    catch {
        Write-ControlEvent -Event "LINUX_OPEN_REQUEST" -Target "1-Dev" -Result "FAIL" -Detail $_.Exception.Message
        Show-PanelError $_.Exception.Message
    }
}

function Open-GitMainSystem {
    if (-not (Test-Path -LiteralPath $GitMainBootstrap)) {
        Show-PanelError "Bootstrap ausente:`r`n$GitMainBootstrap"
        Write-ControlEvent -Event "GITMAIN_SYSTEM_OPEN_REQUEST" -Target "3-Git_Main" -Result "FAIL" -Detail "Bootstrap ausente."
        return
    }

    try {
        $arguments = '--master "' + $GitMainSystem + '" --open-master'
        Start-Process -FilePath $GitMainBootstrap -ArgumentList $arguments -WorkingDirectory $GitMainSystem
        Write-ControlEvent -Event "GITMAIN_SYSTEM_OPEN_REQUEST" -Target "3-Git_Main" -Result "REQUESTED" -Detail $arguments
    }
    catch {
        Write-ControlEvent -Event "GITMAIN_SYSTEM_OPEN_REQUEST" -Target "3-Git_Main" -Result "FAIL" -Detail $_.Exception.Message
        Show-PanelError $_.Exception.Message
    }
}

function Open-GitMainAdmin {
    if (-not (Test-Path -LiteralPath $GitMainBootstrap)) {
        Show-PanelError "Bootstrap ausente:`r`n$GitMainBootstrap"
        Write-ControlEvent -Event "GITMAIN_ADMIN_OPEN_REQUEST" -Target "3-Git_Main" -Result "FAIL" -Detail "Bootstrap ausente."
        return
    }

    try {
        $arguments = '--master "' + $GitMainSystem + '"'
        Start-Process -FilePath $GitMainBootstrap -ArgumentList $arguments -WorkingDirectory $GitMainSystem
        Write-ControlEvent -Event "GITMAIN_ADMIN_OPEN_REQUEST" -Target "3-Git_Main" -Result "REQUESTED" -Detail $arguments
    }
    catch {
        Write-ControlEvent -Event "GITMAIN_ADMIN_OPEN_REQUEST" -Target "3-Git_Main" -Result "FAIL" -Detail $_.Exception.Message
        Show-PanelError $_.Exception.Message
    }
}

function Open-Folder {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Show-PanelError "Pasta ausente:`r`n$Path"
        return
    }

    Start-Process -FilePath "explorer.exe" -ArgumentList "`"$Path`""
}

function Set-StatusVisual {
    param(
        [System.Windows.Forms.Label]$Label,
        [string]$Status
    )

    $Label.Text = $Status

    switch ($Status) {
        "ONLINE" {
            $Label.ForeColor = [System.Drawing.Color]::FromArgb(20, 120, 60)
        }
        "PRONTO" {
            $Label.ForeColor = [System.Drawing.Color]::FromArgb(30, 90, 150)
        }
        "PAUSADO" {
            $Label.ForeColor = [System.Drawing.Color]::FromArgb(150, 100, 20)
        }
        default {
            $Label.ForeColor = [System.Drawing.Color]::FromArgb(150, 45, 45)
        }
    }
}


function Show-Flow21 {
    $flow = New-Object System.Windows.Forms.Form
    $flow.Text = "CJL Control - Fluxo 21 Etapas"
    $flow.StartPosition = "CenterParent"
    $flow.Size = New-Object System.Drawing.Size(860, 640)
    $flow.MinimumSize = New-Object System.Drawing.Size(860, 640)
    $flow.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)
    $flow.Font = New-Object System.Drawing.Font("Segoe UI", 10)

    $info = New-Object System.Windows.Forms.Label
    $info.Text = "Mapa historico das 21 etapas. READY/READ-ONLY = utilizavel hoje. LOCKED/PAUSED = visivel, sem mutacao."
    $info.Location = New-Object System.Drawing.Point(18, 16)
    $info.Size = New-Object System.Drawing.Size(805, 40)
    $info.ForeColor = [System.Drawing.Color]::FromArgb(80, 85, 95)
    $flow.Controls.Add($info)

    $list = New-Object System.Windows.Forms.ListView
    $list.Location = New-Object System.Drawing.Point(18, 62)
    $list.Size = New-Object System.Drawing.Size(805, 440)
    $list.View = [System.Windows.Forms.View]::Details
    $list.FullRowSelect = $true
    $list.GridLines = $true
    $list.HideSelection = $false
    $list.MultiSelect = $false

    [void]$list.Columns.Add("Etapa", 55)
    [void]$list.Columns.Add("Funcao", 520)
    [void]$list.Columns.Add("Status", 190)

    $stages = @(
        [pscustomobject]@{ Number="01"; Name="Check Environment and Branch"; Status="PARTIAL READ-ONLY"; Action="ENV"; Reason="Ambiente local e verificado; branch nao e alterada nem inferida silenciosamente." },
        [pscustomobject]@{ Number="02"; Name="Repair Environment and Correct Branch"; Status="LOCKED"; Action="LOCK"; Reason="Escrita de ambiente/branch ainda nao reativada." },
        [pscustomobject]@{ Number="03"; Name="Identify Machine"; Status="READ-ONLY"; Action="MACHINE"; Reason="Identificacao local sem persistencia." },
        [pscustomobject]@{ Number="04"; Name="Configure Environment, Branch and Machine"; Status="LOCKED"; Action="LOCK"; Reason="Configuracao persistente ainda nao reativada." },
        [pscustomobject]@{ Number="05"; Name="Check Development Tree"; Status="READ-ONLY"; Action="TREE"; Reason="Valida apenas a estrutura local necessaria ao painel." },
        [pscustomobject]@{ Number="06"; Name="Open Development submenu"; Status="READY"; Action="FLOW"; Reason="O submenu historico foi substituido por esta janela grafica." },
        [pscustomobject]@{ Number="07"; Name="Download / Update complete DEV baseline from GitHub main"; Status="LOCKED"; Action="LOCK"; Reason="GitHub sync/write nao esta habilitado nesta versao." },
        [pscustomobject]@{ Number="08"; Name="Open CJL System in Linux (1-Dev)"; Status="READY"; Action="LINUX"; Reason="Usa o launcher Linux local ja validado." },
        [pscustomobject]@{ Number="09"; Name="Select Patch .zip"; Status="READY-LOCAL"; Action="PATCH"; Reason="Seleciona ZIP local, calcula SHA256 e registra estado; nao aplica." },
        [pscustomobject]@{ Number="10"; Name="Close CJL Linux and Test Patch in 1-Dev"; Status="LOCKED"; Action="LOCK"; Reason="Pipeline transacional de Patch ainda nao reativado." },
        [pscustomobject]@{ Number="11"; Name="Check Patch version, freshness and integrity"; Status="LOCKED"; Action="LOCK"; Reason="Depende do contrato de Patch reativado." },
        [pscustomobject]@{ Number="12"; Name="Check Patch Security according to policy"; Status="LOCKED"; Action="LOCK"; Reason="Security gate sera reativado depois do pipeline de Patch." },
        [pscustomobject]@{ Number="13"; Name="Compile validated Patch candidate in 2-Compiler"; Status="PAUSED"; Action="LOCK"; Reason="Compiler explicitamente pausado pelo operador." },
        [pscustomobject]@{ Number="14"; Name="Open Git-Main Local System"; Status="READY"; Action="GITMAIN"; Reason="Git_Main atual funcional." },
        [pscustomobject]@{ Number="15"; Name="Close Git-Main Local and Apply compiled Patch"; Status="LOCKED"; Action="LOCK"; Reason="Depende de candidato compilado e pipeline de aplicacao." },
        [pscustomobject]@{ Number="16"; Name="Open Git-Main Local System with Patch applied"; Status="LOCKED"; Action="LOCK"; Reason="Nao pode ser executada antes da etapa 15; nao deve mascarar Patch nao aplicado." },
        [pscustomobject]@{ Number="17"; Name="Reprove Patch Test"; Status="LOCKED"; Action="LOCK"; Reason="Gate humano de Patch ainda nao reativado." },
        [pscustomobject]@{ Number="18"; Name="Approve local release and authorize main integration"; Status="LOCKED"; Action="LOCK"; Reason="Gate humano/main integration ainda nao reativado." },
        [pscustomobject]@{ Number="19"; Name="Send approved compiled Patch to GitHub branch main"; Status="LOCKED"; Action="LOCK"; Reason="GitHub write nao esta habilitado nesta versao." },
        [pscustomobject]@{ Number="20"; Name="Clean Development Test Files"; Status="LOCKED"; Action="LOCK"; Reason="Cleanup so sera ativado quando o pipeline definir exatamente o que e descartavel." },
        [pscustomobject]@{ Number="21"; Name="Install Real CJL System from GitHub main (C:\CJL)"; Status="LOCKED"; Action="LOCK"; Reason="Producao permanece fora desta versao do painel." }
    )

    foreach ($stage in $stages) {
        $item = New-Object System.Windows.Forms.ListViewItem($stage.Number)
        [void]$item.SubItems.Add($stage.Name)
        [void]$item.SubItems.Add($stage.Status)
        $item.Tag = $stage
        [void]$list.Items.Add($item)
    }

    $flow.Controls.Add($list)

    $detail = New-Object System.Windows.Forms.Label
    $detail.Text = "Selecione uma etapa."
    $detail.Location = New-Object System.Drawing.Point(18, 515)
    $detail.Size = New-Object System.Drawing.Size(580, 52)
    $detail.ForeColor = [System.Drawing.Color]::FromArgb(80, 85, 95)
    $flow.Controls.Add($detail)

    $btnExecute = New-Object System.Windows.Forms.Button
    $btnExecute.Text = "Executar"
    $btnExecute.Location = New-Object System.Drawing.Point(610, 515)
    $btnExecute.Size = New-Object System.Drawing.Size(100, 38)
    $flow.Controls.Add($btnExecute)

    $btnClose = New-Object System.Windows.Forms.Button
    $btnClose.Text = "Fechar"
    $btnClose.Location = New-Object System.Drawing.Point(723, 515)
    $btnClose.Size = New-Object System.Drawing.Size(100, 38)
    $btnClose.Add_Click({ $flow.Close() })
    $flow.Controls.Add($btnClose)

    $list.Add_SelectedIndexChanged({
        if ($list.SelectedItems.Count -eq 0) {
            $detail.Text = "Selecione uma etapa."
            return
        }

        $stage = [pscustomobject]$list.SelectedItems[0].Tag
        $detail.Text = "Etapa " + $stage.Number + " | " + $stage.Status + " | " + $stage.Name + "`r`n" + $stage.Reason
    })

    $btnExecute.Add_Click({
        if ($list.SelectedItems.Count -eq 0) {
            [System.Windows.Forms.MessageBox]::Show(
                "Selecione uma etapa primeiro.",
                "CJL Control",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information
            ) | Out-Null
            return
        }

        $stage = [pscustomobject]$list.SelectedItems[0].Tag

        switch ($stage.Action) {
            "ENV" {
                $linuxStatusLocal = if (Test-Path -LiteralPath $LinuxRoot) { "PASS" } else { "FAIL" }
                $compilerStatusLocal = if (Test-Path -LiteralPath $CompilerRoot) { "PRESENT_PAUSED" } else { "ABSENT_PAUSED" }
                $gitStatusLocal = if (Test-Path -LiteralPath $GitMainSystem) { "PASS" } else { "FAIL" }

                $message = [string]::Join(
                    [Environment]::NewLine,
                    @(
                        "1-Dev=$linuxStatusLocal",
                        "2-Compiler=$compilerStatusLocal",
                        "3-Git_Main=$gitStatusLocal",
                        "",
                        "BRANCH_WRITE=NO",
                        "BRANCH_RESULT=NOT_MUTATED"
                    )
                )

                Write-ControlEvent -Event "OPTION_01_ENVIRONMENT_CHECK" -Target "LOCAL" -Result "READ_ONLY"
                [System.Windows.Forms.MessageBox]::Show(
                    $message,
                    "Etapa 01",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            }

            "MACHINE" {
                $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
                $message = [string]::Join(
                    [Environment]::NewLine,
                    @(
                        "COMPUTER_NAME=$env:COMPUTERNAME",
                        "USER=$env:USERNAME",
                        "ARCH=$env:PROCESSOR_ARCHITECTURE",
                        "WINDOWS=$([string]$os.Caption)",
                        "WINDOWS_VERSION=$([string]$os.Version)",
                        "WSL_EXPECTED=Ubuntu-24.04",
                        "",
                        "PERSISTENCE=NO"
                    )
                )

                Write-ControlEvent -Event "OPTION_03_MACHINE_IDENTITY" -Target "LOCAL" -Result "READ_ONLY"
                [System.Windows.Forms.MessageBox]::Show(
                    $message,
                    "Etapa 03",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            }

            "TREE" {
                $paths = @(
                    $LinuxRoot,
                    $LinuxLauncher,
                    $CompilerRoot,
                    $GitMainRoot,
                    $GitMainSystem,
                    $GitMainBootstrap
                )

                $lines = New-Object System.Collections.Generic.List[string]
                $failCount = 0

                foreach ($path in $paths) {
                    if (Test-Path -LiteralPath $path) {
                        $lines.Add("PASS | $path")
                    }
                    else {
                        $lines.Add("FAIL | $path")
                        $failCount++
                    }
                }

                $lines.Add("")
                $lines.Add("FAIL_COUNT=$failCount")
                $lines.Add("COMPILER_EXECUTION=PAUSED")

                $result = if ($failCount -eq 0) { "PASS" } else { "FAIL" }
                Write-ControlEvent -Event "OPTION_05_TREE_CHECK" -Target $DevRoot -Result $result -Detail "FAIL_COUNT=$failCount"

                [System.Windows.Forms.MessageBox]::Show(
                    [string]::Join([Environment]::NewLine, $lines.ToArray()),
                    "Etapa 05",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            }

            "FLOW" {
                [System.Windows.Forms.MessageBox]::Show(
                    "O submenu historico foi incorporado ao CJL Control como a janela Fluxo 21 Etapas.",
                    "Etapa 06",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            }

            "LINUX" {
                Open-Linux
            }

            "PATCH" {
                $dialog = New-Object System.Windows.Forms.OpenFileDialog
                $dialog.Title = "Selecionar Patch CJL (.zip)"
                $dialog.Filter = "ZIP (*.zip)|*.zip"
                $dialog.Multiselect = $false
                $dialog.CheckFileExists = $true

                if ($dialog.ShowDialog($flow) -eq [System.Windows.Forms.DialogResult]::OK) {
                    $patchPath = $dialog.FileName

                    try {
                        $hash = Get-Sha256Portable -Path $patchPath
                        $fileInfo = Get-Item -LiteralPath $patchPath

                        $state = [ordered]@{
                            selected_at = (Get-Date).ToString("o")
                            source = "LOCAL_FILE"
                            path = $patchPath
                            name = $fileInfo.Name
                            size = [int64]$fileInfo.Length
                            sha256 = $hash
                            status = "SELECTED_NOT_VALIDATED"
                        }

                        Write-JsonNoBom -Path $SelectedPatchFile -Value $state
                        Write-ControlEvent -Event "OPTION_09_PATCH_SELECTED" -Target $patchPath -Result "SELECTED_NOT_VALIDATED" -Detail $hash

                        $message = [string]::Join(
                            [Environment]::NewLine,
                            @(
                                "PATCH_SELECTED=YES",
                                "NAME=$($fileInfo.Name)",
                                "SIZE=$($fileInfo.Length)",
                                "SHA256=$hash",
                                "",
                                "PATCH_APPLIED=NO",
                                "STATUS=SELECTED_NOT_VALIDATED"
                            )
                        )

                        [System.Windows.Forms.MessageBox]::Show(
                            $message,
                            "Etapa 09",
                            [System.Windows.Forms.MessageBoxButtons]::OK,
                            [System.Windows.Forms.MessageBoxIcon]::Information
                        ) | Out-Null
                    }
                    catch {
                        Show-PanelError $_.Exception.Message
                    }
                }
            }

            "GITMAIN" {
                Open-GitMainSystem
            }

            default {
                Write-ControlEvent -Event ("OPTION_" + $stage.Number + "_BLOCKED") -Target $stage.Name -Result $stage.Status -Detail $stage.Reason

                $message = [string]::Join(
                    [Environment]::NewLine,
                    @(
                        "ETAPA=$($stage.Number)",
                        "STATUS=$($stage.Status)",
                        $stage.Name,
                        "",
                        $stage.Reason,
                        "",
                        "Nenhuma mutacao esta habilitada para esta etapa nesta versao."
                    )
                )

                [System.Windows.Forms.MessageBox]::Show(
                    $message,
                    "CJL Control",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            }
        }
    })

    [void]$flow.ShowDialog($form)
}

# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

$form = New-Object System.Windows.Forms.Form
$form.Text = "CJL Control v1.1.2"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(780, 570)
$form.MinimumSize = New-Object System.Drawing.Size(780, 570)
$form.MaximizeBox = $false
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 246, 248)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$title = New-Object System.Windows.Forms.Label
$title.Text = "CJL Control"
$title.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 22)
$title.Location = New-Object System.Drawing.Point(24, 18)
$title.AutoSize = $true
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "1-Dev  |  2-Compiler  |  3-Git_Main"
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(90, 95, 105)
$subtitle.Location = New-Object System.Drawing.Point(28, 58)
$subtitle.AutoSize = $true
$form.Controls.Add($subtitle)

function New-StagePanel {
    param(
        [string]$Title,
        [int]$Top
    )

    $panel = New-Object System.Windows.Forms.Panel
    $panel.Location = New-Object System.Drawing.Point(24, $Top)
    $panel.Size = New-Object System.Drawing.Size(716, 118)
    $panel.BackColor = [System.Drawing.Color]::White
    $panel.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    $form.Controls.Add($panel)

    $labelTitle = New-Object System.Windows.Forms.Label
    $labelTitle.Text = $Title
    $labelTitle.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 13)
    $labelTitle.Location = New-Object System.Drawing.Point(16, 12)
    $labelTitle.AutoSize = $true
    $panel.Controls.Add($labelTitle)

    return $panel
}

$linuxPanel = New-StagePanel -Title "1-Dev / Linux" -Top 92
$compilerPanel = New-StagePanel -Title "2-Compiler" -Top 222
$gitPanel = New-StagePanel -Title "3-Git_Main / Windows" -Top 352

$linuxStatus = New-Object System.Windows.Forms.Label
$linuxStatus.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 11)
$linuxStatus.Location = New-Object System.Drawing.Point(18, 45)
$linuxStatus.AutoSize = $true
$linuxPanel.Controls.Add($linuxStatus)

$linuxDetail = New-Object System.Windows.Forms.Label
$linuxDetail.ForeColor = [System.Drawing.Color]::FromArgb(90, 95, 105)
$linuxDetail.Location = New-Object System.Drawing.Point(18, 72)
$linuxDetail.Size = New-Object System.Drawing.Size(360, 26)
$linuxPanel.Controls.Add($linuxDetail)

$btnLinuxOpen = New-Object System.Windows.Forms.Button
$btnLinuxOpen.Text = "Abrir / Reabrir"
$btnLinuxOpen.Location = New-Object System.Drawing.Point(400, 42)
$btnLinuxOpen.Size = New-Object System.Drawing.Size(135, 40)
$btnLinuxOpen.Add_Click({
    Open-Linux
    $timer.Start()
})
$linuxPanel.Controls.Add($btnLinuxOpen)

$btnLinuxFolder = New-Object System.Windows.Forms.Button
$btnLinuxFolder.Text = "Abrir pasta"
$btnLinuxFolder.Location = New-Object System.Drawing.Point(548, 42)
$btnLinuxFolder.Size = New-Object System.Drawing.Size(140, 40)
$btnLinuxFolder.Add_Click({ Open-Folder -Path $LinuxRoot })
$linuxPanel.Controls.Add($btnLinuxFolder)

$compilerStatus = New-Object System.Windows.Forms.Label
$compilerStatus.Text = "PAUSADO"
$compilerStatus.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 11)
$compilerStatus.ForeColor = [System.Drawing.Color]::FromArgb(150, 100, 20)
$compilerStatus.Location = New-Object System.Drawing.Point(18, 45)
$compilerStatus.AutoSize = $true
$compilerPanel.Controls.Add($compilerStatus)

$compilerDetail = New-Object System.Windows.Forms.Label
$compilerDetail.Text = "Bloqueado por ordem do operador. Nenhuma acao de compilacao esta habilitada."
$compilerDetail.ForeColor = [System.Drawing.Color]::FromArgb(90, 95, 105)
$compilerDetail.Location = New-Object System.Drawing.Point(18, 72)
$compilerDetail.Size = New-Object System.Drawing.Size(520, 26)
$compilerPanel.Controls.Add($compilerDetail)

$btnCompiler = New-Object System.Windows.Forms.Button
$btnCompiler.Text = "COMPILER PAUSADO"
$btnCompiler.Enabled = $false
$btnCompiler.Location = New-Object System.Drawing.Point(548, 42)
$btnCompiler.Size = New-Object System.Drawing.Size(140, 40)
$compilerPanel.Controls.Add($btnCompiler)

$gitStatus = New-Object System.Windows.Forms.Label
$gitStatus.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 11)
$gitStatus.Location = New-Object System.Drawing.Point(18, 45)
$gitStatus.AutoSize = $true
$gitPanel.Controls.Add($gitStatus)

$gitDetail = New-Object System.Windows.Forms.Label
$gitDetail.ForeColor = [System.Drawing.Color]::FromArgb(90, 95, 105)
$gitDetail.Location = New-Object System.Drawing.Point(18, 72)
$gitDetail.Size = New-Object System.Drawing.Size(310, 26)
$gitPanel.Controls.Add($gitDetail)

$btnGitSystem = New-Object System.Windows.Forms.Button
$btnGitSystem.Text = "Abrir Sistema"
$btnGitSystem.Location = New-Object System.Drawing.Point(328, 42)
$btnGitSystem.Size = New-Object System.Drawing.Size(110, 40)
$btnGitSystem.Add_Click({ Open-GitMainSystem })
$gitPanel.Controls.Add($btnGitSystem)

$btnGitAdmin = New-Object System.Windows.Forms.Button
$btnGitAdmin.Text = "ADMIN / DEV"
$btnGitAdmin.Location = New-Object System.Drawing.Point(450, 42)
$btnGitAdmin.Size = New-Object System.Drawing.Size(110, 40)
$btnGitAdmin.Add_Click({ Open-GitMainAdmin })
$gitPanel.Controls.Add($btnGitAdmin)

$btnGitFolder = New-Object System.Windows.Forms.Button
$btnGitFolder.Text = "Abrir pasta"
$btnGitFolder.Location = New-Object System.Drawing.Point(572, 42)
$btnGitFolder.Size = New-Object System.Drawing.Size(116, 40)
$btnGitFolder.Add_Click({ Open-Folder -Path $GitMainRoot })
$gitPanel.Controls.Add($btnGitFolder)

$footer = New-Object System.Windows.Forms.Label
$footer.Text = "Painel de orquestracao. Nao altera source, banco, Repo ou Compiler."
$footer.ForeColor = [System.Drawing.Color]::FromArgb(100, 105, 115)
$footer.Location = New-Object System.Drawing.Point(28, 488)
$footer.AutoSize = $true
$form.Controls.Add($footer)

$btnFlow21 = New-Object System.Windows.Forms.Button
$btnFlow21.Text = "Fluxo 21 Etapas"
$btnFlow21.Location = New-Object System.Drawing.Point(430, 482)
$btnFlow21.Size = New-Object System.Drawing.Size(150, 36)
$btnFlow21.Add_Click({ Show-Flow21 })
$form.Controls.Add($btnFlow21)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = "Atualizar status"
$btnRefresh.Location = New-Object System.Drawing.Point(600, 482)
$btnRefresh.Size = New-Object System.Drawing.Size(140, 36)
$form.Controls.Add($btnRefresh)

function Refresh-PanelStatus {
    try {
        $linux = Get-LinuxState
        Set-StatusVisual -Label $linuxStatus -Status $linux.status
        $linuxDetail.Text = $linux.detail

        $git = Get-GitMainState
        Set-StatusVisual -Label $gitStatus -Status $git.status
        $gitDetail.Text = $git.detail
    }
    catch {
        # Status refresh must not close the panel.
    }
}

$btnRefresh.Add_Click({ Refresh-PanelStatus })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 4000
$timer.Add_Tick({ Refresh-PanelStatus })
$timer.Start()

$form.Add_Shown({
    Write-ControlEvent -Event "CONTROL_PANEL_OPEN" -Target "CJL-Control" -Result "PASS" -Detail "v1.1.2"
    Refresh-PanelStatus
})

$form.Add_FormClosed({
    $timer.Stop()
    Write-ControlEvent -Event "CONTROL_PANEL_CLOSE" -Target "CJL-Control" -Result "PASS" -Detail "v1.1.2"
})

[void]$form.ShowDialog()
