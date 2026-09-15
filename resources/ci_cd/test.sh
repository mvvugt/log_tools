#!/usr/bin/env bash
# Lints and tests the project. Called by both the GitLab `test` job and
# resources/ci_cd/run_docker.sh, so CI and local runs can never drift
# apart the way inlined, duplicated commands would.
set -euo pipefail

ruff check .
ruff format --check .
pytest
