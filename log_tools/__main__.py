"""Module entry point: `python -m log_tools --version`.

`log_tools` is a package, not a CLI tool (see `log_tools/cli/runlog.py`
for the actual `runlog` command) -- this only supports a version check.
"""
from __future__ import annotations

import argparse

from log_tools import __version__


def main() -> None:
    """Parse `--version` and print the installed package version."""
    parser = argparse.ArgumentParser(prog="log_tools", add_help=False)
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()


if __name__ == "__main__":
    main()
