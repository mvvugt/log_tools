#!/usr/bin/env python3
"""
Record per-script run output into one compact, project-wide Markdown log.

Standalone tool: no dependency on any project-specific code. Designed to be
copied into other repos as-is -- every path is passed in via CLI arguments,
nothing is hardcoded to a particular project layout.

Each call upserts one section (keyed by ``--id``) in a single Markdown file,
ordered by ``--order``. The previous captured output for that id (if any) is
diffed against the new output and shown inline, and the git commit active at
run time is recorded, so a later change can be traced back to the exact
commit that produced a given run's output.

See TODO.md for planned direction (incl. why ``--tagged-only`` is a stopgap).
"""

from __future__ import annotations

import argparse
import difflib
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_LOG_NAME: str = "RUN_LOG.md"
MAX_DIFF_LINES: int = 40
SECTION_HEADER_PREFIX: str = "## "
TAG_PATTERN: str = r"^\[[A-Za-z]+\]"  # see TODO.md
ERROR_TAIL_DIVIDER: str = "--- error output (untagged) ---"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@dataclass
class Entry:
    """One script's latest recorded run.

    Attributes
    ----------
    script_id : `str`
        Identifier passed via ``--id``, also the section key.
    order : `int`
        Sort key controlling section order in the rendered file.
    timestamp : `str`
        Local timestamp of the run, ``YYYY-MM-DD HH:MM:SS``.
    commit : `str`
        Short git commit hash active at run time (``"unknown"`` if not a
        git repo or git is unavailable).
    dirty : `bool`
        Whether the working tree had uncommitted changes at run time.
    label : `str`
        Free-text label describing what was run (e.g. the command line),
        shown next to the section title.
    output : `str`
        The captured output text for this run.
    diff : `str` or `None`, optional
        Unified diff vs the previous run's output, shown as a sibling
        block above `output` when not `None`. Computed fresh at record
        time -- never re-derived from a parsed file, so it is never
        nested inside the ``Output:`` code fence.
    failed : `bool`, optional, default: `False`
        Whether this run's underlying command failed. Only ever set
        `True` via `run`'s exit-code check; `record` never sets it.
    """

    script_id: str
    order: int
    timestamp: str
    commit: str
    dirty: bool
    label: str
    output: str
    diff: str | None = None
    failed: bool = False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_git_info(root: Path) -> tuple[str, bool]:
    """Return the short commit hash and dirty flag for a git repo.

    Parameters
    ----------
    root : `Path`
        Path inside (or at the top of) the git working tree.

    Returns
    -------
    commit : `str`
        Short commit hash, or ``"unknown"`` if `root` is not a git repo or
        git is not available.
    dirty : `bool`
        `True` if the working tree has uncommitted changes; `False` if
        clean or unknown.
    """
    try:
        commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                check=True, capture_output=True, text=True,
                ).stdout.strip()
        status = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                check=True, capture_output=True, text=True,
                ).stdout
        return commit, bool(status.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_log(path: Path) -> dict[str, Entry]:
    """Parse an existing run-log file back into per-script entries.

    Parameters
    ----------
    path : `Path`
        Path to the Markdown log file. Missing files parse as empty.

    Returns
    -------
    entries : `dict[str, Entry]`
        Mapping of ``script_id`` to its `Entry`.
    """
    if not path.is_file():
        return {}

    entries: dict[str, Entry] = {}
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith(SECTION_HEADER_PREFIX):
            i += 1
            continue

        header = line[len(SECTION_HEADER_PREFIX):]
        order_str, _, rest = header.partition("] ")
        order = int(order_str.strip("["))
        script_id, _, label = rest.partition(" (")
        label = label[:-1] if label.endswith(")") else label
        label = label.strip("`")
        i += 1

        timestamp = ""
        commit = "unknown"
        dirty = False
        failed = False
        while i < len(lines) and lines[i].startswith("- "):
            meta = lines[i][2:]
            if meta.startswith("last run: "):
                timestamp = meta[len("last run: "):]
            elif meta.startswith("commit: "):
                commit = meta[len("commit: `"):].split("`")[0]
                dirty = "(dirty)" in meta
            elif meta.startswith("status: "):
                failed = meta[len("status: "):].strip() == "failed"
            i += 1

        # skip any diff block, then read the current "Output:" fenced block
        output_lines: list[str] = []
        in_output_block = False
        in_fence = False
        while i < len(lines) and not lines[i].startswith(SECTION_HEADER_PREFIX):
            if lines[i].strip() == "Output:":
                in_output_block = True
            elif in_output_block and lines[i].startswith("```"):
                if in_fence:
                    break
                in_fence = True
            elif in_output_block and in_fence:
                output_lines.append(lines[i])
            i += 1

        entries[script_id] = Entry(
                script_id=script_id, order=order, timestamp=timestamp,
                commit=commit, dirty=dirty, label=label,
                output="\n".join(output_lines), failed=failed,
                )

    return entries


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def diff_text(old: str, new: str) -> str | None:
    """Compute a truncated unified diff between two output blocks.

    Parameters
    ----------
    old : `str`
        Previously recorded output.
    new : `str`
        Newly captured output.

    Returns
    -------
    diff : `str` or `None`
        Unified diff text (no file headers), truncated to
        `MAX_DIFF_LINES` with a trailing note if longer. `None` if `old`
        and `new` are identical.
    """
    if old == new:
        return None

    diff_lines = list(difflib.unified_diff(
            old.splitlines(), new.splitlines(), lineterm="",
            ))[2:]  # drop the "---"/"+++" file-header lines
    if len(diff_lines) > MAX_DIFF_LINES:
        omitted = len(diff_lines) - MAX_DIFF_LINES
        diff_lines = diff_lines[:MAX_DIFF_LINES]
        diff_lines.append(f"... {omitted} more line(s) omitted")
    return "\n".join(diff_lines)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def filter_tagged_lines(output: str) -> str:
    """Keep only lines matching `TAG_PATTERN`, dropping the rest silently."""
    pattern = re.compile(TAG_PATTERN, re.IGNORECASE)
    return "\n".join(line for line in output.splitlines() if pattern.match(line))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def build_recorded_output(output: str, *, tagged_only: bool, failed: bool) -> str:
    """Apply `--tagged-only` filtering, appending the error tail on failure.

    Parameters
    ----------
    output : `str`
        Raw captured output.
    tagged_only : `bool`
        Whether to filter to lines matching `TAG_PATTERN`.
    failed : `bool`
        If `True` and `tagged_only` is set, append everything printed after
        the last tagged line (the likely error text) below a divider, so a
        failing run's actual error isn't silently filtered out.

    Returns
    -------
    text : `str`
        The output text to record.
    """
    if not tagged_only:
        return output
    filtered = filter_tagged_lines(output)
    if not failed:
        return filtered

    pattern = re.compile(TAG_PATTERN, re.IGNORECASE)
    lines = output.splitlines()
    last_tagged_idx = -1
    for i, line in enumerate(lines):
        if pattern.match(line):
            last_tagged_idx = i
    tail = "\n".join(lines[last_tagged_idx + 1:])
    if not tail.strip():
        return filtered

    return (
            f"{filtered}\n{ERROR_TAIL_DIVIDER}\n{tail}" if filtered
            else f"{ERROR_TAIL_DIVIDER}\n{tail}"
            )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def render_log(entries: dict[str, Entry]) -> str:
    """Render all entries back to a single Markdown document.

    Parameters
    ----------
    entries : `dict[str, Entry]`
        Entries to render, sorted by `Entry.order`.

    Returns
    -------
    text : `str`
        Full Markdown document text.
    """
    sections: list[str] = []
    for entry in sorted(entries.values(), key=lambda e: (e.order, e.script_id)):
        title = f"[{entry.order}] {entry.script_id}"
        if entry.label:
            title += f" (`{entry.label}`)"
        dirty_note = " (dirty)" if entry.dirty else ""
        block = [
                f"{SECTION_HEADER_PREFIX}{title}",
                f"- last run: {entry.timestamp}",
                f"- commit: `{entry.commit}`{dirty_note}",
                ]
        if entry.failed:
            block.append("- status: failed")
        block.append("")
        if entry.diff is not None:
            block += [entry.diff, ""]
        block += ["Output:", "```text", entry.output, "```"]
        sections.append("\n".join(block))
    return "\n\n".join(sections) + "\n" if sections else ""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def record(
        *, log_file: Path, script_id: str, order: int, output: str,
        root: Path, label: str = "", failed: bool = False,
        tagged_only: bool = False,
        ) -> None:
    """Upsert one script's entry in the run-log, replacing its prior state.

    Parameters
    ----------
    log_file : `Path`
        Path to the project's single Markdown run-log file.
    script_id : `str`
        Identifier for the script/step being recorded.
    order : `int`
        Sort key controlling this section's position in the file.
    output : `str`
        Captured output text for this run.
    root : `Path`
        Git working-tree root used to resolve the commit hash/dirty flag.
    label : `str`, optional
        Free-text label (e.g. the command line) shown in the section title.
    failed : `bool`, optional, default: `False`
        If `True`, skip computing/rendering a diff against the previous
        run -- a diff is noise on a failed run.
    tagged_only : `bool`, optional, default: `False`
        If `True` and the previous run for this id had failed while this
        one succeeds, diff against the previous run's output with its
        untagged error tail (see `ERROR_TAIL_DIVIDER`) stripped out, and
        note that the error was resolved instead of showing its removal
        as part of the diff.

    Notes
    -----
    Writes are atomic: the new file content is written to a temp file in
    the same directory, then moved into place with `os.replace`, so a
    crash mid-write cannot corrupt the log.
    """
    entries = parse_log(log_file)
    commit, dirty = get_git_info(root)
    previous = entries.get(script_id)

    diff = None
    resolved_note = False
    if not failed and previous is not None:
        old_for_diff = previous.output
        if tagged_only and previous.failed:
            resolved_note = True
            if ERROR_TAIL_DIVIDER in previous.output:
                old_for_diff, _, _tail = previous.output.partition(
                        ERROR_TAIL_DIVIDER,
                        )
                old_for_diff = old_for_diff.rstrip("\n")

        diff = diff_text(old_for_diff, output)
        if diff is not None:
            _log.info("changes vs previous run of %r:\n%s", script_id, diff)
        elif resolved_note:
            _log.info("error resolved vs previous run of %r", script_id)
        else:
            _log.info("no change vs previous run of %r", script_id)

    diff_block = None
    if (diff is not None or resolved_note) and previous is not None:
        prev_dirty_note = " (dirty)" if previous.dirty else ""
        parts = [
                f"Δ vs previous run (was `{previous.commit}`"
                f"{prev_dirty_note}):",
                ]
        if resolved_note:
            parts.append("- error resolved")
        if diff is not None:
            parts.append(f"```diff\n{diff}\n```")
        diff_block = "\n".join(parts)

    entries[script_id] = Entry(
            script_id=script_id, order=order,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            commit=commit, dirty=dirty, label=label, output=output,
            diff=diff_block, failed=failed,
            )

    log_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = log_file.with_suffix(log_file.suffix + ".tmp")
    tmp_path.write_text(render_log(entries))
    os.replace(tmp_path, log_file)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def run_and_record(
        *, log_file: Path, script_id: str, order: int, root: Path,
        command: list[str], tagged_only: bool = False,
        ) -> int:
    """Run a command, capture its output, record it, and pass through output.

    Parameters
    ----------
    log_file : `Path`
        Path to the project's single Markdown run-log file.
    script_id : `str`
        Identifier for the script/step being run.
    order : `int`
        Sort key controlling this section's position in the file.
    root : `Path`
        Git working-tree root used to resolve the commit hash/dirty flag.
    command : `list[str]`
        The command and its arguments to execute.
    tagged_only : `bool`, optional, default: `False`
        If `True`, only record lines matching `TAG_PATTERN`. On a failed
        run, the untagged error tail is appended regardless -- see
        `build_recorded_output`.

    Returns
    -------
    returncode : `int`
        The wrapped command's exit code, unchanged, so callers (e.g. a
        ``set -eo pipefail`` bash script) still see failures.
    """
    proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            )
    captured: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        captured.append(line.rstrip("\n"))
    proc.wait()

    failed = proc.returncode != 0
    output = build_recorded_output(
            "\n".join(captured), tagged_only=tagged_only, failed=failed,
            )

    record(
            log_file=log_file, script_id=script_id, order=order,
            output=output, root=root, label=" ".join(command), failed=failed,
            tagged_only=tagged_only,
            )
    return proc.returncode


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
            help=f"Log file path (default: <root>/{DEFAULT_LOG_NAME}).",
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
    args = parser.parse_args()

    root = _resolve_root(args.root)
    log_file = args.log_file or (root / DEFAULT_LOG_NAME)

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
