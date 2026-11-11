"""Unit tests for `log_tools.runlog`."""
from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from log_tools.functions import LockTimeoutError
from log_tools.runlog import (
    Constants,
    Entry,
    build_recorded_output,
    diff_text,
    filter_matching_lines,
    parse_log,
    record,
    render_log,
    run_and_record,
    split_stages,
)

from .conftest import commit_hash


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# diff_text
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_diff_text_identical_returns_none() -> None:
    """No diff is produced when old and new output are identical."""
    assert diff_text("same\ntext", "same\ntext") is None


def test_diff_text_reports_changes() -> None:
    """Added/removed lines show up as unified-diff +/- lines."""
    diff = diff_text("a\nb\n", "a\nc\n")

    assert diff is not None
    assert "-b" in diff
    assert "+c" in diff


def test_diff_text_truncates_long_diffs() -> None:
    """Diffs longer than MAX_DIFF_LINES are truncated with an omitted note."""
    old = "\n".join(f"line{i}" for i in range(100))
    new = "\n".join(f"line{i}x" for i in range(100))

    diff = diff_text(old, new)

    assert diff is not None
    lines = diff.splitlines()
    assert len(lines) == Constants.MAX_DIFF_LINES + 1
    assert lines[-1].endswith("more line(s) omitted")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _emit(tag: str, timestamp: str, msg: str) -> str:
    """Build an emitter-format line (tag padded to 8 chars, as the real
    emitters print it), independent of `log_tools.emitter`."""
    return f"{f'[{tag}]':<8}{timestamp} {msg}"


def test_diff_text_ignores_emitter_timestamps() -> None:
    """Outputs differing only in emitter timestamps give no diff, for every
    tag width."""
    tags = ("info", "warn", "debug", "error", "stage")
    old = "\n".join(_emit(t, "2026-01-01 00:00:00", "msg") for t in tags)
    new = "\n".join(_emit(t, "2026-09-23 12:34:56", "msg") for t in tags)

    assert diff_text(old, new) is None


def test_diff_text_real_change_keeps_original_timestamps() -> None:
    """A genuinely changed message shows as -/+ lines with their original
    timestamps; timestamp-only changes are not shown as -/+ lines."""
    old = "\n".join([
            _emit("info", "2026-01-01 00:00:00", "same"),
            _emit("info", "2026-01-01 00:00:01", "built 3 targets"),
            ])
    new = "\n".join([
            _emit("info", "2026-09-23 10:00:00", "same"),
            _emit("info", "2026-09-23 10:00:01", "built 4 targets"),
            ])

    diff = diff_text(old, new)

    assert diff is not None
    lines = diff.splitlines()
    assert f"-{_emit('info', '2026-01-01 00:00:01', 'built 3 targets')}" in (
            lines)
    assert f"+{_emit('info', '2026-09-23 10:00:01', 'built 4 targets')}" in (
            lines)
    changed = [ln for ln in lines if ln.startswith(("-", "+"))]
    assert not any("same" in ln for ln in changed)


def test_diff_text_non_emitter_timestamps_compared_verbatim() -> None:
    """Only the emitter prefix is normalised: an untagged line starting
    with a timestamp is still compared as-is."""
    diff = diff_text(
            "2026-01-01 00:00:00 foo", "2026-09-23 12:34:56 foo",
            )

    assert diff is not None
    assert "-2026-01-01 00:00:00 foo" in diff
    assert "+2026-09-23 12:34:56 foo" in diff


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# split_stages
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _stage_marker(name: str) -> str:
    """Build a `[stage]` marker line for `name`, matching the emitter's
    real format (a fixed-width timestamp, irrelevant to `split_stages`).
    """
    return f"[stage] 2026-01-01 00:00:00 {name}"


def test_split_stages_no_markers_is_single_default_stage() -> None:
    """Output with no `[stage]` markers is one `DEFAULT_STAGE_KEY` entry."""
    output = "line1\nline2"

    assert split_stages(output) == {Constants.DEFAULT_STAGE_KEY: output}


