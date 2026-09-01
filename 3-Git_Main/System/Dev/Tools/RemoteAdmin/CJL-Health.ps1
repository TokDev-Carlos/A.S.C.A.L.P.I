param(
    [string]$Root = '',
    [switch]$Compact
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
}
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$ConfigPath = Join-Path $Root 'App\Config\sistema.json'
$MasterIdPath = Join-Path $Root 'App\Config\master.id'
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "sistema.json ausente: $ConfigPath" }
if (-not (Test-Path -LiteralPath $MasterIdPath -PathType Leaf)) { throw "master.id ausente: $MasterIdPath" }

$Cfg = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$MasterId = (Get-Content -LiteralPath $MasterIdPath -Raw -Encoding UTF8).Trim()
$StateRoot = Join-Path $env:ProgramData ('CJL\RemoteAdmin\' + $MasterId)
$HeartbeatPath = Join-Path $StateRoot 'broker_heartbeat.json'
$HeartbeatData = $null
$HeartbeatAge = $null
$BrokerRunning = $false
$BrokerLastRunOk = $false

if (Test-Path -LiteralPath $HeartbeatPath -PathType Leaf) {
    try {
        $HeartbeatData = Get-Content -LiteralPath $HeartbeatPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $When = [DateTimeOffset]::Parse([string]$HeartbeatData.updated_at)
        $HeartbeatAge = [Math]::Round(([DateTimeOffset]::Now - $When).TotalSeconds,2)
        $BrokerState = [string]$HeartbeatData.status
        $BrokerRunning = ([int]$HeartbeatData.protocol -eq 7 -and $HeartbeatAge -le 15 -and $BrokerState -in @('STARTING','DRAINING'))
        $BrokerLastRunOk = ([int]$HeartbeatData.protocol -eq 7 -and $BrokerState -eq 'IDLE_EXIT')
    }
    catch {}
}

function Extract-Number([string]$Value) {
    if ($Value -match '(\d+)$') { return [int]$Matches[1] }
    return 0
}

function Test-TailscaleIPv4([string]$Ip) {
    if ([string]::IsNullOrWhiteSpace($Ip)) { return $false }
    $Parts = $Ip.Split('.')
    if ($Parts.Count -ne 4) { return $false }
    try { return ([int]$Parts[0] -eq 100 -and [int]$Parts[1] -ge 64 -and [int]$Parts[1] -le 127) } catch { return $false }
}

function Get-ServiceSnapshot([string]$Name) {
    try {
        $Svc = Get-Service -Name $Name -ErrorAction Stop
        $StartMode = 'UNKNOWN'
        try {
            if ($null -ne $Svc.PSObject.Properties['StartType']) { $StartMode = [string]$Svc.StartType }
        }
        catch {}
        return [ordered]@{installed=$true;state=[string]$Svc.Status;start_mode=$StartMode;evidence='SERVICE_CONTROL_MANAGER'}
    }
    catch {
        return [ordered]@{installed=$false;state='NOT_QUERYABLE';start_mode='UNKNOWN';evidence='SERVICE_QUERY_UNAVAILABLE'}
    }
}

function Read-JsonSafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

$Running = @(Get-Process -Name 'CJL.Host' -ErrorAction SilentlyContinue)
$Hosts = @(
    $Running | ForEach-Object {
        try { $_.Refresh() } catch {}
        [ordered]@{
            pid = [int]$_.Id
            session_id = $(try {[int]$_.SessionId} catch {-1})
            window_handle = $(try {[int64]$_.MainWindowHandle} catch {0})
            responding = $(try {[bool]$_.Responding} catch {$null})
        }
    }
)

$Sshd = Get-ServiceSnapshot 'sshd'
$Tailscale = Get-ServiceSnapshot 'Tailscale'
$SshClientIp = ''
$SshServerIp = ''
if (-not [string]::IsNullOrWhiteSpace($env:SSH_CONNECTION)) {
    $SshParts = @($env:SSH_CONNECTION -split '\s+')
    if ($SshParts.Count -ge 4) { $SshClientIp=[string]$SshParts[0]; $SshServerIp=[string]$SshParts[2] }
    if (-not [bool]$Sshd.installed) {
        $Sshd = [ordered]@{installed=$true;state='Running';start_mode='UNKNOWN';evidence='CURRENT_SSH_SESSION'}
    }
}

$TailscaleIps = @()
try {
    $TailscaleIps = @(
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { Test-TailscaleIPv4 ([string]$_.IPAddress) } |
            Select-Object -ExpandProperty IPAddress -Unique
    )
}
catch {}
if ((Test-TailscaleIPv4 $SshServerIp) -and $SshServerIp -notin $TailscaleIps) { $TailscaleIps = @($TailscaleIps) + $SshServerIp }
if (-not [bool]$Tailscale.installed -and (Test-TailscaleIPv4 $SshServerIp)) {
    $Tailscale = [ordered]@{installed=$true;state='Running';start_mode='UNKNOWN';evidence='CURRENT_SSH_SESSION_OVER_TAILSCALE'}
}

$TransportObserved = [ordered]@{
    ssh_session = (-not [string]::IsNullOrWhiteSpace($env:SSH_CONNECTION))
    ssh_client_ip = $SshClientIp
    ssh_server_ip = $SshServerIp
    tailscale_address_observed = (Test-TailscaleIPv4 $SshServerIp)
}
$SshReady = ([bool]$Sshd.installed -and [string]$Sshd.state -eq 'Running')
$TailscaleReady = ([bool]$Tailscale.installed -and [string]$Tailscale.state -eq 'Running')
$TransportReady = ($SshReady -and $TailscaleReady)

$Ba = Extract-Number ([string]$Cfg.versioning.business_id)
$Es = Extract-Number ([string]$Cfg.versioning.structural_id)
$In = Extract-Number ([string]$Cfg.versioning.incremental_id)
$Se = Extract-Number ([string]$Cfg.versioning.security_id)
$DisplayVersion = ('{0}.{1}.{2:D2}.{3:D3}' -f $Ba,$Es,$In,$Se)

$MaintenancePath = Join-Path $Root 'Repo\Manutencao\estado.json'
$Maintenance = Read-JsonSafe $MaintenancePath
if ($null -eq $Maintenance) {
    $Maintenance = [ordered]@{active=$false;mode='NONE';phase='NONE'}
}
$MaintenanceActive = $false
try {
    $Mode = [string]$Maintenance.mode
    $Phase = [string]$Maintenance.phase
    $MaintenanceActive = ([bool]$Maintenance.active -and $Mode.ToUpperInvariant() -eq 'CRITICAL' -and $Phase.ToUpperInvariant() -notin @('RELEASED','IDLE','NONE'))
}
catch {}

$Stations = @()
$StationDir = Join-Path $Root 'Repo\Estacoes'
if (Test-Path -LiteralPath $StationDir -PathType Container) {
    $NowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    foreach ($File in @(Get-ChildItem -LiteralPath $StationDir -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        $Item = Read-JsonSafe $File.FullName
        if ($null -eq $Item) { continue }
        try {
            $Age = $NowEpoch - [double]$Item.last_seen_epoch
            if ($Age -ge 0 -and $Age -le 40 -and -not [string]::IsNullOrWhiteSpace([string]$Item.station_id)) {
                $Stations += [ordered]@{station_id=[string]$Item.station_id;host=[string]$Item.host;pid=[int]$Item.pid;version=[string]$Item.version;last_seen=[string]$Item.last_seen;age_seconds=[Math]::Round($Age,1)}
            }
        }
        catch {}
    }
}

$LockPath = Join-Path $Root 'Repo\Bloqueios\ESCRITA_GLOBAL.lock'
$Lock = $null
if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
    $Lock = Read-JsonSafe $LockPath
    if ($null -eq $Lock) { $Lock = [ordered]@{present=$true;path=$LockPath} }
    else { try { $Lock | Add-Member -NotePropertyName present -NotePropertyValue $true -Force } catch {} }
}

$UpdateState = Read-JsonSafe (Join-Path $Root 'Updates\State\atual.json')
$UpdateOperation = Read-JsonSafe (Join-Path $Root 'Updates\State\operation.json')
$LastAction = Read-JsonSafe (Join-Path $Root 'Logs\RemoteAdmin\last_action.json')

$DriveFree = $null
$DriveTotal = $null
try {
    $DriveLetter = [IO.Path]::GetPathRoot($Root).TrimEnd('\').TrimEnd(':')
    $Drive = Get-PSDrive -Name $DriveLetter -PSProvider FileSystem -ErrorAction Stop
    $DriveFree = [int64]$Drive.Free
    $DriveTotal = [int64]($Drive.Free + $Drive.Used)
}
catch {}

$Value = [ordered]@{
    product = 'CJL System'
    component = 'REMOTE_ADMIN_HEALTH_V7'
    protocol = 7
    hostname = $env:COMPUTERNAME
    user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    root = $Root
    master_id = $MasterId
    business = [string]$Cfg.versioning.business_id
    version_internal = [string]$Cfg.version
    version_display = $DisplayVersion
    structural = [string]$Cfg.versioning.structural_id
    incremental = [string]$Cfg.versioning.incremental_id
    security = [string]$Cfg.versioning.security_id
    build = [int64]$Cfg.build
    layout = [int]$Cfg.layout_version
    runtime = [int]$Cfg.runtime_version
    cjl_running = ($Running.Count -gt 0)
    cjl_hosts = $Hosts
    broker_running = $BrokerRunning
    broker_last_run_ok = $BrokerLastRunOk
    broker_last_activity_age_seconds = $HeartbeatAge
    broker_heartbeat = $HeartbeatData
    state_root = $StateRoot
    sshd = $Sshd
    tailscale = $Tailscale
    tailscale_ipv4 = $TailscaleIps
    transport_observed = $TransportObserved
    transport_ready = $TransportReady
    maintenance_active = $MaintenanceActive
    maintenance = $Maintenance
    active_stations = $Stations
    active_station_count = $Stations.Count
    global_write_lock_present = ($null -ne $Lock)
    global_write_lock = $Lock
    update_state = $UpdateState
    update_operation = $UpdateOperation
    disk_free_bytes = $DriveFree
    disk_total_bytes = $DriveTotal
    last_remote_action = $LastAction
    session_broker = 'TASK_SCHEDULER_INTERACTIVE_ONE_SHOT_PROTECTED_EXECUTOR_V7'
    same_windows_user_required = $false
    credentials_embedded = $false
    health_class = $(if($TransportReady){'TRANSPORT_READY'}else{'DEGRADED'})
}

if ($Compact) { $Value | ConvertTo-Json -Compress -Depth 14 }
else { $Value | ConvertTo-Json -Depth 14 }
