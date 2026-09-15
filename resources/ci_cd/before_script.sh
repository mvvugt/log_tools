#!/usr/bin/env bash
# Sourced by .gitlab-ci.yml jobs before their `script:` step runs.
set -euo pipefail

# The `test` job's matrix legs run on official `python:*-slim` images,
# which don't ship git (unlike the custom `mvanvugt/log_tools:master`
# image used elsewhere) -- install it if missing.
command -v git >/dev/null 2>&1 || \
    (apt-get update -qq && apt-get install -y --no-install-recommends git)

# The container runs as root, but a locally bind-mounted checkout is
# owned by the host user -- git's dubious-ownership check then refuses
# to treat it as a repo at all (any `git` call, including runlog's own
# `git rev-parse --show-toplevel`, fails). A no-op in real CI, where
# the cloned workspace is already owned by the job's own user.
git config --global --add safe.directory '*'

python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install -r resources/ci_cd/sphinx.txt
