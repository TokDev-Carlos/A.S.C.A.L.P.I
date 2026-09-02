#!/usr/bin/env bash
set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
dev_root="$(CDPATH= cd -- "$script_dir/../../../" && pwd -P)"
config="$script_dir/CJL-LINUX.conf"
engine="$script_dir/ASCALPI-LINUX-PATCH.py"
status_script="$script_dir/STATUS-CJL-LINUX.sh"
selector="$dev_root/SM_Repo/Tools/Windows/ASCALPI-SELECT-PATCH.ps1"
powershell="${CJL_WINDOWS_POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"

read_conf() {
    local key="$1"
    sed -n "s/^${key}=//p" "$config" | head -n 1
}

runtime="$(read_conf CJL_LINUX_PYTHON)"

pause_menu() {
    printf '\nPressione ENTER para continuar...'
    IFS= read -r _
}

run_engine() {
    "$runtime" "$engine" "$@"
    local rc=$?
    printf '\nExitCode=%s\n' "$rc"
    return "$rc"
}

header() {
    clear 2>/dev/null || true
    printf '%s\n' '=============================================================='
    printf '%s\n' ' ASCALPI - DESENVOLVIMENTO LINUX'
    printf '%s\n' ' Ubuntu-24.04 | 1-Dev | Linux Patch Stage R1'
    printf '%s\n' '=============================================================='
    printf '\n'
}

doctor_or_stop() {
    [[ -f "$config" ]] || { printf '[STOP] Config ausente: %s\n' "$config" >&2; return 2; }
    [[ -x "$runtime" ]] || { printf '[STOP] Python Linux indisponível: %s\n' "$runtime" >&2; return 2; }
    [[ -f "$engine" ]] || { printf '[STOP] Motor Linux ausente: %s\n' "$engine" >&2; return 2; }
    "$runtime" "$engine" doctor >/dev/null || return $?
    return 0
}

import_select_menu() {
    while true; do
        header
        cat <<'EOF'
IMPORTAR / SELECIONAR PATCH

 1 - Escolher arquivo pelo Windows
 2 - Informar caminho manualmente
 3 - Selecionar patch já gerenciado
 0 - Voltar
EOF
        printf '\nOpção: '
        IFS= read -r op
        case "$op" in
            1)
                if [[ ! -x "$powershell" ]]; then
                    printf '[STOP] Windows PowerShell indisponível.\n'
                    pause_menu
                    continue
                fi
                if [[ ! -f "$selector" ]]; then
                    printf '[STOP] Seletor Windows ausente: %s\n' "$selector"
                    pause_menu
                    continue
                fi
                selector_win="$(wslpath -w "$selector" 2>/dev/null)" || {
                    printf '[STOP] Não foi possível converter o caminho do seletor.\n'
                    pause_menu
                    continue
                }
                win_path="$("$powershell" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$selector_win" 2>/dev/null | tr -d '\r' | tail -n 1)"
                if [[ -z "$win_path" ]]; then
                    printf 'Seleção cancelada.\n'
                    pause_menu
                    continue
                fi
                linux_path="$(wslpath -u "$win_path" 2>/dev/null)" || {
                    printf '[STOP] Caminho Windows não pôde ser convertido para WSL: %s\n' "$win_path"
                    pause_menu
                    continue
                }
                printf '\nArquivo selecionado:\n%s\n' "$win_path"
                printf '\nO patch será MOVIDO para SM_Repo/Patches/Entrada.\n'
                printf 'Digite MOVER para confirmar: '
                IFS= read -r confirm
                if [[ "$confirm" == "MOVER" ]]; then
                    run_engine import "$linux_path"
                else
                    printf 'Importação cancelada.\n'
                fi
                pause_menu
                ;;
            2)
                printf '\nInforme o caminho Linux/WSL do ZIP.\n'
                printf 'Exemplo: /mnt/c/Users/.../Downloads/PATCH.zip\n> '
                IFS= read -r manual
                [[ -n "$manual" ]] || { printf 'Cancelado.\n'; pause_menu; continue; }
                printf 'Digite MOVER para confirmar: '
                IFS= read -r confirm
                if [[ "$confirm" == "MOVER" ]]; then
                    run_engine import "$manual"
                else
                    printf 'Importação cancelada.\n'
                fi
                pause_menu
                ;;
            3)
                run_engine select
                pause_menu
                ;;
            0) return 0 ;;
            *) printf 'Opção inválida.\n'; sleep 1 ;;
        esac
    done
}

