#!/usr/bin/env bash
# Source this file, then call `runlog_setup` near the top of a script to
# self-register its run in RUN_LOG.md -- the Bash counterpart to
# `log_tools.setup.runlog_setup()` (see that module's docstring for the
# full design rationale: PPID-scoped order counter, TTL-based
# staleness, mkdir-based locking). Do not execute directly.
#
# `runlog_setup` takes no arguments: script_id is derived from the
# calling script's own filename, order from a counter scoped to this
# pipeline run (identified by $PPID, shared with any sibling script
# invoked directly by the same orchestrator process), and
# RUNLOG_LOG_FILE/RUNLOG_ROOT env vars (falling back to the same
# git-toplevel/RUN_LOG.md defaults as the `runlog` CLI) locate the log.
# Call it at most once per script, before any output the script wants
# captured.
#
# RUNLOG_SCRIPT_ID/RUNLOG_ORDER env vars, if set, override the
# auto-derived id/order outright (mirroring `log_tools.setup.
# runlog_setup()`'s script_id/order params) -- needed whenever a step's
# real run-time process ancestry doesn't match its logical pipeline
# position: a script submitted to a batch scheduler (its $PPID at
# execution time has no relation to the submitting shell), a script
# invoked multiple times with a distinct identity each time (e.g. one
# per-cohort call of a shared extraction script), or a step re-invoked
# from a fresh orchestrator process in a later, separate stage of a
# multi-stage pipeline.
#
# Sources emitter.sh internally so one `source "$(runlog-setup-path)"`
# line gives a script both `runlog_setup` and `log_info`/`log_warn`/
# `log_error`/`log_debug`.

# shellcheck disable=SC1091  # sibling file, resolved relative to this one
source "$(dirname "${BASH_SOURCE[0]}")/emitter.sh"

_RUNLOG_ORDER_STEP=10
_RUNLOG_STATE_TTL_SECONDS=86400
# Must match log_tools.runlog.Constants.ERROR_TAIL_DIVIDER exactly --
# Bash can't import the Python constant, so this is a deliberate,
# documented duplication of that literal string.
_RUNLOG_ERROR_TAIL_DIVIDER="--- error output (raw) ---"


# -----------------------------------------------------------------------
# Print the order-state file path for run id $1 (a PPID).
#
# Parameters
# ----------
#   $1 - ppid : The run-identity key.
#
# Outputs
# -------
#   Writes the path to stdout.
# -----------------------------------------------------------------------
_runlog_state_path() {
    local ppid="${1:?Error: ppid required}"
    echo "${TMPDIR:-/tmp}/runlog-order-${ppid}.state"
}


# -----------------------------------------------------------------------
# Print the order-state lock directory path for run id $1 (a PPID).
#
# Parameters
# ----------
#   $1 - ppid : The run-identity key.
#
# Outputs
# -------
#   Writes the path to stdout.
# -----------------------------------------------------------------------
_runlog_lock_path() {
    local ppid="${1:?Error: ppid required}"
    echo "${TMPDIR:-/tmp}/runlog-order-${ppid}.lock"
}


# -----------------------------------------------------------------------
# Acquire an advisory lock at $1 via atomic mkdir, retrying briefly.
#
# Parameters
# ----------
#   $1 - lock_dir : Directory path to create as the lock.
#
# Returns
# -------
#   0 if acquired, 1 if `LOCK_MAX_TRIES` was exceeded (fail open --
#   callers must not let this abort the script under `set -e`, hence
#   always invoked as `_runlog_acquire_lock ... || true`).
# -----------------------------------------------------------------------
_runlog_acquire_lock() {
    local lock_dir="${1:?Error: lock_dir required}"
    local tries=0
    until mkdir "${lock_dir}" 2>/dev/null; do
        tries=$((tries + 1))
        if [[ "${tries}" -ge 200 ]]; then
            log_warn \
                    "could not acquire order-state lock ${lock_dir};" \
                    " proceeding unlocked" no-record
            return 1
        fi
        sleep 0.05
    done
    return 0
}


