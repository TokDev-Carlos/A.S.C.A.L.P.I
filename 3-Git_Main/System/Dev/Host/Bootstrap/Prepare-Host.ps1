param(
    [Parameter(Mandatory=$true)][string]$Root,
    [string]$SdkVersion = "10.0.400"
)
# CJL System - Base 5 - build transacional do Host .NET
# Compativel com Windows PowerShell 5.1.
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Now-SaoPaulo {
    try {
        $tz = [TimeZoneInfo]::FindSystemTimeZoneById('E. South America Standard Time')
        return [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow,$tz)
    } catch {
        return [DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(-3))
    }
}

$Root = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($Root)).TrimEnd('\')
$App = Join-Path $Root "App"
$Source = Join-Path $Root "Dev\Host"
$Bin = Join-Path $Root "Host\Bin"
$LogRoot = Join-Path $Root "Logs\Bootstrap"
$Python = Join-Path $Root "Runtime\Python\python.exe"
$Bridge = Join-Path $Root "Host\Bridge\host_bridge.py"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$RunId = (Now-SaoPaulo).ToString("yyyyMMdd_HHmmss") + "_" + ([Guid]::NewGuid().ToString("N").Substring(0,8).ToUpperInvariant())
$Log = Join-Path $LogRoot ("host_build_{0}.log" -f $RunId)

function To-Ascii([string]$Text) {
    if ($null -eq $Text) { return "" }
    $normalized = $Text.Normalize([System.Text.NormalizationForm]::FormD)
    $builder = New-Object System.Text.StringBuilder
    foreach ($ch in $normalized.ToCharArray()) {
        $category = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch)
        if ($category -eq [System.Globalization.UnicodeCategory]::NonSpacingMark) { continue }
        $code = [int][char]$ch
        if ($code -eq 9 -or ($code -ge 32 -and $code -le 126)) { [void]$builder.Append($ch) } else { [void]$builder.Append('?') }
    }
    return $builder.ToString()
}
function Log([string]$Text) {
    $safe = To-Ascii $Text
    $line = "[{0}] {1}" -f (Now-SaoPaulo).ToString("yyyy-MM-dd HH:mm:ss.fff zzz"),$safe
    [IO.File]::AppendAllText($Log,$line+[Environment]::NewLine,[System.Text.Encoding]::ASCII)
    Write-Host $line
}
function Fail([string]$Text) { Log ("FALHA: " + $Text); throw $Text }
function Invoke-NativeLogged([string]$File,[object[]]$Arguments) {
    $previous=$ErrorActionPreference; $output=@(); $code=9009
    try { $ErrorActionPreference="Continue"; $output=@(& $File @Arguments 2>&1); $code=[int]$LASTEXITCODE }
    finally { $ErrorActionPreference=$previous }
    foreach($line in $output){ Log ([string]$line) }
    return $code
}
function Sha([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function WriteUtf8([string]$Path,[string]$Text) { [IO.File]::WriteAllText($Path,$Text,(New-Object System.Text.UTF8Encoding($false))) }

function Get-SourceTreeHash {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $rows = New-Object System.Collections.Generic.List[string]
        foreach ($item in (Get-ChildItem -LiteralPath $Source -File -Recurse)) {
            $rel = $item.FullName.Substring($Source.Length).TrimStart('\').Replace('\','/')
            $parts = $rel.Split('/')
            if ($parts -contains 'bin' -or $parts -contains 'obj') { continue }
            if ($item.Name -like 'host-build*') { continue }
            if ($rel -match 'Bin\.Novo\.|Bin\.Anterior\.') { continue }
            $rows.Add($rel + "`n" + (Sha $item.FullName) + "`n")
        }
        $ordered = @($rows.ToArray())
        [Array]::Sort($ordered, [StringComparer]::Ordinal)
        $text = [string]::Join('',[string[]]$ordered)
        $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

function Find-DotNet {
    $candidates = New-Object System.Collections.Generic.List[string]
    $cmd = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $candidates.Add([string]$cmd.Source) }
    if ($env:DOTNET_ROOT) { $candidates.Add((Join-Path $env:DOTNET_ROOT 'dotnet.exe')) }
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles 'dotnet\dotnet.exe')) }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $sdks = & $candidate --list-sdks 2>$null
        if ($sdks -match ('(?m)^' + [regex]::Escape($SdkVersion) + '\s')) { return $candidate }
    }
    return $null
}

