"""Unit tests for `log_tools.runlog`."""
from __future__ import annotations

from pathlib import Path

from log_tools.runlog import (
    Constants,
    Entry,
    build_recorded_output,
    diff_text,
    filter_tagged_lines,
    parse_log,
    record,
    render_log,
    run_and_record,
)

from .conftest import commit_hash, make_dirty


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
# filter_tagged_lines
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_filter_tagged_lines_keeps_only_tagged() -> None:
    """Only lines starting with a `[tag]` prefix survive filtering."""
    output = "\n".join([
            "[info] starting",
            "raw untagged noise",
            "[warn] careful",
            "traceback line",
            ])

    filtered = filter_tagged_lines(output)

    assert filtered.splitlines() == ["[info] starting", "[warn] careful"]


def test_filter_tagged_lines_empty_input() -> None:
    """Filtering empty output returns an empty string."""
    assert filter_tagged_lines("") == ""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# build_recorded_output
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_build_recorded_output_passthrough_when_not_tagged_only() -> None:
    """With tagged_only=False, the raw output is returned unchanged."""
    raw = "[info] a\nraw noise"

    assert build_recorded_output(raw, tagged_only=False, failed=False) == raw
    assert build_recorded_output(raw, tagged_only=False, failed=True) == raw


def test_build_recorded_output_tagged_only_success_filters() -> None:
    """tagged_only + success just filters, with no error-tail handling."""
    raw = "[info] a\nnoise\n[info] b"

    result = build_recorded_output(raw, tagged_only=True, failed=False)

    assert result == "[info] a\n[info] b"


def test_build_recorded_output_tagged_only_failure_appends_tail() -> None:
    """A failed run appends everything after the last tagged line."""
    raw = "[info] a\nTraceback (most recent call last):\nBoom: bad"

    result = build_recorded_output(raw, tagged_only=True, failed=True)

    assert result == (
            "[info] a\n"
            f"{Constants.ERROR_TAIL_DIVIDER}\n"
            "Traceback (most recent call last):\nBoom: bad"
            )


def test_build_recorded_output_tagged_only_failure_no_tail() -> None:
    """A failed run with nothing after the last tag returns just the filter."""
    raw = "[info] a\n[error] b"

    result = build_recorded_output(raw, tagged_only=True, failed=True)

    assert result == "[info] a\n[error] b"


def test_build_recorded_output_tagged_only_failure_no_tags_at_all() -> None:
    """A failed run with no tagged lines uses the divider alone as prefix."""
    raw = "Traceback (most recent call last):\nBoom: bad"

    result = build_recorded_output(raw, tagged_only=True, failed=True)

    assert result == (
            f"{Constants.ERROR_TAIL_DIVIDER}\n"
            "Traceback (most recent call last):\nBoom: bad"
            )


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
                    commit="abc", dirty=False, label="", output="out-b",
                    ),
            "a_script": Entry(
                    script_id="a_script", order=1, timestamp="t",
                    commit="abc", dirty=False, label="", output="out-a",
                    ),
            "zeroth": Entry(
                    script_id="zeroth", order=0, timestamp="t",
                    commit="abc", dirty=False, label="", output="out-z",
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
                    commit="abc123", dirty=True, label="./run.sh", output="ok",
                    ),
            }

    rendered = render_log(entries)

    assert "[0] s (`./run.sh`)" in rendered
    assert "commit: `abc123` (dirty)" in rendered


def test_render_log_failed_status_line() -> None:
    """A failed entry gets `- status: failed`; a successful one doesn't."""
    ok_entry = Entry(
            script_id="ok", order=0, timestamp="t", commit="abc",
            dirty=False, label="", output="out", failed=False,
            )
    failed_entry = Entry(
            script_id="bad", order=1, timestamp="t", commit="abc",
            dirty=False, label="", output="out", failed=True,
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
                    commit="deadbee", dirty=True, label="my label",
                    output="line1\nline2", failed=False,
                    ),
            "s2": Entry(
                    script_id="s2", order=1, timestamp="2026-01-02 00:00:00",
                    commit="cafef00", dirty=False, label="",
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
        assert got.commit == original.commit
        assert got.dirty == original.dirty
        assert got.label == original.label
        assert got.output == original.output
        assert got.failed == original.failed


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


def test_record_tagged_only_resolved_error_notes_and_strips_tail(
        git_repo: Path,
        ) -> None:
    """After a tagged_only failure, a success notes resolution and diffs
    against the previous output with its untagged error tail stripped."""
    log_file = git_repo / "RUN_LOG.md"
    failed_output = (
            "[info] a\n"
            f"{Constants.ERROR_TAIL_DIVIDER}\n"
            "Traceback (most recent call last):\nBoom"
            )
    record(
            log_file=log_file, script_id="s1", order=0, output=failed_output,
            root=git_repo, failed=True, tagged_only=True,
            )

    record(
            log_file=log_file, script_id="s1", order=0, output="[info] a",
            root=git_repo, failed=False, tagged_only=True,
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


def test_run_and_record_tagged_only_keeps_tail_on_failure(
        git_repo: Path,
        ) -> None:
    """tagged_only + failing command keeps the untagged error tail."""
    log_file = git_repo / "RUN_LOG.md"
    script = (
            "print('[info] starting'); "
            "print('unrelated noise'); "
            "import sys; sys.exit(1)"
            )

    returncode = run_and_record(
            log_file=log_file, script_id="s1", order=0, root=git_repo,
            command=["python3", "-c", script], tagged_only=True,
            )

    assert returncode == 1
    text = log_file.read_text()
    assert "[info] starting" in text
    assert Constants.ERROR_TAIL_DIVIDER in text
    assert "unrelated noise" in text
