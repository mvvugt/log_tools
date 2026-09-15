"""
log_tools.setup

A self-registering counterpart to `log_tools.runlog`'s CLI wrapping: a
step script calls `runlog_setup()` at its own top instead of being run
via ``runlog run --id --order -- CMD``. The context manager derives the
script's own id (its filename) and order (a counter scoped to the
current pipeline run) automatically, tees the script's own stdout/stderr
so a crash still leaves a raw-output safety net, and upserts the result
into `RUN_LOG.md` via the existing `log_tools.runlog.record`.

Run identity is inferred from the parent PID (`os.getppid()`): sibling
step scripts invoked directly by one orchestrator process share a PPID
for the run's duration, so no orchestrator changes are needed in the
common case. The order counter is persisted in a small plain-text state
file in the system temp directory, keyed by that PPID -- see
`resolve_order`. This is a deliberately simple, PID-reuse-tolerant
design, not a PID-reuse-proof one: a state file older than
`Constants.ORDER_STATE_TTL_SECONDS` is discarded and the counter
restarts, which doubles as the only cleanup mechanism (no reaper needed).
"""
from __future__ import annotations

import contextlib
import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from types import TracebackType

from log_tools.functions import atomic_write, resolve_git_root
from log_tools.runlog import Constants as RunlogConstants
from log_tools.runlog import build_recorded_output, record

