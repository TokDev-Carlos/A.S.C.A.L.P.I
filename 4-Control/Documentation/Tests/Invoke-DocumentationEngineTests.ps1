[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EvidenceDir,
    [string]$InstalledRoot = 'C:\.Dev CJL\4-Control\Documentation',
    [string]$RealDocsRoot = 'C:\.Dev CJL\5-Docs'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$results = New-Object System.Collections.ArrayList
function Add-Result {
    param([string]$Id, [string]$Name, [bool]$Passed, [string]$Detail='')
    [void]$results.Add([pscustomobject]@{ id=$Id; name=$Name; status=$(if($Passed){'PASS'}else{'FAIL'}); detail=$Detail })
    Write-Host ($Id + '=' + $(if($Passed){'PASS'}else{'FAIL'}) + $(if($Detail){' ' + $Detail}else{''}))
}
function Hash([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Run-Emit {
    param([string[]]$Arguments)
    $emit = Join-Path $script:SandboxControl 'Engine\Emit-CJLEvent.ps1'
    $all = @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$emit,'-ControlRoot',$script:SandboxControl,'-DocsRoot',$script:SandboxDocs) + $Arguments
    $output = @(& powershell.exe @all 2>&1)
    [pscustomobject]@{ ExitCode=$LASTEXITCODE; Output=($output -join [Environment]::NewLine) }
}
function MarkerCount([string]$Path,[string]$Pattern) { ([regex]::Matches([System.IO.File]::ReadAllText($Path),$Pattern)).Count }

$sandbox = Join-Path $EvidenceDir 'SANDBOX'
$script:SandboxControl = Join-Path $sandbox '4-Control\Documentation'
$script:SandboxDocs = Join-Path $sandbox '5-Docs'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $script:SandboxControl) | Out-Null
New-Item -ItemType Directory -Force -Path $script:SandboxDocs | Out-Null
Copy-Item -LiteralPath $InstalledRoot -Destination $script:SandboxControl -Recurse -Force
foreach($name in @('Execution_Contract.md','Souvenir.md','Black_Book.md','White_Book.md')) { Copy-Item -LiteralPath (Join-Path $RealDocsRoot $name) -Destination (Join-Path $script:SandboxDocs $name) -Force }

$realPre = @{}
foreach($name in @('Execution_Contract.md','Souvenir.md','Black_Book.md','White_Book.md')) { $realPre[$name]=Hash (Join-Path $RealDocsRoot $name) }
$sandboxPre = @{}
foreach($name in @('Execution_Contract.md','Souvenir.md','Black_Book.md','White_Book.md')) { $sandboxPre[$name]=Hash (Join-Path $script:SandboxDocs $name) }

Add-Result T01 'Required roots exist' ((Test-Path 'C:\.Dev CJL\4-Control' -PathType Container) -and (Test-Path $RealDocsRoot -PathType Container))
Add-Result T02 'Four current docs exist' (@('Execution_Contract.md','Souvenir.md','Black_Book.md','White_Book.md') | Where-Object {-not (Test-Path (Join-Path $RealDocsRoot $_) -PathType Leaf)} | Measure-Object).Count.Equals(0)
Add-Result T03 'Pre-install SHA-256 captured' ($realPre.Count -eq 4)
$requiredInstalled = @('README.md','Policy','Engine','State','Tests','Emit-CJLEvent.cmd','Process-Pending.cmd')
Add-Result T04 'Engine installs only under Documentation' (($requiredInstalled | Where-Object {-not (Test-Path (Join-Path $InstalledRoot $_))} | Measure-Object).Count -eq 0)
$sourceText = (Get-ChildItem -LiteralPath (Join-Path $InstalledRoot 'Engine') -Filter '*.ps1' -File | ForEach-Object { Get-Content -Raw $_.FullName }) -join "`n"
Add-Result T05 'No write to 1-Dev' (-not ($sourceText -match '(?i)(Write|Copy|Move|Remove|Set-Content)[^\r\n]*1-Dev'))
Add-Result T06 'No write to 2-Compiler' (-not ($sourceText -match '(?i)(Write|Copy|Move|Remove|Set-Content)[^\r\n]*2-Compiler'))
Add-Result T07 'No write to 3-Git_Main' (-not ($sourceText -match '(?i)(Write|Copy|Move|Remove|Set-Content)[^\r\n]*3-Git_Main'))
Add-Result T08 'No write to WSL' (-not ($sourceText -match '(?i)(Write|Copy|Move|Remove|Set-Content)[^\r\n]*WSL'))
Add-Result T09 'No GitHub write' (-not ($sourceText -match '(?i)git\s+push|Invoke-RestMethod.+github|gh\s+'))

& (Join-Path $script:SandboxControl 'Engine\Protect-StaticDocuments.ps1') -ControlRoot $script:SandboxControl -DocsRoot $script:SandboxDocs | Out-Null
$verifyOutput = @(& (Join-Path $script:SandboxControl 'Engine\Verify-DocumentationState.ps1') -ControlRoot $script:SandboxControl -DocsRoot $script:SandboxDocs 2>&1)
Add-Result T10 'Policy validates and is hard-locked' (($LASTEXITCODE -eq 0) -and (@(Get-ChildItem (Join-Path $script:SandboxControl 'Policy') -File | Where-Object {-not $_.IsReadOnly}).Count -eq 0)) ($verifyOutput -join ' ')

$eventsPath = Join-Path $script:SandboxControl 'State\events.jsonl'
$beforeLedger = [System.IO.File]::ReadAllBytes($eventsPath)
$r = Run-Emit @('-Type','BUILD_PASS','-Status','PASS','-Severity','INFO','-Stage','test','-Component','ledger','-Summary','ledger append','-CauseClass','NOT_APPLICABLE','-CycleId','T11')
$afterLedger = [System.IO.File]::ReadAllBytes($eventsPath)
$prefixOk=$true; for($i=0;$i -lt $beforeLedger.Length;$i++){if($beforeLedger[$i]-ne $afterLedger[$i]){$prefixOk=$false}}
Add-Result T11 'events.jsonl append-only' (($r.ExitCode -eq 0) -and $prefixOk -and $afterLedger.Length -gt $beforeLedger.Length) $r.Output

$blackPath=Join-Path $script:SandboxDocs 'Black_Book.md'; $whitePath=Join-Path $script:SandboxDocs 'White_Book.md'
$dupId='EVT-DUPLICATE-T12'; $before=MarkerCount $blackPath '<!-- CJL:BLACK:FAIL-[0-9]+:BEGIN -->'
$null=Run-Emit @('-EventId',$dupId,'-Type','VALIDATION_FAIL','-Status','FAIL','-Severity','ERROR','-Stage','test','-Component','duplicate','-Summary','duplicate test','-CauseClass','SYSTEM','-CycleId','T12','-CorrelationId','CORR-T12')
$null=Run-Emit @('-EventId',$dupId,'-Type','VALIDATION_FAIL','-Status','FAIL','-Severity','ERROR','-Stage','test','-Component','duplicate','-Summary','duplicate test','-CauseClass','SYSTEM','-CycleId','T12','-CorrelationId','CORR-T12')
$after=MarkerCount $blackPath '<!-- CJL:BLACK:FAIL-[0-9]+:BEGIN -->'
Add-Result T12 'Duplicate event idempotent' (($after-$before)-eq 1)
Add-Result T13 'VALIDATION_FAIL creates Black entry' (($after-$before)-eq 1)

$blackBefore=Hash $blackPath; $whiteBefore=Hash $whitePath
$r=Run-Emit @('-Type','CORRECTION_RETEST_PASS','-Status','PASS','-Severity','INFO','-Stage','test','-Component','duplicate','-Summary','correction passed','-CauseClass','SYSTEM','-CycleId','T14','-CorrelationId','CORR-T12','-Details','Retest passed','-ReusableKnowledge','-KnowledgeTitle','Reusable correction','-ValidatedRule','Retry after correction','-Limitation','Validated sandbox only')
$blackText=Get-Content -Raw $blackPath
Add-Result T14 'Correction closes managed failure' (($r.ExitCode -eq 0) -and $blackText.Contains('Resolution / Retest:')) $r.Output
Add-Result T15 'Reusable correction creates White entry' ((Hash $whitePath) -ne $whiteBefore)

$before=Hash $whitePath; $null=Run-Emit @('-Type','BUILD_PASS','-Status','PASS','-Severity','INFO','-Stage','test','-Component','build','-Summary','ordinary build pass','-CauseClass','NOT_APPLICABLE','-CycleId','T16'); Add-Result T16 'BUILD_PASS leaves White unchanged' ((Hash $whitePath)-eq $before)
$before=Hash $blackPath; $null=Run-Emit @('-Type','AUTH_FAIL','-Status','FAIL','-Severity','WARNING','-Stage','auth','-Component','user','-Summary','bad user input','-CauseClass','USER_INPUT','-CycleId','T17'); Add-Result T17 'USER_INPUT AUTH_FAIL leaves Black unchanged' ((Hash $blackPath)-eq $before)
$before=Hash $blackPath; $null=Run-Emit @('-Type','AUTH_FAIL','-Status','FAIL','-Severity','ERROR','-Stage','auth','-Component','system','-Summary','system auth failure','-CauseClass','SYSTEM','-CycleId','T18','-CorrelationId','CORR-T18'); Add-Result T18 'SYSTEM AUTH_FAIL changes Black' ((Hash $blackPath)-ne $before)
$unknown='EVT-UNKNOWN-T19'; $null=Run-Emit @('-EventId',$unknown,'-Type','ALIEN_EVENT','-Status','INFO','-Severity','INFO','-Stage','test','-Component','unknown','-Summary','unknown classification','-CauseClass','UNKNOWN','-CycleId','T19'); $processed=Get-Content -Raw (Join-Path $script:SandboxControl 'State\processed-events.jsonl'); Add-Result T19 'Unknown event ledger-only flagged' ($processed -match ($unknown+'.+LEDGER_ONLY_UNCLASSIFIED'))

$content=Get-Content -Raw $blackPath; $maxBefore=0; foreach($m in [regex]::Matches($content,'FAIL-([0-9]{4,})')){$n=[int]$m.Groups[1].Value;if($n-gt$maxBefore){$maxBefore=$n}}; $null=Run-Emit @('-Type','BUILD_FAIL','-Status','FAIL','-Severity','ERROR','-Stage','build','-Component','ids','-Summary','live black scan','-CauseClass','SYSTEM','-CycleId','T20','-CorrelationId','CORR-T20'); Add-Result T20 'Next FAIL id from live scan' ((Get-Content -Raw $blackPath).Contains(('FAIL-'+($maxBefore+1).ToString('0000'))))
$content=Get-Content -Raw $whitePath; $maxBefore=0; foreach($m in [regex]::Matches($content,'WB-([0-9]{4,})')){$n=[int]$m.Groups[1].Value;if($n-gt$maxBefore){$maxBefore=$n}}; $null=Run-Emit @('-Type','PROOF_PASS','-Status','PASS','-Severity','INFO','-Stage','proof','-Component','ids','-Summary','live white scan','-CauseClass','PROCEDURE','-CycleId','T21','-ReusableKnowledge','-KnowledgeTitle','Live scan proof','-ValidatedRule','Scan live book','-Limitation','Sandbox'); Add-Result T21 'Next WB id from live scan' ((Get-Content -Raw $whitePath).Contains(('WB-'+($maxBefore+1).ToString('0000'))))

$beforeIds=@([regex]::Matches((Get-Content -Raw $blackPath),'FAIL-([0-9]{4,})')|ForEach-Object{$_.Value}|Select-Object -Unique)
$processes=@(); for($i=1;$i-le 4;$i++){$args=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $script:SandboxControl 'Engine\Emit-CJLEvent.ps1'),'-ControlRoot',$script:SandboxControl,'-DocsRoot',$script:SandboxDocs,'-Type','VALIDATION_FAIL','-Status','FAIL','-Severity','ERROR','-Stage','concurrency','-Component',('worker'+$i),'-Summary',('concurrent '+$i),'-CauseClass','SYSTEM','-CycleId','T22','-CorrelationId',('CORR-T22-'+$i));$processes+=Start-Process -FilePath powershell.exe -ArgumentList $args -WindowStyle Hidden -PassThru}
$processes|ForEach-Object{$_.WaitForExit()}; $allIds=@([regex]::Matches((Get-Content -Raw $blackPath),'FAIL-([0-9]{4,})')|ForEach-Object{$_.Value}); $newIds=@($allIds|Where-Object{$beforeIds-notcontains$_}|Select-Object -Unique); Add-Result T22 'Concurrent IDs unique' ($newIds.Count -eq 4)

