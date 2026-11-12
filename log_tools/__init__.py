"""log_tools: a home for small, stdlib-only logging/pipeline-tracking tools.

Currently contains `runlog` (see `log_tools.runlog` and the `runlog`
console-script entry point in `pyproject.toml`).
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    # The distribution name (pyproject.toml [project] name), not the
    # import name: they differ since the PyPI rename to runlog-tools.
    __version__ = version("runlog-tools")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
