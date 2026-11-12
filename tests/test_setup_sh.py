"""
End-to-end tests for `log_tools/setup.sh` (the Bash counterpart to
`log_tools.setup.runlog_setup()`).

Like `tests/test_example_pipeline.py`, these exercise the *installed*
`runlog` and `runlog-setup-path` console scripts directly (`setup.sh`
shells out to `runlog record` at teardown, and is located via
`runlog-setup-path`) -- so they only run meaningfully once `log_tools`
is installed on `PATH` (`pip install -e ".[dev]"`) and are skipped
otherwise.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

from .conftest import REPO_ROOT

_SHELL_FILES = sorted((REPO_ROOT / "log_tools").glob("*.sh"))
# `"${name[@]}"` not preceded by `+` (i.e. not the bash-4.2-safe
# `${name[@]+"${name[@]}"}` form) and not a key listing `${!name[@]}`.
_UNGUARDED_ARRAY = re.compile(r'(?<!\+)"\$\{(?!!)[A-Za-z_]\w*\[@\]\}"')
_SKIP_REASON = (
        "requires `log_tools` installed on PATH (pip install -e .)"
        )
_SKIP = (
        shutil.which("runlog") is None
        or shutil.which("runlog-setup-path") is None
        )
_SETUP_SH = REPO_ROOT / "log_tools" / "setup.sh"
# Extra bash to run the strict-mode/teardown tests under, e.g. the system
# bash 4.2 on Myriad: `RUNLOG_TEST_BASH=/bin/bash pytest ...`. Unset, only
# the `bash` on PATH is used.
_BASHES = ["bash"] + (
        [os.environ["RUNLOG_TEST_BASH"]]
        if os.environ.get("RUNLOG_TEST_BASH") else []
        )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _write_step_script(path: Path, body: str) -> None:
    """Write an executable Bash step script calling `runlog_setup`.

    Parameters
    ----------
    path : `Path`
        Destination path (its stem becomes the auto-derived `script_id`).
    body : `str`
        Statements to run after `runlog_setup`, dedented by the caller.
    """
    script = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            '# shellcheck disable=SC1090\n'
            'source "$(runlog-setup-path)"\n'
            "runlog_setup\n"
            f"{textwrap.dedent(body)}\n"
            )
    path.write_text(script)
    path.chmod(0o755)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _order_of(log_text: str, script_id: str) -> int:
    """Extract the `[order]` of `script_id`'s section from rendered text."""
    for line in log_text.splitlines():
        if line.startswith("## [") and f"] {script_id}" in line:
            return int(line[len("## ["):line.index("]")])
    raise AssertionError(f"no section for {script_id!r} in log text")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_id_from_basename_and_live_streaming(git_repo: Path) -> None:
    """The section id matches the step's own basename, and output still
    streams live to the caller while being recorded."""
    script = git_repo / "fetch_thing.sh"
    _write_step_script(script, 'log_info "hello from bash"')

    result = subprocess.run(
            [str(script)], cwd=git_repo, capture_output=True, text=True,
            )

    assert result.returncode == 0, result.stderr
    assert "hello from bash" in result.stdout
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, "fetch_thing") > 0
    assert "hello from bash" in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_order_increments_across_sibling_scripts(git_repo: Path) -> None:
    """Two new script_ids registering from the same parent process (this
    test process) get strictly increasing orders, `ORDER_STEP` apart."""
    script_a = git_repo / "step_one.sh"
    script_b = git_repo / "step_two.sh"
    _write_step_script(script_a, 'log_info "a"')
    _write_step_script(script_b, 'log_info "b"')

    assert subprocess.run(
            [str(script_a)], cwd=git_repo, capture_output=True, text=True,
            ).returncode == 0
    assert subprocess.run(
            [str(script_b)], cwd=git_repo, capture_output=True, text=True,
            ).returncode == 0

    text = (git_repo / "RUN_LOG.md").read_text()
    order_a = _order_of(text, "step_one")
    order_b = _order_of(text, "step_two")
    assert order_b - order_a == 10  # Constants.ORDER_STEP


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_order_reused_on_reregistration(git_repo: Path) -> None:
    """Running the same step script twice keeps its order unchanged."""
    script = git_repo / "rerun_step.sh"
    _write_step_script(script, 'log_info "run"')

    subprocess.run([str(script)], cwd=git_repo, capture_output=True)
    first = _order_of((git_repo / "RUN_LOG.md").read_text(), "rerun_step")

    subprocess.run([str(script)], cwd=git_repo, capture_output=True)
    second = _order_of((git_repo / "RUN_LOG.md").read_text(), "rerun_step")

    assert first == second


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_raw_output_captured_on_plain_exit_without_emitter_calls(
        git_repo: Path,
        ) -> None:
    """A script that only `echo`s (no emitter calls) then exits non-zero
    still has its raw output recorded with a failed status -- and the
    EXIT trap's `$?` correctly reflects the script's own exit code, not
    the trap handling itself."""
    script = git_repo / "crash_step.sh"
    _write_step_script(script, 'echo "about to fail"\nexit 3')

    result = subprocess.run(
            [str(script)], cwd=git_repo, capture_output=True, text=True,
            )

    assert result.returncode == 3
    assert "about to fail" in result.stdout
    text = (git_repo / "RUN_LOG.md").read_text()
    assert "- status: failed" in text
    assert "about to fail" in text
    assert "--- error output (raw) ---" in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_runlog_order_env_var_overrides_autoincrement(
        git_repo: Path,
        ) -> None:
    """`RUNLOG_ORDER`, if set, wins over the PPID-scoped counter --
    needed for a script submitted to a batch scheduler or re-invoked
    from a fresh orchestrator process in a later pipeline stage."""
    script = git_repo / "pinned_order_step.sh"
    _write_step_script(script, 'log_info "pinned"')

    env = dict(os.environ, RUNLOG_ORDER="4242")
    result = subprocess.run(
            [str(script)], cwd=git_repo, capture_output=True, text=True,
            env=env,
            )

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, "pinned_order_step") == 4242


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_runlog_script_id_env_var_overrides_basename(
        git_repo: Path,
        ) -> None:
    """`RUNLOG_SCRIPT_ID`, if set, wins over the basename-derived
    default -- needed when one shared script self-registers multiple
    distinct identities (e.g. one call per cohort)."""
    script = git_repo / "shared_extractor.sh"
    _write_step_script(script, 'log_info "cohort run"')

    env = dict(os.environ, RUNLOG_SCRIPT_ID="cohort_ahola")
    result = subprocess.run(
            [str(script)], cwd=git_repo, capture_output=True, text=True,
            env=env,
            )

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, "cohort_ahola") > 0
    assert "] shared_extractor" not in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_env_var_overrides_log_file_and_root(
        git_repo: Path, tmp_path: Path,
        ) -> None:
    """`RUNLOG_LOG_FILE`/`RUNLOG_ROOT` are honoured over the git-toplevel
    default resolution."""
    script = git_repo / "override_step.sh"
    _write_step_script(script, 'log_info "here"')
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    custom_log = other_dir / "custom_log.md"

    env = dict(
            os.environ, RUNLOG_LOG_FILE=str(custom_log),
            RUNLOG_ROOT=str(other_dir),
            )
    result = subprocess.run(
            [str(script)], cwd=git_repo, capture_output=True, text=True,
            env=env,
            )

    assert result.returncode == 0, result.stderr
    assert custom_log.is_file()
    assert not (git_repo / "RUN_LOG.md").is_file()
    assert "override_step" in custom_log.read_text()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_shell_files_found() -> None:
    """Guard for the static check below: it must scan real files."""
    names = {path.name for path in _SHELL_FILES}
    assert {"setup.sh", "emitter.sh"} <= names


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("path", _SHELL_FILES, ids=lambda p: p.name)
def test_no_unguarded_array_expansion(path: Path) -> None:
    """No `"${arr[@]}"` expansion that bash < 4.4 treats as unbound when
    `arr` is empty under `set -u` (the Myriad bash 4.2 teardown crash);
    use `${arr[@]+"${arr[@]}"}` instead."""
    offending = [
            f"{lineno}: {line.strip()}"
            for lineno, line in enumerate(path.read_text().splitlines(), 1)
            if not line.lstrip().startswith("#")
            and _UNGUARDED_ARRAY.search(line)
            ]
    assert offending == []


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.parametrize("bash", _BASHES)
@pytest.mark.parametrize("exit_code", [0, 1])
def test_strict_mode_after_setup_keeps_exit_code(
        git_repo: Path, exit_code: int, bash: str,
        ) -> None:
    """With `set -u` enabled after `runlog_setup` (the Myriad wrapper
    pattern), teardown completes, the script's own exit code is
    preserved, and no 'unbound variable' error is printed."""
    script = git_repo / "strict_step.sh"
    script.write_text(
            "#!/usr/bin/env bash\n"
            '# shellcheck disable=SC1090\n'
            'source "$(runlog-setup-path)"\n'
            "runlog_setup\n"
            "set -euo pipefail\n"
            'log_info "strict"\n'
            f"exit {exit_code}\n"
            )
    script.chmod(0o755)

    result = subprocess.run(
            [bash, str(script)], cwd=git_repo, capture_output=True,
            text=True,
            )

    assert result.returncode == exit_code
    assert "unbound variable" not in result.stdout + result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, "strict_step") > 0
    assert ("- status: failed" in text) is (exit_code != 0)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
