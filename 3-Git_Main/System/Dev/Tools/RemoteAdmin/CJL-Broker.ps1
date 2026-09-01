param(
    [string]$Root = '',
    [string]$AllowedRequesterSids = '',
    [int]$DrainSeconds = 4
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($Root)) {
    throw 'Root explícito é obrigatório para o executor protegido do Remote Admin.'
}
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$MasterId = (Get-Content -LiteralPath (Join-Path $Root 'App\Config\master.id') -Raw -Encoding UTF8).Trim()
$StateRoot = Join-Path $env:ProgramData ('CJL\RemoteAdmin\' + $MasterId)
$Pending = Join-Path $StateRoot 'Pending'
$Processing = Join-Path $StateRoot 'Processing'
$Results = Join-Path $StateRoot 'Results'
$HeartbeatPath = Join-Path $StateRoot 'broker_heartbeat.json'
$ErrorPath = Join-Path $StateRoot 'broker_error.json'
$SessionAction = Join-Path $PSScriptRoot 'CJL-Session.ps1'
$ExecutorManifest = Join-Path $PSScriptRoot 'executor.integrity.json'
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$SessionId = (Get-Process -Id $PID).SessionId
$StartedAt = [DateTimeOffset]::Now
$DrainSeconds = [Math]::Max(2,[Math]::Min(15,$DrainSeconds))

$Allowed = @(
    $AllowedRequesterSids.Split(',') |
        ForEach-Object { $_.Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($Allowed.Count -eq 0) { throw 'AllowedRequesterSids vazio.' }

function Write-JsonAtomic([string]$Path,[object]$Value) {
    $Parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    $Tmp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $Json = ($Value | ConvertTo-Json -Depth 14) + [Environment]::NewLine
    [IO.File]::WriteAllText($Tmp,$Json,(New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $Tmp -Destination $Path -Force
}

function Verify-ExecutorIntegrity {
    if (-not (Test-Path -LiteralPath $ExecutorManifest -PathType Leaf)) {
        throw 'Manifesto de integridade do executor protegido ausente.'
    }
    if (-not (Test-Path -LiteralPath $SessionAction -PathType Leaf)) {
        throw 'CJL-Session.ps1 protegido ausente.'
    }
    $Manifest = Get-Content -LiteralPath $ExecutorManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$Manifest.master_id -ne $MasterId) { throw 'master_id do executor protegido divergiu.' }
    if ([string]$Manifest.root -ne $Root) { throw 'Root do executor protegido divergiu.' }
    $ExpectedBroker = ([string]$Manifest.broker_sha256).ToLowerInvariant()
    $ExpectedSession = ([string]$Manifest.session_sha256).ToLowerInvariant()
    $ActualBroker = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $ActualSession = (Get-FileHash -LiteralPath $SessionAction -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualBroker -ne $ExpectedBroker) { throw 'Hash do CJL-Broker protegido divergiu.' }
    if ($ActualSession -ne $ExpectedSession) { throw 'Hash do CJL-Session protegido divergiu.' }
}

function Write-Heartbeat([string]$Status,[int]$Processed = 0) {
    Write-JsonAtomic $HeartbeatPath ([ordered]@{
        product = 'CJL System'
        component = 'REMOTE_ADMIN_SESSION_BROKER_V7'
        protocol = 7
        model = 'ON_DEMAND_ONE_SHOT_PROTECTED_EXECUTOR'
        status = $Status
        user = $Identity
        session_id = $SessionId
        pid = $PID
        processed = $Processed
        allowed_requester_sids = $Allowed
        state_root = $StateRoot
        executor_root = $PSScriptRoot
        started_at = $StartedAt.ToString('yyyy-MM-ddTHH:mm:ssK')
        updated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    })
}

function Safe-String([object]$Object,[string]$Name) {
    if ($null -eq $Object) { return '' }
    try {
        $P = $Object.PSObject.Properties[$Name]
        if ($null -eq $P) { return '' }
        return [string]$P.Value
    }
    catch { return '' }
}

function Write-FailedRequest([object]$Request,[string]$Status,[string]$Message) {
    $Id = Safe-String $Request 'request_id'
    if ($Id -notmatch '^[a-fA-F0-9]{32}$') { return }
    Write-JsonAtomic (Join-Path $Results ($Id + '.json')) ([ordered]@{
        product = 'CJL System'
        component = 'REMOTE_ADMIN_SESSION_BROKER_V7'
        protocol = 7
        request_id = $Id
        action = (Safe-String $Request 'action')
        complete = $true
        ok = $false
        status = $Status
        error = $Message
        requested_by = (Safe-String $Request 'requested_by')
        panel_operator = (Safe-String $Request 'panel_operator')
        admin_machine = (Safe-String $Request 'admin_machine')
        requester_sid = (Safe-String $Request 'requester_sid')
        broker_user = $Identity
        session_id = $SessionId
        executed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    })
}

function Request-Expired([object]$Request) {
    try {
        $P = $Request.PSObject.Properties['expires_epoch']
        if ($null -eq $P) { return $true }
        $Expires = [int64]$P.Value
        $Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        return ($Expires -le 0 -or $Now -gt $Expires)
    }
    catch { return $true }
}

function Cleanup-EphemeralState {
    $Now = Get-Date
    foreach ($Spec in @(
        [pscustomobject]@{Path=$Pending;Hours=24},
        [pscustomobject]@{Path=$Processing;Hours=24},
        [pscustomobject]@{Path=$Results;Hours=168}
    )) {
        try {
            Get-ChildItem -LiteralPath $Spec.Path -Filter '*.json' -File -ErrorAction SilentlyContinue |
                Where-Object { ($Now - $_.LastWriteTime).TotalHours -gt [double]$Spec.Hours } |
                Remove-Item -Force -ErrorAction SilentlyContinue
        }
        catch {}
    }
}

function Process-Pending {
    $Processed = 0
    $Items = @(
        Get-ChildItem -LiteralPath $Pending -Filter '*.json' -File -ErrorAction SilentlyContinue |
            Sort-Object CreationTime,Name |
            Select-Object -First 50
    )

    foreach ($Item in $Items) {
        $Request = $null
        $ProcessingPath = Join-Path $Processing $Item.Name
        try {
            Move-Item -LiteralPath $Item.FullName -Destination $ProcessingPath -ErrorAction Stop
        }
        catch { continue }

        try {
            $Request = Get-Content -LiteralPath $ProcessingPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $Id = Safe-String $Request 'request_id'
            $ActionName = Safe-String $Request 'action'
            $RequestedBy = Safe-String $Request 'requested_by'
            $PanelOperator = Safe-String $Request 'panel_operator'
            $AdminMachine = Safe-String $Request 'admin_machine'
            $RequesterSid = Safe-String $Request 'requester_sid'

            if ($Id -notmatch '^[a-fA-F0-9]{32}$') { throw 'RequestId inválido.' }
            if (Request-Expired $Request) {
                Write-FailedRequest $Request 'REQUEST_EXPIRED' 'A requisição expirou antes da execução interativa.'
                $Processed++
                continue
            }
            if ($ActionName -notin @('Open','Focus','Close','Probe')) { throw 'Ação fora da allowlist do Broker.' }
            if ($RequesterSid -notin $Allowed) { throw 'SID da requisição não autorizado no Broker.' }

            $ResultPath = Join-Path $Results ($Id + '.json')
            if ($ActionName -eq 'Probe') {
                $CjlHosts = @(
                    Get-Process -Name 'CJL.Host' -ErrorAction SilentlyContinue |
                        Where-Object { try { $_.SessionId -eq $SessionId } catch { $false } }
                )
                Write-JsonAtomic $ResultPath ([ordered]@{
                    product = 'CJL System'
                    component = 'REMOTE_ADMIN_SESSION_BROKER_V7'
                    protocol = 7
                    request_id = $Id
                    action = 'Probe'
                    complete = $true
                    ok = $true
                    status = 'BROKER_INTERACTIVE_OK'
                    requested_by = $RequestedBy
                    panel_operator = $PanelOperator
                    admin_machine = $AdminMachine
                    requester_sid = $RequesterSid
                    broker_user = $Identity
                    session_id = $SessionId
                    broker_pid = $PID
                    cjl_running = ($CjlHosts.Count -gt 0)
                    cjl_host_pids = @($CjlHosts | Select-Object -ExpandProperty Id)
                    broker_model = 'ON_DEMAND_ONE_SHOT_PROTECTED_EXECUTOR'
                    executor_root = $PSScriptRoot
                    executed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
                })
            }
            else {
                $PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
                & $PowerShell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $SessionAction -Action $ActionName -Root $Root -RequestId $Id -ResultPath $ResultPath | Out-Null
                $Code = [int]$LASTEXITCODE
                if ($Code -ne 0 -and -not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
                    throw "CJL-Session falhou com código $Code."
                }
            }
            $Processed++
        }
        catch {
            try {
                if ($null -ne $Request) { Write-FailedRequest $Request 'BROKER_REQUEST_FAILED' $_.Exception.Message }
            }
            catch {}
        }
        finally {
            Remove-Item -LiteralPath $ProcessingPath -Force -ErrorAction SilentlyContinue
        }
    }
    return $Processed
}

try {
    Verify-ExecutorIntegrity
    New-Item -ItemType Directory -Force -Path $Pending,$Processing,$Results | Out-Null
    Remove-Item -LiteralPath $ErrorPath -Force -ErrorAction SilentlyContinue
    Cleanup-EphemeralState
    Write-Heartbeat 'STARTING' 0

    $Total = 0
    $QuietSince = Get-Date
    while ($true) {
        $Count = Process-Pending
        $Total += $Count
        if ($Count -gt 0) { $QuietSince = Get-Date }
        Write-Heartbeat 'DRAINING' $Total
        if (((Get-Date) - $QuietSince).TotalSeconds -ge $DrainSeconds) { break }
        Start-Sleep -Milliseconds 200
    }

    Write-Heartbeat 'IDLE_EXIT' $Total
    exit 0
}
catch {
    try {
        Write-JsonAtomic $ErrorPath ([ordered]@{
            product = 'CJL System'
            component = 'REMOTE_ADMIN_SESSION_BROKER_V7'
            protocol = 7
            status = 'BROKER_RUN_FAILED'
            error = $_.Exception.Message
            user = $Identity
            session_id = $SessionId
            pid = $PID
            executor_root = $PSScriptRoot
            failed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
        })
    }
    catch {}
    exit 1
}
