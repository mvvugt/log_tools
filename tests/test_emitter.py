"""Unit tests for `log_tools.emitter`."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from log_tools.emitter import (
    get_logger,
    log_debug,
    log_error,
    log_info,
    log_warn,
)
from log_tools.runlog import Constants


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.fixture(autouse=True)
def record_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point `RUNLOG_RECORD_FILE` at a fresh temp file for every test."""
    path = tmp_path / "record"
    monkeypatch.setenv(Constants.RECORD_FILE_ENV_VAR, str(path))
    return path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_log_info_prints_to_stdout_with_tag_pattern(
        capsys: pytest.CaptureFixture[str],
        ) -> None:
    """`log_info` prints to stdout, matching `Constants.TAG_PATTERN`."""
    log_info("hello")

    out = capsys.readouterr().out.strip()
    assert re.match(Constants.TAG_PATTERN, out)
    assert "hello" in out
    assert out.startswith("[info")


def test_log_warn_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_warn` prints to stderr, not stdout."""
    log_warn("careful")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "careful" in captured.err
    assert captured.err.strip().startswith("[warn")


def test_log_error_prints_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_error` prints to stderr, not stdout."""
    log_error("boom")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "boom" in captured.err
    assert captured.err.strip().startswith("[error")


def test_log_debug_prints_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """`log_debug` always prints to stdout -- no level-based suppression."""
    log_debug("details")

    out = capsys.readouterr().out.strip()
    assert "details" in out
    assert out.startswith("[debug")


def test_log_stage_prints_to_stdout_with_tag_pattern(
        capsys: pytest.CaptureFixture[str],
        ) -> None:
    """`log_stage` prints to stdout, matching `Constants.TAG_PATTERN`."""
    log_stage("prepare")

    out = capsys.readouterr().out.strip()
    assert re.match(Constants.TAG_PATTERN, out)
    assert re.match(Constants.STAGE_MARKER_PATTERN, out)
    assert out.startswith("[stage]")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_log_info_records_by_default(record_file: Path) -> None:
    """`log_info` appends to the record file unless told not to."""
    log_info("kept")

    assert "kept" in record_file.read_text()


def test_log_info_record_false_suppresses_file_write(record_file: Path) -> None:
    """`record=False` on `log_info` skips the record-file append."""
    log_info("not kept", record=False)

    assert not record_file.exists() or "not kept" not in record_file.read_text()


def test_log_warn_records_by_default(record_file: Path) -> None:
    """`log_warn` appends to the record file unless told not to."""
    log_warn("kept")

    assert "kept" in record_file.read_text()


def test_log_debug_does_not_record_by_default(record_file: Path) -> None:
    """`log_debug` does not append to the record file unless opted in."""
    log_debug("quiet")

    assert not record_file.exists() or "quiet" not in record_file.read_text()


def test_log_debug_record_true_opts_in(record_file: Path) -> None:
    """`record=True` on `log_debug` opts that call into the record file."""
    log_debug("kept", record=True)

    assert "kept" in record_file.read_text()


def test_log_error_always_records(record_file: Path) -> None:
    """`log_error` always appends to the record file; no `record` kwarg."""
    log_error("boom")

    assert "boom" in record_file.read_text()


def test_log_error_has_no_record_kwarg() -> None:
    """`log_error`'s signature doesn't expose a `record` toggle at all."""
    with pytest.raises(TypeError):
        log_error("boom", record=False)  # type: ignore[call-arg]


def test_no_record_file_env_var_is_a_silent_noop(
        monkeypatch: pytest.MonkeyPatch,
        ) -> None:
    """Without `RUNLOG_RECORD_FILE` set, logging still prints, no error."""
    monkeypatch.delenv(Constants.RECORD_FILE_ENV_VAR, raising=False)

    log_info("fine")  # should not raise


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_logger_is_idempotent_no_duplicate_handlers() -> None:
    """Repeated `get_logger()` calls don't attach handlers more than once."""
    first = get_logger()
    handler_count = len(first.handlers)

    second = get_logger()

    assert second is first
    assert len(second.handlers) == handler_count
