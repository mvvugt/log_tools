# Logging tools

__version__: `0.1.0`

A small, stdlib-only package for logging/pipeline-tracking tools.
Currently contains **`runlog`**, which records every pipeline script's
run into **one compact, project-wide Markdown log** (`RUN_LOG.md` by
default) — instead of scrolling back through terminal output, or one
log file per script piling up over time.

There is [online](https://mvvugt.gitlab.io/log_tools/index.html)
documentation for log_tools.


## Installation instructions
At present, `log_tools` is undergoing development and no packages exist yet on
PyPi. Therefore it is recommended that you install in either of the two ways
below. Please keep in mind that all development is carried out on MacOS and
Python v3.13.

### Using pip

You can install using pip from the root of the cloned repository, first clone
and cd into the repository root:

```
git clone git@gitlab.com:mvvugt/log_tools.git
cd log_tools
```

Install the dependencies:
```
python -m pip install --upgrade -r requirements.txt
```

Then install using pip
```
python -m pip install .
```

Or for an editable (developer) install run the command below from the root of
the repository. The difference with this is that you can just to a `git pull`
to update, or switch branches without re-installing:
```
python -m pip install -e .
```

### Using Conda
There are also conda yaml environment files in `./resources/conda/envs` that
have the same contents as `requirements.txt` but for conda packages, so all the
pre-requisites.


A new conda environment can be built using the command:
```
conda env create --file ./resources/conda/envs/conda_create.yaml
```


To add to an existing environment use:
```
conda env update --file ./resources/conda/envs/conda_update.yaml
```

Next the package can be installed:
NOTE is is possible with make?
```
make install
```

### Verify installation
```
log_tools --version
log_tools --help
```


#### Development
For development work, install the package in editable mode with Git commit
hooks configured:

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

#### Git Hooks Configuration
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
`_setup_git_hooks.py`, you can configure the hooks manually at any time by
running:

```bash
_setup_git_hooks.py
```


## Run the tests
After installation you will be able to run the tests. If you have cloned the
repository you can run the command below from the root of the repository:
```
pytest ./tests
```


### Get help

To get help, type `runlog -h` (or `runlog run -h` / `runlog record -h`
for a subcommand's own options).


### Quick start example

Two subcommands: `run` wraps a command, streaming its output through
live while capturing and recording it; `record` is the primitive
underneath `run`, for when the output text is already in hand.

Wrap a command (as wired into `src/mr_arrhythmia.sh`):
NOTE update with real examples

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
