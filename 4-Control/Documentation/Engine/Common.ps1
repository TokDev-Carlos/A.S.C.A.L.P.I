Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-CJLPaths {
    param([string]$ControlRoot, [string]$DocsRoot)
    if ([string]::IsNullOrWhiteSpace($ControlRoot)) {
        $ControlRoot = Split-Path -Parent $PSScriptRoot
    }
    $ControlRoot = [System.IO.Path]::GetFullPath($ControlRoot)
    $policyPath = Join-Path $ControlRoot 'Policy\DOCUMENT_POLICY.json'
    if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
        throw "DOCUMENT_POLICY missing: $policyPath"
    }
    $policy = Get-Content -Raw -LiteralPath $policyPath | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($DocsRoot)) { $DocsRoot = [string]$policy.roots.docs_root }
    [pscustomobject]@{
        Control = $ControlRoot
        Policy = Join-Path $ControlRoot 'Policy'
        Engine = Join-Path $ControlRoot 'Engine'
        State = Join-Path $ControlRoot 'State'
        Docs = [System.IO.Path]::GetFullPath($DocsRoot)
        Evidence = [string]$policy.roots.evidence_root
    }
}

function Get-CJLSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { $bytes = $sha.ComputeHash($stream) } finally { $sha.Dispose() }
    }
    finally { $stream.Dispose() }
    ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

