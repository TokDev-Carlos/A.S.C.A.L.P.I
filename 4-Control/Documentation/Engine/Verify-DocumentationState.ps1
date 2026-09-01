[CmdletBinding()]
param([string]$ControlRoot, [string]$DocsRoot)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
try {
    $paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
    Test-CJLPolicyIntegrity -Paths $paths | Out-Null
    Test-CJLStaticIntegrity -Paths $paths | Out-Null
    Write-Host 'POLICY_INTEGRITY=PASS'
    Write-Host 'STATIC_DOC_PROTECTION=PASS'
    exit 0
}
catch { Write-Host $_.Exception.Message; Write-Host 'VERIFICATION=FAIL'; exit 2 }
