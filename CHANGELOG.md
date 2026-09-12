# Changelog

### [Unreleased]

* BUILD - Convert single-file `runlog.py` script into an installable `log_tools` package with a `runlog` console-script entry point.
* REFACTOR - Split `runlog.py` into `log_tools/functions.py` (shared functions), `log_tools/runlog.py` (specific functions), and `log_tools/cli/runlog.py` (thin argparse CLI wrapper).
* BUILD - Add GitLab CI/CD scaffolding: `.gitlab-ci.yml` (GitLab Pages deploy stage) plus `resources/ci_cd/` scripts for local Docker-parity lint/test debugging.
* DOCS - Add Sphinx documentation scaffolding under `docs/`.
* DOCS - Rewrite README.md's packaging section.
* BUILD - Add `VERSION`, `.bumpversion.cfg`, `LICENSE.txt` (MIT), and ruff configuration in `pyproject.toml`.