function Install-PrivateDotNet([string]$TempRoot) {
    $sdkRoot = Join-Path $TempRoot 'dotnet'
    $installer = Join-Path $TempRoot 'dotnet-install.ps1'
    Log "SDK .NET $SdkVersion nao encontrado. Baixando SDK privado temporario oficial."
    Invoke-WebRequest -UseBasicParsing -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile $installer
    $code=Invoke-NativeLogged "powershell.exe" @("-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",$installer,"-Version",$SdkVersion,"-InstallDir",$sdkRoot,"-Architecture","x64","-NoPath")
    if ($code -ne 0) { Fail "Falha ao instalar SDK .NET privado." }
    $dotnet = Join-Path $sdkRoot 'dotnet.exe'
    if (-not (Test-Path -LiteralPath $dotnet)) { Fail "dotnet.exe privado nao foi criado." }
    return $dotnet
}

function Validate-Root {
    foreach ($required in @(
        (Join-Path $App 'Config\master.id'),
        (Join-Path $App 'Config\sistema.json'),
        $Python,
        $Bridge,
        (Join-Path $Source 'Directory.Build.props')
    )) { if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { Fail "Pre-requisito ausente: $required" } }
}

function Clean-BuildResidue {
    $src = Join-Path $Source 'src'
    if (-not (Test-Path -LiteralPath $src)) { return }
    Get-ChildItem -LiteralPath $src -Directory | ForEach-Object {
        foreach ($n in @('bin','obj')) { $p=Join-Path $_.FullName $n; if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue } }
    }
}

$TempRoot = Join-Path $env:TEMP ('cjl-host-v5-' + [Guid]::NewGuid().ToString('N'))
$Published = Join-Path $TempRoot 'published'
$NewBin = Join-Path $TempRoot 'Bin.Novo'
$CommitStage = Join-Path (Split-Path -Parent $Bin) ('Bin.Novo.'+$RunId)
$Backup = Join-Path (Split-Path -Parent $Bin) ('Bin.Anterior.'+$RunId)
New-Item -ItemType Directory -Force -Path $TempRoot,$Published,$NewBin | Out-Null

