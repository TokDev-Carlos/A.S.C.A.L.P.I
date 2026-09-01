[CmdletBinding()]
param([string]$ControlRoot, [string]$DocsRoot)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
Test-CJLPolicyIntegrity -Paths $paths | Out-Null
$files = @()
foreach ($item in @(Get-ChildItem -LiteralPath $paths.Docs -Filter '*.md' -File | Sort-Object Name)) {
    if (@('Black_Book.md','White_Book.md') -contains $item.Name) { continue }
    $files += [ordered]@{ filename=$item.Name; sha256=Get-CJLSha256 -Path $item.FullName; original_attributes=[string]$item.Attributes }
    $item.IsReadOnly = $true
}
$baseline = [ordered]@{ created_at_sp=(Get-CJLNow).ToString('o'); docs_root=$paths.Docs; files=$files }
Write-CJLJson -Path (Join-Path $paths.State 'STATIC_BASELINE.json') -Value $baseline
Write-Host 'STATIC_DOC_PROTECTION=PASS'
