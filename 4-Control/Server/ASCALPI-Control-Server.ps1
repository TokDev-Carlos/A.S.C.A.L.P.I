[CmdletBinding()]
param(
    [string]$BasePath = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [int]$StartPort = 18151
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ConfigPath = Join-Path $BasePath "Config\control.json"
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Config ausente: $ConfigPath"
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

$EvidenceRoot = [string]$Config.evidence_root
$RuntimeFile = Join-Path $EvidenceRoot "panel-runtime.json"
$EventFile = Join-Path $EvidenceRoot "events.jsonl"

function Ensure-Directory([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        [void][System.IO.Directory]::CreateDirectory($Path)
    }
}
Ensure-Directory $EvidenceRoot

if (-not ("ASCALPI.NativeWindow" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace ASCALPI {
    public static class NativeWindow {
        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool BringWindowToTop(IntPtr hWnd);
    }
}
"@
}


function Write-Utf8NoBom([string]$Path, [string]$Text) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function Write-Event([string]$Event, [string]$Target, [string]$Result, [string]$Detail = "") {
    try {
        $payload = [ordered]@{
            timestamp = [DateTimeOffset]::Now.ToString("o")
            event = $Event
            target = $Target
            result = $Result
            detail = $Detail
        }
        $enc = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::AppendAllText($EventFile, (($payload | ConvertTo-Json -Compress) + [Environment]::NewLine), $enc)
    } catch {}
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

function ConvertTo-JsonText($Object) {
    return ($Object | ConvertTo-Json -Depth 10 -Compress)
}

function Test-WslPid([int]$ProcessId) {
    if ($ProcessId -le 0) { return $false }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "wsl.exe"
        $psi.Arguments = "-d " + [string]$Config.wsl_distribution + " -- ps -p $ProcessId -o pid="
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $out = $p.StandardOutput.ReadToEnd()
        $null = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        return ($p.ExitCode -eq 0 -and $out.Trim() -eq [string]$ProcessId)
    } catch { return $false }
}

function Get-LinuxState {
    $state = [ordered]@{
        title = "Desenvolvimento Linux"
        status = "OFFLINE"
        detail = "O ambiente Linux está disponível, mas não foi iniciado."
        pid = 0
        url = ""
        launcher = [string]$Config.linux_launcher
    }
    if (-not (Test-Path -LiteralPath ([string]$Config.linux_root))) {
        $state.status = "AUSENTE"; $state.detail = "O diretório 1-Dev não foi localizado."; return $state
    }
    if (-not (Test-Path -LiteralPath ([string]$Config.linux_launcher))) {
        $state.status = "INCOMPLETO"; $state.detail = "Launcher Linux ausente."; return $state
    }
    if (Test-Path -LiteralPath ([string]$Config.linux_instance)) {
        try {
            $instance = Get-Content -LiteralPath ([string]$Config.linux_instance) -Raw | ConvertFrom-Json
            $pidValue = [int]$instance.pid
            $port = [int]$instance.port
            if (Test-WslPid $pidValue) {
                $state.status = "ONLINE"
                $state.pid = $pidValue
                $state.url = "http://127.0.0.1:$port"
                $state.detail = "Ambiente em execução no processo $pidValue e porta local $port."
            } else {
                $state.status = "OFFLINE"
                $state.detail = "A sessão anterior foi encerrada e pode ser iniciada novamente."
            }
        } catch {
            $state.status = "INCOMPLETO"
            $state.detail = "O registro da sessão Linux não pôde ser interpretado."
        }
    }
    return $state
}

function Get-GitMainState {
    $state = [ordered]@{
        status = "OFFLINE"
        detail = "O sistema está disponível para abertura."
        count = 0
        system = [string]$Config.git_main_system
    }
    if (-not (Test-Path -LiteralPath ([string]$Config.git_main_system))) {
        $state.status = "AUSENTE"; $state.detail = "O sistema Git_Main não foi localizado."; return $state
    }
    try {
        $rows = @(
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                ($_.ExecutablePath -and ([string]$_.ExecutablePath).StartsWith([string]$Config.git_main_system, [StringComparison]::OrdinalIgnoreCase)) -or
                ($_.CommandLine -and ([string]$_.CommandLine).IndexOf([string]$Config.git_main_system, [StringComparison]::OrdinalIgnoreCase) -ge 0)
            }
        )
        $state.count = $rows.Count
        if ($rows.Count -gt 0) {
            $state.status = "ONLINE"
            $state.detail = if ($rows.Count -eq 1) { "Sistema em execução com 1 processo associado." } else { "Sistema em execução com $($rows.Count) processos associados." }
        } else {
            $state.status = "PRONTO"
            $state.detail = "Sistema validado e disponível para abertura."
        }
    } catch {
        $state.status = "INCOMPLETO"
        $state.detail = "Status de processo indisponivel."
    }
    return $state
}

function Get-WslState {
    $state = [ordered]@{
        status = "OFFLINE"
        distribution = [string]$Config.wsl_distribution
        detail = "Aguardando diagnóstico da infraestrutura WSL."
    }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        $state.status = "AUSENTE"; $state.detail = "O subsistema WSL não foi localizado."; return $state
    }
    try {
        $raw = (& wsl.exe -l -q 2>&1) -join "`n"
        $distros = @(
            $raw -split "`r?`n" |
                ForEach-Object { ([string]$_).Replace([string][char]0, "").Trim() } |
                Where-Object { $_ }
        )
        if ($distros -contains [string]$Config.wsl_distribution) {
            $state.status = "ONLINE"
            $state.detail = "Distribuição configurada e disponível."
        } else {
            $state.status = "INCOMPLETO"
            $state.detail = "A distribuição configurada não foi localizada."
        }
    } catch {
        $state.status = "INCOMPLETO"
        $state.detail = $_.Exception.Message
    }
    return $state
}

