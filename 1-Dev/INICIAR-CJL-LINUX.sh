#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
system="$script_dir/System"
tools_linux="$script_dir/SM_Repo/Tools/Linux"
tools_windows="$script_dir/SM_Repo/Tools/Windows"
config="$tools_linux/CJL-LINUX.conf"
validator="$tools_linux/CJL-LINUX-VALIDAR.py"
windows_opener="$tools_windows/ABRIR-CJL-WINDOWS.ps1"
power_shell="${CJL_WINDOWS_POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"
windows_workdir="${CJL_WINDOWS_WORKDIR:-/mnt/c}"

stop() {
    printf '[STOP] %s\n' "$1" >&2
    exit 2
}

read_config_value() {
    local key="$1"
    local value
    value="$(sed -n "s/^${key}=//p" "$config")"
    if [[ -z "$value" || "$value" == *$'\n'* ]]; then
        stop "Invalid configuration key: $key"
    fi
    printf '%s' "$value"
}

[[ -d "$system" ]] || stop "System directory is absent: $system"
[[ -f "$config" ]] || stop "Linux configuration is absent: $config"
[[ -f "$validator" ]] || stop "Linux validator is absent: $validator"
[[ -f "$windows_opener" ]] || stop "Windows opener is absent: $windows_opener"
command -v curl >/dev/null 2>&1 || stop 'curl is absent.'
command -v wslpath >/dev/null 2>&1 || stop 'wslpath is absent.'

runtime="$(read_config_value 'CJL_LINUX_PYTHON')"
state="$(read_config_value 'CJL_LINUX_STATE_ROOT')"
version_file="/cjl/Sistema_Dev/VERSION"
[[ "$runtime" == /* ]] || stop 'CJL_LINUX_PYTHON must be an absolute Linux path.'
[[ "$state" == /* ]] || stop 'CJL_LINUX_STATE_ROOT must be an absolute Linux path.'
[[ -f "$version_file" ]] || stop "Canonical DEV VERSION is absent: $version_file"
[[ -x "$runtime" ]] || stop "Linux Python is unavailable: $runtime"
[[ -x "$power_shell" ]] || stop "Windows PowerShell is unavailable: $power_shell"

export PYTHONDONTWRITEBYTECODE=1
export CJL_NETWORK_ROOT="$system"
export CJL_STATE_ROOT="$state"
export CJL_VERSION_FILE="$version_file"
export CJL_BROWSER_MANAGED=1

"$runtime" "$validator" "$system" >/dev/null

registry="$state/Instancia/instance.json"
logs_root="${CJL_LINUX_LOGS_ROOT:-/mnt/c/CJL_Work_Evidence/Linux-Runs/1-Dev}"
mkdir -p -- "$logs_root" "$state/Instancia"

read_instance() {
    "$runtime" - "$registry" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pid = int(value.get("pid") or 0)
port = int(value.get("port") or 0)
token = str(value.get("token") or "")
if pid < 1 or not 1 <= port <= 65535 or not token:
    raise SystemExit(2)
print(f"{pid}\t{port}\t{token}")
PY
}

open_windows() {
    local url="$1"
    local windows_script
    [[ -d "$windows_workdir" ]] || return 1
    windows_script="$(wslpath -w "$windows_opener")" ||
        stop 'Could not convert the Windows opener path.'
    if ! (
        cd "$windows_workdir" || exit 2
        "$power_shell" \
            -NoLogo \
            -NoProfile \
            -NonInteractive \
            -ExecutionPolicy Bypass \
            -File "$windows_script" \
            -Url "$url"
    ); then
        return 1
    fi
}

if [[ -f "$registry" ]]; then
    instance="$(read_instance 2>/dev/null || true)"
    if [[ -n "$instance" ]]; then
        IFS=$'\t' read -r current_pid current_port current_token <<<"$instance"
        current_url="http://127.0.0.1:${current_port}"
        if kill -0 "$current_pid" 2>/dev/null &&
            curl -fsS --max-time 4 \
                "$current_url/api/instance/ping?token=$current_token" \
                >/dev/null
        then
            printf '[PASS] CJL_LINUX_ALREADY_RUNNING=YES\n'
            printf 'PID=%s\nURL=%s\n' "$current_pid" "$current_url"
            open_windows "$current_url" ||
                stop 'Windows could not reach the active CJL instance.'
            exit 0
        fi
    fi
    stale="$logs_root/instance.stale.$(date +%Y%m%dT%H%M%S).json"
    mv -- "$registry" "$stale"
fi

stamp="$(TZ=America/Sao_Paulo date +%Y%m%dT%H%M%S)"
run_dir="$logs_root/$stamp"
mkdir -p -- "$run_dir"
server_log="$run_dir/server.log"

nohup env \
    PYTHONDONTWRITEBYTECODE=1 \
    CJL_NETWORK_ROOT="$system" \
    CJL_STATE_ROOT="$state" \
    CJL_BROWSER_MANAGED=1 \
    "$runtime" -u "$system/App/painel.py" \
    >"$server_log" 2>&1 </dev/null &
server_pid=$!

startup_failed() {
    local message="$1"
    if kill -0 "$server_pid" 2>/dev/null; then
        kill -TERM "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    sed -n '1,200p' "$server_log" >&2 || true
    stop "$message"
}

instance=''
for _ in $(seq 1 300); do
    if ! kill -0 "$server_pid" 2>/dev/null; then
        startup_failed 'CJL Linux process terminated during startup.'
    fi
    if [[ -f "$registry" ]]; then
        instance="$(read_instance 2>/dev/null || true)"
        [[ -n "$instance" ]] && break
    fi
    sleep 0.1
done

[[ -n "$instance" ]] ||
    startup_failed 'CJL instance registry was not published in 30 seconds.'
IFS=$'\t' read -r published_pid port token <<<"$instance"
[[ "$published_pid" == "$server_pid" ]] ||
    startup_failed 'Published PID differs from the launched process.'
url="http://127.0.0.1:${port}"

if ! curl -fsS --max-time 5 \
    "$url/api/instance/ping?token=$token" \
    >"$run_dir/linux-ping.json"
then
    startup_failed 'Linux HTTP gate failed.'
fi

printf '%s\n' "$url" >"$run_dir/current-url.txt"

if ! open_windows "$url"; then
    curl -fsS --max-time 5 \
        -H 'Content-Type: application/json' \
        -X POST \
        -d "{\"token\":\"$token\"}" \
        "$url/api/instance/shutdown" >/dev/null 2>&1 || true
    startup_failed 'Windows localhost could not reach the Linux CJL instance.'
fi

printf '[PASS] CJL_LINUX_START=PASS\n'
printf 'PID=%s\nURL=%s\nLOG=%s\n' "$server_pid" "$url" "$server_log"
printf 'SYSTEM_WRITE=APPLICATION_RUNTIME_ALLOWED\n'
printf 'GITHUB_WRITE=NO\nPRODUCTION_WRITE=NO\n'
