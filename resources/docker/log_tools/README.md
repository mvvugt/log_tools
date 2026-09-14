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

This only builds the image locally — pushing it to wherever
`.gitlab-ci.yml`/CI pulls `mvanvugt/log_tools:master` from is a
separate, manual step.