def test_split_stages_splits_on_markers() -> None:
    """Each marker starts a new named stage; content before the first
    marker is kept under `DEFAULT_STAGE_KEY`."""
    output = "\n".join([
            "preamble",
            _stage_marker("prepare"),
            "prep line 1",
            "prep line 2",
            _stage_marker("submit"),
            "submit line",
            ])

    stages = split_stages(output)

    assert stages == {
            Constants.DEFAULT_STAGE_KEY: "preamble",
            "prepare": "prep line 1\nprep line 2",
            "submit": "submit line",
            }


def test_split_stages_repeated_marker_concatenates() -> None:
    """A stage name reused later in the output appends, not overwrites."""
    output = "\n".join([
            _stage_marker("loop"),
            "first",
            _stage_marker("loop"),
            "second",
            ])

    assert split_stages(output) == {"loop": "first\nsecond"}


def test_split_stages_empty_stage_is_omitted() -> None:
    """A marker immediately followed by another (no content) is dropped."""
    output = "\n".join([_stage_marker("empty"), _stage_marker("full"), "x"])

    assert split_stages(output) == {"full": "x"}


def test_split_stages_empty_output() -> None:
    """Empty output splits into no stages at all."""
    assert split_stages("") == {}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# filter_matching_lines
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_filter_matching_lines_keeps_only_matching() -> None:
    """Only lines matching `pattern` survive filtering."""
    output = "\n".join([
            "[info] starting",
            "raw untagged noise",
            "[warn] careful",
            "traceback line",
            ])

    filtered = filter_matching_lines(output, Constants.TAG_PATTERN)

    assert filtered == ["[info] starting", "[warn] careful"]


def test_filter_matching_lines_empty_input() -> None:
    """Filtering empty output returns an empty list."""
    assert filter_matching_lines("", Constants.TAG_PATTERN) == []


def test_filter_matching_lines_custom_pattern() -> None:
    """An arbitrary user-supplied regex is honored, not just TAG_PATTERN."""
    output = "\n".join(["ERROR: boom", "fine", "WARNING: careful"])

    filtered = filter_matching_lines(output, r"^(ERROR|WARNING):")

    assert filtered == ["ERROR: boom", "WARNING: careful"]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# build_recorded_output
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_build_recorded_output_no_record_no_pattern_uses_raw() -> None:
    """With no record-file content and no include_pattern, raw is kept."""
    raw = "[info] a\nraw noise"

    assert build_recorded_output(raw) == raw
    assert build_recorded_output(raw, failed=True) == raw


def test_build_recorded_output_record_file_wins_when_nonempty() -> None:
    """Non-empty record-file content is used as-is when it's the only input."""
    raw = "[info] a\nnoise\n[info] b"

    result = build_recorded_output(
            raw, record_file_content="[info] a\n[info] b",
            )

    assert result == "[info] a\n[info] b"


def test_build_recorded_output_include_pattern_merges_chronologically() -> None:
    """include_pattern adds matching raw lines, preserving original order."""
    raw = "[info] a\nERROR here\n[info] b"

    result = build_recorded_output(
            raw, record_file_content="[info] a\n[info] b",
            include_pattern=r"^ERROR",
            )

    assert result == "[info] a\nERROR here\n[info] b"


def test_build_recorded_output_include_pattern_no_record_file() -> None:
    """include_pattern alone (no record-file content) filters raw by pattern."""
    raw = "keep this\nnot this\nERROR: keep too"

    result = build_recorded_output(raw, include_pattern=r"^(keep|ERROR)")

    assert result == "keep this\nERROR: keep too"


def test_build_recorded_output_raw_on_failure_appends_full_raw() -> None:
    """raw_on_failure appends the full raw output under the divider."""
    raw = "[info] a\nTraceback (most recent call last):\nBoom: bad"

    result = build_recorded_output(
            raw, record_file_content="[info] a",
            raw_on_failure=True, failed=True,
            )

    assert result == f"[info] a\n{Constants.ERROR_TAIL_DIVIDER}\n{raw}"


