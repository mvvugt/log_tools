# resources/docker/log_tools

Build recipe for `mvanvugt/log_tools:master`, the image
`.gitlab-ci.yml`'s `pages:` job runs in, and that
`resources/ci_cd/run_docker.sh`/`build.sh` use to reproduce the same
environment locally.

Contains: Python 3.13 (Debian slim), `pandoc` (needed by `nbsphinx` for
notebook docs), and basic build tooling (`build-essential`, `git`,
`make`, `sed`) in case a future dependency needs compiling.

Deliberately does **not** bake in any Python-level dependencies —
`resources/ci_cd/before_script.sh` and `run_docker.sh` install
`log_tools`'s dev extras and `resources/ci_cd/sphinx.txt` fresh each
run, so `pyproject.toml` stays the single source of truth for those
versions instead of drifting against a separate image `requirements.txt`.

## Build

    ./build.sh

This only builds the image locally. Push it to Docker Hub so
`.gitlab-ci.yml`/CI can pull `mvanvugt/log_tools:master` — this is a
manual step, not scripted or run in CI:

    docker login
    docker push mvanvugt/log_tools:master

Re-run this push any time the image is rebuilt after a `Dockerfile`
change (see "Checking staleness" below for detecting that).

`build.sh` also labels the image with a sha256 hash of this
`Dockerfile`, so later runs can tell whether the image is stale (i.e.
the `Dockerfile` changed since it was last built).

## Checking staleness

    ./check_stale.sh

Compares the current `Dockerfile`'s hash against the image's
`dockerfile_hash` label; prints `up to date` or `stale` (exit 1 if
stale or the image doesn't exist yet). `resources/ci_cd/run_docker.sh`
already calls this automatically before each local debug run and
warns if it fails — you only need to run it directly if you want to
check outside of that flow.
