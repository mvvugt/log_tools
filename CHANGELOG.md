# Changelog

### [Unreleased]

* BUILD - Build and run the CI image as `linux/amd64` (`--platform`) so images built on Apple Silicon run on GitLab runners.

### [0.1.0] - 2026-11-12

* BUILD - Convert single-file `runlog.py` script into an installable `log_tools` package with a `runlog` console-script entry point.
* REFACTOR - Split `runlog.py` into `log_tools/functions.py` (shared functions), `log_tools/runlog.py` (specific functions), and `log_tools/cli/runlog.py` (thin argparse CLI wrapper).
* BUILD - Add GitLab CI/CD scaffolding: `.gitlab-ci.yml` (GitLab Pages deploy stage) plus `resources/ci_cd/` scripts for local Docker-parity lint/test debugging.
* DOCS - Add Sphinx documentation scaffolding under `docs/`.
* DOCS - Rewrite README.md's packaging section.
* BUILD - Add `VERSION`, `.bumpversion.cfg`, `LICENSE.txt` (MIT), and ruff configuration in `pyproject.toml`.
* FEAT - Add `log_tools.emitter` (Python) and `log_tools/emitter.sh` (Bash) tagged-logging emitters that record via a temp file (`RUNLOG_RECORD_FILE`) `runlog run` exposes to the child process, so recorded output is decided by explicit calls rather than regex-guessed from text shape.
* FEAT - Add `runlog-emitter-path` console script to locate the installed `log_tools/emitter.sh` for sourcing from any script.
* REMOVED - Remove `-t/--tagged-only` and `filter_tagged_lines()`; the record-file mechanism above replaces it as the primary recording path.
* API - Add `-i/--include-pattern PATTERN` (replaces `--tagged-only`, now an additive user-supplied regex) and `--raw-on-failure` (opt-in safety net) to `runlog run`/`record`; rename `filter_tagged_lines()` to `filter_matching_lines(output, pattern)`; change `build_recorded_output()`'s signature from `tagged_only: bool` to `record_file_content`/`include_pattern`/`raw_on_failure`; drop `record()`'s `tagged_only` parameter (resolved-error detection now keys off `Constants.ERROR_TAIL_DIVIDER`'s presence, not a mode flag).
* DOCS - Add a runnable example pipeline (`resources/examples/pipeline/`) demonstrating `runlog run`/`record` and the emitter end to end; replace README.md's stale Quick Start snippet with it and cross-link from `docs/source/usage.rst`.
* DOCS - Introduce the emitter alongside `runlog` in README.md/docs/source/index.rst; README covers combined usage concisely, online docs (usage.rst) gain standalone emitter-only and runlog-only usage sections plus a combined/integration section.
* FEAT - Add `log_tools.setup.runlog_setup()` (Python context manager) and `log_tools/setup.sh`'s `runlog_setup` (Bash), so a step script self-registers its own `RUN_LOG.md` id (from its own filename) and order (auto-incremented via a PPID-scoped, lock-protected state file) without an orchestrator passing `--id`/`--order`; both replicate `runlog run --raw-on-failure`'s safety net by tee-ing the script's own stdout/stderr, and record via the existing `record()`/`runlog record` rather than duplicating the Markdown format.
* FEAT - Add `runlog-setup-path` console script to locate the installed `log_tools/setup.sh` for sourcing from any script.
* API - Add `--failed` flag to `runlog record`, letting a caller mark a run failed (skipping the diff) without going through `runlog run`'s subprocess-exit-code detection.
* REFACTOR - Move git-toplevel root resolution out of `log_tools/cli/runlog.py` into `log_tools.functions.resolve_git_root()` (raising `RuntimeError` instead of calling `sys.exit`), so both the CLI and `log_tools.setup` share one implementation.
* DOCS - Update the example pipeline (`resources/examples/pipeline/`) and its README to use self-registering steps instead of `runlog run` wrapping; add a `runlog_setup`/`runlog_setup()` usage section to `docs/source/usage.rst` and an `api/setup.rst` page.
* BUILD - Lower minimum supported Python from 3.11 to 3.9 (`requires-python`, classifiers, `ruff target-version`, and `resources/conda/` version pins); add a GitLab CI `test` job matrix across Python 3.9/3.11/3.13 (official `python:*-slim` images) to actually verify 3.9 compatibility.
* API - Add an `order` override to `log_tools.setup.runlog_setup()`/`RunlogSetup` (mirrors the existing `script_id` override) and `RUNLOG_ORDER`/`RUNLOG_SCRIPT_ID` env var overrides to `log_tools/setup.sh`'s `runlog_setup`, so a step can pin its `RUN_LOG.md` position instead of relying on the `$PPID`-scoped auto-increment -- needed for steps whose real run-time process ancestry (a batch-submitted job, a later stage of a manually re-invoked pipeline) doesn't match their logical pipeline position.
* FEAT - Add `log_stage(name)` to `log_tools.emitter`/`log_tools/emitter.sh`, marking a stage boundary within one script id's output; `log_tools.runlog.record()` now diffs each stage independently (`split_stages()`/`_stage_diff_blocks()`) instead of the whole output as one blob, so a stage that ran for the first time is never diffed against nothing, an unchanged stage never buries a diff in a stage that actually changed, and a stage missing from the current run gets a "not present this run" note. Output with no `log_stage` calls is unaffected -- still one implicit stage, diffed exactly as before.
* FEAT - Add `log_count(key)`/`log_count_summary(key, label=...)` to `log_tools.emitter`/`log_tools/emitter.sh`, batching a high-cardinality loop (e.g. one call per file) into a single recorded `"label: count"` line instead of one row per item; `log_count` only increments an in-process counter (no print/record), `log_count_summary` emits the summary via `log_info` and resets that key's counter.
* FEAT - Record a `- first run:` date per id in `RUN_LOG.md`, set once and preserved across runs (older logs fall back to the entry's `last run`).
* FEAT - Only mark a run `(dirty)` when uncommitted/untracked `.py`/`.sh` files exist (`DIRTY_CHECK_EXTENSIONS`), not for any working-tree change.
* DOCS - Document the `RUN_LOG.md` section format (first run, dirty flag scope) in `docs/source/usage.rst`.
* DOCS - Add `docs/source/examples.rst`, a step-by-step walkthrough of the example pipeline with captured `RUN_LOG.md` output.
* FIX - Ignore emitter timestamps when diffing (`diff_text()`), so lines/stages that only differ in time no longer show as changed; changed lines keep their original timestamps.
* FIX - Guard the empty `failed_flag` array expansion in `log_tools/setup.sh`'s teardown, which aborted the EXIT trap under `set -u` on bash < 4.4 (no RUN_LOG.md entry, successful jobs exiting 1).
* FEAT - Python `runlog_setup()` now honours the `RUNLOG_SCRIPT_ID`/`RUNLOG_ORDER` env vars like `setup.sh`; explicit `script_id=`/`order=` arguments still take precedence.
* FIX - `atomic_write()` uses a unique temp file per call (no crash when concurrent writers, e.g. SGE array tasks, share one RUN_LOG.md) and preserves the destination's permission bits.
* FIX - `record()` holds an exclusive lock (`RUN_LOG.md.lock`, new `log_tools.functions.file_lock()`: atomic `mkdir`, 30 s timeout, stale locks older than 120 s are broken) for its whole read-modify-write, so concurrent writers (e.g. SLURM/SGE array tasks) no longer lose each other's entries; on timeout it raises `LockTimeoutError` and writes nothing.
* FIX - A failure to record no longer changes the wrapped script's exit code: `runlog run` and `runlog_setup()` warn (naming the script's exit code and stating that only the log entry is missing, not the script's results) and keep the script's own exit status; `runlog record` exits 1 with a clean error instead of a traceback.
* REFACTOR - `log_tools.setup.resolve_order()` uses the shared `file_lock()` (gaining stale-lock breaking) and no longer removes a lock it failed to acquire.
* FIX - `log_tools/setup.sh`'s teardown only warns when `runlog record` fails (naming the exit code; only the log entry is missing), so a logging failure no longer turns the script's exit status into 1 under `set -e`.
* FIX - `log_tools/setup.sh`'s order-state lock now times out after 10 s and breaks stale locks (> 120 s), no longer removes a lock it failed to acquire, and prints its full "proceeding unlocked" warning without recording it (the message was cut off and recorded before).
* TEST - Set `RUNLOG_TEST_BASH=/path/to/bash` to also run the `setup.sh` strict-mode, teardown and lock tests under another bash, e.g. the system bash 4.2 on Myriad.
* BUILD - Publish to PyPI as `runlog-tools` (`pip install runlog-tools`; the import name stays `log_tools`); add `resources/pypi/` upload scripts for TestPyPI and PyPI (clean build, version check, `twine check`, upload).
* BUILD - Support Python 3.14: drop the `<3.14` cap from `requires-python`, add the 3.14 classifier, and run the CI `test` matrix on every supported version (3.9-3.14).
* BUILD - Run CI pipelines only for merge requests into the default branch, tags, and the default branch (`workflow: rules:` in `.gitlab-ci.yml`).
* BUILD - Add `pyyaml`, `setuptools>=77` and `wheel` to the `dev` extras and the conda environment files (the packaging test builds with `--no-isolation`, and slim Python images ship neither build backend).
* FIX - Raise the `[build-system]` floor to `setuptools>=77`, the first version that supports the SPDX `license = "MIT"` string with `license-files`.
* DOCS - README installation now uses PyPI; installing from a git checkout moved to the Development section.
* TEST - Add `tests/test_ci.py` (CI triggers and Python matrix) and `tests/test_packaging.py` (builds the sdist and wheel; checks shell files, version, and that no private or test files are shipped) and `tests/test_pypi_scripts.py` (upload scripts against a stub `python`).
