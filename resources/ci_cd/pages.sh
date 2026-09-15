#!/usr/bin/env bash
# Builds Sphinx docs and stages them for GitLab Pages (expects `public/`
# as the artifact path, per .gitlab-ci.yml `pages:` job).
set -euo pipefail

if [[ -d resources/images ]]; then
    mkdir -p docs/source/_static
    cp -r resources/images docs/source/_static/images
fi

cd docs
make html
cd ..
rm -rf public
mv docs/build/html public
