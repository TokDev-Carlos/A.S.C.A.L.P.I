param(
    [ValidateSet('Open','Focus','Close')]
    [string]$Action,
    [string]$Root,
    [string]$RequestId = '',
    [string]$ResultPath = ''
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if ([string]::IsNullOrWhiteSpace($RequestId)) { $RequestId = [Guid]::NewGuid().ToString('N') }
$LogDir = Join-Path $Root 'Logs\RemoteAdmin'
$RequestDir = Join-Path $LogDir 'Requests'
New-Item -ItemType Directory -Force -Path $RequestDir | Out-Null
if ([string]::IsNullOrWhiteSpace($ResultPath)) { $ResultPath = Join-Path $RequestDir ($RequestId + '.json') }
$LastStateFile = Join-Path $LogDir 'last_action.json'

if (-not ('CJLRemoteAdmin.WindowNativeV7' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace CJLRemoteAdmin
{
    public static class WindowNativeV7
    {
        [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
    }
}
'@
}

function Current-SessionId { return (Get-Process -Id $PID).SessionId }
function Get-HostProcesses {
    $sid = Current-SessionId
    return @(Get-Process -Name 'CJL.Host' -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sid })
}
function Find-WindowProcess([int]$TimeoutSeconds) {
    $limit = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        foreach ($p in (Get-HostProcesses)) {
            try {
                $p.Refresh()
                if ($p.MainWindowHandle -ne 0 -and [CJLRemoteAdmin.WindowNativeV7]::IsWindow($p.MainWindowHandle)) { return $p }
            } catch {}
        }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $limit)
    return $null
}
function Prepare-Window([int]$TimeoutSeconds = 8) {
    $p = Find-WindowProcess $TimeoutSeconds
    if ($null -eq $p) { return $null }
    $h = $p.MainWindowHandle
    $restore = [CJLRemoteAdmin.WindowNativeV7]::ShowWindowAsync($h, 9)
    Start-Sleep -Milliseconds 100
    $maximize = [CJLRemoteAdmin.WindowNativeV7]::ShowWindowAsync($h, 3)
    $top = [CJLRemoteAdmin.WindowNativeV7]::BringWindowToTop($h)
    $foreground = [CJLRemoteAdmin.WindowNativeV7]::SetForegroundWindow($h)
    return [pscustomobject]@{process=$p;restore=$restore;maximize=$maximize;top=$top;foreground=$foreground}
}
function Latest-BootstrapLogTail {
    $dir = Join-Path $Root 'Logs\Bootstrap'
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { return @() }
    $latest = Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $latest) { return @() }
    try { return @(Get-Content -LiteralPath $latest.FullName -Tail 24 -ErrorAction Stop) } catch { return @() }
}
function Write-State([object]$Value) {
    $Value.complete = $true
    $json = $Value | ConvertTo-Json -Depth 10
    $tmp = $ResultPath + '.tmp'
    $json | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $ResultPath -Force
    $lastTmp = $LastStateFile + '.' + $RequestId + '.tmp'
    $json | Set-Content -LiteralPath $lastTmp -Encoding UTF8
    Move-Item -LiteralPath $lastTmp -Destination $LastStateFile -Force
}

$result = [ordered]@{
    product = 'CJL System'
    component = 'REMOTE_ADMIN_SESSION_ACTION_V7'
    protocol = 7
    request_id = $RequestId
    action = $Action
    session_id = (Current-SessionId)
    executed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    complete = $false
    ok = $false
    status = 'UNKNOWN'
}

try {
    if ($Action -eq 'Open') {
        $existing = @(Get-HostProcesses)
        if ($existing.Count -eq 0) {
            $launcher = Join-Path $Root 'CJL.exe'
            if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Launcher missing: $launcher" }
            $lp = Start-Process -FilePath $launcher -ArgumentList @("--open-master") -WorkingDirectory $Root -PassThru
            $result.launcher_pid = [int]$lp.Id
            $result.launcher_started = $true
        } else {
            $result.launcher_started = $false
            $result.existing_host_pids = @($existing | Select-Object -ExpandProperty Id)
        }
        $prepared = Prepare-Window 45
        if ($null -ne $prepared) {
            $result.host_pid = [int]$prepared.process.Id
            $result.window_handle = [int64]$prepared.process.MainWindowHandle
            $result.restore_requested = [bool]$prepared.restore
            $result.maximize_requested = [bool]$prepared.maximize
            $result.bring_to_top = [bool]$prepared.top
            $result.set_foreground = [bool]$prepared.foreground
            $result.ok = $true
            $result.status = 'OPEN_WINDOW_READY'
        } else {
            $result.ok = $false
            $result.status = 'OPEN_FAILED_WINDOW_NOT_FOUND'
            $result.host_pids = @(Get-HostProcesses | Select-Object -ExpandProperty Id)
            $result.bootstrap_log_tail = @(Latest-BootstrapLogTail)
        }
    }
    elseif ($Action -eq 'Focus') {
        $prepared = Prepare-Window 10
        if ($null -ne $prepared) {
            $result.host_pid = [int]$prepared.process.Id
            $result.window_handle = [int64]$prepared.process.MainWindowHandle
            $result.restore_requested = [bool]$prepared.restore
            $result.maximize_requested = [bool]$prepared.maximize
            $result.bring_to_top = [bool]$prepared.top
            $result.set_foreground = [bool]$prepared.foreground
            $result.ok = $true
            $result.status = 'WINDOW_READY_MAXIMIZED'
        } else {
            $result.ok = $false
            $result.status = 'WINDOW_NOT_FOUND'
        }
    }
    elseif ($Action -eq 'Close') {
        $items = @(Get-HostProcesses)
        if ($items.Count -eq 0) {
            $result.ok = $true
            $result.status = 'ALREADY_CLOSED'
        } else {
            foreach ($p in $items) { try { [void]$p.CloseMainWindow() } catch {} }
            $limit = (Get-Date).AddSeconds(15)
            do {
                Start-Sleep -Milliseconds 400
                $remaining = @(Get-HostProcesses)
            } while ($remaining.Count -gt 0 -and (Get-Date) -lt $limit)
            $forced = $false
            if ($remaining.Count -gt 0) {
                $forced = $true
                foreach ($p in $remaining) { try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {} }
                Start-Sleep -Milliseconds 600
                $remaining = @(Get-HostProcesses)
            }
            $result.ok = ($remaining.Count -eq 0)
            $result.forced = $forced
            $result.status = $(if ($result.ok) { $(if ($forced) { 'CLOSED_FORCED_AFTER_GRACE' } else { 'CLOSED' }) } else { 'CLOSE_FAILED_PROCESS_REMAINS' })
            $result.remaining_pids = @($remaining | Select-Object -ExpandProperty Id)
        }
    }
}
catch {
    $result.ok = $false
    $result.status = 'ERROR'
    $result.error = $_.Exception.Message
}

Write-State $result
$result | ConvertTo-Json -Compress -Depth 10
if ($result.ok) { exit 0 } else { exit 5 }
