[CmdletBinding()]
param(
    [string]$ControlRoot,
    [string]$DocsRoot,
    [Parameter(Mandatory=$true)][string]$CycleId,
    [Parameter(Mandatory=$true)][string[]]$ChangedBooks
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
Test-CJLPolicyIntegrity -Paths $paths | Out-Null
$policy = Get-Content -Raw -LiteralPath (Join-Path $paths.Policy 'DOCUMENT_POLICY.json') | ConvertFrom-Json
$books = @()
foreach ($name in $ChangedBooks) {
    $path = Join-Path $paths.Docs $name
    $sourcePath = if ($name -eq 'Black_Book.md') { [string]$policy.remote_book_sync.current_reference_only.black_book_path } else { [string]$policy.remote_book_sync.current_reference_only.white_book_path }
    $books += [ordered]@{ filename=$name; local_sha256=Get-CJLSha256 -Path $path; repository=[string]$policy.remote_book_sync.current_reference_only.repository; branch=[string]$policy.remote_book_sync.current_reference_only.branch; intended_path=$sourcePath }
}
$record = [ordered]@{ timestamp_sp=(Get-CJLNow).ToString('o'); cycle_id=$CycleId; books=$books; status='WAITING_FOR_OPERATOR_GIT_CLEANUP' }
$mutexName = Get-CJLMutexName -ControlRoot $paths.Control -Purpose 'SYNC'
Invoke-CJLMutex -Name $mutexName -Body { Add-CJLJsonLine -Path (Join-Path $paths.State 'pending-sync.jsonl') -Value $record }
Write-Host 'REMOTE_BOOK_SYNC=QUEUE_ONLY'
