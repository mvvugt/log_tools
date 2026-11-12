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
#
# log_stage $1=name marks a stage boundary: always recorded, printed
# like log_info but tagged [stage]. Everything recorded after it, up to
# the next log_stage call, is grouped under that name by
# log_tools.runlog.split_stages when `record()` diffs -- see
# log_tools/emitter.py's log_stage docstring for the full rationale.
#
# log_count $1=key increments an in-process counter for key; prints and
# records nothing. Call once per high-cardinality event (e.g. once per
# file in a loop) instead of log_info, then call
# log_count_summary $1=key [$2=label] once after the loop to record one
# "label: count" line (via log_info) instead of one row per event, and
# reset key's counter to 0.

declare -gA _LOG_TOOLS_COUNTS=()

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

log_stage() {
    local msg="[stage] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo "${msg}"
    _write_record "${msg}" 1
}

log_count() {
    local key="${1:?Error: key required}"
    _LOG_TOOLS_COUNTS["${key}"]=$(( ${_LOG_TOOLS_COUNTS["${key}"]:-0} + 1 ))
}

log_count_summary() {
    local key="${1:?Error: key required}"
    local label="${2:-${key}}"
    local count="${_LOG_TOOLS_COUNTS[${key}]:-0}"
    unset "_LOG_TOOLS_COUNTS[${key}]"
    log_info "${label}: ${count}"
}
