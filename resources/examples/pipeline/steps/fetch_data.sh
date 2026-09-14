#!/usr/bin/env bash
# Toy "fetch" step for the runlog example pipeline (see
# resources/examples/pipeline/run_pipeline.sh). Writes a small dummy
# TSV of per-sample counts into the work dir passed as $1, logging
# through the runlog emitter so runlog run records it.
set -euo pipefail

# shellcheck disable=SC1090  # dynamic path, resolved via runlog-emitter-path
source "$(runlog-emitter-path)"

work_dir="${1:?Error: work_dir required}"
out_file="${work_dir}/raw_counts.tsv"

log_info "Fetching toy dataset into ${out_file}"
printf 'sample\tcount\n' > "${out_file}"
for i in 1 2 3; do
    printf 'sample_%d\t%d\n' "${i}" "$(( i * 7 ))" >> "${out_file}"
done
log_info "Wrote $(wc -l < "${out_file}" | tr -d ' ') lines to ${out_file}"
