param(
    [ValidateSet(
        'Open','Focus','Close','Status','Probe','Result',
        'Validate','Health','Logs','LogGet','MaintenanceEnter',
        'MaintenanceExit','UpdateStatus'
    )]
    [string]$Action = 'Status',
    [string]$Root = '',
    [switch]$Compact,
    [switch]$Async,
    [string]$RequestId = '',
    [int]$TimeoutSeconds = 60,
    [int]$MaxLogs = 25,
    [string]$LogPath = '',
    [string]$Reason = 'REMOTE_ADMIN',
    [string]$PanelOperator = '',
    [string]$AdminMachine = ''
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
}
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$MasterIdPath = Join-Path $Root 'App\Config\master.id'
if (-not (Test-Path -LiteralPath $MasterIdPath -PathType Leaf)) { throw "master.id ausente: $MasterIdPath" }
$MasterId = (Get-Content -LiteralPath $MasterIdPath -Raw -Encoding UTF8).Trim()
$SuffixSource = ($MasterId -replace '[^A-Za-z0-9]','')
$Suffix = if ($SuffixSource.Length -ge 8) { $SuffixSource.Substring($SuffixSource.Length - 8) } else { $SuffixSource }
$TaskName = "CJL Broker $Suffix"

$StateRoot = Join-Path $env:ProgramData ('CJL\RemoteAdmin\' + $MasterId)
$Pending = Join-Path $StateRoot 'Pending'
$Results = Join-Path $StateRoot 'Results'
$HeartbeatPath = Join-Path $StateRoot 'broker_heartbeat.json'
$AuditPath = Join-Path $Root 'Logs\RemoteAdmin\remote_admin_audit.jsonl'
New-Item -ItemType Directory -Force -Path $Pending,$Results,(Split-Path $AuditPath -Parent) | Out-Null

if ([string]::IsNullOrWhiteSpace($RequestId)) { $RequestId = [Guid]::NewGuid().ToString('N') }
if ($RequestId -notmatch '^[a-fA-F0-9]{32}$') { throw 'RequestId inválido.' }
$MaxLogs = [Math]::Max(1,[Math]::Min(100,$MaxLogs))
$Reason = ($Reason -replace '[\r\n\t]',' ').Trim()
if ([string]::IsNullOrWhiteSpace($Reason)) { $Reason = 'REMOTE_ADMIN' }
if ($Reason.Length -gt 200) { $Reason = $Reason.Substring(0,200) }
$PanelOperator = ($PanelOperator -replace '[\r\n\t]',' ').Trim()
if ($PanelOperator.Length -gt 100) { $PanelOperator = $PanelOperator.Substring(0,100) }
$AdminMachine = ($AdminMachine -replace '[\r\n\t]',' ').Trim()
if ($AdminMachine.Length -gt 100) { $AdminMachine = $AdminMachine.Substring(0,100) }

$IdentityObject = [Security.Principal.WindowsIdentity]::GetCurrent()
$RequesterName = $IdentityObject.Name
$RequesterSid = $IdentityObject.User.Value
$SshClientIp = ''
$SshServerIp = ''
if (-not [string]::IsNullOrWhiteSpace($env:SSH_CONNECTION)) {
    $Parts = @($env:SSH_CONNECTION -split '\s+')
    if ($Parts.Count -ge 4) { $SshClientIp=[string]$Parts[0]; $SshServerIp=[string]$Parts[2] }
}

function Now-Iso { return (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK') }

function Emit([object]$Value) {
    if ($Compact) { $Value | ConvertTo-Json -Compress -Depth 16 }
    else { $Value | ConvertTo-Json -Depth 16 }
}

function Atomic-Json([string]$Path,[object]$Value) {
    $Tmp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $Json = ($Value | ConvertTo-Json -Depth 16) + [Environment]::NewLine
    [IO.File]::WriteAllText($Tmp,$Json,(New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $Tmp -Destination $Path -Force
}

function Read-JsonSafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Append-Audit([object]$Value) {
    try {
        $Json = ($Value | ConvertTo-Json -Compress -Depth 10)
        Add-Content -LiteralPath $AuditPath -Value $Json -Encoding UTF8
    }
    catch {}
}

function Complete([object]$Value,[int]$ExitCode = 0) {
    if ($Value -is [System.Collections.IDictionary]) {
        if (-not $Value.Contains('request_id')) { $Value['request_id'] = $RequestId }
        if (-not $Value.Contains('action')) { $Value['action'] = $Action }
    }
    $OkValue = $false
    try { $OkValue = [bool]$Value.ok } catch {}
    $StatusValue = ''
    try { $StatusValue = [string]$Value.status } catch {}
    $SessionValue = $null
    $HostPidValue = $null
    $LauncherPidValue = $null
    $BrokerPidValue = $null
    $BrokerUserValue = ''
    $ForcedValue = $null
    try { if ($null -ne $Value.session_id) { $SessionValue = [int]$Value.session_id } } catch {}
    try { if ($null -ne $Value.host_pid) { $HostPidValue = [int]$Value.host_pid } } catch {}
    try { if ($null -ne $Value.launcher_pid) { $LauncherPidValue = [int]$Value.launcher_pid } } catch {}
    try { if ($null -ne $Value.broker_pid) { $BrokerPidValue = [int]$Value.broker_pid } } catch {}
    try { $BrokerUserValue = [string]$Value.broker_user } catch {}
    try { if ($null -ne $Value.forced) { $ForcedValue = [bool]$Value.forced } } catch {}
    Append-Audit ([ordered]@{
        format = 1
        product = 'CJL System'
        component = 'REMOTE_ADMIN_AUDIT_V1'
        time = (Now-Iso)
        request_id = $RequestId
        operator = $RequesterName
        panel_operator = $PanelOperator
        admin_machine = $AdminMachine
        requester_sid = $RequesterSid
        admin_client_ip = $SshClientIp
        ssh_server_ip = $SshServerIp
        master_id = $MasterId
        action = $Action
        ok = $OkValue
        status = $StatusValue
        session_id = $SessionValue
        host_pid = $HostPidValue
        launcher_pid = $LauncherPidValue
        broker_pid = $BrokerPidValue
        broker_user = $BrokerUserValue
        forced = $ForcedValue
        reason = $(if($Action -in @('MaintenanceEnter','MaintenanceExit')){$Reason}else{''})
    })
    Emit $Value
    exit $ExitCode
}

function Request-Path([string]$Id,[string]$Dir) {
    if ($Id -notmatch '^[a-fA-F0-9]{32}$') { throw 'RequestId inválido.' }
    return Join-Path $Dir ($Id + '.json')
}

function Broker-Heartbeat {
    $Heartbeat = Read-JsonSafe $HeartbeatPath
    if ($null -eq $Heartbeat) { return [ordered]@{present=$false;heartbeat=$null} }
    $Age = $null
    try {
        $When = [DateTimeOffset]::Parse([string]$Heartbeat.updated_at)
        $Age = [Math]::Round(([DateTimeOffset]::Now - $When).TotalSeconds,2)
    }
    catch {}
    return [ordered]@{present=$true;age_seconds=$Age;heartbeat=$Heartbeat}
}

function Wake-Broker {
    $Schtasks = Join-Path $env:SystemRoot 'System32\schtasks.exe'
    $Output = @(& $Schtasks /Run /TN $TaskName 2>&1 | ForEach-Object { [string]$_ })
    $Code = [int]$LASTEXITCODE
    return [ordered]@{requested=($Code -eq 0);exit_code=$Code;output=$Output;task_name=$TaskName;requested_at=(Now-Iso)}
}

function Dispatch-BrokerAction([string]$Name,[string]$Id,[int]$WaitSeconds = 60) {
    $RequestFile = Request-Path $Id $Pending
    $ResultFile = Request-Path $Id $Results
    Remove-Item -LiteralPath $ResultFile -Force -ErrorAction SilentlyContinue
    $NowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $TtlSeconds = $(if($Async){600}else{[Math]::Max(120,$WaitSeconds + 45)})
    Atomic-Json $RequestFile ([ordered]@{
        format = 4
        product = 'CJL System'
        protocol = 7
        request_id = $Id
        action = $Name
        requested_by = $RequesterName
        panel_operator = $PanelOperator
        admin_machine = $AdminMachine
        requester_sid = $RequesterSid
        admin_client_ip = $SshClientIp
        requested_at = (Now-Iso)
        requested_epoch = $NowEpoch
        expires_epoch = ($NowEpoch + $TtlSeconds)
        root = $Root
    })

    # A requisição é persistida ANTES do /Run. Se uma instância do Broker já
    # estiver drenando a fila, ela também poderá consumir esta requisição.
    $Wake = Wake-Broker
    if ($Wake.exit_code -ne 0) {
        Remove-Item -LiteralPath $RequestFile -Force -ErrorAction SilentlyContinue
        return [ordered]@{
            product='CJL System';component='REMOTE_ADMIN_V7';protocol=7;
            request_id=$Id;action=$Name;complete=$true;ok=$false;
            status='BROKER_TASK_START_FAILED';broker_wake=$Wake;broker_last_activity=(Broker-Heartbeat)
        }
    }

    if ($Async) {
        return [ordered]@{
            product='CJL System';component='REMOTE_ADMIN_V7';protocol=7;
            request_id=$Id;action=$Name;complete=$false;ok=$true;
            status='DISPATCH_ACCEPTED';broker_wake=$Wake
        }
    }

    $Limit = (Get-Date).AddSeconds([Math]::Max(5,$WaitSeconds))
    do {
        Start-Sleep -Milliseconds 250
        $State = Read-JsonSafe $ResultFile
        if ($null -ne $State -and [string]$State.request_id -eq $Id) {
            try { $State | Add-Member -NotePropertyName broker_wake -NotePropertyValue $Wake -Force } catch {}
            return $State
        }
    } while ((Get-Date) -lt $Limit)

    # Evita que um OPEN/CLOSE expirado seja executado muito depois, por exemplo
    # quando o usuário interativo fizer logon novamente.
    Remove-Item -LiteralPath $RequestFile -Force -ErrorAction SilentlyContinue
    return [ordered]@{
        product='CJL System';component='REMOTE_ADMIN_V7';protocol=7;
        request_id=$Id;action=$Name;complete=$true;ok=$false;
        status='ACTION_RESULT_TIMEOUT';broker_wake=$Wake;broker_last_activity=(Broker-Heartbeat)
    }
}

function Get-ActiveStations {
    $Items = @()
    $Dir = Join-Path $Root 'Repo\Estacoes'
    if (-not (Test-Path -LiteralPath $Dir -PathType Container)) { return @() }
    $NowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    foreach ($File in @(Get-ChildItem -LiteralPath $Dir -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        $V = Read-JsonSafe $File.FullName
        if ($null -eq $V) { continue }
        try {
            $Age = $NowEpoch - [double]$V.last_seen_epoch
            if ($Age -ge 0 -and $Age -le 40 -and -not [string]::IsNullOrWhiteSpace([string]$V.station_id)) {
                $Items += [ordered]@{station_id=[string]$V.station_id;host=[string]$V.host;pid=[int]$V.pid;last_seen=[string]$V.last_seen;age_seconds=[Math]::Round($Age,1)}
            }
        }
        catch {}
    }
    return @($Items)
}

function Invoke-OfficialValidator {
    $Python = Join-Path $Root 'Runtime\Python\python.exe'
    $Validator = Join-Path $Root 'App\Validacao\validar_sistema.py'
    $Output = @(& $Python -B -I -S $Validator $Root 2>&1 | ForEach-Object { [string]$_ })
    $Code = [int]$LASTEXITCODE
    $Parsed = $null
    if ($Code -eq 0) { try { $Parsed = ($Output -join "`n") | ConvertFrom-Json } catch {} }
    return [ordered]@{code=$Code;parsed=$Parsed;output=$Output}
}

if ($Action -eq 'Result') {
    $ResultFile = Request-Path $RequestId $Results
    if (-not (Test-Path -LiteralPath $ResultFile -PathType Leaf)) {
        Complete ([ordered]@{ok=$true;complete=$false;status='PENDING';request_id=$RequestId;action='Result'}) 0
    }
    $State = Read-JsonSafe $ResultFile
    if ($null -eq $State -or [string]$State.request_id -ne $RequestId) {
        Complete ([ordered]@{ok=$false;complete=$true;status='RESULT_READ_ERROR';request_id=$RequestId;action='Result'}) 4
    }
    Complete $State $(if([bool]$State.ok){0}else{4})
}

if ($Action -in @('Open','Focus','Close','Probe')) {
    $Result = Dispatch-BrokerAction $Action $RequestId $TimeoutSeconds
    Complete $Result $(if([bool]$Result.ok){0}else{4})
}

if ($Action -eq 'Status') {
    $ProbeId = [Guid]::NewGuid().ToString('N')
    $Probe = Dispatch-BrokerAction 'Probe' $ProbeId 35
    $HealthScript = Join-Path $PSScriptRoot 'CJL-Health.ps1'
    $Health = (& $HealthScript -Root $Root -Compact | ConvertFrom-Json)
    $Value = [ordered]@{}
    foreach ($P in $Health.PSObject.Properties) { $Value[$P.Name] = $P.Value }
    $Value['broker_ready'] = [bool]$Probe.ok
    $Value['broker_probe'] = $Probe
    if ($null -ne $Probe.PSObject.Properties['cjl_running']) { $Value['cjl_running'] = [bool]$Probe.cjl_running }
    if ($null -ne $Probe.PSObject.Properties['cjl_host_pids']) { $Value['cjl_host_pids'] = @($Probe.cjl_host_pids) }
    $Value['ok'] = $true
    $Value['status'] = $(if([bool]$Health.transport_ready -and [bool]$Probe.ok){'ONLINE'}else{'DEGRADED'})
    $Value['request_id'] = $RequestId
    $Value['action'] = 'Status'
    Complete $Value 0
}

if ($Action -eq 'Validate') {
    $Validation = Invoke-OfficialValidator
    if ($Validation.code -eq 0 -and $null -ne $Validation.parsed) {
        $Value = [ordered]@{}
        foreach ($P in $Validation.parsed.PSObject.Properties) { $Value[$P.Name] = $P.Value }
        $Value['status'] = 'VALIDATED'
        $Value['request_id'] = $RequestId
        $Value['action'] = 'Validate'
        Complete $Value 0
    }
    Complete ([ordered]@{ok=$false;status='VALIDATION_FAILED';validation_output=$Validation.output;request_id=$RequestId;action='Validate'}) 4
}

if ($Action -eq 'Health') {
    $ProbeId = [Guid]::NewGuid().ToString('N')
    $Probe = Dispatch-BrokerAction 'Probe' $ProbeId 35
    $HealthScript = Join-Path $PSScriptRoot 'CJL-Health.ps1'
    $Health = (& $HealthScript -Root $Root -Compact | ConvertFrom-Json)
    try { $Health | Add-Member -NotePropertyName broker_ready -NotePropertyValue ([bool]$Probe.ok) -Force } catch {}
    try { $Health | Add-Member -NotePropertyName broker_probe -NotePropertyValue $Probe -Force } catch {}
    try { if ($null -ne $Probe.PSObject.Properties['cjl_running']) { $Health | Add-Member -NotePropertyName cjl_running -NotePropertyValue ([bool]$Probe.cjl_running) -Force } } catch {}
    try { if ($null -ne $Probe.PSObject.Properties['cjl_host_pids']) { $Health | Add-Member -NotePropertyName cjl_host_pids -NotePropertyValue @($Probe.cjl_host_pids) -Force } } catch {}
    $Validation = Invoke-OfficialValidator
    $Healthy = ($Validation.code -eq 0 -and $null -ne $Validation.parsed -and [bool]$Health.transport_ready -and [bool]$Probe.ok)
    Complete ([ordered]@{
        ok = $Healthy
        status = $(if($Healthy){'HEALTHY'}else{'DEGRADED'})
        health = $Health
        validation = $Validation.parsed
        validation_output = $(if($Validation.code -ne 0){$Validation.output}else{@()})
        broker_probe = $Probe
        checked_at = (Now-Iso)
        request_id = $RequestId
        action = 'Health'
    }) $(if($Healthy){0}else{4})
}

if ($Action -eq 'Logs') {
    $LogRoot = Join-Path $Root 'Logs'
    $Logs = @()
    if (Test-Path -LiteralPath $LogRoot -PathType Container) {
        $Files = @(
            Get-ChildItem -LiteralPath $LogRoot -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Extension.ToLowerInvariant() -in @('.log','.txt','.json','.jsonl') } |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First $MaxLogs
        )
        foreach ($File in $Files) {
            $Relative = $File.FullName.Substring($LogRoot.Length).TrimStart('\')
            $Logs += [ordered]@{relative_path=$Relative;modified=$File.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss');length=[int64]$File.Length}
        }
    }
    Complete ([ordered]@{ok=$true;status='LOGS_READY';logs=$Logs;count=$Logs.Count;log_root='Logs';request_id=$RequestId;action='Logs'}) 0
}

if ($Action -eq 'LogGet') {
    $LogRoot = [IO.Path]::GetFullPath((Join-Path $Root 'Logs')).TrimEnd('\')
    if ([string]::IsNullOrWhiteSpace($LogPath)) {
        Complete ([ordered]@{ok=$false;status='LOG_PATH_REQUIRED';request_id=$RequestId;action='LogGet'}) 4
    }
    if ([IO.Path]::IsPathRooted($LogPath) -or $LogPath.IndexOf(':') -ge 0) {
        Complete ([ordered]@{ok=$false;status='LOG_PATH_MUST_BE_RELATIVE';request_id=$RequestId;action='LogGet'}) 4
    }
    $Candidate = [IO.Path]::GetFullPath((Join-Path $LogRoot $LogPath))
    $Prefix = $LogRoot + '\'
    if (-not $Candidate.StartsWith($Prefix,[StringComparison]::OrdinalIgnoreCase)) {
        Complete ([ordered]@{ok=$false;status='LOG_PATH_OUTSIDE_ALLOWED_ROOT';request_id=$RequestId;action='LogGet'}) 4
    }
    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        Complete ([ordered]@{ok=$false;status='LOG_NOT_FOUND';request_id=$RequestId;action='LogGet'}) 4
    }
    $Info = Get-Item -LiteralPath $Candidate -Force
    if ($Info.Extension.ToLowerInvariant() -notin @('.log','.txt','.json','.jsonl')) {
        Complete ([ordered]@{ok=$false;status='LOG_EXTENSION_NOT_ALLOWED';request_id=$RequestId;action='LogGet'}) 4
    }
    $MaxBytes = 8MB
    if ([int64]$Info.Length -gt $MaxBytes) {
        Complete ([ordered]@{ok=$false;status='LOG_TOO_LARGE';length=[int64]$Info.Length;max_bytes=[int64]$MaxBytes;request_id=$RequestId;action='LogGet'}) 4
    }
    $Bytes = [IO.File]::ReadAllBytes($Candidate)
    Complete ([ordered]@{
        ok = $true
        status = 'LOG_CONTENT_READY'
        relative_path = $LogPath
        length = [int64]$Bytes.Length
        sha256 = (Get-FileHash -LiteralPath $Candidate -Algorithm SHA256).Hash.ToLowerInvariant()
        content_b64 = [Convert]::ToBase64String($Bytes)
        modified = $Info.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        request_id = $RequestId
        action = 'LogGet'
    }) 0
}

if ($Action -eq 'UpdateStatus') {
    Complete ([ordered]@{
        ok = $true
        status = 'UPDATE_STATUS'
        operation = (Read-JsonSafe (Join-Path $Root 'Updates\State\operation.json'))
        current = (Read-JsonSafe (Join-Path $Root 'Updates\State\atual.json'))
        checked_at = (Now-Iso)
        request_id = $RequestId
        action = 'UpdateStatus'
    }) 0
}

if ($Action -eq 'MaintenanceEnter') {
    $PreProbeId = [Guid]::NewGuid().ToString('N')
    $PreProbe = Dispatch-BrokerAction 'Probe' $PreProbeId 35
    if (-not [bool]$PreProbe.ok) {
        Complete ([ordered]@{ok=$false;status='BROKER_NOT_READY_FOR_MAINTENANCE';broker_probe=$PreProbe;request_id=$RequestId;action='MaintenanceEnter'}) 4
    }

    $Marker = Join-Path $Root 'Repo\Manutencao\estado.json'
    New-Item -ItemType Directory -Force -Path (Split-Path $Marker -Parent) | Out-Null
    $State = Read-JsonSafe (Join-Path $Root 'Updates\State\atual.json')
    $Compat = 0; $Version = ''
    if ($null -ne $State) {
        try { $Compat = [int]$State.compat_sequence } catch {}
        try { $Version = [string]$State.version } catch {}
    }
    $OperationId = 'REMOTE-' + $RequestId.Substring(0,12).ToUpperInvariant()
    $Payload = [ordered]@{
        format = 3
        product = 'CJL System'
        mode = 'CRITICAL'
        phase = 'REMOTE_MAINTENANCE'
        active = $true
        patch_id = 'REMOTE_ADMIN'
        operation_id = $OperationId
        target_version = $Version
        compat_sequence = $Compat
        minimum_station_compat = $Compat
        message = 'MANUTENCAO ADMINISTRATIVA REMOTA ATIVA'
        reason = $Reason
        requested_by = $RequesterName
        panel_operator = $PanelOperator
        admin_machine = $AdminMachine
        requester_sid = $RequesterSid
        admin_client_ip = $SshClientIp
        requested_at = (Now-Iso)
    }
    Atomic-Json $Marker $Payload

    $DrainLimit = (Get-Date).AddSeconds(30)
    $ActiveStations = @(Get-ActiveStations)
    do {
        if ($ActiveStations.Count -eq 0) { break }
        Start-Sleep -Seconds 2
        $ActiveStations = @(Get-ActiveStations)
    } while ((Get-Date) -lt $DrainLimit)

    if ($ActiveStations.Count -gt 0) {
        Complete ([ordered]@{ok=$false;status='MAINTENANCE_DRAIN_TIMEOUT';maintenance=$Payload;active_stations=$ActiveStations;note='Marcador crítico permanece ativo por segurança.';request_id=$RequestId;action='MaintenanceEnter'}) 4
    }

    $CloseId = [Guid]::NewGuid().ToString('N')
    $CloseResult = Dispatch-BrokerAction 'Close' $CloseId 45
    if (-not [bool]$CloseResult.ok) {
        Complete ([ordered]@{ok=$false;status='MAINTENANCE_CLOSE_FAILED';maintenance=$Payload;close_result=$CloseResult;note='Marcador crítico permanece ativo por segurança.';request_id=$RequestId;action='MaintenanceEnter'}) 4
    }

    $LockPath = Join-Path $Root 'Repo\Bloqueios\ESCRITA_GLOBAL.lock'
    $LockLimit = (Get-Date).AddSeconds(30)
    while ((Test-Path -LiteralPath $LockPath -PathType Leaf) -and (Get-Date) -lt $LockLimit) { Start-Sleep -Milliseconds 500 }
    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        Complete ([ordered]@{ok=$false;status='MAINTENANCE_WRITE_LOCK_REMAINS';maintenance=$Payload;lock_path=$LockPath;note='Marcador crítico permanece ativo por segurança.';request_id=$RequestId;action='MaintenanceEnter'}) 4
    }

    $Validation = Invoke-OfficialValidator
    if ($Validation.code -ne 0) {
        Complete ([ordered]@{ok=$false;status='MAINTENANCE_VALIDATION_FAILED';maintenance=$Payload;validation_output=$Validation.output;note='Marcador crítico permanece ativo por segurança.';request_id=$RequestId;action='MaintenanceEnter'}) 4
    }

    Complete ([ordered]@{
        ok = $true
        status = 'MAINTENANCE_READY'
        maintenance = $Payload
        active_stations = @()
        global_write_lock_present = $false
        close_result = $CloseResult
        validation = $Validation.parsed
        request_id = $RequestId
        action = 'MaintenanceEnter'
    }) 0
}

if ($Action -eq 'MaintenanceExit') {
    $Operation = Read-JsonSafe (Join-Path $Root 'Updates\State\operation.json')
    if ($null -ne $Operation -and [string]$Operation.status -in @('WAITING','APPLYING')) {
        Complete ([ordered]@{ok=$false;status='UPDATE_ACTIVE';operation=$Operation;request_id=$RequestId;action='MaintenanceExit'}) 4
    }
    $LockPath = Join-Path $Root 'Repo\Bloqueios\ESCRITA_GLOBAL.lock'
    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        Complete ([ordered]@{ok=$false;status='WRITE_LOCK_ACTIVE';lock_path=$LockPath;request_id=$RequestId;action='MaintenanceExit'}) 4
    }
    $Validation = Invoke-OfficialValidator
    if ($Validation.code -ne 0) {
        Complete ([ordered]@{ok=$false;status='VALIDATION_FAILED_MAINTENANCE_REMAINS';validation_output=$Validation.output;request_id=$RequestId;action='MaintenanceExit'}) 4
    }
    $Marker = Join-Path $Root 'Repo\Manutencao\estado.json'
    New-Item -ItemType Directory -Force -Path (Split-Path $Marker -Parent) | Out-Null
    $Payload = [ordered]@{
        format = 3
        product = 'CJL System'
        mode = 'CRITICAL'
        phase = 'RELEASED'
        active = $false
        message = 'MANUTENCAO LIBERADA'
        reason = $Reason
        released_by = $RequesterName
        panel_operator = $PanelOperator
        admin_machine = $AdminMachine
        requester_sid = $RequesterSid
        admin_client_ip = $SshClientIp
        released_at = (Now-Iso)
    }
    Atomic-Json $Marker $Payload
    Complete ([ordered]@{ok=$true;status='MAINTENANCE_RELEASED';maintenance=$Payload;validation=$Validation.parsed;request_id=$RequestId;action='MaintenanceExit'}) 0
}

Complete ([ordered]@{ok=$false;status='ACTION_NOT_IMPLEMENTED';request_id=$RequestId;action=$Action}) 4
