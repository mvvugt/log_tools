#!/usr/bin/env bash
# Runnable example pipeline demonstrating `runlog run` and `runlog
# record` end to end (see resources/examples/README.md). Requires
# `log_tools` installed (`pip install -e .` from the repo root) so
# `runlog` and `runlog-emitter-path` are on PATH.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

log_file="${work_dir}/RUN_LOG.md"

runlog run --id fetch_data --order 10 --log-file "${log_file}" -- \
    "${script_dir}/steps/fetch_data.sh" "${work_dir}"

runlog run --id process_data --order 20 --log-file "${log_file}" -- \
    python3 "${script_dir}/steps/process_data.py" "${work_dir}"

runlog record --id pipeline_summary --order 30 --log-file "${log_file}" \
    --text "Pipeline finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo
echo "=== ${log_file} ==="
cat "${log_file}"
