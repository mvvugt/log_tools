"""
log_tools.runlog

Record per-script run output into one compact, project-wide Markdown log.

Each call upserts one section (keyed by ``--id``) in a single Markdown file,
ordered by ``--order``. The previous captured output for that id (if any) is
diffed against the new output and shown inline, and the git commit active at
run time is recorded, so a later change can be traced back to the exact
commit that produced a given run's output.

Recorded output is produced primarily by scripts calling into
``log_tools.emitter`` (Python) or sourcing ``log_tools/emitter.sh``
(Bash), which append to a temp file this module exposes to the child
process via ``Constants.RECORD_FILE_ENV_VAR`` -- see `run_and_record`.
An optional user-supplied ``include_pattern`` regex can additionally
pull matching raw lines into the recorded output.

A script whose output naturally splits into independent sections (e.g.
one execution that prepares several unrelated job types) can call
``log_stage(name)`` between them; `record` then diffs each stage
separately (see `split_stages`) instead of diffing the whole output as
one blob, so a stage that ran for the first time or is unchanged never
buries a diff in a stage that actually changed.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from log_tools.functions import atomic_write, get_git_info

_log = logging.getLogger(__name__)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Constants:
    """Constants specific to the runlog Markdown-log format."""

    DEFAULT_LOG_NAME: str = "RUN_LOG.md"
    MAX_DIFF_LINES: int = 40
    SECTION_HEADER_PREFIX: str = "## "
    TAG_PATTERN: str = r"^\[[A-Za-z]+\]"  # emitter's documented format
    ERROR_TAIL_DIVIDER: str = "--- error output (raw) ---"
    RECORD_FILE_ENV_VAR: str = "RUNLOG_RECORD_FILE"
    STAGE_MARKER_PATTERN: str = (
            r"^\[stage\] \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (.+)$"
            )
    """Matches a `log_stage` marker line; group 1 is the stage name."""
    EMITTER_TIMESTAMP_PATTERN: str = (
            r"^(\[[A-Za-z]+\]\s+)\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} "
            )
    """Matches an emitter line's tag + timestamp prefix; group 1 is the
    padded tag. Used by `diff_text` to ignore timestamps when comparing."""
    DEFAULT_STAGE_KEY: str = ""
    """`split_stages` key for content before the first marker, or the
    whole output when there are no markers at all."""


_EMITTER_TIMESTAMP_RE = re.compile(Constants.EMITTER_TIMESTAMP_PATTERN)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@dataclass
class Entry:
    """One script's latest recorded run."""

    script_id: str
    """Identifier passed via ``--id``, also the section key."""

    order: int
    """Sort key controlling section order in the rendered file."""

    timestamp: str
    """Local timestamp of the run, ``YYYY-MM-DD HH:MM:SS``."""

    first_run: str
    """Local timestamp of this script id's first-ever recorded run,
    ``YYYY-MM-DD HH:MM:SS``. Set once and never changed on reruns; see
    `record`. Falls back to `timestamp` when parsed from a log written
    before this field existed (see `parse_log`)."""

    commit: str
    """Short git commit hash active at run time (``"unknown"`` if not
    a git repo or git is unavailable)."""

    dirty: bool
    """Whether the working tree had uncommitted changes at run time."""

    label: str
    """Free-text label describing what was run (e.g. the command
    line), shown next to the section title."""

    output: str
    """The captured output text for this run."""

    diff: str | None = None
    """Per-stage diff(s) vs the previous run's output (see
    `split_stages`/`_stage_diff_blocks`), shown as a sibling block above
    `output` when not `None`. Computed fresh at record time -- never
    re-derived from a parsed file, so it is never nested inside the
    ``Output:`` code fence."""

    failed: bool = False
    """Whether this run's underlying command failed. Only ever set
    `True` via `run`'s exit-code check; `record` never sets it."""


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
        if not line.startswith(Constants.SECTION_HEADER_PREFIX):
            i += 1
            continue

        header = line[len(Constants.SECTION_HEADER_PREFIX):]
        order_str, _, rest = header.partition("] ")
        order = int(order_str.strip("["))
        script_id, _, label = rest.partition(" (")
        label = label[:-1] if label.endswith(")") else label
        label = label.strip("`")
        i += 1

        timestamp = ""
        first_run = ""
        commit = "unknown"
        dirty = False
        failed = False
        while i < len(lines) and lines[i].startswith("- "):
            meta = lines[i][2:]
            if meta.startswith("first run: "):
                first_run = meta[len("first run: "):]
            elif meta.startswith("last run: "):
                timestamp = meta[len("last run: "):]
            elif meta.startswith("commit: "):
                commit = meta[len("commit: `"):].split("`")[0]
                dirty = "(dirty)" in meta
            elif meta.startswith("status: "):
                failed = meta[len("status: "):].strip() == "failed"
            i += 1

        # logs written before this field existed have no `- first run:`
        # line -- fall back to this section's last-run timestamp.
        if not first_run:
            first_run = timestamp

        # skip any diff block, then read the current "Output:" fenced block
        output_lines: list[str] = []
        in_output_block = False
        in_fence = False
        while (
                i < len(lines)
                and not lines[i].startswith(Constants.SECTION_HEADER_PREFIX)
                ):
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
                first_run=first_run, commit=commit, dirty=dirty,
                label=label, output="\n".join(output_lines), failed=failed,
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
        `Constants.MAX_DIFF_LINES` with a trailing note if longer. `None`
        if `old` and `new` are identical once emitter timestamps are
        ignored.

    Notes
    -----
    Lines are compared with their emitter timestamp removed (see
    `_strip_emitter_timestamp`), so a line that only differs in when it
    was logged is not a change. The diff itself shows the original
    lines, timestamps included; unchanged context lines are taken from
    `new`.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    old_norm = [_strip_emitter_timestamp(line) for line in old_lines]
    new_norm = [_strip_emitter_timestamp(line) for line in new_lines]
    if old_norm == new_norm:
        return None

    matcher = difflib.SequenceMatcher(None, old_norm, new_norm)
    diff_lines: list[str] = []
    for group in matcher.get_grouped_opcodes(3):
        first, last = group[0], group[-1]
        old_range = _unified_range(first[1], last[2])
        new_range = _unified_range(first[3], last[4])
        diff_lines.append(f"@@ -{old_range} +{new_range} @@")
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                diff_lines.extend(f" {line}" for line in new_lines[j1:j2])
                continue
            diff_lines.extend(f"-{line}" for line in old_lines[i1:i2])
            diff_lines.extend(f"+{line}" for line in new_lines[j1:j2])

    if len(diff_lines) > Constants.MAX_DIFF_LINES:
        omitted = len(diff_lines) - Constants.MAX_DIFF_LINES
        diff_lines = diff_lines[:Constants.MAX_DIFF_LINES]
        diff_lines.append(f"... {omitted} more line(s) omitted")
    return "\n".join(diff_lines)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _strip_emitter_timestamp(line: str) -> str:
    """Remove an emitter line's timestamp, keeping its tag.

    Parameters
    ----------
    line : `str`
        One output line, e.g. ``[info]  2026-01-01 00:00:00 msg``.

    Returns
    -------
    line : `str`
        The line without its timestamp (``[info]  msg``), or unchanged if
        it does not match `Constants.EMITTER_TIMESTAMP_PATTERN`.
    """
    return _EMITTER_TIMESTAMP_RE.sub(r"\1", line, count=1)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _unified_range(start: int, stop: int) -> str:
    """Format a line range for a unified-diff ``@@`` hunk header.

    Parameters
    ----------
    start : `int`
        Zero-based start index of the range.
    stop : `int`
        Zero-based exclusive end index of the range.

    Returns
    -------
    range : `str`
        ``"start,length"`` (one-based), ``"start"`` for a single line, or
        ``"start,0"`` for an empty range -- matching `difflib`'s own
        formatting.
    """
    length = stop - start
    beginning = start + 1
    if length == 1:
        return f"{beginning}"
    if length == 0:
        beginning -= 1  # empty ranges begin at the line just before
    return f"{beginning},{length}"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def split_stages(output: str) -> dict[str, str]:
    """Split `output` into named stages via `log_stage`'s marker lines.

    Parameters
    ----------
    output : `str`
        Recorded output text, optionally containing
        ``[stage] <timestamp> <name>`` marker lines emitted by
        `log_tools.emitter.log_stage` / ``log_tools/emitter.sh``'s
        ``log_stage``.

    Returns
    -------
    stages : `dict[str, str]`
        Mapping of stage name to its content (the lines emitted after
        that marker, up to the next one), in first-seen order. Content
        before the first marker -- or the entire output, when there are
        no markers -- is keyed by `Constants.DEFAULT_STAGE_KEY`. A
        repeated marker for the same name concatenates onto that name's
        existing content rather than overwriting it. Stages with no
        content are omitted.
    """
    pattern = re.compile(Constants.STAGE_MARKER_PATTERN)
    stages: dict[str, list[str]] = {}
    current = Constants.DEFAULT_STAGE_KEY
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            current = match.group(1)
            continue
        stages.setdefault(current, []).append(line)
    return {name: "\n".join(lines) for name, lines in stages.items() if lines}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _stage_diff_blocks(
        old_stages: dict[str, str], new_stages: dict[str, str],
        ) -> list[str]:
    """Build per-stage diff blocks/notes for a stage-aware `record()` diff.

    Parameters
    ----------
    old_stages : `dict[str, str]`
        Previous run's output, split via `split_stages`.
    new_stages : `dict[str, str]`
        New run's output, split via `split_stages`.

    Returns
    -------
    blocks : `list[str]`
        One entry per stage that has something to report, in
        `new_stages`' order followed by dropped stages in `old_stages`'
        order. A stage in `new_stages` absent from `old_stages` (it ran
        for the first time) is skipped entirely -- diffing against
        nothing is not a meaningful diff. A stage in `old_stages` absent
        from `new_stages` gets a one-line "not present this run" note
        instead of a diff. `Constants.DEFAULT_STAGE_KEY` (no explicit
        `log_stage` calls used) renders its diff unlabeled, identical to
        `record()`'s pre-stage-splitting output.
    """
    blocks: list[str] = []
    for name, new_content in new_stages.items():
        if name not in old_stages:
            continue
        diff = diff_text(old_stages[name], new_content)
        if diff is None:
            continue
        if name == Constants.DEFAULT_STAGE_KEY:
            blocks.append(f"```diff\n{diff}\n```")
        else:
            blocks.append(f"stage `{name}`:\n```diff\n{diff}\n```")

    for name in old_stages:
        if name not in new_stages:
            blocks.append(f"- stage `{name}`: not present this run")

    return blocks


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def filter_matching_lines(output: str, pattern: str) -> list[str]:
    """Return the lines of `output` matching `pattern`.

    Parameters
    ----------
    output : `str`
        Text to filter, split on newlines.
    pattern : `str`
        Regex tested against the start of each line (`re.match`,
        case-insensitive).

    Returns
    -------
    lines : `list[str]`
        Matching lines, in their original order.
    """
    compiled = re.compile(pattern, re.IGNORECASE)
    return [line for line in output.splitlines() if compiled.match(line)]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def build_recorded_output(
        raw_output: str, *, record_file_content: str = "",
        include_pattern: str | None = None, raw_on_failure: bool = False,
        failed: bool = False,
        ) -> str:
    """Select what to record from a run's raw captured output.

    Parameters
    ----------
    raw_output : `str`
        The full raw captured output of the run.
    record_file_content : `str`, optional
        Content appended by the emitter (`log_tools.emitter` /
        ``log_tools/emitter.sh``) via `Constants.RECORD_FILE_ENV_VAR`.
        Used as-is (already chronological) when non-empty and
        `include_pattern` is not given.
    include_pattern : `str` or `None`, optional
        A user-supplied regex (see `filter_matching_lines`). When given,
        the result is a single chronological pass over `raw_output`,
        keeping a line if it was written to the record file or matches
        `include_pattern` -- so recorded output always preserves the
        original print order, whichever mechanism selected each line.
    raw_on_failure : `bool`, optional, default: `False`
        If `True` and `failed` is `True`, append the full `raw_output`
        under `Constants.ERROR_TAIL_DIVIDER` as a safety net against
        losing a crash that never went through the emitter (e.g. an
        unhandled traceback). This is a deliberate full duplicate
        appendix, not chronologically merged into the curated view.
    failed : `bool`, optional, default: `False`
        Whether the run failed.

    Returns
    -------
    text : `str`
        The output text to record.
    """
    recorded = (
            record_file_content.splitlines()
            if record_file_content.strip() else None
            )
    if recorded is None and include_pattern is None:
        base = raw_output
    elif include_pattern is None:
        base = record_file_content
    else:
        recorded_set = set(recorded or [])
        pattern = re.compile(include_pattern, re.IGNORECASE)
        kept = [
                line for line in raw_output.splitlines()
                if line in recorded_set or pattern.match(line)
                ]
        base = "\n".join(kept)

    if failed and raw_on_failure:
        tail = f"{Constants.ERROR_TAIL_DIVIDER}\n{raw_output}"
        base = f"{base}\n{tail}" if base else tail
    return base


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
                f"{Constants.SECTION_HEADER_PREFIX}{title}",
                f"- first run: {entry.first_run}",
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

    Notes
    -----
    Writes are atomic (see `log_tools.functions.atomic_write`), so a crash
    mid-write cannot corrupt the log. If the previous run for this id had
    failed and this one succeeds, and the previous run's output contains
    `Constants.ERROR_TAIL_DIVIDER`, that tail is stripped before diffing
    and a "- error resolved" note is shown instead of a raw diff of its
    removal.

    The diff is computed per stage (see `split_stages`), not over the
    whole output blob: a stage named via `log_stage` that ran for the
    first time is never diffed against nothing, and a stage unchanged
    across runs never buries a stage that genuinely changed inside one
    large diff. Output that never calls `log_stage` behaves exactly as
    before -- it is one implicit stage, diffed as a whole.

    `Entry.first_run` is set once, on the first `record()` call for a
    given `script_id`, and preserved unchanged on every subsequent call
    -- including after a failed run.
    """
    entries = parse_log(log_file)
    commit, dirty = get_git_info(root)
    previous = entries.get(script_id)

    diff_parts: list[str] = []
    resolved_note = False
    if not failed and previous is not None:
        old_for_diff = previous.output
        if previous.failed and Constants.ERROR_TAIL_DIVIDER in previous.output:
            resolved_note = True
            old_for_diff, _, _tail = previous.output.partition(
                    Constants.ERROR_TAIL_DIVIDER,
                    )
            old_for_diff = old_for_diff.rstrip("\n")

        diff_parts = _stage_diff_blocks(
                split_stages(old_for_diff), split_stages(output),
                )
        if diff_parts:
            _log.info(
                    "changes vs previous run of %r:\n%s", script_id,
                    "\n".join(diff_parts),
                    )
        elif resolved_note:
            _log.info("error resolved vs previous run of %r", script_id)
        else:
            _log.info("no change vs previous run of %r", script_id)

    diff_block = None
    if (diff_parts or resolved_note) and previous is not None:
        prev_dirty_note = " (dirty)" if previous.dirty else ""
        parts = [
                f"Δ vs previous run (was `{previous.commit}`"
                f"{prev_dirty_note}):",
                ]
        if resolved_note:
            parts.append("- error resolved")
        parts.extend(diff_parts)
        diff_block = "\n".join(parts)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first_run = previous.first_run if previous is not None else now

    entries[script_id] = Entry(
            script_id=script_id, order=order, timestamp=now,
            first_run=first_run, commit=commit, dirty=dirty, label=label,
            output=output, diff=diff_block, failed=failed,
            )

    atomic_write(log_file, render_log(entries))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def run_and_record(
        *, log_file: Path, script_id: str, order: int, root: Path,
        command: list[str], include_pattern: str | None = None,
        raw_on_failure: bool = False,
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
    include_pattern : `str` or `None`, optional
        User-supplied regex additionally selecting raw output lines to
        record -- see `build_recorded_output`.
    raw_on_failure : `bool`, optional, default: `False`
        Append the full raw captured output as a safety net on failure --
        see `build_recorded_output`.

    Returns
    -------
    returncode : `int`
        The wrapped command's exit code, unchanged, so callers (e.g. a
        ``set -eo pipefail`` bash script) still see failures.

    Notes
    -----
    The child process is given `Constants.RECORD_FILE_ENV_VAR` pointing
    at a fresh temp file. Scripts using `log_tools.emitter` (Python) or
    ``log_tools/emitter.sh`` (Bash) append their tagged output lines to
    it; that content becomes the recorded output (falling back to the
    full raw output if the script never touches the emitter). The temp
    file is always removed before returning.
    """
    record_fd, record_path_str = tempfile.mkstemp(prefix="runlog-record-")
    os.close(record_fd)
    record_path = Path(record_path_str)
    try:
        env = dict(
                os.environ,
                **{Constants.RECORD_FILE_ENV_VAR: str(record_path)},
                )
        proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
                )
        captured: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            captured.append(line.rstrip("\n"))
        proc.wait()

        failed = proc.returncode != 0
        record_file_content = record_path.read_text()
    finally:
        record_path.unlink(missing_ok=True)

    output = build_recorded_output(
            "\n".join(captured), record_file_content=record_file_content,
            include_pattern=include_pattern, raw_on_failure=raw_on_failure,
            failed=failed,
            )

    record(
            log_file=log_file, script_id=script_id, order=order,
            output=output, root=root, label=" ".join(command), failed=failed,
            )
    return proc.returncode
