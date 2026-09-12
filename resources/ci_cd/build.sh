#!/usr/bin/env bash
# Resolves paths relative to this script's own location, then delegates
# to run_docker.sh with a fixed placeholder image + repo root, for a
# no-arguments "just build it" convenience entry point.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE="mvvugt/pypan:complete-3.13"  # TODO: replace with your actual CI image once built

"${SCRIPT_DIR}/run_docker.sh" "${IMAGE}" "${REPO_ROOT}"