_log = logging.getLogger(__name__)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Constants:
    """Constants specific to automatic setup/order-registration."""

    ORDER_STATE_FILENAME_TEMPLATE: str = "runlog-order-{ppid}.state"
    ORDER_LOCK_DIRNAME_TEMPLATE: str = "runlog-order-{ppid}.lock"
    ORDER_STEP: int = 10
    ORDER_STATE_TTL_SECONDS: float = 86400.0
    LOCK_RETRY_INTERVAL_SECONDS: float = 0.05
    LOCK_MAX_TRIES: int = 200
    LOG_FILE_ENV_VAR: str = "RUNLOG_LOG_FILE"
    ROOT_ENV_VAR: str = "RUNLOG_ROOT"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class _TeeWriter:
    """Write-through wrapper recording everything written to `stream`.

    Notes
    -----
    Used to replace `sys.stdout`/`sys.stderr` for the duration of a
    `RunlogSetup` block, so the script's own raw output stays available
    for `build_recorded_output`'s `raw_on_failure` safety net without
    losing live streaming to the real terminal.
    """

    def __init__(self, stream: object, buffer: list[str]) -> None:
        self._stream = stream
        self._buffer = buffer

    def write(self, text: str) -> int:
        """Append `text` to the buffer, then write it through."""
        self._buffer.append(text)
        return self._stream.write(text)

    def flush(self) -> None:
        """Flush the wrapped stream."""
        self._stream.flush()

    def __getattr__(self, name: str) -> object:
        """Delegate any other attribute access to the wrapped stream."""
        return getattr(self._stream, name)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _order_state_path(ppid: int) -> Path:
    """Return the order-state file path for run id `ppid`."""
    name = Constants.ORDER_STATE_FILENAME_TEMPLATE.format(ppid=ppid)
    return Path(tempfile.gettempdir()) / name


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _order_lock_path(ppid: int) -> Path:
    """Return the order-state lock directory path for run id `ppid`."""
    name = Constants.ORDER_LOCK_DIRNAME_TEMPLATE.format(ppid=ppid)
    return Path(tempfile.gettempdir()) / name


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _acquire_lock(lock_path: Path) -> bool:
    """Acquire `lock_path` via atomic `mkdir`, retrying briefly.

    Returns
    -------
    acquired : `bool`
        `True` if the lock was acquired. `False` if `Constants.
        LOCK_MAX_TRIES` was exceeded, in which case the caller proceeds
        unlocked (fail open, rather than hanging a pipeline forever) and
        a warning is logged.
    """
    for _ in range(Constants.LOCK_MAX_TRIES):
        try:
            lock_path.mkdir()
            return True
        except FileExistsError:
            time.sleep(Constants.LOCK_RETRY_INTERVAL_SECONDS)
    _log.warning(
            "could not acquire order-state lock %r; proceeding unlocked",
            str(lock_path),
            )
    return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _release_lock(lock_path: Path) -> None:
    """Release a lock acquired via `_acquire_lock`, ignoring absence."""
    with contextlib.suppress(OSError):
        lock_path.rmdir()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _parse_state(text: str) -> dict[str, str]:
    """Parse `KEY=value` lines into a dict, ignoring blank/malformed ones."""
    state: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        state[key] = value
    return state


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _serialize_state(state: dict[str, str]) -> str:
    """Render a state dict back to `KEY=value` lines."""
    return "".join(f"{key}={value}\n" for key, value in state.items())


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _fresh_state() -> dict[str, str]:
    """Return a new, empty order-state dict, timestamped now."""
    return {
            "CREATED_AT": str(time.time()),
            "NEXT_ORDER": str(Constants.ORDER_STEP),
            }


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _is_stale(state: dict[str, str]) -> bool:
    """Return `True` if `state`'s `CREATED_AT` is past the TTL (or missing/
    unparseable, treated the same as stale)."""
    try:
        created_at = float(state["CREATED_AT"])
    except (KeyError, ValueError):
        return True
    return (time.time() - created_at) > Constants.ORDER_STATE_TTL_SECONDS


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def resolve_order(ppid: int, script_id: str) -> int:
    """Resolve `script_id`'s order within the pipeline run keyed by `ppid`.

    Parameters
    ----------
    ppid : `int`
        Run-identity key -- the calling script's parent PID.
    script_id : `str`
        The registering script's id.

    Returns
    -------
    order : `int`
        `script_id`'s existing order if it already registered in this
        run, else a freshly assigned one (`Constants.ORDER_STEP` apart
        from the previous fresh assignment).

    Notes
    -----
    Guarded by an `mkdir`-based advisory lock around the state file's
    read-modify-write, so concurrent sibling registrations don't lose an
    update -- see `_acquire_lock`.
    """
    state_path = _order_state_path(ppid)
    lock_path = _order_lock_path(ppid)
    _acquire_lock(lock_path)
    try:
        state = (
                _parse_state(state_path.read_text())
                if state_path.is_file() else {}
                )
        if not state or _is_stale(state):
            state = _fresh_state()

        if script_id in state:
            return int(state[script_id])

        order = int(state["NEXT_ORDER"])
        state[script_id] = str(order)
        state["NEXT_ORDER"] = str(order + Constants.ORDER_STEP)
        atomic_write(state_path, _serialize_state(state))
        return order
    finally:
        _release_lock(lock_path)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _resolve_root_for_setup(root: Path | None) -> Path:
    """Resolve the git root for `RunlogSetup`: explicit, then
    `Constants.ROOT_ENV_VAR`, then the git-toplevel-from-cwd default."""
    if root is not None:
        return root
    env_root = os.environ.get(Constants.ROOT_ENV_VAR)
    if env_root:
        return Path(env_root)
    return resolve_git_root(None)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _resolve_log_file_for_setup(log_file: Path | None, root: Path) -> Path:
    """Resolve the log file for `RunlogSetup`: explicit, then
    `Constants.LOG_FILE_ENV_VAR`, then `<root>/RUN_LOG.md`."""
    if log_file is not None:
        return log_file
    env_log_file = os.environ.get(Constants.LOG_FILE_ENV_VAR)
    if env_log_file:
        return Path(env_log_file)
    return root / RunlogConstants.DEFAULT_LOG_NAME


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class RunlogSetup:
    """Context manager registering the current script's run in RUN_LOG.md.

    Parameters
    ----------
    script_id : `str` or `None`, optional
        Overrides the automatically derived id
        (`Path(sys.argv[0]).stem`).
    log_file : `Path` or `None`, optional
        Overrides `Constants.LOG_FILE_ENV_VAR`/default resolution.
    root : `Path` or `None`, optional
        Overrides `Constants.ROOT_ENV_VAR`/default resolution.
    include_pattern : `str` or `None`, optional
        Forwarded to `log_tools.runlog.build_recorded_output` at
        teardown.
    raw_on_failure : `bool`, optional, default: `True`
        Forwarded to `build_recorded_output` at teardown. Defaults to
        `True` here (unlike `runlog run`'s CLI default of `False`)
        since there is no explicit flag to opt in for an in-process
        crash -- see the module docstring's raw-output-safety-net intent.

    Notes
    -----
    `__exit__` always returns `False` -- it never suppresses the
    original exception; it only records the run before letting the
    exception (or a nonzero `sys.exit`) propagate.
    """

    def __init__(
            self, *, script_id: str | None = None,
            log_file: Path | None = None, root: Path | None = None,
            include_pattern: str | None = None,
            raw_on_failure: bool = True,
            ) -> None:
        self._script_id_override = script_id
        self._log_file_override = log_file
        self._root_override = root
        self._include_pattern = include_pattern
        self._raw_on_failure = raw_on_failure

    def __enter__(self) -> RunlogSetup:
        """Resolve identity/location, reserve an order, and start tee'ing
        stdout/stderr plus the emitter's record file."""
        self.root = _resolve_root_for_setup(self._root_override)
        self.log_file = _resolve_log_file_for_setup(
                self._log_file_override, self.root,
                )
        self.script_id = self._script_id_override or Path(sys.argv[0]).stem
        self.order = resolve_order(os.getppid(), self.script_id)

        record_fd, record_path_str = tempfile.mkstemp(
                prefix="runlog-record-",
                )
        os.close(record_fd)
        self._record_path = Path(record_path_str)
        self._prev_record_env = os.environ.get(
                RunlogConstants.RECORD_FILE_ENV_VAR,
                )
        os.environ[RunlogConstants.RECORD_FILE_ENV_VAR] = str(
                self._record_path,
                )

        self._raw_buffer: list[str] = []
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _TeeWriter(self._orig_stdout, self._raw_buffer)
        sys.stderr = _TeeWriter(self._orig_stderr, self._raw_buffer)
        return self

    def __exit__(
            self, exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
            ) -> bool:
        """Restore stdout/stderr, then record the run and clean up."""
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

        clean_exit = exc_type is None or (
                exc_type is SystemExit
                and getattr(exc_val, "code", None) in (None, 0)
                )
        failed = not clean_exit

        raw_output = "".join(self._raw_buffer)
        if exc_type is not None and exc_type is not SystemExit:
            raw_output += "".join(
                    traceback.format_exception(exc_type, exc_val, exc_tb),
                    )

        record_file_content = (
                self._record_path.read_text()
                if self._record_path.is_file() else ""
                )
        output = build_recorded_output(
                raw_output, record_file_content=record_file_content,
                include_pattern=self._include_pattern,
                raw_on_failure=self._raw_on_failure, failed=failed,
                )

        record(
                log_file=self.log_file, script_id=self.script_id,
                order=self.order, output=output, root=self.root,
                label=" ".join(sys.argv), failed=failed,
                )

        self._record_path.unlink(missing_ok=True)
        if self._prev_record_env is None:
            os.environ.pop(RunlogConstants.RECORD_FILE_ENV_VAR, None)
        else:
            os.environ[RunlogConstants.RECORD_FILE_ENV_VAR] = (
                    self._prev_record_env
                    )
        return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def runlog_setup(
        *, script_id: str | None = None, log_file: Path | None = None,
        root: Path | None = None, include_pattern: str | None = None,
        raw_on_failure: bool = True,
        ) -> RunlogSetup:
    """Return a context manager that self-registers this script's run.

    Parameters
    ----------
    script_id, log_file, root, include_pattern, raw_on_failure
        See `RunlogSetup`.

    Returns
    -------
    ctx : `RunlogSetup`
        Use as ``with runlog_setup(): ...``.
    """
    return RunlogSetup(
            script_id=script_id, log_file=log_file, root=root,
            include_pattern=include_pattern,
            raw_on_failure=raw_on_failure,
            )