@pytest.mark.parametrize("bash", _BASHES)
@pytest.mark.parametrize("exit_code", [0, 3])
def test_teardown_record_failure_only_warns(
        git_repo: Path, exit_code: int, bash: str,
        ) -> None:
    """If `runlog record` fails at teardown (here: the log file's parent
    is a regular file), the script keeps its own exit code under
    `set -euo pipefail`, and the warning says only the log entry is
    missing."""
    blocker = git_repo / "not_a_dir"
    blocker.write_text("")
    script = git_repo / "unrecorded_step.sh"
    script.write_text(
            "#!/usr/bin/env bash\n"
            '# shellcheck disable=SC1090\n'
            'source "$(runlog-setup-path)"\n'
            "runlog_setup\n"
            "set -euo pipefail\n"
            'log_info "work done"\n'
            f"exit {exit_code}\n"
            )
    script.chmod(0o755)

    result = subprocess.run(
            [bash, str(script)], cwd=git_repo, capture_output=True,
            text=True,
            env=dict(os.environ, RUNLOG_LOG_FILE=str(blocker / "RUN_LOG.md")),
            )

    # `runlog_setup` merges stderr into stdout and only saves the real
    # stdout, so teardown messages arrive on stdout.
    seen = result.stdout + result.stderr
    assert result.returncode == exit_code, seen
    assert "unbound variable" not in seen
    assert f"'unrecorded_step' finished with exit code {exit_code}" in seen
    assert "NOT recorded" in seen
    assert "own results are unaffected" in seen


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _run_sourced(
        snippet: str, tmp_path: Path, bash: str = "bash",
        ) -> subprocess.CompletedProcess[str]:
    """Source the repo's `setup.sh` (no install needed) and run `snippet`.

    Parameters
    ----------
    snippet : `str`
        Bash code run after sourcing, e.g. calls to internal helpers.
    tmp_path : `Path`
        Used as `TMPDIR`, so order-state/lock paths stay in the test dir.
    bash : `str`, optional, default: `"bash"`
        The bash binary to run under.
    """
    code = f'source "{_SETUP_SH}"\n{textwrap.dedent(snippet)}'
    return subprocess.run(
            [bash, "-c", code], capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=str(tmp_path)),
            )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("bash", _BASHES)
