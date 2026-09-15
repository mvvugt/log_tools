#!/usr/bin/env bash
# Reports whether mvanvugt/log_tools:master needs rebuilding: compares
# the sha256 of the current Dockerfile against the dockerfile_hash
# label baked into the image by build.sh. Exit 0 = up to date,
# 1 = stale or image missing entirely (message on stderr either way).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="mvanvugt/log_tools:master"

CURRENT_HASH="$(sha256sum "${SCRIPT_DIR}/Dockerfile" | cut -d' ' -f1)"

if ! IMAGE_HASH="$(docker inspect \
    --format '{{ index .Config.Labels "dockerfile_hash" }}' \
    "${IMAGE}" 2>/dev/null)"; then
    echo "[warn] ${IMAGE} not found locally -- build it first: " \
        "resources/docker/log_tools/build.sh" >&2
    exit 1
fi

if [[ "${IMAGE_HASH}" != "${CURRENT_HASH}" ]]; then
    echo "[warn] ${IMAGE} is stale (Dockerfile changed since last" \
        "build) -- rebuild with: resources/docker/log_tools/build.sh" >&2
    exit 1
fi

echo "[info] ${IMAGE} is up to date with Dockerfile"
