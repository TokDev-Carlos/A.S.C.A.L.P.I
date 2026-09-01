[CmdletBinding()]
param([string]$ControlRoot, [string]$DocsRoot)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')

function Save-State {
    param([object]$Paths, [object]$State)
    Write-CJLJson -Path (Join-Path $Paths.State 'document-state.json') -Value $State
}

function Save-Correlations {
    param([object]$Paths, [object[]]$Items)
    $valid = @($Items | Where-Object { $null -ne $_ -and $null -ne $_.PSObject.Properties['correlation_id'] })
    if ($valid.Count -eq 0) {
        Write-CJLUtf8 -Path (Join-Path $Paths.State 'correlation-map.json') -Text ("[]" + [Environment]::NewLine)
    }
    else {
        Write-CJLJson -Path (Join-Path $Paths.State 'correlation-map.json') -Value $valid
    }
}

function New-BlackEntry {
    param([object]$Event, [string]$Id, [string]$Correlation)
    $evidenceText = (@(Get-CJLProperty -Object $Event -Name 'evidence' -Default @()) -join '; ')
    if ([string]::IsNullOrWhiteSpace($evidenceText)) { $evidenceText = 'See event ledger: ' + [string]$Event.event_id }
    $details = [string](Get-CJLProperty -Object $Event -Name 'details' -Default '')
    $lines = @(
        '', ('<!-- CJL:BLACK:{0}:BEGIN -->' -f $Id),
        '===============================================================================',
        ($Id + ' - ' + ([string]$Event.summary).ToUpperInvariant()),
        '===============================================================================', '',
        ('Event ID: ' + [string]$Event.event_id), ('Correlation ID: ' + $Correlation),
        ('Date: ' + [string]$Event.timestamp_sp), ('Area: ' + [string]$Event.component + ' / ' + [string]$Event.stage),
        'Status: OPEN', '', 'Context:', [string]$Event.summary, '',
        'Expected result:', $(if ([string]::IsNullOrWhiteSpace([string](Get-CJLProperty $Event 'action' ''))) { 'Successful completion of the declared action.' } else { [string](Get-CJLProperty $Event 'action' '') }), '',
        'Failed result:', $(if ([string]::IsNullOrWhiteSpace($details)) { [string]$Event.summary } else { $details }), '',
        'Cause:', [string]$Event.cause_class, '', 'Evidence:', $evidenceText, '',
        'Lesson:', 'Pending correction and validated retest.', '',
        ('<!-- CJL:BLACK:{0}:END -->' -f $Id), ''
    )
    $lines -join "`n"
}

function New-WhiteEntry {
    param([object]$Event, [string]$Id, [string]$RelatedFailure)
    $title = [string](Get-CJLProperty $Event 'knowledge_title' '')
    if ([string]::IsNullOrWhiteSpace($title)) { $title = [string]$Event.summary }
    $rule = [string](Get-CJLProperty $Event 'validated_rule' '')
    if ([string]::IsNullOrWhiteSpace($rule)) { $rule = [string]$Event.summary }
    $limitation = [string](Get-CJLProperty $Event 'limitation' '')
    if ([string]::IsNullOrWhiteSpace($limitation)) { $limitation = 'Applies to the validated scope recorded by this event.' }
    $proof = (@(Get-CJLProperty $Event 'evidence' @()) -join '; ')
    if ([string]::IsNullOrWhiteSpace($proof)) { $proof = 'See event ledger: ' + [string]$Event.event_id }
    $lines = @(
        '', ('<!-- CJL:WHITE:{0}:BEGIN -->' -f $Id),
        '===============================================================================',
        ($Id + ' - ' + $title.ToUpperInvariant()),
        '===============================================================================', '',
        ('Event ID: ' + [string]$Event.event_id), ('Date proven: ' + [string]$Event.timestamp_sp),
        'Status: PROVEN', ('Area: ' + [string]$Event.component + ' / ' + [string]$Event.stage),
        ('Related failure: ' + $(if ([string]::IsNullOrWhiteSpace($RelatedFailure)) { 'None' } else { $RelatedFailure })), '',
        'Problem solved:', [string]$Event.summary, '', 'Proven rule:', $rule, '',
        'Proof:', $proof, '', 'Validated use:', [string]$Event.component, '',
        'Limitation:', $limitation, '', ('<!-- CJL:WHITE:{0}:END -->' -f $Id), ''
    )
    $lines -join "`n"
}

