# log_tools

A small, stdlib-only package for logging/pipeline-tracking tools. Currently
contains **`runlog`**, which records every pipeline script's run into **one
compact, project-wide Markdown log** (`RUN_LOG.md` by default) — instead of
scrolling back through terminal output, or one log file per script piling
up over time.

## Installation

    pip install -e .

This installs the `runlog` command via the package's console-script entry
point (`log_tools.cli.runlog:main`).

## Why

Each time you run a step through `runlog`, it:

- captures that step's combined stdout+stderr
- **replaces** (not appends) the section for that step's `--id`, so the
  file stays small no matter how many times you re-run the pipeline
- shows a diff against that step's *previous* run, so you can see exactly
  what changed
- tags the entry with the short git commit hash (and a dirty-working-tree
  flag) active at run time, so if a later change turns out to be wrong you
  know exactly which commit to check out to get back the old behavior

Sections are ordered by an explicit `--order` number you choose per call,
so the log's layout can mirror your pipeline's execution order (e.g.
`src/mr_arrhythmia.sh`) regardless of which steps you happen to re-run.

## Usage

Two subcommands:

```
runlog run    --id ID --order N [--root PATH] [--log-file PATH] -- CMD...
runlog record --id ID --order N [--root PATH] [--log-file PATH] (--text TEXT | --stdin)
```

- `--id` — identifier for the step; keys its section in the log.
- `--order` — sort key controlling where that section lands in the file.
- `--root` — git working-tree root used to resolve the commit hash/dirty
  flag (defaults to `git rev-parse --show-toplevel` from cwd).
- `--log-file` — defaults to `<root>/RUN_LOG.md`.

**`run`** wraps a command: runs it, streams its output through live (so
you still see it interactively), captures it, and records it. Exit code is
passed through unchanged, so it plays well with `set -eo pipefail`. Example
(as wired into `src/mr_arrhythmia.sh`):

```bash
runlog run --id id_mapping --order 10 --root "$ROOT" -- \
    mamba run --no-capture-output -n "$ENV" \
    "$ROOT"/src/id_mapping.py build
```

**`record`** is the primitive underneath `run` — use it directly when you
already have the output text in hand and there's nothing to wrap (e.g. a
step whose real output only exists later, asynchronously, such as a SLURM
job you want to record from inside its own batch script once it finishes):

```bash
runlog record --id my_step --order 50 --root "$ROOT" --text "$(cat some_summary.txt)"
```
