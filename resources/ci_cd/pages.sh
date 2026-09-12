#!/usr/bin/env bash
# Builds Sphinx docs and stages them for GitLab Pages (expects `public/`
# as the artifact path, per .gitlab-ci.yml `pages:` job).
set -euo pipefail

cd docs
make html
cd ..
rm -rf public
mv docs/build/html public