# -----------------------------------------------------------------------
# Release a lock directory acquired via `_runlog_acquire_lock`.
#
# Parameters
# ----------
#   $1 - lock_dir : Directory path to remove.
# -----------------------------------------------------------------------
_runlog_release_lock() {
    local lock_dir="${1:?Error: lock_dir required}"
    rmdir "${lock_dir}" 2>/dev/null || true
}


# -----------------------------------------------------------------------
# Resolve script_id's order within the pipeline run keyed by ppid,
# reusing an existing assignment or handing out a fresh one.
#
# Parameters
# ----------
#   $1 - ppid      : Run-identity key -- the calling script's parent PID.
#   $2 - script_id : The registering script's id.
#
# Outputs
# -------
#   Writes the resolved order (an integer) to stdout.
#
# Notes
# -----
# Uses the same plain-text `KEY=value` state-file format as
# `log_tools.setup._parse_state`/`_serialize_state`, so Python and Bash
# steps in one mixed pipeline share one consistent state file per run.
# -----------------------------------------------------------------------
_runlog_resolve_order() {
    local ppid="${1:?Error: ppid required}"
    local script_id="${2:?Error: script_id required}"
    local state_path lock_path
    state_path="$(_runlog_state_path "${ppid}")"
    lock_path="$(_runlog_lock_path "${ppid}")"

    _runlog_acquire_lock "${lock_path}" || true

    local -A state=()
    if [[ -f "${state_path}" ]]; then
        local key value
        while IFS='=' read -r key value; do
            [[ -z "${key}" ]] && continue
            state["${key}"]="${value}"
        done < "${state_path}"
    fi

    local now created_at is_stale=1
    now="$(date +%s)"
    created_at="${state[CREATED_AT]:-}"
    if [[ -n "${created_at}" ]]; then
        local age=$(( now - ${created_at%.*} ))
        [[ "${age}" -le "${_RUNLOG_STATE_TTL_SECONDS}" ]] && is_stale=0
    fi
    if [[ "${is_stale}" -eq 1 ]]; then
        state=()
        state[CREATED_AT]="${now}"
        state[NEXT_ORDER]="${_RUNLOG_ORDER_STEP}"
    fi

    local order
    if [[ -n "${state[${script_id}]:-}" ]]; then
        order="${state[${script_id}]}"
    else
        order="${state[NEXT_ORDER]:-${_RUNLOG_ORDER_STEP}}"
        state["${script_id}"]="${order}"
        state[NEXT_ORDER]=$(( order + _RUNLOG_ORDER_STEP ))
    fi

    local out_key
    {
        for out_key in "${!state[@]}"; do
            echo "${out_key}=${state[${out_key}]}"
        done
    } > "${state_path}.tmp"
    mv "${state_path}.tmp" "${state_path}"

    _runlog_release_lock "${lock_path}"
    echo "${order}"
}


