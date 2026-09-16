"""
log_tools.emitter

A `logging`-based emitter matching the tagged-logging convention used by
`log_tools/emitter.sh` (Bash): ``[tag]  timestamp message``, printed to
stdout (info/debug) or stderr (warn/error), and additionally appended to
`log_tools.runlog.Constants.RECORD_FILE_ENV_VAR` when set -- see
`log_tools.runlog.run_and_record`.

`log_info`/`log_warn` record by default (pass ``record=False`` to opt a
given call out); `log_debug` is the opposite, off by default (pass
``record=True`` to opt in), since debug output is expected to be noisy.
`log_error` always records. All four always print -- there is no
level-based verbosity gate.
"""
from __future__ import annotations

import logging
import os
import sys

from log_tools.runlog import Constants

# Bracketed prefix per level, padded to match `log_tools/emitter.sh`'s
# column-8 alignment: "[info] "/"[warn] " (extra space; template below
# adds one more) vs "[debug]"/"[error]" (no extra space). The padding
# must stay *after* the closing bracket -- putting it inside (e.g.
# "[info ]") would break `Constants.TAG_PATTERN`, which only allows
# letters between the brackets.
_PREFIX_BY_LEVEL: dict[int, str] = {
        logging.DEBUG: "[debug]",
        logging.INFO: "[info] ",
        logging.WARNING: "[warn] ",
        logging.ERROR: "[error]",
        logging.CRITICAL: "[error]",
        }

