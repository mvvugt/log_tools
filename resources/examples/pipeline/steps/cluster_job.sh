#!/usr/bin/env bash
# Toy stand-in for a script submitted to a batch scheduler multiple
# times with a different logical identity each call -- mirrors
# mrsrc/extract_results.sh, which requires its caller
# (mr_result_extraction.sh) to submit it via
# `sbatch --export=ALL,RUNLOG_SCRIPT_ID=<id>,RUNLOG_ORDER=<n>` rather
# than relying on runlog_setup's default PPID-scoped auto-order: a
# scheduler-launched job's real $PPID at execution time has no relation
# to the submitting shell, and the same script is invoked once per
# cohort/dataset here, so the auto-derived (basename-based) id would
# collide across calls. run_pipeline.sh sets RUNLOG_SCRIPT_ID/
# RUNLOG_ORDER before each call instead of passing them as arguments,
# exactly as `sbatch --export=...` would.
set -euo pipefail

: "${RUNLOG_SCRIPT_ID:?Error: RUNLOG_SCRIPT_ID required (see file header)}"
: "${RUNLOG_ORDER:?Error: RUNLOG_ORDER required (see file header)}"

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-setup-path
source "$(runlog-setup-path)"
runlog_setup

dataset="${1:?Error: dataset name required}"

log_info "Processing dataset '${dataset}' as ${RUNLOG_SCRIPT_ID}"
log_info "Done with '${dataset}'"
