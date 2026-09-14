#!/usr/bin/env bash
# Source this file for tagged-logging functions compatible with `runlog`
# (matches ~/AGENTS.md's log_info/log_warn/log_error convention), plus
# RUNLOG_RECORD_FILE recording -- see log_tools.runlog.run_and_record.
# Do not execute directly.
#
# log_info/log_warn record by default (pass "no-record" as $2 to opt a
# call out); log_debug is the opposite, off by default (pass "record" as
# $2 to opt in). log_error always records. Each function takes a single
# $1 message (not $*) so $2 is unambiguously the recording-toggle slot.

_write_record() {
    # $1 = formatted message, $2 = "1"/"0" whether to record it.
    if [[ "$2" -eq 1 && -n "${RUNLOG_RECORD_FILE:-}" ]]; then
        echo "$1" >> "${RUNLOG_RECORD_FILE}"
    fi
}

log_debug() {
    local msg="[debug] $(date '+%Y-%m-%d %H:%M:%S') $1"
    local should_record=0
    [[ "${2:-}" == "record" ]] && should_record=1
    echo "${msg}"
    _write_record "${msg}" "${should_record}"
}

log_info() {
    local msg="[info]  $(date '+%Y-%m-%d %H:%M:%S') $1"
    local should_record=1
    [[ "${2:-}" == "no-record" ]] && should_record=0
    echo "${msg}"
    _write_record "${msg}" "${should_record}"
}

log_warn() {
    local msg="[warn]  $(date '+%Y-%m-%d %H:%M:%S') $1"
    local should_record=1
    [[ "${2:-}" == "no-record" ]] && should_record=0
    echo "${msg}" >&2
    _write_record "${msg}" "${should_record}"
}

log_error() {
    local msg="[error] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo "${msg}" >&2
    _write_record "${msg}" 1
}
