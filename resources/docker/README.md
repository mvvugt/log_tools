# resources/docker

This contains build files to build a Docker image used for GitLab
CI/CD for this repo. This image is not a docker image containing
`log_tools` itself — it's the base environment CI runs against.

- `log_tools/` — build recipe for `mvanvugt/log_tools:master`, the
  image referenced by `.gitlab-ci.yml` and by
  `resources/ci_cd/run_docker.sh`/`build.sh` for local CI-parity runs.