# ASCALPI_GIT_POLICY_R1
function Find-GitRoot {
    try {
        if ($Config.PSObject.Properties.Name -contains "git") {
            $configured = [string]$Config.git.repository_root
            if ($configured -and (Test-Path -LiteralPath (Join-Path $configured ".git") -PathType Container)) {
                return $configured
            }
        }
    } catch {}

    # Legacy fallback remains for compatibility only.
    foreach ($candidate in @([string]$Config.git_main_root, [string]$Config.linux_root)) {
        if (Test-Path -LiteralPath (Join-Path $candidate ".git") -PathType Container) {
            return $candidate
        }
    }
    return ""
}

function Get-GitRemoteHead([string]$Root, [string]$Branch) {
    if (-not $Root -or -not $Branch) { return "" }
    try {
        $ref = "refs/heads/" + $Branch
        $raw = ((& git.exe -C $Root ls-remote origin $ref 2>$null) -join "`n").Trim()
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return "" }
        return ($raw -split "\s+")[0]
    } catch {
        return ""
    }
}

function Get-GitState {
    $devBranch = "Dev-Work"
    $mainBranch = "main"
    $repositoryFullName = "TokDev-Carlos/A.S.C.A.L.P.I"
    $devInclude = @("1-Dev","2-Compiler","3-Git_Main","4-Control","5-Docs","WSL")
    $mainInclude = @("3-Git_Main","5-Docs")
    $localOnly = @()
    $writeEnabled = $false
    $forcePush = $false
    $requirePreview = $true
    $requireApproval = $true
    $informationRoutes = $null

    try {
        if ($Config.PSObject.Properties.Name -contains "git") {
            $repositoryFullName = [string]$Config.git.repository_full_name
            $devBranch = [string]$Config.git.branch_dev_work
            $mainBranch = [string]$Config.git.branch_main
            $devInclude = @($Config.git.dev_work_include)
            $mainInclude = @($Config.git.main_include)
            $localOnly = @($Config.git.local_only)
            $writeEnabled = [bool]$Config.git.write_enabled
            $forcePush = [bool]$Config.git.force_push
            $requirePreview = [bool]$Config.git.require_preview
            $requireApproval = [bool]$Config.git.require_operator_approval
        }
        if ($Config.PSObject.Properties.Name -contains "information_policy") {
            $informationRoutes = $Config.information_policy.routes
        }
    } catch {}

    $state = [ordered]@{
        status = "AUSENTE"
        mode = "READ_ONLY"
        repository = ""
        repository_full_name = $repositoryFullName
        branch = ""
        head_short = ""
        change_count = 0
        changes = @()
        detail = "O repositório Git oficial ainda não foi localizado."
        dev_work = [ordered]@{
            branch = $devBranch
            head = ""
            head_short = ""
            status = "AUSENTE"
            include = @($devInclude)
            detail = "Estado remoto ainda não verificado."
        }
        main = [ordered]@{
            branch = $mainBranch
            head = ""
            head_short = ""
            status = "AUSENTE"
            include = @($mainInclude)
            detail = "Estado remoto ainda não verificado."
        }
        policy = [ordered]@{
            write_enabled = $writeEnabled
            force_push = $forcePush
            require_preview = $requirePreview
            require_operator_approval = $requireApproval
            local_only = @($localOnly)
        }
        information = [ordered]@{
            create_random_documents = $false
            routes = $informationRoutes
        }
    }

    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        $state.detail = "O executável Git não foi localizado."
        return $state
    }

    $root = Find-GitRoot
    if (-not $root) {
        return $state
    }

    try {
        $branch = ((& git.exe -C $root rev-parse --abbrev-ref HEAD 2>$null) -join "").Trim()
        $headFull = ((& git.exe -C $root rev-parse HEAD 2>$null) -join "").Trim()
        $headShort = if ($headFull.Length -ge 8) { $headFull.Substring(0,8) } else { $headFull }
        $lines = @((& git.exe -C $root status --porcelain=v1 2>$null) | Where-Object { $_ })

        $changes = @()
        foreach ($line in $lines) {
            if ($line.Length -ge 4) {
                $changes += [pscustomobject]@{
                    code = $line.Substring(0,2).Trim()
                    path = $line.Substring(3)
                }
            }
        }

        $devHead = Get-GitRemoteHead -Root $root -Branch $devBranch
        $mainHead = Get-GitRemoteHead -Root $root -Branch $mainBranch

        $state.status = if ($lines.Count -eq 0) { "PRONTO" } else { "WARNING" }
        $state.repository = $root
        $state.branch = $branch
        $state.head_short = $headShort
        $state.change_count = $lines.Count
        $state.changes = $changes
        $state.detail = if ($lines.Count -eq 0) {
            "Repositório Git oficial localizado; árvore local sem alterações."
        } elseif ($lines.Count -eq 1) {
            "Repositório Git oficial localizado; 1 alteração local detectada."
        } else {
            "Repositório Git oficial localizado; $($lines.Count) alterações locais detectadas."
        }

        if ($devHead) {
            $state.dev_work.head = $devHead
            $state.dev_work.head_short = if ($devHead.Length -ge 8) { $devHead.Substring(0,8) } else { $devHead }
            $state.dev_work.status = "PRONTO"
            $state.dev_work.detail = "Ambiente portátil de engenharia."
        } else {
            $state.dev_work.status = "INCOMPLETO"
            $state.dev_work.detail = "Branch remota Dev-Work não pôde ser lida."
        }

        if ($mainHead) {
            $state.main.head = $mainHead
            $state.main.head_short = if ($mainHead.Length -ge 8) { $mainHead.Substring(0,8) } else { $mainHead }
            $state.main.status = "PRONTO"
            $state.main.detail = "Linha homologada: 3-Git_Main + 5-Docs."
        } else {
            $state.main.status = "INCOMPLETO"
            $state.main.detail = "Branch remota main não pôde ser lida."
        }
    } catch {
        $state.status = "INCOMPLETO"
        $state.detail = $_.Exception.Message
    }

    return $state
}
function Get-DocsState {
    $docs = [ordered]@{
        status = "AUSENTE"
        detail = "O acervo 5-Docs não foi localizado."
        events_status = "AUSENTE"
        events_detail = "O registro de eventos não foi localizado."
        engine_status = "AUSENTE"
        engine_detail = "O mecanismo documental não foi localizado."
    }
    $docsRoot = [string]$Config.docs_root
    if (Test-Path -LiteralPath $docsRoot -PathType Container) {
        $expected = @("Execution_Contract.md","Souvenir.md","Black_Book.md","White_Book.md")
        $present = @($expected | Where-Object { Test-Path -LiteralPath (Join-Path $docsRoot $_) -PathType Leaf })
        $docs.status = if ($present.Count -eq 4) { "PRONTO" } else { "INCOMPLETO" }
        $docs.detail = "$($present.Count) de 4 documentos controlados localizados."
    }
    $engine = Join-Path ([string]$Config.control_root) "Documentation"
    if (Test-Path -LiteralPath $engine -PathType Container) {
        $docs.engine_status = "PRONTO"
            $docs.engine_detail = "Mecanismo documental preservado e disponível."
        $eventLedger = Join-Path $engine "State\events.jsonl"
        if (Test-Path -LiteralPath $eventLedger -PathType Leaf) {
            $count = @(Get-Content -LiteralPath $eventLedger -ErrorAction SilentlyContinue).Count
            $docs.events_status = "PRONTO"
            $docs.events_detail = if ($count -eq 1) { "1 evento registrado." } else { "$count eventos registrados." }
        }
    }
    return $docs
}

