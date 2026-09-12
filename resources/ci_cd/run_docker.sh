#!/usr/bin/env bash
# Run the same Docker image GitLab CI uses, locally, for pre-commit
# debugging. Mirrors the before_script.sh + lint/test steps a CI job
# would run, inside the container, against a mounted copy of the repo.
#
# Usage: ./run_docker.sh <docker-image> <repo-root> [docs-build-dir]
set -euo pipefail

IMAGE="${1:?docker image required, e.g. mvvugt/pypan:complete-3.13}"  # TODO: replace with your actual CI image once built
REPO_ROOT="${2:?repo root path required}"
DOCS_BUILD_DIR="${3:-docs/build}"

docker run --rm -it \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    "${IMAGE}" \
    bash -c "
        set -euo pipefail
        pip install -e '.[dev]'
        ruff check .
        ruff format --check .
        if [[ -d tests ]]; then pytest; fi  # TODO: drop this guard once the deferred test suite lands
        cd docs && make html
    "

echo "Docs built under: ${REPO_ROOT}/${DOCS_BUILD_DIR}"
