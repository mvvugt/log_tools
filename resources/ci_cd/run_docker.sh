#!/usr/bin/env bash
# Run the same Docker image GitLab CI uses, locally, for pre-commit
# debugging. Populates a temp directory with a clean `git clone` of
# REPO_ROOT (not the live working tree) and bind-mounts that, so
# container-side build artifacts never land in the real repo and the
# build only sees committed files — closer to what CI actually sees,
# without marvel's full docker-cp/rsync machinery. A local clone (not
# `git archive`) so the checkout has a real `.git`, matching a GitLab
# runner's own clone step -- code that resolves its git root (e.g.
# `runlog`'s `--root` default, via `git rev-parse --show-toplevel`)
# needs one to run at all; `git archive` alone leaves no `.git`, so
# anything relying on it would pass in real CI but fail here. Runs the
# exact same before_script.sh -> test.sh -> pages.sh sequence as
# `.gitlab-ci.yml`'s `test`/`pages` jobs, so `public/` ends up
# identical to what CI would publish (per pages.sh's own
# docs/build/html -> public/ move).
#
# Usage: ./run_docker.sh <docker-image> <repo-root> [output-dir]
set -euo pipefail

IMAGE="${1:?docker image required, e.g. mvanvugt/log_tools:master}"
REPO_ROOT="${2:?repo root path required}"
OUTPUT_DIR="${3:-public}"

if ! "${REPO_ROOT}/resources/docker/log_tools/check_stale.sh"; then
    echo "[warn] continuing anyway with the existing image" >&2
fi

# Placed inside REPO_ROOT (already under $HOME), not the system temp
# dir (/var/folders/... on macOS): Docker Desktop and Colima both only
# bind-mount paths under directories they're configured to share --
# $HOME by default -- so a system-tmp checkout can silently bind-mount
# as empty instead of erroring. `.*` is already gitignored, so this
# never risks being committed even if the trap below doesn't run.
TMP_CHECKOUT="$(mktemp -d "${REPO_ROOT}/.ci_debug_tmp.XXXXXX")"
trap 'rm -rf "${TMP_CHECKOUT}"' EXIT
# Resolve symlinks defensively, in case REPO_ROOT itself is reached via
# one -- Docker's file-sharing check matches on the resolved path.
TMP_CHECKOUT="$(cd "${TMP_CHECKOUT}" && pwd -P)"

# --local clones via the filesystem (hardlinking objects, no network);
# the checked-out working tree reflects HEAD only, same as `git
# archive` -- uncommitted changes in REPO_ROOT still can't leak in.
git clone --quiet --local "${REPO_ROOT}" "${TMP_CHECKOUT}"

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
