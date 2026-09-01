[CmdletBinding()]
param([string]$ControlRoot, [string]$DocsRoot, [switch]$InteractiveOperator)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
if (-not $InteractiveOperator -or -not [Environment]::UserInteractive) { throw 'REBASELINE_DENIED: interactive Operator route required.' }
$paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
Test-CJLPolicyIntegrity -Paths $paths | Out-Null
$first = Read-Host 'Type AUTHORIZE STATIC DOCUMENT REVIEW'
if ($first -ne 'AUTHORIZE STATIC DOCUMENT REVIEW') { throw 'REBASELINE_CANCELLED' }
$baseline = Get-Content -Raw -LiteralPath (Join-Path $paths.State 'STATIC_BASELINE.json') | ConvertFrom-Json
$changes = @()
foreach ($item in @($baseline.files)) {
    $path = Join-Path $paths.Docs ([string]$item.filename)
    $actual = if (Test-Path -LiteralPath $path -PathType Leaf) { Get-CJLSha256 -Path $path } else { 'MISSING' }
    if ($actual -ne [string]$item.sha256) { $changes += "$($item.filename): $($item.sha256) -> $actual" }
}
$changes | ForEach-Object { Write-Host $_ }
$second = Read-Host 'Type ACCEPT NEW STATIC BASELINE'
if ($second -ne 'ACCEPT NEW STATIC BASELINE') { throw 'REBASELINE_CANCELLED' }
$stamp = (Get-CJLNow).ToString('yyyyMMddTHHmmssfff') + '_STATIC_REBASELINE'
$evidence = Join-Path $paths.Evidence $stamp
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
[System.IO.File]::Copy((Join-Path $paths.State 'STATIC_BASELINE.json'), (Join-Path $evidence 'STATIC_BASELINE.before.json'), $true)
& (Join-Path $PSScriptRoot 'Protect-StaticDocuments.ps1') -ControlRoot $paths.Control -DocsRoot $paths.Docs
Write-CJLJson -Path (Join-Path $evidence 'receipt.json') -Value ([ordered]@{ timestamp_sp=(Get-CJLNow).ToString('o'); changes=$changes; result='PASS' })
Write-Host 'STATIC_REBASELINE=PASS'