def test_build_recorded_output_raw_on_failure_ignored_on_success() -> None:
    """raw_on_failure has no effect unless the run actually failed."""
    raw = "[info] a\nnoise"

    result = build_recorded_output(
            raw, record_file_content="[info] a",
            raw_on_failure=True, failed=False,
            )

    assert result == "[info] a"


def test_build_recorded_output_raw_on_failure_duplicates_raw_fallback() -> None:
    """With no record-file content, base already == raw (auto fallback), so
    raw_on_failure deliberately duplicates it under the divider -- a
    simplicity/never-lose-data tradeoff, not deduplicated."""
    raw = "Traceback (most recent call last):\nBoom: bad"

    result = build_recorded_output(raw, raw_on_failure=True, failed=True)

    assert result == f"{raw}\n{Constants.ERROR_TAIL_DIVIDER}\n{raw}"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# render_log / parse_log
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_render_log_empty_entries() -> None:
    """Rendering an empty entry dict produces an empty string."""
    assert render_log({}) == ""


def test_render_log_orders_by_order_then_id() -> None:
    """Sections are ordered by (order, script_id), not insertion order."""
    entries = {
            "b_script": Entry(
                    script_id="b_script", order=1, timestamp="t",
                    first_run="t", commit="abc", dirty=False, label="",
                    output="out-b",
                    ),
            "a_script": Entry(
                    script_id="a_script", order=1, timestamp="t",
                    first_run="t", commit="abc", dirty=False, label="",
                    output="out-a",
                    ),
            "zeroth": Entry(
                    script_id="zeroth", order=0, timestamp="t",
                    first_run="t", commit="abc", dirty=False, label="",
                    output="out-z",
                    ),
            }

    rendered = render_log(entries)

    assert rendered.index("zeroth") < rendered.index("a_script")
    assert rendered.index("a_script") < rendered.index("b_script")


def test_render_log_includes_label_and_dirty_note() -> None:
    """The label appears in backticks and dirty state is noted."""
    entries = {
            "s": Entry(
                    script_id="s", order=0, timestamp="2026-01-01 00:00:00",
                    first_run="2025-12-31 00:00:00", commit="abc123",
                    dirty=True, label="./run.sh", output="ok",
                    ),
            }

    rendered = render_log(entries)

    assert "[0] s (`./run.sh`)" in rendered
    assert "commit: `abc123` (dirty)" in rendered
    assert "- first run: 2025-12-31 00:00:00" in rendered
    assert rendered.index("- first run:") < rendered.index("- last run:")


def test_render_log_failed_status_line() -> None:
    """A failed entry gets `- status: failed`; a successful one doesn't."""
    ok_entry = Entry(
            script_id="ok", order=0, timestamp="t", first_run="t",
            commit="abc", dirty=False, label="", output="out", failed=False,
            )
    failed_entry = Entry(
            script_id="bad", order=1, timestamp="t", first_run="t",
            commit="abc", dirty=False, label="", output="out", failed=True,
            )

    rendered = render_log({"ok": ok_entry, "bad": failed_entry})

    assert "- status: failed" in rendered
    ok_section = rendered.split("## [1]")[0]
    assert "- status: failed" not in ok_section


def test_parse_log_missing_file_returns_empty(tmp_path: Path) -> None:
    """Parsing a non-existent log file returns an empty dict."""
    assert parse_log(tmp_path / "does_not_exist.md") == {}


