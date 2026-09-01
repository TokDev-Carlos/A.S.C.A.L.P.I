[CmdletBinding()]
param(
    [string]$ControlRoot, [string]$DocsRoot,
    [Parameter(Mandatory=$true)][string]$Type,
    [Parameter(Mandatory=$true)][string]$Status,
    [Parameter(Mandatory=$true)][string]$Severity,
    [Parameter(Mandatory=$true)][string]$Stage,
    [Parameter(Mandatory=$true)][string]$Component,
    [Parameter(Mandatory=$true)][string]$Summary,
    [Parameter(Mandatory=$true)][string]$CauseClass,
    [Parameter(Mandatory=$true)][string]$CycleId,
    [string]$CorrelationId, [string]$Action, [string]$Details,
    [string[]]$Evidence=@(), [string]$SourceCommit, [string]$SourceBranch,
    [switch]$ReusableKnowledge, [string]$KnowledgeTitle,
    [string]$ValidatedRule, [string]$Limitation, [string]$RelatedFailureId,
    [string]$EventId
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
Test-CJLPolicyIntegrity -Paths $paths | Out-Null
Test-CJLStaticIntegrity -Paths $paths | Out-Null
if ([string]::IsNullOrWhiteSpace($EventId)) { $EventId = 'EVT-' + [guid]::NewGuid().ToString('N') }
$event = [ordered]@{
    event_id=$EventId; timestamp_sp=(Get-CJLNow).ToString('o'); cycle_id=$CycleId; correlation_id=$CorrelationId
    type=$Type; status=$Status; severity=$Severity; stage=$Stage; component=$Component; action=$Action
    summary=$Summary; details=$Details; cause_class=$CauseClass; evidence=@($Evidence)
    source_commit=$SourceCommit; source_branch=$SourceBranch; reusable_knowledge=[bool]$ReusableKnowledge
    knowledge_title=$KnowledgeTitle; validated_rule=$ValidatedRule; limitation=$Limitation; related_failure_id=$RelatedFailureId
}
$eventObject = [pscustomobject]$event
Test-CJLEvent -Event $eventObject | Out-Null
$mutexName = Get-CJLMutexName -ControlRoot $paths.Control -Purpose 'EVENT_APPEND'
Invoke-CJLMutex -Name $mutexName -Body { Add-CJLJsonLine -Path (Join-Path $paths.State 'events.jsonl') -Value $eventObject }
& (Join-Path $PSScriptRoot 'Process-CJLEvents.ps1') -ControlRoot $paths.Control -DocsRoot $paths.Docs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ('EVENT_ID=' + $EventId)
exit 0