function Get-PanelStatus {
    $linux = Get-LinuxState
    $gitMain = Get-GitMainState
    $wsl = Get-WslState
    $git = Get-GitState
    $docs = Get-DocsState
    $signals = @($linux.status, $gitMain.status, $wsl.status, $docs.status, $docs.engine_status)
    $hasStructuralIssue = @($signals | Where-Object { $_ -in @("AUSENTE", "INCOMPLETO") }).Count -gt 0
    $hasActiveEnvironment = ($linux.status -eq "ONLINE" -or $gitMain.status -eq "ONLINE")
    $global = if ($hasStructuralIssue) { "ATENCAO" } elseif ($hasActiveEnvironment) { "OPERACIONAL" } else { "DISPONIVEL" }
    $summary = if ($hasStructuralIssue) {
        "A central permanece funcional, mas identificou componentes que exigem revisão antes de uma operação completa."
    } elseif ($hasActiveEnvironment) {
        "Ambientes ativos e proteções de escrita preservadas para GitHub e produção."
    } else {
        "Ambientes validados e disponíveis para abertura, com proteções de escrita preservadas."
    }
    return [ordered]@{
        environment = "LOCAL"
        global_status = $global
        summary = $summary
        linux = $linux
        compiler = [ordered]@{
            status = "PAUSADO"
            detail = "Execução suspensa por política nesta revisão."
        }
        git_main = $gitMain
        wsl = $wsl
        git = $git
        docs = $docs
        paths = [ordered]@{
            workspace_root = [string]$Config.workspace_root
            linux_root = [string]$Config.linux_root
            compiler_root = [string]$Config.compiler_root
            git_main_root = [string]$Config.git_main_root
            docs_root = [string]$Config.docs_root
            git_repository_root = if ($Config.PSObject.Properties.Name -contains "git") { [string]$Config.git.repository_root } else { "" }
        }
        policy = [ordered]@{
            github_write = [bool]$Config.github_write
            production_write = [bool]$Config.production_write
            git_mode = if ($Config.PSObject.Properties.Name -contains "git") { [string]$Config.git.mode } else { "READ_ONLY" }
            git_force_push = if ($Config.PSObject.Properties.Name -contains "git") { [bool]$Config.git.force_push } else { $false }
        }
    }
}

