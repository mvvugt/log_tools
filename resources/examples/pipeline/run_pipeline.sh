#!/usr/bin/env bash
# Runnable example pipeline demonstrating self-registering steps
# (`runlog_setup`/`runlog_setup()`) plus a plain `runlog record` closing
# entry, end to end (see resources/examples/README.md). Requires
# `log_tools` installed (`pip install -e .` from the repo root) so
# `runlog`, `runlog-setup-path`, and `runlog-emitter-path` are on PATH.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/runlog-example.XXXXXX")"
trap 'rm -rf "${work_dir}"' EXIT

log_file="${work_dir}/RUN_LOG.md"
export RUNLOG_LOG_FILE="${log_file}"

# Each step calls `runlog_setup`/`runlog_setup()` itself -- no
# `--id`/`--order` wrapping needed; both share `RUNLOG_LOG_FILE` above.
"${script_dir}/steps/fetch_data.sh" "${work_dir}"
python3 "${script_dir}/steps/process_data.py" "${work_dir}"

runlog record --id pipeline_summary --order 30 --log-file "${log_file}" \
    --text "Pipeline finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo
echo "=== ${log_file} ==="
cat "${log_file}"