def test_bash_lock_times_out_with_full_warning(
        tmp_path: Path, bash: str,
        ) -> None:
    """A fresh lock held by someone else makes `_runlog_acquire_lock`
    give up after its timeout with the *whole* warning on stderr, not
    recorded, leaving the other holder's lock alone."""
    lock = tmp_path / "held.lock"
    lock.mkdir()
    record = tmp_path / "record"

    result = _run_sourced(
            f"""
            export RUNLOG_RECORD_FILE="{record}"
            _RUNLOG_LOCK_TIMEOUT_SECONDS=1
            _runlog_acquire_lock "{lock}"
            echo "rc=$?"
            """,
            tmp_path, bash,
            )

    assert "rc=1" in result.stdout
    assert f"could not acquire order-state lock {lock}" in result.stderr
    assert "proceeding unlocked" in result.stderr
    assert not record.exists() or record.read_text() == ""
    assert lock.is_dir()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("bash", _BASHES)
def test_bash_lock_breaks_stale_lock(tmp_path: Path, bash: str) -> None:
    """A lock dir older than the stale limit (left by a killed job) is
    broken and acquired instead of waiting for the timeout."""
    lock = tmp_path / "stale.lock"
    lock.mkdir()
    old = time.time() - 600
    os.utime(lock, (old, old))

    result = _run_sourced(
            f"""
            _RUNLOG_LOCK_TIMEOUT_SECONDS=5
            _runlog_acquire_lock "{lock}"
            echo "rc=$?"
            """,
            tmp_path, bash,
            )

    assert "rc=0" in result.stdout, result.stderr
    assert lock.is_dir()
    assert lock.stat().st_mtime > old


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("bash", _BASHES)
def test_bash_resolve_order_keeps_lock_it_did_not_acquire(
        tmp_path: Path, bash: str,
        ) -> None:
    """When `_runlog_resolve_order` times out on a lock held by a live
    sibling, it proceeds unlocked but must not remove that sibling's
    lock."""
    ppid = 424242
    lock = tmp_path / f"runlog-order-{ppid}.lock"
    lock.mkdir()

    result = _run_sourced(
            f"""
            _RUNLOG_LOCK_TIMEOUT_SECONDS=1
            _runlog_resolve_order {ppid} some_step
            """,
            tmp_path, bash,
            )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().isdigit()
    assert lock.is_dir()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("bash", _BASHES)
def test_bash_resolve_order_releases_its_own_lock(
        tmp_path: Path, bash: str,
        ) -> None:
    """On the normal path the order-state lock is removed afterwards."""
    ppid = 434343

    result = _run_sourced(
            f"_runlog_resolve_order {ppid} some_step\n", tmp_path, bash,
            )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().isdigit()
    assert not (tmp_path / f"runlog-order-{ppid}.lock").exists()