function Write-CJLUtf8 {
    param([string]$Path, [AllowEmptyString()][string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $temp = Join-Path $parent ('.' + [System.IO.Path]::GetFileName($Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $stream = New-Object System.IO.FileStream($temp, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4096, [System.IO.FileOptions]::WriteThrough)
    try {
        $bytes = $encoding.GetBytes($Text)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally { $stream.Dispose() }
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        $discard = $temp + '.discard'
        [System.IO.File]::Replace($temp, $Path, $discard, $true)
        if (Test-Path -LiteralPath $discard) { Remove-Item -LiteralPath $discard -Force }
    }
    else { [System.IO.File]::Move($temp, $Path) }
}

function Write-CJLJson {
    param([string]$Path, [object]$Value, [switch]$Compact)
    $json = if ($Compact) { $Value | ConvertTo-Json -Depth 12 -Compress } else { $Value | ConvertTo-Json -Depth 12 }
    Write-CJLUtf8 -Path $Path -Text ($json + [Environment]::NewLine)
}

function Add-CJLJsonLine {
    param([string]$Path, [object]$Value)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $stream = New-Object System.IO.FileStream($Path, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read, 4096, [System.IO.FileOptions]::WriteThrough)
    try {
        $writer = New-Object System.IO.StreamWriter($stream, $encoding)
        try {
            $writer.WriteLine(($Value | ConvertTo-Json -Depth 12 -Compress))
            $writer.Flush()
            $stream.Flush($true)
        }
        finally { $writer.Dispose() }
    }
    finally { if ($null -ne $stream) { $stream.Dispose() } }
}

function Get-CJLNow {
    $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById('E. South America Standard Time')
    [System.TimeZoneInfo]::ConvertTime([System.DateTimeOffset]::Now, $tz)
}

function Get-CJLMutexName {
    param([string]$ControlRoot, [string]$Purpose)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($ControlRoot.ToLowerInvariant())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').Substring(0, 16) } finally { $sha.Dispose() }
    'Local\CJL_DOC_' + $Purpose + '_' + $hash
}

function Invoke-CJLMutex {
    param([string]$Name, [scriptblock]$Body, [int]$TimeoutMs = 30000)
    $created = $false
    $mutex = New-Object System.Threading.Mutex($false, $Name, [ref]$created)
    $locked = $false
    try {
        try { $locked = $mutex.WaitOne($TimeoutMs) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
        if (-not $locked) { throw "Mutex timeout: $Name" }
        & $Body
    }
    finally {
        if ($locked) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

function Test-CJLPolicyIntegrity {
    param([object]$Paths)
    $baselinePath = Join-Path $Paths.State 'POLICY_BASELINE.json'
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) { throw 'POLICY_INTEGRITY=FAIL: baseline missing' }
    $baseline = Get-Content -Raw -LiteralPath $baselinePath | ConvertFrom-Json
    foreach ($item in @($baseline.files)) {
        $path = Join-Path $Paths.Control ([string]$item.path)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "POLICY_INTEGRITY=FAIL: missing $($item.path)" }
        if ((Get-CJLSha256 -Path $path) -ne [string]$item.sha256) { throw "POLICY_INTEGRITY=FAIL: hash mismatch $($item.path)" }
    }
    $true
}

function Test-CJLStaticIntegrity {
    param([object]$Paths)
    $baselinePath = Join-Path $Paths.State 'STATIC_BASELINE.json'
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) { throw 'STATIC_DOC_PROTECTION=FAIL: baseline missing' }
    $baseline = Get-Content -Raw -LiteralPath $baselinePath | ConvertFrom-Json
    foreach ($item in @($baseline.files)) {
        $path = Join-Path $Paths.Docs ([string]$item.filename)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "STATIC_DOC_PROTECTION=FAIL: missing $($item.filename)" }
        if ((Get-CJLSha256 -Path $path) -ne [string]$item.sha256) { throw "STATIC_DOC_PROTECTION=FAIL: hash mismatch $($item.filename)" }
    }
    $true
}

function Test-CJLEvent {
    param([object]$Event)
    $required = @('event_id','timestamp_sp','cycle_id','type','status','severity','stage','component','summary','cause_class')
    foreach ($name in $required) {
        $property = $Event.PSObject.Properties[$name]
        if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) { throw "EVENT_SCHEMA=FAIL: missing $name" }
    }
    if (@('PASS','FAIL','INFO','PENDING','BLOCK') -notcontains [string]$Event.status) { throw 'EVENT_SCHEMA=FAIL: status' }
    if (@('INFO','WARNING','ERROR','CRITICAL') -notcontains [string]$Event.severity) { throw 'EVENT_SCHEMA=FAIL: severity' }
    if (@('SYSTEM','CONFIGURATION','INTEGRATION','SECURITY','USER_INPUT','EXPECTED_NEGATIVE_TEST','PROCEDURE','UNKNOWN','NOT_APPLICABLE') -notcontains [string]$Event.cause_class) { throw 'EVENT_SCHEMA=FAIL: cause_class' }
    $true
}

function Get-CJLHighestId {
    param([string]$Content, [string]$Prefix)
    $max = 0
    foreach ($match in [regex]::Matches($Content, ([regex]::Escape($Prefix) + '-([0-9]{4,})'))) {
        $number = [int]$match.Groups[1].Value
        if ($number -gt $max) { $max = $number }
    }
    $max
}

function Get-CJLProperty {
    param([object]$Object, [string]$Name, $Default = $null)
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    $property.Value
}

function Set-CJLBookAtomic {
    param([string]$Path, [string]$Content, [string]$ExpectedHeading, [object]$Paths, [string]$CycleId)
    if (-not $Content.StartsWith($ExpectedHeading)) { throw "BOOK_WRITE=FAIL: unexpected heading $Path" }
    $evidenceName = (Get-CJLNow).ToString('yyyyMMddTHHmmssfff') + '_BOOK_UPDATE'
    $evidenceDir = Join-Path $Paths.Evidence $evidenceName
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
    $backup = Join-Path $evidenceDir ([System.IO.Path]::GetFileName($Path) + '.before')
    if (Test-Path -LiteralPath $Path -PathType Leaf) { [System.IO.File]::Copy($Path, $backup, $true) }
    Write-CJLUtf8 -Path $Path -Text $Content
    if (-not ([System.IO.File]::ReadAllText($Path, (New-Object System.Text.UTF8Encoding($false))).StartsWith($ExpectedHeading))) {
        if (Test-Path -LiteralPath $backup) { [System.IO.File]::Copy($backup, $Path, $true) }
        throw 'BOOK_WRITE=FAIL: post-write validation'
    }
    Write-CJLJson -Path (Join-Path $evidenceDir 'receipt.json') -Value ([ordered]@{ timestamp_sp=(Get-CJLNow).ToString('o'); cycle_id=$CycleId; path=$Path; sha256=Get-CJLSha256 -Path $Path })
}

function Read-CJLJsonLines {
    param([string]$Path)
    $items = @()
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $items }
    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        if (-not [string]::IsNullOrWhiteSpace($line)) { $items += ($line | ConvertFrom-Json) }
    }
    $items
}
