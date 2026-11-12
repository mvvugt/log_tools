#!/usr/bin/env bash
# Toy "fetch" step for the runlog example pipeline (see
# resources/examples/pipeline/run_pipeline.sh). Writes a small dummy
# TSV of per-sample counts into the work dir passed as $1, self-
# registering its own RUN_LOG.md entry via runlog_setup (id/order
# derived automatically; location via RUNLOG_LOG_FILE/RUNLOG_ROOT, set
# once by run_pipeline.sh). $2 (default 3) controls how many sample
# rows are written -- run_pipeline.sh's second pass bumps this so the
# step's recorded output actually changes, producing a real diff.
set -euo pipefail

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-setup-path
source "$(runlog-setup-path)"
runlog_setup

work_dir="${1:?Error: work_dir required}"
n_samples="${2:-3}"
out_file="${work_dir}/raw_counts.tsv"

log_info "Fetching toy dataset into ${out_file}"
log_debug "n_samples requested: ${n_samples}" record
if [[ "${n_samples}" -lt 1 ]]; then
    log_warn "n_samples < 1, nothing will be written"
fi
printf 'sample\tcount\n' > "${out_file}"
for ((i = 1; i <= n_samples; i++)); do
    printf 'sample_%d\t%d\n' "${i}" "$(( i * 7 ))" >> "${out_file}"
done
log_info "Wrote $(wc -l < "${out_file}" | tr -d ' ') lines to ${out_file}"
