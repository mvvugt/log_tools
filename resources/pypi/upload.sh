#!/usr/bin/env bash
# Build the sdist + wheel from a clean dist/, check them, and upload to
# PyPI. Run from anywhere: the script works from the repo root.
# Credentials come from ~/.pypirc (see resources/pypi/README.md).
set -euo pipefail
readonly UPLOAD_ARGS=()
log_info()  { echo "[info]  $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_error() { echo "[error] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# MAIN

# -----------------------------------------------------------------------
# Build, verify and upload the package from the repo root.
#
# Returns
# -------
#   0 on success; non-zero if the build, the version check, twine check
#   or the upload fails (nothing is uploaded after a failed check).
#
# Outputs
# -------
#   Replaces <repo>/dist/ with the freshly built sdist and wheel.
# -----------------------------------------------------------------------
main() {
    local script_dir version
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "${script_dir}/../.."
    version="$(tr -d '[:space:]' < VERSION)"
    rm -rf dist
    log_info "building log_tools ${version}"
    python -m build
    local -a dists=(dist/*"-${version}"{.tar.gz,-*.whl})
    local dist
    for dist in "${dists[@]}"; do
        if [[ ! -f "${dist}" ]]; then
            log_error "no built file ${dist} for VERSION ${version}"
            return 1
        fi
    done
    python -m twine check "${dists[@]}"
    log_info "uploading ${dists[*]} to PyPI"
    python -m twine upload ${UPLOAD_ARGS[@]+"${UPLOAD_ARGS[@]}"} "${dists[@]}"
}
main "$@"
