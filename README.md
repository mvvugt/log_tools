# log_tools

__version__: `0.1.0`

A small, stdlib-only package for logging/pipeline-tracking tools.
Currently contains **`runlog`**, which records every pipeline script's
run into **one compact, project-wide Markdown log** (`RUN_LOG.md` by
default) — instead of scrolling back through terminal output, or one
log file per script piling up over time.

There is [online](https://mvvugt.gitlab.io/log_tools/index.html)
documentation for log_tools.

## Installation instructions

### Using pip

Install from the root of the cloned repository:

```
git clone git@gitlab.com:mvvugt/log_tools.git
cd log_tools
python -m pip install .
```

Or for an editable (developer) install, which lets you `git pull` to
update without re-installing:

```
python -m pip install -e .
```

A conda build recipe (for publishing a conda package, not a dev
environment) is also available under `resources/conda/` — see
`resources/conda/README.md`.

#### Development

For development work, install with the `dev` extras (`pytest`, `ruff`,
`bump2version`, `build`, `twine`, `sphinx`):

```bash
python -m pip install -e ".[dev]"
```

Lint/format before committing:

```bash
ruff check --fix . && ruff format .
```

### Verify installation

```
runlog --help
```

## Run the tests

After installation you will be able to run the tests. If you have
cloned the repository you can run the command below from the root of
the repository:

```
pytest tests
```

### Get help

To get help, type `runlog -h` (or `runlog run -h` / `runlog record -h`
for a subcommand's own options).

### Quick start example

Two subcommands: `run` wraps a command, streaming its output through
live while capturing and recording it; `record` is the primitive
underneath `run`, for when the output text is already in hand.

Wrap a command (as wired into `src/mr_arrhythmia.sh`):

```bash
runlog run --id id_mapping --order 10 --root "$ROOT" -- \
    mamba run --no-capture-output -n "$ENV" \
    "$ROOT"/src/id_mapping.py build
```

Record already-known output directly (e.g. a step whose real output
only exists later, asynchronously, such as a SLURM job recording from
inside its own batch script once it finishes):

```bash
runlog record --id my_step --order 50 --root "$ROOT" --text "$(cat some_summary.txt)"
```

### Change log

See `CHANGELOG.md` for the full history. Latest (`[Unreleased]`):

#### version `Unreleased`

* BUILD - Convert single-file `runlog.py` script into an installable `log_tools` package with a `runlog` console-script entry point.
* REFACTOR - Split `runlog.py` into `log_tools/functions.py` (shared functions), `log_tools/runlog.py` (specific functions), and `log_tools/cli/runlog.py` (thin argparse CLI wrapper).
* BUILD - Add GitLab CI/CD scaffolding: `.gitlab-ci.yml` (GitLab Pages deploy stage) plus `resources/ci_cd/` scripts for local Docker-parity lint/test debugging.
* DOCS - Add Sphinx documentation scaffolding under `docs/`.
* DOCS - Rewrite README.md's packaging section.
* BUILD - Add `VERSION`, `.bumpversion.cfg`, `LICENSE.txt` (MIT), and ruff configuration in `pyproject.toml`.
