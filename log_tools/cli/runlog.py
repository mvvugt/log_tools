"""
Command-line entry point for `runlog`.

Thin wrapper: parses args and calls into `log_tools.runlog` -- no domain
logic lives here. Registered in pyproject.toml as:

    [project.scripts]
    runlog = "log_tools.cli.runlog:main"
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from log_tools.runlog import (
    Constants,
    filter_tagged_lines,
    record,
    run_and_record,
)

_log = logging.getLogger(__name__)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _init_cmd_args() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
            description=(
                    "Record per-script run output into one compact, "
                    "project-wide Markdown log."
                    ),
            )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
            "--id", dest="script_id", required=True,
            help="Identifier for this script/step; keys its log section.",
            )
    common.add_argument(
            "--order", type=int, required=True,
            help="Sort key controlling this section's position in the log.",
            )
    common.add_argument(
            "--root", type=Path, default=None,
            help=(
                    "Git working-tree root (default: resolved via "
                    "`git rev-parse --show-toplevel` from cwd)."
                    ),
            )
    common.add_argument(
            "--log-file", type=Path, default=None,
            help=f"Log file path (default: <root>/{Constants.DEFAULT_LOG_NAME}).",
            )
    common.add_argument(
            "-t", "--tagged-only", action="store_true",
            help="Only record lines matching an [info]/[warn]/[error]/[debug] tag.",
            )

    run_parser = subparsers.add_parser(
            "run", parents=[common],
            help="Run a command, capture its output, and record it.",
            )
    run_parser.add_argument(
            "cmd", metavar="command", nargs=argparse.REMAINDER,
            help="Command and arguments to run (after `--`).",
            )

    record_parser = subparsers.add_parser(
            "record", parents=[common],
            help="Record already-known output text directly.",
            )
    text_group = record_parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Output text to record.")
    text_group.add_argument(
            "--stdin", action="store_true",
            help="Read output text to record from stdin.",
            )

    return parser


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _parse_cmd_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    return parser.parse_args()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _resolve_root(root_arg: Path | None) -> Path:
    """Resolve the git working-tree root, defaulting from cwd.

    Parameters
    ----------
    root_arg : `Path` or `None`
        Explicit `--root` value, if given.

    Returns
    -------
    root : `Path`
        Resolved working-tree root.

    Raises
    ------
    SystemExit
        If `root_arg` is `None` and cwd is not inside a git working tree.
    """
    if root_arg is not None:
        return root_arg
    try:
        top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                check=True, capture_output=True, text=True,
                ).stdout.strip()
        return Path(top)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit(
                "error: --root not given and cwd is not inside a git "
                "working tree",
                )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main() -> None:
    """Entry point for the CLI."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    parser = _init_cmd_args()
    args = _parse_cmd_args(parser)

    root = _resolve_root(args.root)
    log_file = args.log_file or (root / Constants.DEFAULT_LOG_NAME)

    if args.command == "run":
        command = [c for c in args.cmd if c != "--"]
        if not command:
            parser.error("no command given after `run` (pass it after `--`)")
        returncode = run_and_record(
                log_file=log_file, script_id=args.script_id,
                order=args.order, root=root, command=command,
                tagged_only=args.tagged_only,
                )
        sys.exit(returncode)
    else:
        output = sys.stdin.read() if args.stdin else args.text
        if args.tagged_only:
            output = filter_tagged_lines(output)
        record(
                log_file=log_file, script_id=args.script_id,
                order=args.order, output=output, root=root,
                tagged_only=args.tagged_only,
                )


if __name__ == "__main__":
    main()
