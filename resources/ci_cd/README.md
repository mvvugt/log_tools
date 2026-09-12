# resources/ci_cd

Scripts called by `.gitlab-ci.yml`, also runnable locally in the same
Docker image the GitLab runner uses, so you can debug CI failures before
pushing.

## Local usage

    ./resources/ci_cd/run_docker.sh <docker-image> <repo-root>

or, using the placeholder image baked into `build.sh`:

    ./resources/ci_cd/build.sh

## Files

- `before_script.sh` — shared setup step, sourced via the
  `.before_script_template` YAML anchor in `.gitlab-ci.yml`.
- `pages.sh` — builds Sphinx docs and stages `public/` for GitLab Pages.
- `run_docker.sh` — runs lint + tests (once the test suite exists) +
  docs build inside the given Docker image, for local parity with CI.
- `build.sh` — convenience wrapper around `run_docker.sh` with the
  project's image/repo-root pre-filled.
