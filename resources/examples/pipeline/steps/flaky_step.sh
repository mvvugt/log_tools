#!/usr/bin/env bash
# Toy step demonstrating failure handling: self-registers via
# runlog_setup, then either fails or succeeds depending on $1
# ("fail"/"succeed"). run_pipeline.sh's first pass calls this with
# "fail" (the failed run's status is recorded and its diff against any
# prior run is skipped -- see log_tools/setup.sh's _runlog_teardown),
# then its second pass calls it with "succeed" -- record()'s "error
# resolved" note fires instead of a raw diff removal, since the prior
# run was marked failed.
set -euo pipefail

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-setup-path
source "$(runlog-setup-path)"
runlog_setup

mode="${1:?Error: mode required (fail|succeed)}"

log_info "attempting the flaky operation (mode=${mode})"
if [[ "${mode}" == "fail" ]]; then
    log_error "flaky operation failed"
    exit 1
fi
log_info "flaky operation succeeded"
