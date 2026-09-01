param(
    [ValidateSet('Ensure','Status','Remove')]
    [string]$Mode = 'Ensure',
    [string]$Root = '',
    [string]$RemoteUser = 'CJLAdmin',
    [int]$DrainSeconds = 4,
    [switch]$Compact
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
}
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')

$MasterIdPath = Join-Path $Root 'App\Config\master.id'
$SourceBroker = Join-Path $PSScriptRoot 'CJL-Broker.ps1'
$SourceSession = Join-Path $PSScriptRoot 'CJL-Session.ps1'
if (-not (Test-Path -LiteralPath $MasterIdPath -PathType Leaf)) { throw "master.id ausente: $MasterIdPath" }
if (-not (Test-Path -LiteralPath $SourceBroker -PathType Leaf)) { throw "CJL-Broker.ps1 ausente: $SourceBroker" }
if (-not (Test-Path -LiteralPath $SourceSession -PathType Leaf)) { throw "CJL-Session.ps1 ausente: $SourceSession" }

$MasterId = (Get-Content -LiteralPath $MasterIdPath -Raw -Encoding UTF8).Trim()
if ([string]::IsNullOrWhiteSpace($MasterId)) { throw 'master.id vazio.' }

$SuffixSource = ($MasterId -replace '[^A-Za-z0-9]','')
$Suffix = if ($SuffixSource.Length -ge 8) { $SuffixSource.Substring($SuffixSource.Length - 8) } else { $SuffixSource }
$TaskName = "CJL Broker $Suffix"

$IdentityObject = [Security.Principal.WindowsIdentity]::GetCurrent()
$Identity = $IdentityObject.Name
$IdentitySid = $IdentityObject.User.Value
$CurrentSessionId = (Get-Process -Id $PID).SessionId

$RemoteLocalUser = Get-LocalUser -Name $RemoteUser -ErrorAction SilentlyContinue
if ($null -eq $RemoteLocalUser) { throw "Conta Windows remota ausente: $RemoteUser" }
if (-not $RemoteLocalUser.Enabled) { throw "Conta Windows remota desabilitada: $RemoteUser" }
$RemoteSid = $RemoteLocalUser.SID.Value
$RemoteAccount = "$env:COMPUTERNAME\$RemoteUser"

# A conta de transporte permanece não administrativa no Windows.
try {
    $AdminsGroup = Get-LocalGroup -SID 'S-1-5-32-544' -ErrorAction Stop
    $AdminMembers = @(Get-LocalGroupMember -Group $AdminsGroup.Name -ErrorAction Stop)
    $RemoteIsAdmin = @($AdminMembers | Where-Object {
        try { $_.SID.Value -eq $RemoteSid } catch { $false }
    }).Count -gt 0
    if ($RemoteIsAdmin) {
        throw "$RemoteAccount pertence ao grupo Administradores. O Remote Admin exige conta Windows dedicada sem privilégio administrativo global."
    }
}
catch {
    if ($_.Exception.Message -like '*pertence ao grupo Administradores*') { throw }
    throw ('Não foi possível confirmar que a conta de transporte permanece não administrativa: ' + $_.Exception.Message)
}