approve_patch() {
    header
    run_engine evidence || true
    printf '\nA aprovação só será aceita com validação, aplicação e testes obrigatórios PASS.\n'
    printf 'Segurança é informativa e NÃO bloqueia nesta revisão.\n\n'
    printf 'Digite exatamente APROVAR LINUX PASS para confirmar:\n> '
    IFS= read -r phrase
    if [[ "$phrase" != "APROVAR LINUX PASS" ]]; then
        printf 'Aprovação cancelada.\n'
        pause_menu
        return
    fi
    run_engine approve
    pause_menu
}

reject_patch() {
    header
    run_engine evidence || true
    printf '\nMotivo objetivo da reprovação:\n> '
    IFS= read -r reason
    [[ -n "$reason" ]] || { printf 'Reprovação cancelada: motivo vazio.\n'; pause_menu; return; }
    printf '\nDigite exatamente REPROVAR PATCH para confirmar:\n> '
    IFS= read -r phrase
    if [[ "$phrase" != "REPROVAR PATCH" ]]; then
        printf 'Reprovação cancelada.\n'
        pause_menu
        return
    fi
    run_engine reject --reason "$reason"
    pause_menu
}

run_tests_menu() {
    header
    cat <<'EOF'
TESTES DO PATCH

Obrigatórios para LINUX_PASS:
 - Integridade
 - Smoke funcional
 - Regressão controlada

Segurança:
 - Opcional / informativa nesta revisão
 - PASS, WARNING ou NOT_RUN
 - NÃO bloqueia LINUX_PASS
EOF
    printf '\nExecutar também o teste opcional de segurança? [s/N]: '
    IFS= read -r sec
    if [[ "$sec" == "s" || "$sec" == "S" ]]; then
        run_engine tests --security
    else
        run_engine tests
    fi
    pause_menu
}

if ! doctor_or_stop; then
    printf '\nO motor Linux não passou no diagnóstico inicial.\n'
    printf 'Pressione ENTER para abrir um shell normal...'
    IFS= read -r _
    exec bash -l
fi

while true; do
    header
    cat <<'EOF'
 1 - Status do ambiente
 2 - Verificar integridade do 1-Dev

 3 - IMPORTAR / SELECIONAR PATCH
 4 - LISTAR PATCHES
 5 - Validar Patch Atual
 6 - Aplicar Patch Atual
 7 - Executar testes do Patch

 8 - APROVAR - LINUX PASS
 9 - REPROVAR / RESTAURAR

10 - Excluir patches antigos
11 - Ver resultado / evidências

 0 - Sair para Shell Linux
EOF
    printf '\nOpção: '
    IFS= read -r op

    case "$op" in
        1)
            header
            printf '%s\n' '--- STATUS DO PROCESSO LINUX ---'
            bash "$status_script" || true
            printf '\n%s\n' '--- STATUS DO ESTÁGIO DE PATCH ---'
            run_engine status || true
            pause_menu
            ;;
        2)
            header
            run_engine integrity
            pause_menu
            ;;
        3)
            import_select_menu
            ;;
        4)
            header
            run_engine list
            pause_menu
            ;;
        5)
            header
            run_engine validate
            pause_menu
            ;;
        6)
            header
            cat <<'EOF'
APLICAÇÃO CONTROLADA

O motor irá:
 - confirmar PATCH_READY;
 - fechar o ASCALPI Linux de forma autorizada;
 - confirmar ausência de processos relacionados;
 - criar lock de manutenção;
 - validar integridade antes de alterar;
 - criar backup com hashes;
 - aplicar somente operações declaradas pelo Patch Format 7;
 - reconstruir a integridade da App usando o Python Linux;
 - validar o sistema depois da aplicação;
 - executar rollback automático se qualquer gate falhar.

O ambiente permanece OFFLINE ao concluir a aplicação.
EOF
            printf '\nDigite APLICAR PATCH para continuar:\n> '
            IFS= read -r phrase
            if [[ "$phrase" == "APLICAR PATCH" ]]; then
                run_engine apply
            else
                printf 'Aplicação cancelada.\n'
            fi
            pause_menu
            ;;
        7)
            run_tests_menu
            ;;
        8)
            approve_patch
            ;;
        9)
            reject_patch
            ;;
        10)
            header
            run_engine delete
            pause_menu
            ;;
        11)
            header
            run_engine evidence
            pause_menu
            ;;
        0)
            printf '\nMenu encerrado. Entrando no Shell Linux normal.\n'
            exec bash -l
            ;;
        *)
            printf 'Opção inválida.\n'
            sleep 1
            ;;
    esac
done
