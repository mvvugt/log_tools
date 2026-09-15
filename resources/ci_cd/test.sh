#!/usr/bin/env bash
# Lints and tests the project. Called by both the GitLab `test` job and
# resources/ci_cd/run_docker.sh, so CI and local runs can never drift
# apart the way inlined, duplicated commands would.
#
# No `ruff format --check` here: the codebase predates a formatter
# pass and its hand-written style (hanging indents, compact multi-arg
# calls) doesn't match ruff's opinionated formatter, so that check
# would fail on style alone rather than catching real issues. Only
# `ruff check` (correctness/lint) gates the pipeline.
set -euo pipefail

ruff check .
pytest