_LOGGER_NAME = "log_tools"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class _TagFormatter(logging.Formatter):
    """Render `[tag]  timestamp message`, tag looked up by level.

    Notes
    -----
    Builds the string directly from `record.getMessage()` rather than
    mutating `record.msg`/calling `super().format()` -- the same
    `LogRecord` is formatted independently by multiple handlers (stream
    + record file), so mutating shared state would double-prefix it on
    the second call.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format `record` using `_PREFIX_BY_LEVEL` for the bracket tag.

        A record carrying a truthy `stage` attribute (set by `log_stage`)
        uses the literal `"[stage]"` prefix instead of the level-based
        lookup -- stage markers are a structural annotation, not a log
        level.
        """
        if getattr(record, "stage", False):
            prefix = "[stage]"
        else:
            prefix = _PREFIX_BY_LEVEL.get(record.levelno, "[info] ")
        timestamp = self.formatTime(record, self.datefmt)
        return f"{prefix} {timestamp} {record.getMessage()}"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class _StreamLevelFilter(logging.Filter):
    """Keep records within an inclusive `[min_level, max_level]` range."""

    def __init__(self, min_level: int, max_level: int) -> None:
        super().__init__()
        self._min_level = min_level
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """Return `True` if `record.levelno` is within range."""
        return self._min_level <= record.levelno <= self._max_level


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class _DynamicStreamHandler(logging.Handler):
    """Write to `sys.stdout`/`sys.stderr`, resolved fresh on every emit.

    Notes
    -----
    Unlike `logging.StreamHandler(sys.stdout)`, which binds whatever
    stream object `sys.stdout` was at construction time, this looks the
    attribute up on each `emit()` call -- so it keeps working after
    something replaces `sys.stdout`/`sys.stderr` at runtime (e.g.
    pytest's `capsys` fixture), which matters because `get_logger()`'s
    handlers are configured once per process via the `logging` module's
    own name-keyed singleton cache.
    """

    def __init__(self, stream_name: str) -> None:
        super().__init__()
        self._stream_name = stream_name

    def emit(self, record: logging.LogRecord) -> None:
        """Write the formatted `record` to the current named stream."""
        stream = getattr(sys, self._stream_name)
        stream.write(self.format(record) + "\n")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class _RecordFileHandler(logging.Handler):
    """Append formatted records to `Constants.RECORD_FILE_ENV_VAR`.

    Notes
    -----
    A record is appended when `record.record` (set via the `record=`
    kwarg on `log_info`/`log_warn`/`log_debug`) is `True`, or
    unconditionally for `ERROR`/`CRITICAL` level records regardless of
    that attribute -- errors are never silently dropped.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Append `record`'s formatted message to the record file, if set."""
        path = os.environ.get(Constants.RECORD_FILE_ENV_VAR)
        if not path:
            return
        should_record = getattr(record, "record", True) or (
                record.levelno >= logging.ERROR
                )
        if not should_record:
            return
        with open(path, "a") as fh:
            fh.write(self.format(record) + "\n")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return a `logging.Logger` configured for tagged emitter output.

    Parameters
    ----------
    name : `str`, optional, default: `"log_tools"`
        Logger name.

    Returns
    -------
    logger : `logging.Logger`
        A logger with stdout (DEBUG/INFO), stderr (WARNING+), and record
        file handlers attached exactly once. The logger's own level is
        always `logging.DEBUG` (permissive) -- matching `log_debug`
        always printing on the Bash side (`log_tools/emitter.sh`), with
        no level-based verbosity gate. Filtering happens per-stream via
        each handler's level range, not by dropping records at the
        logger before any handler (including the record-file handler)
        ever sees them.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    formatter = _TagFormatter(fmt="%(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    stdout_handler = _DynamicStreamHandler("stdout")
    stdout_handler.addFilter(_StreamLevelFilter(logging.DEBUG, logging.INFO))
    stdout_handler.setFormatter(formatter)

    stderr_handler = _DynamicStreamHandler("stderr")
    stderr_handler.addFilter(
            _StreamLevelFilter(logging.WARNING, logging.CRITICAL),
            )
    stderr_handler.setFormatter(formatter)

    record_handler = _RecordFileHandler()
    record_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)
    logger.addHandler(record_handler)
    logger.propagate = False
    return logger


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_debug(msg: str, *, record: bool = False) -> None:
    """Log `msg` at DEBUG level; recorded only when `record` is `True`."""
    get_logger().debug(msg, extra={"record": record})


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_info(msg: str, *, record: bool = True) -> None:
    """Log `msg` at INFO level; recorded unless `record` is `False`."""
    get_logger().info(msg, extra={"record": record})


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_warn(msg: str, *, record: bool = True) -> None:
    """Log `msg` at WARNING level; recorded unless `record` is `False`."""
    get_logger().warning(msg, extra={"record": record})


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_error(msg: str) -> None:
    """Log `msg` at ERROR level; always recorded."""
    get_logger().error(msg)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_stage(name: str) -> None:
    """Mark the start of stage `name`; always recorded, printed to stdout.

    Produces a `"[stage] <timestamp> <name>"` line matching
    `log_tools.runlog.Constants.STAGE_MARKER_PATTERN`. Everything
    recorded after this call, up to the next `log_stage` call, is
    grouped under `name` by `log_tools.runlog.split_stages` when
    `record()` computes a diff -- so a stage that ran for the first
    time is never diffed against nothing, and a stage that is unchanged
    across runs never drowns out a stage that genuinely changed.
    """
    get_logger().info(name, extra={"record": True, "stage": True})


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_count(key: str) -> None:
    """Increment `key`'s in-process counter; does not print or record.

    Call once per high-cardinality event (e.g. once per file in a loop)
    in place of `log_info`/`log_debug`, then call `log_count_summary(key)`
    once after the loop to record a single summary line instead of one
    row per event.
    """
    _counts[key] = _counts.get(key, 0) + 1


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def log_count_summary(key: str, *, label: str | None = None) -> None:
    """Record one summary line for `key`'s count, then reset it to 0.

    Parameters
    ----------
    key : `str`
        The counter to summarize, as passed to `log_count`.
    label : `str` or `None`, optional
        Text shown in place of `key` in the summary line. Defaults to
        `key` itself.

    Notes
    -----
    Emits `"<label or key>: <count>"` via `log_info` (printed to stdout,
    always appended to the record file -- like `log_stage`, this call
    always records). A `key` never passed to `log_count` summarizes as
    `0`, which is itself useful signal (e.g. "files failed: 0").
    """
    count = _counts.pop(key, 0)
    log_info(f"{label or key}: {count}")
