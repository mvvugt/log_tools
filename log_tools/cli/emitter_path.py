"""
Command-line entry point for `runlog-emitter-path`.

Prints the absolute path to the installed `log_tools/emitter.sh`, so a
Bash script can do ``source "$(runlog-emitter-path)"`` after
`pip install log_tools` without knowing where the package lives.
Registered in pyproject.toml as:

    [project.scripts]
    runlog-emitter-path = "log_tools.cli.emitter_path:main"
"""
from __future__ import annotations

import sys
from pathlib import Path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main() -> None:
    """Print the installed `emitter.sh` path, or exit with an error."""
    path = Path(__file__).resolve().parent.parent / "emitter.sh"
    if not path.is_file():
        sys.exit(f"error: emitter.sh not found at {path} (broken install?)")
    print(path)


if __name__ == "__main__":
    main()