def test_parse_log_round_trips_core_fields(tmp_path: Path) -> None:
    """A rendered log parses back with matching id/order/commit/output/failed.

    Per `Entry.diff`'s docstring, the diff block is deliberately not
    persisted/re-parsed -- so it is excluded from this round-trip check.
    """
    entries = {
            "s1": Entry(
                    script_id="s1", order=2, timestamp="2026-01-01 00:00:00",
                    first_run="2025-12-01 00:00:00", commit="deadbee",
                    dirty=True, label="my label",
                    output="line1\nline2", failed=False,
                    ),
            "s2": Entry(
                    script_id="s2", order=1, timestamp="2026-01-02 00:00:00",
                    first_run="2025-12-15 00:00:00", commit="cafef00",
                    dirty=False, label="",
                    output="only line", failed=True,
                    ),
            }
    log_file = tmp_path / "RUN_LOG.md"
    log_file.write_text(render_log(entries))

    parsed = parse_log(log_file)

    assert set(parsed) == {"s1", "s2"}
    for script_id, original in entries.items():
        got = parsed[script_id]
        assert got.order == original.order
        assert got.timestamp == original.timestamp
        assert got.first_run == original.first_run
        assert got.commit == original.commit
        assert got.dirty == original.dirty
        assert got.label == original.label
        assert got.output == original.output
        assert got.failed == original.failed


def test_parse_log_missing_first_run_line_falls_back_to_last_run(
        tmp_path: Path,
        ) -> None:
    """A log written before this field existed has no `- first run:` line;
    parsing it falls back to that entry's `- last run:` value instead of
    crashing or leaving `first_run` empty."""
    log_file = tmp_path / "RUN_LOG.md"
    log_file.write_text(
            "## [0] s1\n"
            "- last run: 2026-01-01 00:00:00\n"
            "- commit: `abc123`\n"
            "\n"
            "Output:\n"
            "```text\n"
            "hello\n"
            "```\n",
            )

    parsed = parse_log(log_file)

    assert parsed["s1"].first_run == "2026-01-01 00:00:00"
    assert parsed["s1"].timestamp == "2026-01-01 00:00:00"
    assert parsed["s1"].output == "hello"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# record
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_creates_new_entry(git_repo: Path) -> None:
    """A first `record()` call for an id creates its section, no diff."""
    log_file = git_repo / "RUN_LOG.md"

    record(
            log_file=log_file, script_id="s1", order=0, output="hello",
            root=git_repo, label="./run.sh",
            )

    text = log_file.read_text()
    assert "s1" in text
    assert "hello" in text
    assert commit_hash(git_repo) in text
    assert "Δ vs previous run" not in text


def test_record_first_run_set_on_first_record(git_repo: Path) -> None:
    """On a script id's very first record, `first run` == `last run`."""
    log_file = git_repo / "RUN_LOG.md"

    record(
            log_file=log_file, script_id="s1", order=0, output="hello",
            root=git_repo,
            )

    parsed = parse_log(log_file)
    assert parsed["s1"].first_run == parsed["s1"].timestamp


def test_record_first_run_persists_across_reruns(git_repo: Path) -> None:
    """`first run` stays fixed across reruns, even as output changes."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="old text",
            root=git_repo,
            )
    first_run = parse_log(log_file)["s1"].first_run

    record(
            log_file=log_file, script_id="s1", order=0, output="new text",
            root=git_repo,
            )

    assert parse_log(log_file)["s1"].first_run == first_run


def test_record_first_run_persists_after_failed_run(git_repo: Path) -> None:
    """`first run` survives a failed rerun, and a rerun after that."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="ok",
            root=git_repo,
            )
    first_run = parse_log(log_file)["s1"].first_run

    record(
            log_file=log_file, script_id="s1", order=0, output="boom",
            root=git_repo, failed=True,
            )
    assert parse_log(log_file)["s1"].first_run == first_run
    assert parse_log(log_file)["s1"].failed is True

    record(
            log_file=log_file, script_id="s1", order=0, output="ok again",
            root=git_repo,
            )
    assert parse_log(log_file)["s1"].first_run == first_run


