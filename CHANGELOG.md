# Changelog

### [Unreleased]

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
