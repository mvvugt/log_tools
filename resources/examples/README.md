# Example code

This directory holds runnable examples for `log_tools`.

## `pipeline/`

A single, self-contained example pipeline exercising every `log_tools`
feature end to end, in `resources/examples/pipeline/steps/`:

- `fetch_data.sh` / `process_data.py` -- self-registering
  (`runlog_setup`/`runlog_setup()`) bash and python steps, id/order
  derived automatically. Exercise all four emitter levels
  (`log_info`/`log_warn`/`log_debug`/`log_error`) and the
  `record=`/`no-record`/`record` recording toggles.
- `prepare_stages.sh` -- self-registering; uses `log_stage` to split its
  output into independent `validate`/`build` sections, so a change to
  one is diffed on its own (mirrors `mrsrc/prepare_mr.sh`).
- `bulk_counts.py` -- self-registering; uses `log_count`/
  `log_count_summary` to record one summary line per outcome for a
  high-cardinality loop instead of one row per item (mirrors the
  per-file loop in `mrsrc/extract_results.sh`).
- `external_tool.sh` -- a plain script with **no** `runlog_setup`,
  standing in for a third-party CLI. Wrapped from the outside via
  `runlog run --root ... --log-file ... -i '^RESULT:' --`, since `runlog
  run` (unlike `runlog_setup`) does not read `RUNLOG_ROOT`/
  `RUNLOG_LOG_FILE` (mirrors `ex_src/rv_gen.sh`'s external-tool calls).
  `-i/--include-pattern` keeps only its `RESULT:` lines out of an
  otherwise noisy raw output.
- `flaky_step.sh` -- self-registering; fails on the pipeline's first
  pass and succeeds on its second, demonstrating failure handling
  (`--failed`, skip-diff-on-failure) and the "error resolved" note
  `record()` shows instead of a raw diff of the error going away.
- `cluster_job.sh` -- a plain script relying on the
  `RUNLOG_SCRIPT_ID`/`RUNLOG_ORDER` env var overrides, invoked twice
  with different values for two logical "cohorts". Mirrors
  `mrsrc/extract_results.sh`, which requires these to be set via
  `sbatch --export=ALL,RUNLOG_SCRIPT_ID=...,RUNLOG_ORDER=...` since a
  batch-scheduled job's real `$PPID` has no relation to the submitting
  shell and the same script legitimately runs multiple times per
  pipeline.

`run_pipeline.sh` runs every step once (producing "first run" entries
for all of them), then re-runs `fetch_data.sh`/`process_data.py`/
`prepare_stages.sh`/`flaky_step.sh` with slightly changed inputs, so a
real content diff, a stage-scoped diff, and an error-resolved note all
get produced -- printing each one immediately after its own step (see
the script's header comment for why: `record()`'s diff block is not
persisted once a later step's own `record()` call rewrites the file).

To run it (after `pip install -e .` from the repo root, so `runlog`,
`runlog-setup-path`, and `runlog-emitter-path` are on `PATH`):

```bash
./resources/examples/pipeline/run_pipeline.sh
```

It writes its own throwaway `RUN_LOG.md` under a temp directory (never
the real project log), so running the script is a complete
demonstration by itself.

## Notebooks

This directory will also contain example Jupyter notebooks that users
can use to learn the API. Please note, the notebooks are also built
into the documentation (via `nbsphinx`/`nbsphinx-link`, see
`resources/ci_cd/sphinx.txt`), so should not contain __any__
identifiable data. Use dummy or synthetic data if you want to
illustrate examples with identifiable data.

No example notebooks exist yet -- this exists so the convention is in
place once there's real content to walk through.
