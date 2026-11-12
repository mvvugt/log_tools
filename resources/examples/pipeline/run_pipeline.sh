#!/usr/bin/env bash
# Comprehensive runnable example pipeline exercising every log_tools
# feature end to end (see resources/examples/README.md for a step-by-
# step walkthrough). Requires `log_tools` installed
# (`pip install -e .` from the repo root) so `runlog`,
# `runlog-setup-path`, and `runlog-emitter-path` are on PATH.
#
# Runs the pipeline twice ("pass 1"/"pass 2") with a small change to
# some steps' inputs in between, so a content diff, a stage-scoped
# diff, and an "error resolved" note all get produced for real. Each
# is printed right after its own step, not just once at the end --
# `record()`'s diff block is deliberately NOT persisted across later
# record() calls (parse_log() recomputes diffs fresh each time rather
# than re-parsing a stored one, see log_tools/runlog.py's Entry.diff
# docstring), so a step's diff is only visible in RUN_LOG.md between
# that step's own run and the next step's run -- the final cat at the
# bottom of this script shows a clean file with no diffs at all, by
# design.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
steps_dir="${script_dir}/steps"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/runlog-example.XXXXXX")"
trap 'rm -rf "${work_dir}"' EXIT

log_file="${work_dir}/RUN_LOG.md"
root="$(cd "${script_dir}" && git rev-parse --show-toplevel)"
export RUNLOG_LOG_FILE="${log_file}"

# Print one step's current section of RUN_LOG.md (including its diff
# block, if any) -- must be called immediately after that step's own
# run, before any other step's record() call overwrites it away.
show_section() {
    local script_id="$1"
    awk -v id="${script_id}" '
        /^## \[[0-9]+\] / {
            printing = ($0 ~ ("\\] " id "([ (]|$)"))
        }
        printing { print }
    ' "${log_file}"
}

echo "=== Pass 1: first run of every step ==="

# Self-registering steps (runlog_setup/runlog_setup()) -- id/order
# derived automatically from a counter scoped to this orchestrator
# process, shared by every sibling step invoked directly below.
"${steps_dir}/fetch_data.sh" "${work_dir}" 3
python3 "${steps_dir}/process_data.py" "${work_dir}"
"${steps_dir}/prepare_stages.sh" "${work_dir}" 3
python3 "${steps_dir}/bulk_counts.py"

# External tool, not self-registering -- wrapped from the outside via
# `runlog run`. Unlike runlog_setup, `runlog run` does not read
# RUNLOG_ROOT/RUNLOG_LOG_FILE, so --root/--log-file are passed
# explicitly (matching ex_src/rv_gen.sh's pattern). -i/--include-pattern
# pulls in only this tool's "RESULT:" lines from its otherwise-noisy
# raw output.
runlog run --id external_tool --order 45 --root "${root}" \
    --log-file "${log_file}" -i '^RESULT:' -- \
    "${steps_dir}/external_tool.sh"

# Self-registering, but this run is expected to fail -- `|| true` keeps
# the orchestrator going under `set -e` (the step's own failure is
# recorded by runlog_setup regardless of how the orchestrator reacts).
"${steps_dir}/flaky_step.sh" fail || true

# Two calls to the same script, each given a distinct identity via
# RUNLOG_SCRIPT_ID/RUNLOG_ORDER -- mimicking two separate
# `sbatch --export=ALL,RUNLOG_SCRIPT_ID=...,RUNLOG_ORDER=...`
# submissions of one script for two different cohorts (see
# steps/cluster_job.sh's header for why the override is needed here).
RUNLOG_SCRIPT_ID=cluster_job_cohort_a RUNLOG_ORDER=60 \
    "${steps_dir}/cluster_job.sh" cohort_a
RUNLOG_SCRIPT_ID=cluster_job_cohort_b RUNLOG_ORDER=61 \
    "${steps_dir}/cluster_job.sh" cohort_b

echo
echo "=== Pass 2: re-run a few steps with changed inputs, to produce diffs ==="

# One more sample row -- fetch_data's own diff, and process_data's
# downstream total, both change.
"${steps_dir}/fetch_data.sh" "${work_dir}" 4
echo "--- RUN_LOG.md section for 'fetch_data' right after its own run ---"
show_section fetch_data

python3 "${steps_dir}/process_data.py" "${work_dir}"

# One more "build" artifact -- only the "build" stage's diff should
# show a change; "validate" is identical both times.
"${steps_dir}/prepare_stages.sh" "${work_dir}" 4
echo "--- RUN_LOG.md section for 'prepare_stages' right after its own run ---"
show_section prepare_stages

# Succeeds this time -- the previous failed run is not diffed against;
# record() instead notes the error as resolved.
"${steps_dir}/flaky_step.sh" succeed
echo "--- RUN_LOG.md section for 'flaky_step' right after its own run ---"
show_section flaky_step

runlog record --id pipeline_summary --order 900 --log-file "${log_file}" \
    --text "Pipeline finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo
echo "=== Final ${log_file} (diff blocks are gone by now -- see this" \
    "script's header note) ==="
cat "${log_file}"