function Get-NormalizedPath([string]$Path) {
    try {
        return ([IO.Path]::GetFullPath($Path)).TrimEnd("\").ToLowerInvariant()
    }
    catch {
        return $Path.TrimEnd("\").ToLowerInvariant()
    }
}

function Convert-ToWslPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $relative = $Matches[2].Replace('\', '/')
        return "/mnt/$drive/$relative"
    }
    throw "O caminho não pode ser convertido para WSL: $Path"
}

function Focus-ExplorerWindow([string]$Path) {
    $target = Get-NormalizedPath $Path

    try {
        $shell = New-Object -ComObject Shell.Application
        foreach ($window in @($shell.Windows())) {
            try {
                if (-not $window.Document -or -not $window.Document.Folder) { continue }
                $windowPath = [string]$window.Document.Folder.Self.Path
                if (-not $windowPath) { continue }

                if ((Get-NormalizedPath $windowPath) -eq $target) {
                    $hwnd = [IntPtr][int64]$window.HWND
                    [void][ASCALPI.NativeWindow]::ShowWindowAsync($hwnd, 9)
                    [void][ASCALPI.NativeWindow]::BringWindowToTop($hwnd)
                    [void][ASCALPI.NativeWindow]::SetForegroundWindow($hwnd)
                    return $true
                }
            }
            catch {
            }
        }
    }
    catch {
    }

    return $false
}

function Open-FolderFocused([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Pasta ausente: $Path"
    }

    if (Focus-ExplorerWindow $Path) {
        return "FOCUSED_EXISTING"
    }

    Start-Process -FilePath "explorer.exe" -ArgumentList @("`"$Path`"")

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 100
        if (Focus-ExplorerWindow $Path) {
            return "OPENED_AND_FOCUSED"
        }
    }

    return "OPENED"
}

function Resolve-ExistingDirectory([string]$Path, [string]$Label = "Diretório") {
    $candidate = ([string]$Path).Trim()
    if (-not $candidate) {
        throw "$Label não informado."
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw "$Label não localizado: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
}

function Open-GitTerminal([string]$RepositoryRoot) {
    $root = Resolve-ExistingDirectory -Path $RepositoryRoot -Label "Repositório Git"
    $powerShell = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if (-not $powerShell) {
        throw "Windows PowerShell não localizado."
    }

    # The repository path is passed through WorkingDirectory, never embedded in
    # the command string. This preserves spaces and prevents quoting failures.
    Start-Process `
        -FilePath $powerShell.Source `
        -WorkingDirectory $root `
        -WindowStyle Normal `
        -ArgumentList @("-NoLogo", "-NoProfile", "-NoExit", "-Command", "git status")

    Write-Event "GIT_TERMINAL_OPEN_REQUEST" "Git" "REQUESTED" $root
    return $root
}

function Run-Action($Body) {
    $action = [string]$Body.action
    switch ($action) {
        "linux.open" {
            if (-not (Test-Path -LiteralPath ([string]$Config.linux_launcher) -PathType Leaf)) {
                throw "Launcher Linux ausente: " + [string]$Config.linux_launcher
            }

            try {
                $linuxLauncherWsl = Convert-ToWslPath ([string]$Config.linux_launcher)
                $distribution = [string]$Config.wsl_distribution
                $arguments = '-d ' + $distribution + ' -- bash "' + $linuxLauncherWsl + '"'
                $process = Start-HiddenProcess -FileName "wsl.exe" -Arguments $arguments

                $detail = $linuxLauncherWsl
                if ($null -ne $process) {
                    $detail += " | launcher_pid=" + [string]$process.Id
                }

                Write-Event "LINUX_OPEN_REQUEST" "1-Dev" "REQUESTED" $detail
                return @{
                    ok = $true
                    message = "Inicialização do ambiente Linux solicitada."
                    refresh = $true
                }
            }
            catch {
                Write-Event "LINUX_OPEN_REQUEST" "1-Dev" "FAIL" $_.Exception.Message
                throw
            }
        }
        "linux.folder" {
            $focus = Open-FolderFocused ([string]$Config.linux_root)
            return @{ ok=$true; message=("Diretório 1-Dev: " + $focus); refresh=$false }
        }
        "gitmain.openSystem" {
            if (-not (Test-Path -LiteralPath ([string]$Config.git_main_bootstrap))){ throw "Bootstrap Git_Main ausente." }
            $args = '--master "' + [string]$Config.git_main_system + '" --open-master'
            Start-Process -FilePath ([string]$Config.git_main_bootstrap) -ArgumentList $args -WorkingDirectory ([string]$Config.git_main_system)
            Write-Event "GITMAIN_SYSTEM_OPEN_REQUEST" "3-Git_Main" "REQUESTED" $args
            return @{ ok=$true; message="Abertura do sistema de homologação solicitada." }
        }
        "gitmain.openAdmin" {
            if (-not (Test-Path -LiteralPath ([string]$Config.git_main_bootstrap))){ throw "Bootstrap Git_Main ausente." }
            $args = '--master "' + [string]$Config.git_main_system + '"'
            Start-Process -FilePath ([string]$Config.git_main_bootstrap) -ArgumentList $args -WorkingDirectory ([string]$Config.git_main_system)
            Write-Event "GITMAIN_ADMIN_OPEN_REQUEST" "3-Git_Main" "REQUESTED" $args
            return @{ ok=$true; message="Gerenciador da instalação solicitado." }
        }
        "gitmain.folder" {
            $focus = Open-FolderFocused ([string]$Config.git_main_root)
            return @{ ok=$true; message=("Diretório Git_Main: " + $focus); refresh=$false }
        }
        "wsl.terminal" {
            # ASCALPI_LINUX_MENU_R2
            $menuWindows = Join-Path ([string]$Config.linux_root) "SM_Repo\Tools\Linux\ASCALPI-LINUX-MENU.sh"

            if (-not (Test-Path -LiteralPath $menuWindows -PathType Leaf)) {
                throw "Menu Linux ausente: $menuWindows"
            }

            $menuWsl = Convert-ToWslPath $menuWindows
            $distribution = [string]$Config.wsl_distribution

            if ([string]::IsNullOrWhiteSpace($distribution)) {
                throw "Distribuicao WSL nao configurada."
            }

            if ($distribution.Contains('"') -or $menuWsl.Contains('"')) {
                throw "Argumento inseguro para abertura do Terminal Linux."
            }

            $powerShell = Get-Command powershell.exe -ErrorAction SilentlyContinue

            if ($null -eq $powerShell) {
                throw "Windows PowerShell nao localizado para hospedar o Terminal Linux."
            }

            $safeDistribution = $distribution.Replace("'", "''")
            $safeMenuWsl = $menuWsl.Replace("'", "''")
            $terminalCommand = (
                # ASCALPI_LINUX_VISIBLE_CONSOLE_R2
                '$Host.UI.RawUI.WindowTitle = ''ASCALPI - Terminal Linux''; ' +
                '& "$env:SystemRoot\System32\wsl.exe" -d ''' +
                $safeDistribution +
                ''' -- bash ''' +
                $safeMenuWsl +
                ''''
            )
            $encodedCommand = [Convert]::ToBase64String(
                [Text.Encoding]::Unicode.GetBytes($terminalCommand)
            )

            $process = Start-Process `
                -FilePath $powerShell.Source `
                -ArgumentList @(
                    "-NoLogo",
                    "-NoProfile",
                    "-NoExit",
                    "-EncodedCommand",
                    $encodedCommand
                ) `
                -WindowStyle Normal `
                -PassThru

            $detail = $menuWsl

            if ($null -ne $process) {
                $detail += " | process_id=" + [string]$process.Id
            }

            Write-Event "LINUX_TERMINAL_MENU_OPEN_REQUEST" "1-Dev" "REQUESTED" $detail

            return @{
                ok = $true
                message = "Terminal Linux ASCALPI aberto."
                refresh = $false
                process_id = if ($null -ne $process) { [int]$process.Id } else { 0 }
                terminal_host = "Windows PowerShell"
            }
        }
        "docs.folder" {
            $focus = Open-FolderFocused ([string]$Config.docs_root)
            return @{ ok=$true; message=("5-Docs: " + $focus); refresh=$false }
        }
        "docs.engineFolder" {
            $focus = Open-FolderFocused (Join-Path ([string]$Config.control_root) "Documentation")
            return @{ ok=$true; message=("Documentation Engine: " + $focus); refresh=$false }
        }
        "logs.folder" {
            $focus = Open-FolderFocused ([string]$Config.evidence_root)
            return @{ ok=$true; message=("Diretório de evidências: " + $focus); refresh=$false }
        }
        "logs.load" {
            $lines = @()
            if (Test-Path -LiteralPath $EventFile -PathType Leaf) {
                $lines = @(Get-Content -LiteralPath $EventFile -Tail 40 -ErrorAction SilentlyContinue)
            }
            return @{ ok=$true; message="Eventos recentes carregados."; refresh=$false; lines=$lines }
        }
        "git.folder" {
            $root = Find-GitRoot
            if (-not $root) { throw "Repositório Git local não identificado." }
            $focus = Open-FolderFocused $root
            return @{ ok=$true; message=("Repositório: " + $focus); refresh=$false }
        }
        "git.terminal" {
            $root = Find-GitRoot
            if (-not $root) { throw "Repositório Git local não identificado." }
            $openedRoot = Open-GitTerminal $root
            return @{ ok=$true; message=("Terminal Git aberto em: " + $openedRoot); refresh=$false }
        }
        "status.refresh" { return @{ ok=$true; message="Status atualizado." } }
        default { throw "Ação não habilitada: $action" }
    }
}

function Get-Mime([string]$Path) {
    switch ([IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".html" { "text/html; charset=utf-8" }
        ".css" { "text/css; charset=utf-8" }
        ".js" { "application/javascript; charset=utf-8" }
        ".json" { "application/json; charset=utf-8" }
        default { "application/octet-stream" }
    }
}

function Write-HttpResponse($Stream, [int]$StatusCode, [string]$ContentType, [byte[]]$Body) {
    $statusText = if ($StatusCode -eq 200) { "OK" } elseif ($StatusCode -eq 404) { "Not Found" } else { "Error" }
    $header = "HTTP/1.1 $StatusCode $statusText`r`nContent-Type: $ContentType`r`nContent-Length: $($Body.Length)`r`nConnection: close`r`nCache-Control: no-store`r`n`r`n"
    $headerBytes = [Text.Encoding]::ASCII.GetBytes($header)
    $Stream.Write($headerBytes, 0, $headerBytes.Length)
    if ($Body.Length -gt 0) { $Stream.Write($Body, 0, $Body.Length) }
    $Stream.Flush()
}

function Read-Request($Stream) {
    $reader = New-Object IO.StreamReader($Stream, [Text.Encoding]::ASCII, $false, 4096, $true)
    $requestLine = $reader.ReadLine()
    if (-not $requestLine) { return $null }
    $headers = @{}
    while ($true) {
        $line = $reader.ReadLine()
        if ($null -eq $line -or $line -eq "") { break }
        $idx = $line.IndexOf(":")
        if ($idx -gt 0) { $headers[$line.Substring(0,$idx).Trim().ToLowerInvariant()] = $line.Substring($idx+1).Trim() }
    }
    $parts = $requestLine.Split(" ")
    $method = $parts[0]
    $path = $parts[1]
    $body = ""
    $len = 0
    if ($headers.ContainsKey("content-length")) { [void][int]::TryParse($headers["content-length"], [ref]$len) }
    if ($len -gt 0) {
        $chars = New-Object char[] $len
        $read = 0
        while ($read -lt $len) {
            $n = $reader.Read($chars, $read, $len - $read)
            if ($n -le 0) { break }
            $read += $n
        }
        $body = -join $chars[0..($read-1)]
    }
    return [pscustomobject]@{ method=$method; path=$path; body=$body }
}

# Find a free localhost port.
$Listener = $null
$Port = 0
for ($p = $StartPort; $p -le ($StartPort + 30); $p++) {
    try {
        $candidate = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $p)
        $candidate.Start()
        $Listener = $candidate
        $Port = $p
        break
    } catch {}
}
if (-not $Listener) { throw "Nenhuma porta local livre encontrada." }

$runtime = [ordered]@{
    pid = $PID
    port = $Port
    started_at = [DateTimeOffset]::Now.ToString("o")
    url = "http://127.0.0.1:$Port/"
}
Write-Utf8NoBom $RuntimeFile (($runtime | ConvertTo-Json -Depth 5) + [Environment]::NewLine)
Write-Event "PANEL_SERVER_START" "ASCALPI CONTROL CENTER" "PASS" ("PORT="+$Port)

$script:StopServer = $false
$lastRequest = Get-Date

try {
    while (-not $script:StopServer) {
        if (-not $Listener.Pending()) {
            Start-Sleep -Milliseconds 80
            continue
        }
        $client = $Listener.AcceptTcpClient()
        $lastRequest = Get-Date
        try {
            $stream = $client.GetStream()
            $req = Read-Request $stream
            if ($null -eq $req) { continue }

            if ($req.path -eq "/api/status" -and $req.method -eq "GET") {
                $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-JsonText (Get-PanelStatus)))
                Write-HttpResponse $stream 200 "application/json; charset=utf-8" $bytes
            }
            elseif ($req.path -eq "/api/action" -and $req.method -eq "POST") {
                try {
                    $body = $req.body | ConvertFrom-Json
                    $result = Run-Action $body
                    $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-JsonText $result))
                    Write-HttpResponse $stream 200 "application/json; charset=utf-8" $bytes
                } catch {
                    Write-Event "PANEL_ACTION_ERROR" "API" "FAIL" $_.Exception.Message
                    $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-JsonText @{ ok=$false; error=$_.Exception.Message }))
                    Write-HttpResponse $stream 500 "application/json; charset=utf-8" $bytes
                }
            }
            elseif ($req.path -eq "/api/shutdown" -and $req.method -eq "POST") {
                $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-JsonText @{ ok=$true; message="Encerrando ASCALPI Control Center." }))
                Write-HttpResponse $stream 200 "application/json; charset=utf-8" $bytes
                Write-Event "PANEL_SHUTDOWN_REQUEST" "ASCALPI CONTROL CENTER" "PASS" ""
                $script:StopServer = $true
            }
            else {
                $relative = if ($req.path -eq "/") { "index.html" } else { $req.path.TrimStart("/") }
                if ($relative -notin @("index.html","styles.css","app.js")) {
                    $bytes = [Text.Encoding]::UTF8.GetBytes("Not Found")
                    Write-HttpResponse $stream 404 "text/plain; charset=utf-8" $bytes
                } else {
                    $filePath = Join-Path (Join-Path $BasePath "UI") $relative
                    if (Test-Path -LiteralPath $filePath -PathType Leaf) {
                        $bytes = [IO.File]::ReadAllBytes($filePath)
                        Write-HttpResponse $stream 200 (Get-Mime $filePath) $bytes
                    } else {
                        $bytes = [Text.Encoding]::UTF8.GetBytes("Not Found")
                        Write-HttpResponse $stream 404 "text/plain; charset=utf-8" $bytes
                    }
                }
            }
        } finally {
            $client.Close()
        }
    }
}
finally {
    try { $Listener.Stop() } catch {}
    try { Remove-Item -LiteralPath $RuntimeFile -Force -ErrorAction SilentlyContinue } catch {}
    Write-Event "PANEL_SERVER_STOP" "ASCALPI CONTROL CENTER" "PASS" ""
}
