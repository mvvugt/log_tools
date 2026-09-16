"""Unit tests for `log_tools.runlog`."""
from __future__ import annotations

from pathlib import Path

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