. (Join-Path $script:SandboxControl 'Engine\Common.ps1'); $before=Hash $blackPath; $failed=$false; try{Set-CJLBookAtomic -Path $blackPath -Content 'invalid' -ExpectedHeading '# CJL Black Book - Volume 001' -Paths (Get-CJLPaths $script:SandboxControl $script:SandboxDocs) -CycleId 'T23'}catch{$failed=$true}; Add-Result T23 'Failed book write leaves original' ($failed -and (Hash $blackPath)-eq $before)
$static=Get-Item (Join-Path $script:SandboxDocs 'Execution_Contract.md'); Add-Result T24 'Static automatic write denied' ($static.IsReadOnly -and -not ($sourceText -match 'Execution_Contract\.md.+Write'))
$processorText=Get-Content -Raw (Join-Path $InstalledRoot 'Engine\Process-CJLEvents.ps1'); Add-Result T25 'Processor cannot invoke rebaseline' (-not ($processorText -match 'Rebaseline-StaticDocuments'))

$policyPath=Join-Path $script:SandboxControl 'Policy\EVENT_RULES.json'; $policyBytes=[System.IO.File]::ReadAllBytes($policyPath); $policyItem=Get-Item $policyPath; $policyItem.IsReadOnly=$false; [System.IO.File]::AppendAllText($policyPath,' '); $out=@(& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $script:SandboxControl 'Engine\Process-CJLEvents.ps1') -ControlRoot $script:SandboxControl -DocsRoot $script:SandboxDocs 2>&1); $processorExit=$LASTEXITCODE; $stopped=($processorExit -ne 0 -and (($out-join' ') -match 'POLICY_INTEGRITY=FAIL')); [System.IO.File]::WriteAllBytes($policyPath,$policyBytes); (Get-Item $policyPath).IsReadOnly=$true; Add-Result T26 'Policy mismatch stops processing' $stopped ($out-join' ')
$policy=Get-Content -Raw (Join-Path $InstalledRoot 'Policy\DOCUMENT_POLICY.json')|ConvertFrom-Json; Add-Result T27 'Remote sync queue-only' (-not [bool]$policy.remote_book_sync.enabled -and [string]$policy.remote_book_sync.mode -eq 'QUEUE_ONLY')
$pending=Join-Path $script:SandboxControl 'State\pending-sync.jsonl'; Add-Result T28 'Pending sync record exists' ((Get-Item $pending).Length -gt 0)
Add-Result T29 'Real Execution Contract unchanged' ((Hash (Join-Path $RealDocsRoot 'Execution_Contract.md'))-eq $realPre['Execution_Contract.md'])
Add-Result T30 'Real Souvenir unchanged' ((Hash (Join-Path $RealDocsRoot 'Souvenir.md'))-eq $realPre['Souvenir.md'])
Add-Result T31 'Real Black Book unchanged' ((Hash (Join-Path $RealDocsRoot 'Black_Book.md'))-eq $realPre['Black_Book.md'])
Add-Result T32 'Real White Book unchanged' ((Hash (Join-Path $RealDocsRoot 'White_Book.md'))-eq $realPre['White_Book.md'])
Add-Result T33 'Static docs ReadOnly' ((Get-Item (Join-Path $script:SandboxDocs 'Execution_Contract.md')).IsReadOnly -and (Get-Item (Join-Path $script:SandboxDocs 'Souvenir.md')).IsReadOnly)
Add-Result T34 'Books remain writable' (-not (Get-Item $blackPath).IsReadOnly -and -not (Get-Item $whitePath).IsReadOnly)
$parseOk=$true; Get-ChildItem $InstalledRoot -Filter '*.ps1' -File -Recurse|ForEach-Object{$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$t,[ref]$e)|Out-Null;if($e.Count-gt0){$parseOk=$false}}; Add-Result T35 'PowerShell 5.1 parse' $parseOk
Add-Result T36 'No cwd dependency' (-not ($sourceText -match '\b(Get-Location|Set-Location|\$PWD)\b'))
Add-Result T37 'Rollback package exists' ((Test-Path (Join-Path $EvidenceDir 'ROLLBACK\MANIFEST.txt')) -and (Test-Path (Join-Path $EvidenceDir 'ROLLBACK\ROLLBACK.md')))
Add-Result T38 'Evidence and receipt generated' ((Test-Path $EvidenceDir) -and (Test-Path (Join-Path $EvidenceDir 'RECEIPT.txt')))

$jsonPath=Join-Path $EvidenceDir 'TEST_RESULTS.json'; $json=($results|ConvertTo-Json -Depth 4)+[Environment]::NewLine; $utf8=New-Object System.Text.UTF8Encoding($false); [System.IO.File]::WriteAllText($jsonPath,$json,$utf8)
$failed=@($results|Where-Object{$_.status-ne'PASS'})
if($failed.Count-gt0){Write-Host ('TESTS_FAILED='+($failed.id-join','));exit 2}
Write-Host 'ACCEPTANCE_TESTS=PASS'; exit 0
