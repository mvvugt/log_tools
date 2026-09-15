"""
Command-line entry point for `runlog-setup-path`.

Prints the absolute path to the installed `log_tools/setup.sh`, so a
Bash script can do ``source "$(runlog-setup-path)"`` after
`pip install log_tools` without knowing where the package lives.
Registered in pyproject.toml as:

    [project.scripts]
    runlog-setup-path = "log_tools.cli.setup_path:main"
"""
from __future__ import annotations

import sys
from pathlib import Path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main() -> None:
    """Print the installed `setup.sh` path, or exit with an error."""
    path = Path(__file__).resolve().parent.parent / "setup.sh"
    if not path.is_file():
        sys.exit(f"error: setup.sh not found at {path} (broken install?)")
    print(path)


if __name__ == "__main__":
    main()
