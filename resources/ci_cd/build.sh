#!/usr/bin/env bash
# Resolves paths relative to this script's own location, then delegates
# to run_docker.sh with the project's CI image + repo root, for a
# no-arguments "just build it" convenience entry point.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE="mvanvugt/log_tools:master"  # built via resources/docker/log_tools/build.sh

"${SCRIPT_DIR}/run_docker.sh" "${IMAGE}" "${REPO_ROOT}"
