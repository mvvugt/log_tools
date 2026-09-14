#!/usr/bin/env bash
# Builds the log_tools CI image referenced by .gitlab-ci.yml and by
# resources/ci_cd/run_docker.sh / build.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker build -t mvanvugt/log_tools:master "${SCRIPT_DIR}"