def test_record_upserts_same_id_no_change(git_repo: Path) -> None:
    """Recording identical output twice keeps one section, no diff block."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="same",
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="same",
            root=git_repo,
            )

    text = log_file.read_text()
    assert text.count("## [0] s1") == 1
    assert "Δ vs previous run" not in text


def test_record_shows_diff_on_changed_output(git_repo: Path) -> None:
    """A changed output produces a `Δ vs previous run` diff block."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="old text",
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="new text",
            root=git_repo,
            )

    text = log_file.read_text()
    assert "Δ vs previous run" in text
    assert "-old text" in text
    assert "+new text" in text
    assert "Output:" in text and "new text" in text


def test_record_failed_run_skips_diff(git_repo: Path) -> None:
    """failed=True never shows a diff, even with a differing previous run."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="old text",
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="boom",
            root=git_repo, failed=True,
            )

    text = log_file.read_text()
    assert "Δ vs previous run" not in text
    assert "- status: failed" in text
    assert "boom" in text


def test_record_resolved_error_notes_and_strips_tail(git_repo: Path) -> None:
    """After a failure whose output contains the error-tail divider, a
    success notes resolution and diffs against the previous output with
    its tail stripped -- keyed purely off the divider's presence, no mode
    flag needed."""
    log_file = git_repo / "RUN_LOG.md"
    failed_output = (
            "[info] a\n"
            f"{Constants.ERROR_TAIL_DIVIDER}\n"
            "Traceback (most recent call last):\nBoom"
            )
    record(
            log_file=log_file, script_id="s1", order=0, output=failed_output,
            root=git_repo, failed=True,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="[info] a",
            root=git_repo, failed=False,
            )

    text = log_file.read_text()
    assert "- error resolved" in text
    # old_for_diff ("[info] a") == new output, so no +/- diff lines needed.
    assert "```diff" not in text
    assert "- status: failed" not in text.split("Output:")[-1]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# record -- stage-aware diffing
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_new_stage_is_not_diffed(git_repo: Path) -> None:
    """A stage that only appears in this run isn't mentioned in the diff,
    even though its content is new -- diffing against nothing isn't
    meaningful."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0,
            output=f"{_stage_marker('prepare')}\nprep v1", root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0,
            output=(
                    f"{_stage_marker('prepare')}\nprep v1\n"
                    f"{_stage_marker('submit')}\nsubmit v1"
                    ),
            root=git_repo,
            )

    text = log_file.read_text()
    assert "Δ vs previous run" not in text
    assert "submit v1" in text


def test_record_unchanged_stage_is_not_diffed(git_repo: Path) -> None:
    """A stage whose content is identical across runs produces no diff for
    that stage, even while a sibling stage changed."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0,
            output=(
                    f"{_stage_marker('prepare')}\nprep v1\n"
                    f"{_stage_marker('submit')}\nsubmit v1"
                    ),
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0,
            output=(
                    f"{_stage_marker('prepare')}\nprep v1\n"
                    f"{_stage_marker('submit')}\nsubmit v2"
                    ),
            root=git_repo,
            )

    text = log_file.read_text()
    diff_section = text.split("Output:")[0]
    assert "stage `submit`" in diff_section
    assert "-submit v1" in diff_section
    assert "+submit v2" in diff_section
    assert "stage `prepare`" not in diff_section


def test_record_dropped_stage_gets_note(git_repo: Path) -> None:
    """A stage present previously but absent this run gets a one-line
    'not present this run' note instead of a diff."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0,
            output=(
                    f"{_stage_marker('prepare')}\nprep v1\n"
                    f"{_stage_marker('submit')}\nsubmit v1"
                    ),
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0,
            output=f"{_stage_marker('prepare')}\nprep v1",
            root=git_repo,
            )

    text = log_file.read_text()
    diff_section = text.split("Output:")[0]
    assert "stage `submit`: not present this run" in diff_section


