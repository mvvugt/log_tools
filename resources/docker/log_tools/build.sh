#!/usr/bin/env bash
# Builds the log_tools CI image referenced by .gitlab-ci.yml and by
# resources/ci_cd/run_docker.sh / build.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE_HASH="$(sha256sum "${SCRIPT_DIR}/Dockerfile" | cut -d' ' -f1)"

docker build \
    --label "dockerfile_hash=${DOCKERFILE_HASH}" \
    -t mvanvugt/log_tools:master \
    "${SCRIPT_DIR}"
