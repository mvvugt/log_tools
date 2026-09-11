# runlog

A standalone, stdlib-only tool that records every pipeline script's run
into **one compact, project-wide Markdown log** (`RUN_LOG.md` by default) —
instead of scrolling back through terminal output, or one log file per
script piling up over time.

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
runlog.py run    --id ID --order N [--root PATH] [--log-file PATH] -- CMD...
runlog.py record --id ID --order N [--root PATH] [--log-file PATH] (--text TEXT | --stdin)
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
"$ROOT"/tools/runlog/runlog.py run --id id_mapping --order 10 --root "$ROOT" -- \
    mamba run --no-capture-output -n "$ENV" \
    "$ROOT"/src/id_mapping.py build
```

**`record`** is the primitive underneath `run` — use it directly when you
already have the output text in hand and there's nothing to wrap (e.g. a
step whose real output only exists later, asynchronously, such as a SLURM
job you want to record from inside its own batch script once it finishes):

```bash
runlog.py record --id my_step --order 50 --root "$ROOT" --text "$(cat some_summary.txt)"
```

## Invoking it as `runlog` instead of `runlog.py`

The script is already executable (`chmod +x`) with a
`#!/usr/bin/env python3` shebang, so either of these gets you a bare
`runlog` command with no packaging (no `pyproject.toml`/console entry
point needed):

- **Shell alias (simplest)** — add to `~/.zshrc` (or `~/.bashrc`):

  ```bash
  alias runlog="/path/to/tools/runlog/runlog.py"
  ```

  then reload your shell (`source ~/.zshrc`). One line, no directory/PATH
  management. Tradeoff: if you later move this tool into a personal
  toolkit location (as planned), update the alias target to match.

- **Symlink into a directory already on `PATH`** — e.g.:

  ```bash
  ln -s "/path/to/tools/runlog/runlog.py" ~/bin/runlog
  ```

  (check `~/bin` is on `PATH` with `echo $PATH`; if not, add
  `export PATH="$HOME/bin:$PATH"` to `~/.zshrc`). Slightly more setup than
  an alias, but works in non-interactive shells/scripts where aliases
  aren't expanded, and can be re-pointed later with `ln -sf` without
  touching shell config.

Note: the call sites in `src/mr_arrhythmia.sh` intentionally keep the full
`"$ROOT"/tools/runlog/runlog.py` path (since `$ROOT` there already branches
per-machine) — the above is for convenient ad hoc/manual invocation, not
required for the pipeline itself.
