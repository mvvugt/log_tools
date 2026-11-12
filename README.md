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
`log_tools` is on [PyPI](https://pypi.org/project/log-tools/) and has no
runtime dependencies:
```
python -m pip install log_tools
```

Please keep in mind that development is primarily carried out on macOS
with Python v3.13, and testing is additionally carried out on Linux (HPC
clusters, and the CI pipeline's Docker containers) across Python 3.9-3.14.

To install from a git checkout instead (e.g. for development), see
[Development](#development) below.


### Bash-specific installation
The steps above install `runlog`, `runlog-emitter-path`, and
`runlog-setup-path` as console-scripts into whichever environment's
`bin/` directory (`pip venv` or `conda env`) you installed into. They resolve
automatically in any shell where that environment is already active, but not
in a shell that never activates it (e.g. SLURM `sbatch`, cron, etc.).
If you plan to call these from that kind of context, pick one of
the following, once, up front:

#### pipx
[`pipx`](https://pipx.pypa.io/) installs a CLI tool into its own
isolated environment (unrelated to conda) and symlinks its commands
into a single, stable location on `PATH` (`~/.local/bin` by default).
This is a one-time, user-wide install: install once, reachable in every
shell (interactive or not) from then on, no matter how many project
environments come and go afterward.
```
pipx install .
pipx ensurepath
```
`pipx ensurepath` only needs running once ever (per machine/user); it
adds `~/.local/bin` to `PATH` in your shell's rc file if it isn't
there already. Note `pipx` does **not** make `import log_tools`
available in Python -- that still needs the pip/conda install above,
per project.

#### PATH export
Add the specific environment's `bin/` directory to `PATH`, e.g. in your
shell's rc file:
```
export PATH="$(conda info --base)/envs/<env_name>/bin:$PATH"
```
Simple, but per-environment: repeat for every new project env you create.

#### Symlink
If you already keep a personal `bin/` directory (e.g. `~/bin`) on `PATH`
for this purpose across tools, symlink the three commands into it instead
of adding a `log_tools`-specific `PATH` entry:
```
ln -sf "$(conda info --base)/envs/<env_name>/bin"/{runlog,runlog-emitter-path,runlog-setup-path} ~/bin/
```
Same per-environment caveat as the `PATH` export option -- this just
consolidates where you point it.

#### Remarks
Whichever option you pick, this only helps where that rc file actually
gets sourced. If you experience problems, add the relevant line 
(`export PATH=...` or the symlinks) directly to the job script instead.

**If you use `pipx` alongside a project's conda/pip install, keep both
on the same version.**
Version skew between the teo installs can silently produce inconsistent log
entries depending on which one happened to resolve first.
**Prevent** this by upgrading both together whenever you bump `log_tools`'s
version, rather than upgrading one and forgetting the other.
**Detect** a mismatch with `log_tools --version`, running it both
with and without the project's conda env active and compare.
**Resolve** by reinstalling/upgrading whichever is behind, or by making `PATH`
ordering deliberate (e.g. only let the project env's `bin/` take
precedence over pipx's `~/.local/bin` while you specifically want that
env's version to win).

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
There are two ways to record a step:

- **Self-registering** (`runlog_setup()`/`runlog_setup`): call it at a
  step script's own top and its id/order are derived automatically
  (from the script's own filename, and a counter scoped to the current
  pipeline run) -- no orchestrator wrapping needed.
- **`runlog` CLI**: `run` wraps a command externally, streaming its
  output live while capturing and recording it; `record` is the
  primitive underneath both `run` and `runlog_setup`, for when the
  output text is already in hand (or the id/order should be explicit).

Either way, the emitter's `log_info`/`log_warn`/`log_error`/`log_debug`
calls are what gets recorded — that's how emitter output from separate
pipeline scripts ends up combined in one `RUN_LOG.md`. A script whose
output naturally splits into independent sections can also call
`log_stage(name)` between them, so `record()` diffs each stage on its
own instead of diffing the whole output as one blob. For a
high-cardinality loop (e.g. one call per file), `log_count(key)` /
`log_count_summary(key)` batch it into one recorded summary line
instead of one row per item.

A full runnable example pipeline exercising every feature above
together — self-registering bash/python steps, `runlog run` wrapping an
external tool, `log_stage`, `log_count`, failure handling, and the
`RUNLOG_SCRIPT_ID`/`RUNLOG_ORDER` overrides needed for batch-scheduler
(e.g. SLURM) pipelines — lives at `resources/examples/pipeline/`; see
`resources/examples/README.md` for a step-by-step breakdown. Run it
directly:

```bash
./resources/examples/pipeline/run_pipeline.sh
```

Self-register a step (as wired into
`resources/examples/pipeline/steps/fetch_data.sh`):

```bash
source "$(runlog-setup-path)"
runlog_setup
log_info "fetching data"
```

Record already-known output directly (e.g. a step whose real output
only exists later, asynchronously, such as a SLURM job recording from
inside its own batch script once it finishes):

```bash
runlog record --id my_step --order 50 --root "$ROOT" --text "$(cat some_summary.txt)"
```

Wrap a third-party CLI you can't add emitter calls to, from the
outside (`runlog run` doesn't read `RUNLOG_ROOT`/`RUNLOG_LOG_FILE`, so
`--root`/`--log-file` are always explicit here; `-i/--include-pattern`
keeps only lines matching a regex, e.g. a tool's own summary lines, out
of an otherwise noisy raw output):

```bash
runlog run --id third_party_tool --order 40 --root "$ROOT" \
    --log-file "$ROOT/RUN_LOG.md" -i '^RESULT:' -- some-external-cli --flag value
```

## Development
To install from source, clone the git repo:
```
git clone git@gitlab.com:mvvugt/log_tools.git
cd log_tools
```

### Dependency installation

#### Using pip
You can install the dependencies using pip from the root of the cloned
repository:
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
# activate environment for package installation
conda activate log_tools
```

To add to an existing environment use:
```
conda activate <env_name>
conda env update --file ./resources/conda/conda_update.yaml
```

### Package installation from source
Next the package can be installed:
```
make install
```

`make` is just a wrapper, you can also use:
```
python -m pip install .
```

### Editable install
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

See `CHANGELOG.md` for the full history. Latest (`[0.1.0]`):

### version `0.1.0`

* BUILD - Convert single-file `runlog.py` script into an installable `log_tools` package with a `runlog` console-script entry point.
* REFACTOR - Split `runlog.py` into `log_tools/functions.py` (shared functions), `log_tools/runlog.py` (specific functions), and `log_tools/cli/runlog.py` (thin argparse CLI wrapper).
* BUILD - Add GitLab CI/CD scaffolding: `.gitlab-ci.yml` (GitLab Pages deploy stage) plus `resources/ci_cd/` scripts for local Docker-parity lint/test debugging.
* DOCS - Add Sphinx documentation scaffolding under `docs/`.
* DOCS - Rewrite README.md's packaging section.
* BUILD - Add `VERSION`, `.bumpversion.cfg`, `LICENSE.txt` (MIT), and ruff configuration in `pyproject.toml`.