$AllowedSids = @($IdentitySid,$RemoteSid) | Select-Object -Unique
$AllowedSidText = ($AllowedSids -join ',')
$StateRoot = Join-Path $env:ProgramData ('CJL\RemoteAdmin\' + $MasterId)
$Pending = Join-Path $StateRoot 'Pending'
$Processing = Join-Path $StateRoot 'Processing'
$Results = Join-Path $StateRoot 'Results'
$HeartbeatPath = Join-Path $StateRoot 'broker_heartbeat.json'
$BrokerErrorPath = Join-Path $StateRoot 'broker_error.json'

# IMPORTANTE: o executor interativo NÃO fica em C:\CJL, pois CJLAdmin possui
# acesso administrativo aos arquivos da árvore CJL. A cópia protegida impede que
# uma chave SSH/SMB da conta CJLAdmin altere o código executado como o usuário
# interativo do Host.
$ExecutorRoot = Join-Path $env:ProgramData ('CJL\RemoteAdminExecutor\' + $MasterId)
$ExecutorBroker = Join-Path $ExecutorRoot 'CJL-Broker.ps1'
$ExecutorSession = Join-Path $ExecutorRoot 'CJL-Session.ps1'
$ExecutorManifest = Join-Path $ExecutorRoot 'executor.integrity.json'

$PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $ExecutorBroker + '" -Root "' + $Root + '" -AllowedRequesterSids "' + $AllowedSidText + '" -DrainSeconds ' + [Math]::Max(2,$DrainSeconds)

function Emit([object]$Value) {
    if ($Compact) { $Value | ConvertTo-Json -Compress -Depth 16 }
    else { $Value | ConvertTo-Json -Depth 16 }
}

function Test-Administrator {
    $P = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $P.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Add-DirectoryAclRule(
    [System.Security.AccessControl.DirectorySecurity]$Acl,
    [string]$Sid,
    [System.Security.AccessControl.FileSystemRights]$Rights
) {
    $SidObject = New-Object System.Security.Principal.SecurityIdentifier($Sid)
    $Inheritance = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $SidObject,
        $Rights,
        $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    [void]$Acl.AddAccessRule($Rule)
}

function Configure-StateAcl {
    New-Item -ItemType Directory -Force -Path $StateRoot,$Pending,$Processing,$Results | Out-Null
    $Acl = New-Object System.Security.AccessControl.DirectorySecurity
    $Acl.SetAccessRuleProtection($true,$false)
    Add-DirectoryAclRule $Acl 'S-1-5-18' ([System.Security.AccessControl.FileSystemRights]::FullControl)
    Add-DirectoryAclRule $Acl 'S-1-5-32-544' ([System.Security.AccessControl.FileSystemRights]::FullControl)
    Add-DirectoryAclRule $Acl $IdentitySid ([System.Security.AccessControl.FileSystemRights]::FullControl)
    Add-DirectoryAclRule $Acl $RemoteSid ([System.Security.AccessControl.FileSystemRights]::Modify)
    $Acl.SetOwner((New-Object System.Security.Principal.SecurityIdentifier($IdentitySid)))
    Set-Acl -LiteralPath $StateRoot -AclObject $Acl
    foreach ($Dir in @($Pending,$Processing,$Results)) {
        $ChildAcl = Get-Acl -LiteralPath $Dir
        $ChildAcl.SetAccessRuleProtection($false,$true)
        Set-Acl -LiteralPath $Dir -AclObject $ChildAcl
    }
}

function Configure-Executor {
    New-Item -ItemType Directory -Force -Path $ExecutorRoot | Out-Null
    $Acl = New-Object System.Security.AccessControl.DirectorySecurity
    $Acl.SetAccessRuleProtection($true,$false)
    Add-DirectoryAclRule $Acl 'S-1-5-18' ([System.Security.AccessControl.FileSystemRights]::FullControl)
    Add-DirectoryAclRule $Acl 'S-1-5-32-544' ([System.Security.AccessControl.FileSystemRights]::FullControl)
    Add-DirectoryAclRule $Acl $IdentitySid ([System.Security.AccessControl.FileSystemRights]::FullControl)
    $Acl.SetOwner((New-Object System.Security.Principal.SecurityIdentifier($IdentitySid)))
    Set-Acl -LiteralPath $ExecutorRoot -AclObject $Acl

    Copy-Item -LiteralPath $SourceBroker -Destination $ExecutorBroker -Force
    Copy-Item -LiteralPath $SourceSession -Destination $ExecutorSession -Force

    $BrokerHash = (Get-FileHash -LiteralPath $ExecutorBroker -Algorithm SHA256).Hash.ToLowerInvariant()
    $SessionHash = (Get-FileHash -LiteralPath $ExecutorSession -Algorithm SHA256).Hash.ToLowerInvariant()
    $Manifest = [ordered]@{
        format = 1
        product = 'CJL System'
        component = 'REMOTE_ADMIN_EXECUTOR_INTEGRITY_V1'
        master_id = $MasterId
        root = $Root
        broker_sha256 = $BrokerHash
        session_sha256 = $SessionHash
        protected_from_remote_sid = $RemoteSid
        generated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    }
    $Json = ($Manifest | ConvertTo-Json -Depth 8) + [Environment]::NewLine
    [IO.File]::WriteAllText($ExecutorManifest,$Json,(New-Object Text.UTF8Encoding($false)))

    # Reaplica ACL no diretório para garantir que os arquivos recém-criados
    # herdem apenas SYSTEM, Administrators e o usuário interativo provisionador.
    Set-Acl -LiteralPath $ExecutorRoot -AclObject $Acl

    return $Manifest
}

function Read-Heartbeat {
    if (-not (Test-Path -LiteralPath $HeartbeatPath -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $HeartbeatPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

function Test-HeartbeatAlive([object]$Heartbeat) {
    if ($null -eq $Heartbeat) { return $false }
    try {
        if ([int]$Heartbeat.protocol -ne 7) { return $false }
        $When = [DateTimeOffset]::Parse([string]$Heartbeat.updated_at)
        return ([DateTimeOffset]::Now - $When).TotalSeconds -le 15
    }
    catch { return $false }
}

function Get-TaskSddl {
    try {
        $Service = New-Object -ComObject 'Schedule.Service'
        $Service.Connect()
        $Folder = $Service.GetFolder('\')
        $Registered = $Folder.GetTask("\$TaskName")
        return [string]$Registered.GetSecurityDescriptor(4)
    }
    catch { return '' }
}

function Grant-TaskReadExecute {
    $Service = New-Object -ComObject 'Schedule.Service'
    $Service.Connect()
    $Folder = $Service.GetFolder('\')
    $Registered = $Folder.GetTask("\$TaskName")
    $Sddl = [string]$Registered.GetSecurityDescriptor(4)
    if ([string]::IsNullOrWhiteSpace($Sddl) -or -not $Sddl.StartsWith('D:')) {
        throw 'Não foi possível ler a DACL da tarefa do Broker.'
    }
    $SidEscaped = [regex]::Escape($RemoteSid)
    $Clean = [regex]::Replace($Sddl, '\([^)]*;;;' + $SidEscaped + '\)', '')
    $ExpectedAce = "(A;;GRGX;;;$RemoteSid)"
    $NewSddl = $Clean + $ExpectedAce
    $Registered.SetSecurityDescriptor($NewSddl,0)
    $Verify = [string]$Registered.GetSecurityDescriptor(4)
    if ($Verify -notmatch [regex]::Escape($RemoteSid)) {
        throw 'A DACL da tarefa não confirmou acesso do CJLAdmin.'
    }
    return $Verify
}

function Task-Info {
    $Task = $null
    try { $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
    if ($null -eq $Task) {
        return [ordered]@{
            exists = $false; task_name = $TaskName; identity = $Identity; session_id = $CurrentSessionId;
            remote_account = $RemoteAccount; state_root = $StateRoot; executor_root = $ExecutorRoot; task_sddl = (Get-TaskSddl)
        }
    }
    $Info = $null
    try { $Info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop } catch {}
    $A = @($Task.Actions | Select-Object -First 1)
    return [ordered]@{
        exists = $true
        task_name = $TaskName
        state = [string]$Task.State
        principal = [string]$Task.Principal.UserId
        logon_type = [string]$Task.Principal.LogonType
        run_level = [string]$Task.Principal.RunLevel
        multiple_instances = [string]$Task.Settings.MultipleInstances
        execute = $(if($A.Count){[string]$A[0].Execute}else{''})
        arguments = $(if($A.Count){[string]$A[0].Arguments}else{''})
        working_directory = $(if($A.Count){[string]$A[0].WorkingDirectory}else{''})
        last_run_time = $(if($null -ne $Info){$Info.LastRunTime}else{$null})
        last_task_result = $(if($null -ne $Info){[int64]$Info.LastTaskResult}else{$null})
        identity = $Identity
        session_id = $CurrentSessionId
        remote_account = $RemoteAccount
        remote_sid = $RemoteSid
        task_sddl = (Get-TaskSddl)
        state_root = $StateRoot
        executor_root = $ExecutorRoot
        executor_manifest = $ExecutorManifest
    }
}

if ($Mode -eq 'Status') {
    $Heartbeat = Read-Heartbeat
    $Alive = Test-HeartbeatAlive $Heartbeat
    $BrokerError = $null
    if (Test-Path -LiteralPath $BrokerErrorPath -PathType Leaf) {
        try { $BrokerError = Get-Content -LiteralPath $BrokerErrorPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }
    $TaskState = Task-Info
    Emit ([ordered]@{
        ok = $true
        status = $(if([bool]$TaskState.exists){'BROKER_TASK_READY'}else{'BROKER_TASK_MISSING'})
        heartbeat_alive = $Alive
        heartbeat = $Heartbeat
        broker_error = $BrokerError
        task = $TaskState
        task_wake_authorized_sid = $RemoteSid
        state_root = $StateRoot
        executor_root = $ExecutorRoot
    })
    exit 0
}

if (-not (Test-Administrator)) { throw 'Ensure/Remove do Broker exige PowerShell como Administrador.' }

if ($Mode -eq 'Remove') {
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    try { Remove-Item -LiteralPath $ExecutorRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    Emit ([ordered]@{ok=$true;status='BROKER_REMOVED';task_name=$TaskName;state_root=$StateRoot;executor_root=$ExecutorRoot})
    exit 0
}

if ($CurrentSessionId -le 0) {
    throw 'O Broker deve ser provisionado a partir da sessão Windows interativa do operador do Host.'
}

Configure-StateAcl
Remove-Item -LiteralPath $HeartbeatPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $BrokerErrorPath -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $Pending,$Processing -Filter '*.json' -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

$ExecutorState = Configure-Executor
$TaskAction = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $ExecutorRoot
$TaskPrincipal = New-ScheduledTaskPrincipal -UserId $Identity -LogonType Interactive -RunLevel Limited
$TaskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances Queue

# Tarefa deliberadamente SEM trigger. Ela só é acionada por demanda pelo
# contrato remoto. O principal Interactive exige que o usuário do Host esteja
# autenticado em uma sessão interativa.
Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Principal $TaskPrincipal -Settings $TaskSettings -Force | Out-Null
$TaskSddl = Grant-TaskReadExecute

Emit ([ordered]@{
    ok = $true
    status = 'BROKER_TASK_READY'
    protocol = 7
    task = (Task-Info)
    task_sddl = $TaskSddl
    remote_account = $RemoteAccount
    remote_sid = $RemoteSid
    state_root = $StateRoot
    executor_root = $ExecutorRoot
    executor_integrity = $ExecutorState
    same_windows_user_required = $false
    wake_model = 'ON_DEMAND_ONE_SHOT_TASK_READ_EXECUTE_ACL'
    broker_resident = $false
    task_triggered_automatically = $false
})
exit 0
