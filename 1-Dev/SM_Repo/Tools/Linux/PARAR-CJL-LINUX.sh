#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
config="$script_dir/CJL-LINUX.conf"
runtime="$(sed -n 's/^CJL_LINUX_PYTHON=//p' "$config")"
state="$(sed -n 's/^CJL_LINUX_STATE_ROOT=//p' "$config")"
registry="$state/Instancia/instance.json"

[[ -x "$runtime" ]] || {
    printf '[STOP] Linux Python is unavailable: %s\n' "$runtime" >&2
    exit 2
}
[[ -f "$registry" ]] || {
    printf '[PASS] CJL_LINUX_ALREADY_OFFLINE=YES\n'
    exit 0
}

instance="$("$runtime" - "$registry" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(
    f"{int(value.get('pid') or 0)}\t"
    f"{int(value.get('port') or 0)}\t"
    f"{str(value.get('token') or '')}"
)
PY
)"
IFS=$'\t' read -r pid port token <<<"$instance"
url="http://127.0.0.1:${port}"

if ! kill -0 "$pid" 2>/dev/null; then
    printf '[PASS] CJL_LINUX_ALREADY_OFFLINE=YES\n'
    exit 0
fi

curl -fsS --max-time 5 \
    -H 'Content-Type: application/json' \
    -X POST \
    -d "{\"token\":\"$token\"}" \
    "$url/api/instance/shutdown" >/dev/null

for _ in $(seq 1 150); do
    if ! kill -0 "$pid" 2>/dev/null; then
        printf '[PASS] CJL_LINUX_STOP=PASS\nPID=%s\n' "$pid"
        exit 0
    fi
    sleep 0.1
done

printf '[STOP] CJL did not complete its authorized shutdown in 15 seconds.\n' >&2
exit 2