def test_record_no_stage_markers_diffs_whole_output_unlabeled(
        git_repo: Path,
        ) -> None:
    """A script never using `log_stage` keeps today's exact rendering: a
    single unlabeled diff block over the whole output."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="old text",
            root=git_repo,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="new text",
            root=git_repo,
            )

    text = log_file.read_text()
    diff_section = text.split("Output:")[0]
    assert "```diff" in diff_section
    assert "stage `" not in diff_section
    assert "-old text" in diff_section
    assert "+new text" in diff_section


def test_record_timestamp_only_stage_is_not_diffed(git_repo: Path) -> None:
    """A stage whose lines differ only in emitter timestamps gets no diff
    block, while a sibling stage with a real change does."""
    log_file = git_repo / "RUN_LOG.md"

    def _output(ts: str, b_msg: str) -> str:
        """Two-stage output with all lines stamped `ts`."""
        return "\n".join([
                _emit("stage", ts, "a"), _emit("info", ts, "a unchanged"),
                _emit("stage", ts, "b"), _emit("info", ts, b_msg),
                ])

    record(
            log_file=log_file, script_id="s1", order=0,
            output=_output("2026-01-01 00:00:00", "b v1"), root=git_repo,
            )
    record(
            log_file=log_file, script_id="s1", order=0,
            output=_output("2026-09-23 12:34:56", "b v2"), root=git_repo,
            )

    diff_section = log_file.read_text().split("Output:")[0]
    assert "stage `b`" in diff_section
    assert "stage `a`" not in diff_section


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# run_and_record
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_and_record_success_returns_zero_and_captures_output(
        git_repo: Path,
        ) -> None:
    """Stdout is captured and the exit code is passed through unchanged."""
    log_file = git_repo / "RUN_LOG.md"

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", "print('hi there')"],
            )

    assert returncode == 0
    text = log_file.read_text()
    assert "hi there" in text
    assert "- status: failed" not in text


def test_run_and_record_failure_marks_failed_and_propagates_exit_code(
        git_repo: Path,
        ) -> None:
    """A non-zero exit code is recorded as failed and returned unchanged."""
    log_file = git_repo / "RUN_LOG.md"

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", "print('oops'); import sys; sys.exit(3)"],
            )

    assert returncode == 3
    text = log_file.read_text()
    assert "- status: failed" in text
    assert "oops" in text


def test_run_and_record_raw_on_failure_keeps_full_raw_tail(
        git_repo: Path,
        ) -> None:
    """--raw-on-failure keeps everything printed, even without the emitter."""
    log_file = git_repo / "RUN_LOG.md"
    script = (
            "print('[info] starting'); "
            "print('unrelated noise'); "
            "import sys; sys.exit(1)"
            )

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", script], raw_on_failure=True,
            )

    assert returncode == 1
    text = log_file.read_text()
    assert "[info] starting" in text
    assert Constants.ERROR_TAIL_DIVIDER in text
    assert "unrelated noise" in text


def test_run_and_record_uses_record_file_over_raw_output(
        git_repo: Path,
        ) -> None:
    """A script appending to $RUNLOG_RECORD_FILE has that content recorded,
    not the full raw stdout."""
    log_file = git_repo / "RUN_LOG.md"
    script = (
            "import os; "
            "print('not recorded'); "
            "f = open(os.environ['RUNLOG_RECORD_FILE'], 'a'); "
            "f.write('[info] kept\\n')"
            )

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", script],
            )

    assert returncode == 0
    output_block = log_file.read_text().split("Output:")[-1]
    assert "[info] kept" in output_block
    assert "not recorded" not in output_block


def test_run_and_record_empty_record_file_falls_back_to_raw(
        git_repo: Path,
        ) -> None:
    """A script that never touches the record file gets full raw output."""
    log_file = git_repo / "RUN_LOG.md"

    run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", "print('plain output')"],
            )

    text = log_file.read_text()
    assert "plain output" in text


def test_run_and_record_cleans_up_temp_record_file(git_repo: Path) -> None:
    """The temp record file is removed after the run, success or failure."""
    log_file = git_repo / "RUN_LOG.md"
    script = (
            "import os; "
            "print(os.environ['RUNLOG_RECORD_FILE'])"
            )

    run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", script],
            )

    text = log_file.read_text()
    printed_path = [
            line for line in text.splitlines() if line.startswith("/")
            ]
    assert printed_path, "expected the record file path to be printed"
    assert not Path(printed_path[0]).exists()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# record() locking (concurrent writers sharing one RUN_LOG.md)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
_N_WRITERS = 8
_RECORDS_PER_WRITER = 5


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _concurrent_writer(
        log_file: str, root: str, index: int,
        barrier: multiprocessing.synchronize.Barrier,
        ) -> None:
    """Wait for all writers, then `record()` one id several times."""
    barrier.wait()
    for run in range(_RECORDS_PER_WRITER):
        record(
                log_file=Path(log_file), script_id=f"task{index}",
                order=index, output=f"task {index} run {run}",
                root=Path(root),
                )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_concurrent_processes_keep_every_entry(git_repo: Path) -> None:
    """N processes recording into one RUN_LOG.md at once (SLURM/SGE array
    tasks on one node) raise nothing and lose no entry; no temp or lock
    files are left behind."""
    log_file = git_repo / "RUN_LOG.md"
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(_N_WRITERS)
    procs = [
            ctx.Process(
                    target=_concurrent_writer,
                    args=(str(log_file), str(git_repo), i, barrier),
                    )
            for i in range(_N_WRITERS)
            ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=120)

    assert [proc.exitcode for proc in procs] == [0] * _N_WRITERS
    entries = parse_log(log_file)
    assert sorted(entries) == sorted(f"task{i}" for i in range(_N_WRITERS))
    for i in range(_N_WRITERS):
        last = _RECORDS_PER_WRITER - 1
        assert entries[f"task{i}"].output == f"task {i} run {last}"
    assert list(git_repo.glob(".RUN_LOG.md.*.tmp")) == []
    assert not (git_repo / "RUN_LOG.md.lock").exists()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_lock_timeout_raises_and_leaves_log_unchanged(
        git_repo: Path, monkeypatch: pytest.MonkeyPatch,
        ) -> None:
    """With the lock held by another (live) writer, `record()` gives up
    after the timeout with `LockTimeoutError` and does not write."""
    log_file = git_repo / "RUN_LOG.md"
    record(
            log_file=log_file, script_id="s1", order=0, output="first",
            root=git_repo,
            )
    before = log_file.read_text()
    (git_repo / "RUN_LOG.md.lock").mkdir()
    monkeypatch.setattr(Constants, "RECORD_LOCK_TIMEOUT_SECONDS", 0.2)

    with pytest.raises(LockTimeoutError):
        record(
                log_file=log_file, script_id="s2", order=1, output="second",
                root=git_repo,
                )

    assert log_file.read_text() == before


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_and_record_keeps_child_exit_code_when_record_fails(
        git_repo: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        ) -> None:
    """A failing record (here: lock timeout) only warns; the wrapped
    command's own exit code is still returned.

    Notes
    -----
    Checks stderr *and* `caplog`: once `log_tools.emitter` has configured
    the ``log_tools`` logger (``propagate=False``, e.g. by an earlier
    test), the warning goes to stderr via the emitter's handler instead
    of reaching pytest's root-logger capture.
    """
    log_file = git_repo / "RUN_LOG.md"
    (git_repo / "RUN_LOG.md.lock").mkdir()
    monkeypatch.setattr(Constants, "RECORD_LOCK_TIMEOUT_SECONDS", 0.2)

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", "import sys; sys.exit(4)"],
            )

    assert returncode == 4
    assert not log_file.exists()
    seen = capsys.readouterr().err + caplog.text
    assert "'s1' finished with exit code 4" in seen
    assert "NOT recorded" in seen
    assert "own results are unaffected" in seen
