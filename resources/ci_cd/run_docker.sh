#!/usr/bin/env bash
# Run the same Docker image GitLab CI uses, locally, for pre-commit
# debugging. Populates a temp directory with a clean `git archive`
# checkout (not the live working tree) and bind-mounts that, so
# container-side build artifacts never land in the real repo and the
# build only sees committed files — closer to what CI actually sees,
# without marvel's full docker-cp/rsync machinery. Runs the exact same
# before_script.sh -> test.sh -> pages.sh sequence as .gitlab-ci.yml's
# `test`/`pages` jobs, so `public/` ends up identical to what CI would
# publish (per pages.sh's own docs/build/html -> public/ move).
#
# Usage: ./run_docker.sh <docker-image> <repo-root> [output-dir]
set -euo pipefail

IMAGE="${1:?docker image required, e.g. mvanvugt/log_tools:master}"
REPO_ROOT="${2:?repo root path required}"
OUTPUT_DIR="${3:-public}"

if ! "${REPO_ROOT}/resources/docker/log_tools/check_stale.sh"; then
    echo "[warn] continuing anyway with the existing image" >&2
fi

TMP_CHECKOUT="$(mktemp -d)"
trap 'rm -rf "${TMP_CHECKOUT}"' EXIT

git -C "${REPO_ROOT}" archive HEAD | tar -x -C "${TMP_CHECKOUT}"

docker run --rm -it \
    -v "${TMP_CHECKOUT}:/workspace" \
    -w /workspace \
    "${IMAGE}" \
    bash -c "
        set -euo pipefail
        source resources/ci_cd/before_script.sh
        bash resources/ci_cd/test.sh
        bash resources/ci_cd/pages.sh
    "

rm -rf "${REPO_ROOT:?}/${OUTPUT_DIR:?}"
cp -r "${TMP_CHECKOUT}/${OUTPUT_DIR}" "${REPO_ROOT}/${OUTPUT_DIR}"

echo "Docs built under: ${REPO_ROOT}/${OUTPUT_DIR}"
