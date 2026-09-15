# Logging tools

__version__: `0.1.0`

A small, stdlib-only package for logging/pipeline-tracking tools.
It contains two things: an **emitter** (`log_tools.emitter` in
Python, `log_tools/emitter.sh` in Bash) providing tagged
`log_info`/`log_warn`/`log_error`/`log_debug` calls, and **`runlog`**,
which records every pipeline script's run into **one compact,
project-wide Markdown log** (`RUN_LOG.md` by default). When a script
is run via `runlog run`, its emitter calls are automatically captured
into that shared log.

For standalone emitter-only and `runlog`-only usage, and full
CLI/record-semantics details, see the
[online usage guide](https://mvvugt.gitlab.io/log_tools/usage.html)
(or the rest of the [online](https://mvvugt.gitlab.io/log_tools/index.html)
documentation).


## Installation instructions
At present, `log_tools` is undergoing development and no packages exist yet on
PyPi. Therefore it is recommended that you install in either of the two ways
below. Please keep in mind that development is primarily carried out on macOS
with Python v3.13, and testing is additionally carried out on Linux (HPC
clusters, and the CI pipeline's Docker container) across Python 3.11-3.13.

To install `log_tools`, please use the git repo:
```
git clone git@gitlab.com:mvvugt/log_tools.git
cd log_tools
```

### Dependency installation

#### Using pip
You can install the dependencies using pip from the root of the cloned
repository.

Install the dependencies:
```
python -m pip install --upgrade -r requirements.txt
```

#### Using Conda
There are also conda yaml environment files in `./resources/conda` that
have the same contents as `requirements.txt` but for conda packages, so all the
pre-requisites.


A new conda environment can be built using the command:
```
conda env create --file ./resources/conda/conda_create.yaml
```

To add to an existing environment use:
```
conda env update --file ./resources/conda/conda_update.yaml
```

### Package installation
Next the package can be installed:
```
make install
```

`make` is just a wrapper, you can also use:
```
python -m pip install .
```

For an editable (developer) install, see [Development](#development) below.

### Verify installation
```
log_tools --version
```


## Run the tests
After installation you will be able to run the tests. If you have cloned the
repository you can run the command below from the root of the repository:
```
pytest ./tests
```


## Quick start example

**`runlog`** records every pipeline script's run into
**one compact, project-wide Markdown log** (`RUN_LOG.md` by default).
Two subcommands: `run` wraps a command, streaming its output through
live while capturing and recording it; `record` is the primitive
underneath `run`, for when the output text is already in hand.
`runlog run` sets the `RUNLOG_RECORD_FILE` environment variable for
the wrapped command; the emitter checks it and, when set, appends its
`log_info`/`log_warn`/`log_error`/`log_debug` calls to that file too
— that's how emitter output from separate pipeline scripts ends up
combined in one `RUN_LOG.md`.

A full runnable example pipeline lives at
`resources/examples/pipeline/` (a bash "fetch" step and a python
"process" step, both wrapped with `runlog run`, plus a `runlog record`
step). Run it directly:

```bash
./resources/examples/pipeline/run_pipeline.sh
```

Wrap a command (as wired into `resources/examples/pipeline/steps/fetch_data.sh`):

```bash
runlog run --id fetch_data --order 10 --root "$ROOT" -- \
    "$ROOT"/resources/examples/pipeline/steps/fetch_data.sh "$WORK_DIR"
```

Record already-known output directly (e.g. a step whose real output
only exists later, asynchronously, such as a SLURM job recording from
inside its own batch script once it finishes):

```bash
runlog record --id my_step --order 50 --root "$ROOT" --text "$(cat some_summary.txt)"
```

## Development
For development work, install the package in editable mode with Git commit
hooks configured.

```bash
make install-dev
```

This command installs the package in editable mode and configures Git commit
hooks, allowing you to run `git pull` to update the repository or switch
branches without reinstalling.

Alternatively, you can install manually:
```bash
python -m pip install -e .
python .setup_git_hooks.py
```

### Git Hooks Configuration
When setting up a development environment, the `setup-hooks` command
configures Git hooks to enforce conventional commit message formatting and
spell check using `codespell`.

To view the commit message format requirements, run:

```bash
./.githooks/commit-msg -help
```

For frequent use, add this function to your shell configuration (`~/.bashrc`
or `~/.zshrc`):

```bash
commit-format-help() {
    local git_root
    git_root=$(git rev-parse --show-toplevel 2>/dev/null)
    
    if [ -z "$git_root" ]; then
        echo "Error: Not inside a git repository"
        return 1
    fi
    
    local hook_path="$git_root/.githooks/commit-msg"
    
    if [ ! -f "$hook_path" ]; then
        echo "Error: commit-msg hook not found"
        return 1
    fi
    
    "$hook_path" --help
}
```

If you have already installed the package in editable mode without running
`.setup_git_hooks.py`, you can configure the hooks manually at any time by
running:

```bash
python .setup_git_hooks.py
```


## Change log

See `CHANGELOG.md` for the full history. Latest (`[Unreleased]`):

#### version `Unreleased`

* BUILD - Convert single-file `runlog.py` script into an installable `log_tools` package with a `runlog` console-script entry point.
* REFACTOR - Split `runlog.py` into `log_tools/functions.py` (shared functions), `log_tools/runlog.py` (specific functions), and `log_tools/cli/runlog.py` (thin argparse CLI wrapper).
* BUILD - Add GitLab CI/CD scaffolding: `.gitlab-ci.yml` (GitLab Pages deploy stage) plus `resources/ci_cd/` scripts for local Docker-parity lint/test debugging.
* DOCS - Add Sphinx documentation scaffolding under `docs/`.
* DOCS - Rewrite README.md's packaging section.
* BUILD - Add `VERSION`, `.bumpversion.cfg`, `LICENSE.txt` (MIT), and ruff configuration in `pyproject.toml`.
