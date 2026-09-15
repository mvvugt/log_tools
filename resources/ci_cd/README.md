# resources/ci_cd

Scripts called by `.gitlab-ci.yml`, also runnable locally in the same
Docker image the GitLab runner uses, so you can debug CI failures before
pushing.

## Local usage

    ./resources/ci_cd/run_docker.sh <docker-image> <repo-root>

or, using the project's CI image baked into `build.sh`
(`mvanvugt/log_tools:master`, built via
`resources/docker/log_tools/build.sh`):

    ./resources/ci_cd/build.sh

1. Build the CI image once (only needed the first time, or again after
   editing `resources/docker/log_tools/Dockerfile`):

       ./resources/docker/log_tools/build.sh

2. Run the local debug build (requires Docker running):

       ./resources/ci_cd/build.sh

   This checks out `HEAD` (committed files only) into a temp
   directory via `git archive`, bind-mounts it into
   `mvanvugt/log_tools:master`, and runs
   `before_script.sh` -> `test.sh` -> `pages.sh` inside it — the exact
   same scripts `.gitlab-ci.yml`'s `test` and `pages` jobs run. When it
   finishes, the built site is copied back to `public/` in the real
   repo so you can open `public/index.html` directly.

   For a custom image or a different repo path, call
   `run_docker.sh <docker-image> <repo-root>` directly instead of
   `build.sh`.

`run_docker.sh` also warns (but does not block) if
`mvanvugt/log_tools:master` predates the current
`resources/docker/log_tools/Dockerfile` — see "Is my image stale?"
below.

## Local debug vs. real CI

`run_docker.sh` is designed so a local pass reliably predicts a CI
pass, and a local failure reproduces a CI failure without waiting on a
pipeline:

- Both run the same three scripts, in the same order:
  `before_script.sh` (install deps) -> `test.sh` (lint + pytest) ->
  `pages.sh` (build docs, stage `public/`).
- Both run inside the same Docker image, `mvanvugt/log_tools:master`.
- Both build from committed files only — CI clones the repo fresh;
  locally, `run_docker.sh` uses `git archive HEAD` into a temp
  directory instead of bind-mounting your live working tree, so
  uncommitted changes can't accidentally pass (or fail) a local run
  that CI would see differently.

The one thing that differs: GitLab's own CI variables
(`$CI_COMMIT_BRANCH`, `$CI_DEFAULT_BRANCH`) aren't set when running
locally. Nothing in `before_script.sh`, `test.sh`, or `pages.sh`
depends on them — only the `pages` job's `rules:` block in
`.gitlab-ci.yml` does (it restricts the real GitLab Pages deploy to
the default branch). That branch-gating logic lives entirely in the
YAML, not in any script, so it has no effect on local runs: a local
`build.sh` run always builds and stages `public/`, regardless of which
branch you're on.

## Is my image stale?

`resources/docker/log_tools/build.sh` stamps the image with a label
containing a sha256 of its `Dockerfile`. Before each local run,
`run_docker.sh` calls `resources/docker/log_tools/check_stale.sh`,
which compares that label against the `Dockerfile`'s current hash and
prints a warning (to stderr, exit 1) if they differ or the image
doesn't exist yet — this catches "I edited the Dockerfile and forgot
to rebuild" without you having to remember to check manually. It's a
warning, not a gate: the run continues against whatever image exists,
since you may be intentionally testing against an older build.

Run it standalone any time:

    ./resources/docker/log_tools/check_stale.sh

Rebuild with `./resources/docker/log_tools/build.sh` when it reports
stale. Real CI never has this question — `.gitlab-ci.yml`'s `image:`
always pulls the tag fresh, so the check only applies to local runs.

## Adding `resources/images/`

This repo doesn't currently have a `resources/images/` directory (the
"marvel" template this setup was adapted from did, and copied it into
the docs build). `pages.sh` already checks for it:

```bash
if [[ -d resources/images ]]; then
    mkdir -p docs/source/_static
    cp -r resources/images docs/source/_static/images
fi
```

So if you add images for the documentation, no script changes are
needed:

1. Create `resources/images/` and add your image files there.
2. Reference them from `docs/source/*.rst` (or Markdown pages) under
   `_static/images/...`.
3. Run `./resources/ci_cd/build.sh` locally to confirm the docs build
   picks them up before pushing — since `pages.sh` is one of the
   shared scripts, this takes effect for both local debug runs and
   real CI automatically.

## Files

- `before_script.sh` — shared setup step, sourced via the
  `.before_script_template` YAML anchor in `.gitlab-ci.yml`. Installs
  the project (`pip install -e ".[dev]"`) and the Sphinx doc-build
  dependencies.
- `test.sh` — lints (`ruff check`) and runs the test suite (`pytest`).
  Used by both the GitLab `test` job and `run_docker.sh`, so CI and
  local runs can't drift apart. Deliberately does not run
  `ruff format --check`: the codebase predates a formatter pass and
  its hand-written style doesn't match ruff's opinionated formatter,
  so that check would fail on style alone, not real issues.
- `sphinx.txt` — doc-build dependencies (themes, MyST, notebook
  support, etc.), installed by `before_script.sh`.
- `pages.sh` — builds Sphinx docs and stages `public/` for GitLab
  Pages; copies `resources/images/` into the docs build if present
  (see above).
- `run_docker.sh` — runs `before_script.sh` -> `test.sh` -> `pages.sh`
  inside the given Docker image, for local parity with CI. Builds from
  a clean `git archive` checkout copied into a temp dir (not the live
  working tree), so container-side artifacts never dirty the real
  repo. Warns (doesn't block) if the image is stale — see "Is my image
  stale?" above.
- `build.sh` — convenience wrapper around `run_docker.sh` with the
  project's image/repo-root pre-filled.
