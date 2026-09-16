#!/usr/bin/env bash
# Toy "prepare" step demonstrating stage-scoped diffing (mirrors
# mrsrc/prepare_mr.sh's log_stage usage). Self-registers via
# runlog_setup, then splits its output into two independent log_stage
# sections: "validate" (constant across runs) and "build" (its content
# depends on $2, which run_pipeline.sh's second pass changes) -- so the
# resulting RUN_LOG.md diff only ever shows the "build" stage changing,
# never "validate".
set -euo pipefail

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-setup-path
source "$(runlog-setup-path)"
runlog_setup

work_dir="${1:?Error: work_dir required}"
n_artifacts="${2:-3}"

log_stage "validate"
log_info "Checking ${work_dir} is writable"
log_info "Checked expected input files are present"

log_stage "build"
log_info "Building ${n_artifacts} artifact(s)"
for ((i = 1; i <= n_artifacts; i++)); do
    log_info "Built artifact_${i}"
done
