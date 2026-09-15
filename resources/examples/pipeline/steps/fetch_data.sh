#!/usr/bin/env bash
# Toy "fetch" step for the runlog example pipeline (see
# resources/examples/pipeline/run_pipeline.sh). Writes a small dummy
# TSV of per-sample counts into the work dir passed as $1, self-
# registering its own RUN_LOG.md entry via runlog_setup (id/order
# derived automatically; location via RUNLOG_LOG_FILE/RUNLOG_ROOT, set
# once by run_pipeline.sh).
set -euo pipefail

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-setup-path
source "$(runlog-setup-path)"
runlog_setup

work_dir="${1:?Error: work_dir required}"
out_file="${work_dir}/raw_counts.tsv"

log_info "Fetching toy dataset into ${out_file}"
printf 'sample\tcount\n' > "${out_file}"
for i in 1 2 3; do
    printf 'sample_%d\t%d\n' "${i}" "$(( i * 7 ))" >> "${out_file}"
done
log_info "Wrote $(wc -l < "${out_file}" | tr -d ' ') lines to ${out_file}"