function Add-Resolution {
    param([string]$Content, [string]$FailureId, [object]$Event, [string]$WhiteId)
    $end = '<!-- CJL:BLACK:' + $FailureId + ':END -->'
    $position = $Content.IndexOf($end, [System.StringComparison]::Ordinal)
    if ($position -lt 0) { throw "Managed Black block missing for $FailureId" }
    $resolution = @(
        'Resolution / Retest:',
        ('Event ID: ' + [string]$Event.event_id),
        ('Timestamp: ' + [string]$Event.timestamp_sp),
        ('Result: ' + [string]$Event.status),
        ('Details: ' + [string](Get-CJLProperty $Event 'details' ([string]$Event.summary))),
        ('White Book link: ' + $(if ([string]::IsNullOrWhiteSpace($WhiteId)) { 'None' } else { $WhiteId })), ''
    ) -join "`n"
    $Content.Insert($position, $resolution)
}

try {
    $paths = Get-CJLPaths -ControlRoot $ControlRoot -DocsRoot $DocsRoot
    Test-CJLPolicyIntegrity -Paths $paths | Out-Null
    Test-CJLStaticIntegrity -Paths $paths | Out-Null
    $mutexName = Get-CJLMutexName -ControlRoot $paths.Control -Purpose 'PROCESSOR'
    Invoke-CJLMutex -Name $mutexName -TimeoutMs 60000 -Body {
        $rules = Get-Content -Raw -LiteralPath (Join-Path $paths.Policy 'EVENT_RULES.json') | ConvertFrom-Json
        $statePath = Join-Path $paths.State 'document-state.json'
        $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
        $correlationPath = Join-Path $paths.State 'correlation-map.json'
        $correlations = @()
        if (Test-Path -LiteralPath $correlationPath -PathType Leaf) {
            $correlations = @(Get-Content -Raw -LiteralPath $correlationPath | ConvertFrom-Json | Where-Object { $null -ne $_ -and $null -ne $_.PSObject.Properties['correlation_id'] })
        }
        $processedPath = Join-Path $paths.State 'processed-events.jsonl'
        $processedIds = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($record in @(Read-CJLJsonLines -Path $processedPath)) { [void]$processedIds.Add([string]$record.event_id) }
        $events = @(Read-CJLJsonLines -Path (Join-Path $paths.State 'events.jsonl'))
        foreach ($event in $events) {
            Test-CJLEvent -Event $event | Out-Null
            if ($processedIds.Contains([string]$event.event_id)) { continue }
            $classification = 'LEDGER_ONLY'
            $changed = @()
            $failureId = ''
            $whiteId = ''
            $type = [string]$event.type
            $correlation = [string](Get-CJLProperty $event 'correlation_id' '')
            if ([string]::IsNullOrWhiteSpace($correlation)) { $correlation = [string]$event.event_id }
            $openBlack = @($rules.black_open) -contains $type
            if ($type -eq 'AUTH_FAIL') {
                $cause = [string]$event.cause_class
                $openBlack = (@($rules.conditional_black_open.AUTH_FAIL.cause_class_in) -contains $cause) -and -not (@($rules.conditional_black_open.AUTH_FAIL.excluded_cause_class) -contains $cause)
            }
            if ($openBlack) {
                $blackPath = Join-Path $paths.Docs 'Black_Book.md'
                $content = [System.IO.File]::ReadAllText($blackPath, (New-Object System.Text.UTF8Encoding($false)))
                $live = Get-CJLHighestId -Content $content -Prefix 'FAIL'
                if ([int]$state.black_last_id -ne $live) { throw "STATE_CONFLICT: Black state=$($state.black_last_id) live=$live" }
                $next = $live + 1
                $failureId = 'FAIL-' + $next.ToString('0000')
                $updated = $content.TrimEnd("`r","`n") + "`n" + (New-BlackEntry -Event $event -Id $failureId -Correlation $correlation)
                Set-CJLBookAtomic -Path $blackPath -Content $updated -ExpectedHeading '# CJL Black Book - Volume 001' -Paths $paths -CycleId ([string]$event.cycle_id)
                $state.black_last_id = $next
                $correlations += [pscustomobject]@{ correlation_id=$correlation; failure_id=$failureId; status='OPEN' }
                $classification = 'BLACK_OPEN'
                $changed += 'Black_Book.md'
            }
            elseif ($type -eq 'CORRECTION_RETEST_PASS') {
                $match = @($correlations | Where-Object { [string]$_.correlation_id -eq $correlation -and [string]$_.status -eq 'OPEN' } | Select-Object -First 1)
                if ($match.Count -gt 0) {
                    $failureId = [string]$match[0].failure_id
                    $createWhite = [bool](Get-CJLProperty $event 'reusable_knowledge' $false)
                    if ($createWhite) {
                        $whitePath = Join-Path $paths.Docs 'White_Book.md'
                        $whiteContent = [System.IO.File]::ReadAllText($whitePath, (New-Object System.Text.UTF8Encoding($false)))
                        $liveWhite = Get-CJLHighestId -Content $whiteContent -Prefix 'WB'
                        if ([int]$state.white_last_id -ne $liveWhite) { throw "STATE_CONFLICT: White state=$($state.white_last_id) live=$liveWhite" }
                        $nextWhite = $liveWhite + 1
                        $whiteId = 'WB-' + $nextWhite.ToString('0000')
                        $whiteUpdated = $whiteContent.TrimEnd("`r","`n") + "`n" + (New-WhiteEntry -Event $event -Id $whiteId -RelatedFailure $failureId)
                        Set-CJLBookAtomic -Path $whitePath -Content $whiteUpdated -ExpectedHeading '# CJL White Book - Volume 001' -Paths $paths -CycleId ([string]$event.cycle_id)
                        $state.white_last_id = $nextWhite
                        $changed += 'White_Book.md'
                    }
                    $blackPath = Join-Path $paths.Docs 'Black_Book.md'
                    $blackContent = [System.IO.File]::ReadAllText($blackPath, (New-Object System.Text.UTF8Encoding($false)))
                    $blackUpdated = Add-Resolution -Content $blackContent -FailureId $failureId -Event $event -WhiteId $whiteId
                    Set-CJLBookAtomic -Path $blackPath -Content $blackUpdated -ExpectedHeading '# CJL Black Book - Volume 001' -Paths $paths -CycleId ([string]$event.cycle_id)
                    $match[0].status = 'CLOSED'
                    $classification = 'BLACK_LIFECYCLE_CLOSED'
                    $changed += 'Black_Book.md'
                }
                else { $classification = 'LEDGER_ONLY_NO_OPEN_CORRELATION' }
            }
            elseif (@($rules.white_create.PSObject.Properties.Name) -contains $type -and [bool](Get-CJLProperty $event 'reusable_knowledge' $false)) {
                $whitePath = Join-Path $paths.Docs 'White_Book.md'
                $content = [System.IO.File]::ReadAllText($whitePath, (New-Object System.Text.UTF8Encoding($false)))
                $live = Get-CJLHighestId -Content $content -Prefix 'WB'
                if ([int]$state.white_last_id -ne $live) { throw "STATE_CONFLICT: White state=$($state.white_last_id) live=$live" }
                $next = $live + 1
                $whiteId = 'WB-' + $next.ToString('0000')
                $related = [string](Get-CJLProperty $event 'related_failure_id' '')
                $updated = $content.TrimEnd("`r","`n") + "`n" + (New-WhiteEntry -Event $event -Id $whiteId -RelatedFailure $related)
                Set-CJLBookAtomic -Path $whitePath -Content $updated -ExpectedHeading '# CJL White Book - Volume 001' -Paths $paths -CycleId ([string]$event.cycle_id)
                $state.white_last_id = $next
                $classification = 'WHITE_CREATE'
                $changed += 'White_Book.md'
            }
            elseif (-not ((@($rules.black_open) + @($rules.ledger_only_examples) + @('AUTH_FAIL','CORRECTION_RETEST_PASS') + @($rules.white_create.PSObject.Properties.Name)) -contains $type)) {
                $classification = 'LEDGER_ONLY_UNCLASSIFIED'
            }
            if ($changed.Count -gt 0) {
                $changed = @($changed | Select-Object -Unique)
                & (Join-Path $PSScriptRoot 'Queue-BookSync.ps1') -ControlRoot $paths.Control -DocsRoot $paths.Docs -CycleId ([string]$event.cycle_id) -ChangedBooks $changed | Out-Null
            }
            Save-State -Paths $paths -State $state
            Save-Correlations -Paths $paths -Items $correlations
            $record = [ordered]@{ event_id=[string]$event.event_id; timestamp_sp=(Get-CJLNow).ToString('o'); classification=$classification; failure_id=$failureId; white_id=$whiteId; changed_books=$changed; status='PROCESSED' }
            Add-CJLJsonLine -Path $processedPath -Value $record
            [void]$processedIds.Add([string]$event.event_id)
        }
    }
    Write-Host 'EVENT_PROCESSING=PASS'
    exit 0
}
catch { Write-Host $_.Exception.Message; Write-Host 'EVENT_PROCESSING=FAIL'; exit 2 }
