# The PyPI resource

Scripts to publish `log_tools` (PyPI name `log-tools`). Both scripts
clear `dist/`, build the sdist and wheel, check that the built files
match `VERSION`, run `twine check`, and only then upload.

```bash
bash resources/pypi/upload_test.sh   # 1. TestPyPI first
bash resources/pypi/upload.sh        # 2. then PyPI
```

Needs `build` and `twine` (both in the `dev` extra) and API tokens for
both indexes in `~/.pypirc` (`[pypi]` and `[testpypi]` sections).

## Check the TestPyPI upload

Install it in a clean environment before uploading to PyPI:

```bash
python -m venv /tmp/lt_check && . /tmp/lt_check/bin/activate
pip install -i https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple log_tools
runlog --help
```

PyPI never accepts the same version twice: bump `VERSION` (via
`bump2version`) before uploading a fixed release.