try {
    Validate-Root
    Clean-BuildResidue
    Log "Validando Base 5 antes do build do Host."
    $PreHost = Join-Path $Root 'Dev\Tools\pre_host_validate.py'
    if (-not (Test-Path -LiteralPath $PreHost -PathType Leaf)) { Fail "pre_host_validate.py ausente." }
    $code=Invoke-NativeLogged $Python @("-B","-I","-S",$PreHost,"--root",$Root)
    if ($code -ne 0) { Fail "Base 5 nao passou na pre-validacao do Host." }

    $dotnet = Find-DotNet
    if (-not $dotnet) { $dotnet = Install-PrivateDotNet $TempRoot }
    Log "Compilador: $dotnet"
    $projects = @('CJL.Bootstrap','CJL.Setup','CJL.Host','CJL.Updater','CJL.Uninstall')
    foreach ($name in $projects) {
        $project = Join-Path $Source ("src\$name\$name.csproj")
        $out = Join-Path $Published $name
        if (-not (Test-Path -LiteralPath $project)) { Fail "Projeto ausente: $project" }
        Log "RESTORE $name"
        $code=Invoke-NativeLogged $dotnet @("restore",$project,"-r","win-x64","--nologo","--verbosity","minimal")
        if ($code -ne 0) { Fail "Restore falhou em $name." }
        Log "PUBLISH $name"
        $code=Invoke-NativeLogged $dotnet @("publish",$project,"-c","Release","-r","win-x64","--self-contained","true","--no-restore","-o",$out,"-p:PublishSingleFile=true","-p:Deterministic=true","-p:ContinuousIntegrationBuild=true")
        if ($code -ne 0) { Fail "Publish falhou em $name." }
        $exe = Join-Path $out ($name+'.exe')
        if (-not (Test-Path -LiteralPath $exe)) { Fail "Executavel nao gerado: $exe" }
        Copy-Item -LiteralPath $exe -Destination (Join-Path $NewBin ($name+'.exe')) -Force
    }

    $files = [ordered]@{}
    Get-ChildItem -LiteralPath $NewBin -File | Sort-Object Name | ForEach-Object { $files[$_.Name] = Sha $_.FullName }
    $sourceHash = Get-SourceTreeHash
    $meta = [ordered]@{
        format=5; product='CJL System'; host_contract='1'; framework='.NET 10'; sdk=$SdkVersion; architecture='win-x64'; self_contained=$true;
        webview2_package='1.0.4129.50'; build_mode='base5_sm_repo';
                source_tree_sha256=$sourceHash; built_at=(Now-SaoPaulo).ToString('o'); timezone='America/Sao_Paulo'; build_log=$Log; files=$files
    }
    WriteUtf8 (Join-Path $NewBin 'host-build.json') (($meta | ConvertTo-Json -Depth 8)+[Environment]::NewLine)
    Log "Source tree SHA-256: $sourceHash"

    Log "SELFTEST Bootstrap candidato"
    $code=Invoke-NativeLogged (Join-Path $NewBin 'CJL.Bootstrap.exe') @("--self-test","--master",$Root,"--host-bin",$NewBin)
    if ($code -ne 0) { Fail "Bootstrap candidato falhou no self-test." }
    Log "SELFTEST Host candidato"
    $code=Invoke-NativeLogged (Join-Path $NewBin 'CJL.Host.exe') @("--self-test","--master",$Root,"--direct-master")
    if ($code -ne 0) { Fail "Host candidato falhou no self-test." }

    if (Test-Path -LiteralPath $CommitStage) { Remove-Item -LiteralPath $CommitStage -Recurse -Force }
    Copy-Item -LiteralPath $NewBin -Destination $CommitStage -Recurse
    if (Test-Path -LiteralPath $Bin) { Move-Item -LiteralPath $Bin -Destination $Backup }
    try {
        Move-Item -LiteralPath $CommitStage -Destination $Bin
        if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force }
    }
    catch {
        if (-not (Test-Path -LiteralPath $Bin) -and (Test-Path -LiteralPath $Backup)) { Move-Item -LiteralPath $Backup -Destination $Bin }
        throw
    }
    $LauncherProject = Join-Path $Source 'src\CJL.Launcher\CJL.Launcher.csproj'
    $LauncherOut = Join-Path $Published 'CJL.Launcher'
    Log "RESTORE CJL.Launcher"
    $code=Invoke-NativeLogged $dotnet @("restore",$LauncherProject,"-r","win-x64","--nologo","--verbosity","minimal")
    if ($code -ne 0) { Fail "Restore falhou em CJL.Launcher." }
    Log "PUBLISH CJL.Launcher"
    $code=Invoke-NativeLogged $dotnet @("publish",$LauncherProject,"-c","Release","-r","win-x64","--self-contained","true","--no-restore","-o",$LauncherOut,"-p:PublishSingleFile=true","-p:Deterministic=true","-p:ContinuousIntegrationBuild=true")
    if ($code -ne 0) { Fail "Publish falhou em CJL.Launcher." }
    $LauncherCandidate=Join-Path $LauncherOut 'CJL.exe'
    if (-not (Test-Path -LiteralPath $LauncherCandidate -PathType Leaf)) { Fail "CJL.exe nao foi gerado." }
    $LauncherBinary=Join-Path $Root 'CJL.exe'
    Copy-Item -LiteralPath $LauncherCandidate -Destination $LauncherBinary -Force
    $launcherMeta=[ordered]@{format=2;product='CJL System';host_contract='1';binary='CJL.exe';binary_sha256=(Sha $LauncherBinary);created_at=(Now-SaoPaulo).ToString('o');timezone='America/Sao_Paulo';note='Launcher publico Base 5 vinculado ao Host Contract.'}
    WriteUtf8 (Join-Path $Root 'Host\launcher-build.json') (($launcherMeta|ConvertTo-Json -Depth 8)+[Environment]::NewLine)
    Log "CJL.exe vinculado por SHA-256 ao Host Contract."
    Log "Host .NET Base 5 preparado e promovido com sucesso."
    exit 0
}
catch {
    Log ("FALHA FINAL: " + $_.Exception.Message)
    Write-Host "LOG: $Log" -ForegroundColor Yellow
    exit 1
}
finally {
    Clean-BuildResidue
    if (Test-Path -LiteralPath $TempRoot) { Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
