#!/usr/bin/env bash
# Sourced by .gitlab-ci.yml jobs before their `script:` step runs.
set -euo pipefail

python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install -r resources/ci_cd/sphinx.txt
