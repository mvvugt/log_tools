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
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_SKIP_REASON = (
        "requires `log_tools` installed on PATH (pip install -e .)"
        )
_SKIP = (
        shutil.which("runlog") is None
        or shutil.which("runlog-setup-path") is None
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
