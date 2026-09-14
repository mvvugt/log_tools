#!/usr/bin/env bash
# Run the same Docker image GitLab CI uses, locally, for pre-commit
# debugging. Populates a temp directory with a clean `git archive`
# checkout (not the live working tree) and bind-mounts that, so
# container-side build artifacts never land in the real repo and the
# build only sees committed files — closer to what CI actually sees,
# without marvel's full docker-cp/rsync machinery.
#
# Usage: ./run_docker.sh <docker-image> <repo-root> [docs-build-dir]
set -euo pipefail

IMAGE="${1:?docker image required, e.g. mvvugt/pypan:complete-3.13}"  # TODO: replace with your actual CI image once built
REPO_ROOT="${2:?repo root path required}"
DOCS_BUILD_DIR="${3:-docs/build}"

TMP_CHECKOUT="$(mktemp -d)"
trap 'rm -rf "${TMP_CHECKOUT}"' EXIT

git -C "${REPO_ROOT}" archive HEAD | tar -x -C "${TMP_CHECKOUT}"

docker run --rm -it \
    -v "${TMP_CHECKOUT}:/workspace" \
    -w /workspace \
    "${IMAGE}" \
    bash -c "
        set -euo pipefail
        pip install -e '.[dev]'
        ruff check .
        ruff format --check .
        pytest
        cd docs && make html
    "

rm -rf "${REPO_ROOT:?}/${DOCS_BUILD_DIR:?}"
cp -r "${TMP_CHECKOUT}/${DOCS_BUILD_DIR}" "${REPO_ROOT}/${DOCS_BUILD_DIR}"

echo "Docs built under: ${REPO_ROOT}/${DOCS_BUILD_DIR}"