# -----------------------------------------------------------------------
# Register the current script's run: resolve id/order/location, start
# capturing its output, and arm the recording teardown on EXIT.
#
# Outputs
# -------
#   Merges stderr into stdout and tees the combined stream to a temp
#   file for the remainder of the script's life (matching
#   `runlog run`'s merged-capture behaviour), while still printing live.
# -----------------------------------------------------------------------
runlog_setup() {
    local caller_script base
    if [[ -n "${RUNLOG_SCRIPT_ID:-}" ]]; then
        _RUNLOG_SCRIPT_ID="${RUNLOG_SCRIPT_ID}"
    else
        caller_script="${BASH_SOURCE[1]}"
        base="$(basename "${caller_script}")"
        _RUNLOG_SCRIPT_ID="${base%.*}"
    fi

    if [[ -n "${RUNLOG_ORDER:-}" ]]; then
        _RUNLOG_ORDER="${RUNLOG_ORDER}"
    else
        _RUNLOG_PPID="${PPID}"
        _RUNLOG_ORDER="$(_runlog_resolve_order "${_RUNLOG_PPID}" "${_RUNLOG_SCRIPT_ID}")"
    fi

    _RUNLOG_ROOT="${RUNLOG_ROOT:-}"
    if [[ -z "${_RUNLOG_ROOT}" ]]; then
        _RUNLOG_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
            echo "error: RUNLOG_ROOT not set and cwd is not inside a" \
                    " git working tree" >&2
            return 1
        }
    fi
    _RUNLOG_LOG_FILE="${RUNLOG_LOG_FILE:-${_RUNLOG_ROOT}/RUN_LOG.md}"

    _RUNLOG_RAW_TMP="$(mktemp "${TMPDIR:-/tmp}/runlog-raw.XXXXXX")"
    export RUNLOG_RECORD_FILE
    RUNLOG_RECORD_FILE="$(mktemp "${TMPDIR:-/tmp}/runlog-record.XXXXXX")"

    # A named pipe + background `tee`, not `exec > >(tee ...)` process
    # substitution: functionally equivalent (still streams live while
    # also capturing), but avoids relying on /dev/fd, which is denied
    # under some sandboxed shells while a plain fifo is not.
    _RUNLOG_FIFO="$(mktemp -u "${TMPDIR:-/tmp}/runlog-fifo.XXXXXX")"
    mkfifo "${_RUNLOG_FIFO}"
    tee -a "${_RUNLOG_RAW_TMP}" < "${_RUNLOG_FIFO}" >&1 &
    _RUNLOG_TEE_PID="$!"

    exec 3>&1
    exec 2>&1
    exec 1> "${_RUNLOG_FIFO}"

    trap '_runlog_teardown "$?"' EXIT
}


# -----------------------------------------------------------------------
# `runlog_setup`'s EXIT trap: build the recorded output and delegate the
# actual RUN_LOG.md upsert to the existing `runlog record` CLI (reusing
# its `record()`/`parse_log()`/`render_log()`/`atomic_write()` --
# nothing about the Markdown format is reimplemented here), then clean
# up temp files.
#
# Parameters
# ----------
#   $1 - exit_code : The script's real exit status, captured by the
#       caller as `trap '_runlog_teardown "$?"' EXIT` (the single-quoted
#       `$?` is expanded when the trap fires, not at registration time).
# -----------------------------------------------------------------------
_runlog_teardown() {
    local exit_code="${1:?Error: exit_code required}"
    local raw_output record_content output

    # Restore the real stdout/stderr (fd 3, saved in runlog_setup) and
    # drop both writer fds pointing at the fifo, so its `tee` reader
    # gets EOF and flushes before we read the raw-output temp file.
    exec 1>&3 2>&3 3>&-
    wait "${_RUNLOG_TEE_PID}" 2>/dev/null || true
    rm -f "${_RUNLOG_FIFO}"

    raw_output="$(cat "${_RUNLOG_RAW_TMP}" 2>/dev/null || true)"
    record_content="$(cat "${RUNLOG_RECORD_FILE}" 2>/dev/null || true)"

    if [[ -n "${record_content}" ]]; then
        output="${record_content}"
    else
        output="${raw_output}"
    fi

    if [[ "${exit_code}" -ne 0 ]]; then
        if [[ -n "${output}" ]]; then
            output="${output}"$'\n'"${_RUNLOG_ERROR_TAIL_DIVIDER}"$'\n'"${raw_output}"
        else
            output="${_RUNLOG_ERROR_TAIL_DIVIDER}"$'\n'"${raw_output}"
        fi
    fi

    local -a failed_flag=()
    [[ "${exit_code}" -ne 0 ]] && failed_flag=(--failed)

    # `${arr[@]+"${arr[@]}"}`, not `"${arr[@]}"`: bash < 4.4 treats an
    # empty array as unbound under `set -u`, which would abort this trap.
    runlog record --id "${_RUNLOG_SCRIPT_ID}" --order "${_RUNLOG_ORDER}" \
            --root "${_RUNLOG_ROOT}" --log-file "${_RUNLOG_LOG_FILE}" \
            ${failed_flag[@]+"${failed_flag[@]}"} --stdin <<< "${output}"

    rm -f "${_RUNLOG_RAW_TMP}" "${RUNLOG_RECORD_FILE}"
}
