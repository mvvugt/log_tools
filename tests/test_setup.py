"""
End-to-end tests for `log_tools.setup` (the self-registering
`runlog_setup()` context manager).

Step scripts under test are written to disk and run as real subprocesses
(this project's testing standard: no mocking of subprocesses/git), so
`sys.argv[0]`-derived ids and `os.getppid()`-derived run identity behave
exactly as they would for a real pipeline step. Scripts launched directly
from a test function share that test (pytest) process as their real
parent, so sequential/concurrent `subprocess` calls from one test are
naturally "siblings" for order-counter purposes -- no synthetic
orchestrator process is needed.

The order-counter state file is keyed by the real OS parent PID, which is
stable (the pytest process's own PID) across the whole test session --
so assertions here deliberately check *relative* order behaviour (deltas,
equality across re-registration) rather than absolute values, and each
step script uses a unique filename (`_unique_step_name`) so different
tests' `script_id`s never collide within that shared per-PID state file.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .conftest import REPO_ROOT


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _unique_step_name(prefix: str) -> str:
    """Return a filename stem unique to this call, avoiding cross-test
    `script_id` collisions in the PID-scoped order-state file."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _write_step_script(tmp_path: Path, name: str, body: str) -> Path:
    """Write a runnable Python step script calling `runlog_setup()`.

    Parameters
    ----------
    tmp_path : `Path`
        Directory to write the script into.
    name : `str`
        Filename stem (becomes the auto-derived `script_id`).
    body : `str`
        Source text to run inside ``with runlog_setup():``, indented by
        the caller as plain statements (no leading indentation needed --
        this helper handles it).

    Returns
    -------
    path : `Path`
        Path to the written ``<name>.py`` script.
    """
    indented = "\n".join(f"    {line}" for line in body.splitlines())
    script = (
            "from log_tools.setup import runlog_setup\n"
            "with runlog_setup():\n"
            f"{indented}\n"
            )
    path = tmp_path / f"{name}.py"
    path.write_text(script)
    return path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _run_step(
        script: Path, *, cwd: Path, env_extra: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
    """Run a step script as a real subprocess of the current test process.

    Notes
    -----
    `PYTHONPATH` is set to `REPO_ROOT` so `log_tools` is importable
    without the package being `pip install`-ed into the test environment
    -- same approach as `tests.conftest.run_cli`.
    """
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), **(env_extra or {}))
    return subprocess.run(
            [sys.executable, str(script)], cwd=cwd,
            capture_output=True, text=True, env=env,
            )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _order_of(log_text: str, script_id: str) -> int:
    """Extract the `[order]` of `script_id`'s section from rendered text."""
    for line in log_text.splitlines():
        if line.startswith("## [") and f"] {script_id}" in line:
            return int(line[len("## ["):line.index("]")])
    raise AssertionError(f"no section for {script_id!r} in log text")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_script_id_derived_from_filename(git_repo: Path) -> None:
    """The section id matches the step script's own filename stem."""
    name = _unique_step_name("id_from_filename")
    script = _write_step_script(git_repo, name, 'print("hello")')

    result = _run_step(script, cwd=git_repo)

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, name) > 0


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_order_increments_across_sibling_scripts(git_repo: Path) -> None:
    """Two new script_ids registering from the same parent process get
    strictly increasing orders, `Constants.ORDER_STEP` apart."""
    from log_tools.setup import Constants

    name_a = _unique_step_name("sibling_a")
    name_b = _unique_step_name("sibling_b")
    script_a = _write_step_script(git_repo, name_a, 'print("a")')
    script_b = _write_step_script(git_repo, name_b, 'print("b")')

    assert _run_step(script_a, cwd=git_repo).returncode == 0
    assert _run_step(script_b, cwd=git_repo).returncode == 0

    text = (git_repo / "RUN_LOG.md").read_text()
    order_a = _order_of(text, name_a)
    order_b = _order_of(text, name_b)
    assert order_b - order_a == Constants.ORDER_STEP


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_order_reused_on_reregistration(git_repo: Path) -> None:
    """Running the same script_id twice from the same parent process keeps
    its order unchanged the second time."""
    name = _unique_step_name("reregister")
    script = _write_step_script(git_repo, name, 'print("run")')

    _run_step(script, cwd=git_repo)
    first_order = _order_of((git_repo / "RUN_LOG.md").read_text(), name)

    _run_step(script, cwd=git_repo)
    second_order = _order_of((git_repo / "RUN_LOG.md").read_text(), name)

    assert first_order == second_order


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_raw_output_captured_on_unhandled_exception(git_repo: Path) -> None:
    """A script that never touches the emitter still has its raw stdout
    and traceback recorded, with a failed status, on an unhandled crash."""
    name = _unique_step_name("crash")
    script = _write_step_script(
            git_repo, name,
            'print("before crash")\nraise ValueError("boom")',
            )

    result = _run_step(script, cwd=git_repo)

    assert result.returncode != 0
    text = (git_repo / "RUN_LOG.md").read_text()
    assert "- status: failed" in text
    assert "before crash" in text
    assert "ValueError" in text
    assert "boom" in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_env_var_overrides_log_file_and_root(
        git_repo: Path, tmp_path: Path,
        ) -> None:
    """`RUNLOG_LOG_FILE`/`RUNLOG_ROOT` are honoured over the git-toplevel
    default resolution."""
    name = _unique_step_name("env_override")
    script = _write_step_script(git_repo, name, 'print("here")')
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    custom_log = other_dir / "custom_log.md"

    result = _run_step(
            script, cwd=git_repo,
            env_extra={
                    "RUNLOG_LOG_FILE": str(custom_log),
                    "RUNLOG_ROOT": str(other_dir),
                    },
            )

    assert result.returncode == 0, result.stderr
    assert custom_log.is_file()
    assert not (git_repo / "RUN_LOG.md").is_file()
    assert name in custom_log.read_text()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_concurrent_siblings_do_not_lose_an_order_update(
        git_repo: Path,
        ) -> None:
    """Several processes calling `resolve_order` nearly simultaneously for
    the same run id each get a distinct order, none dropped by a lost
    concurrent write to the shared order-state file.

    Notes
    -----
    This targets `resolve_order`'s own `mkdir`-lock-guarded state file in
    isolation (via a tiny script that only calls it and prints the
    result), rather than running full step scripts that also call
    `record()` -- concurrent `record()` calls race on `RUN_LOG.md`
    itself via a separate, pre-existing limitation in
    `log_tools.functions.atomic_write` (its fixed `.tmp` sibling name is
    not unique per writer), which is outside this feature's scope.
    """
    from log_tools.setup import Constants

    names = [_unique_step_name(f"concurrent_{i}") for i in range(5)]
    scripts = [
            git_repo / f"{n}.py" for n in names
            ]
    for path, name in zip(scripts, names):
        path.write_text(
                "from log_tools.setup import resolve_order\n"
                "import os\n"
                f'print(resolve_order(os.getppid(), "{name}"))\n',
                )

    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    procs = [
            subprocess.Popen(
                    [sys.executable, str(s)], cwd=git_repo,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env,
                    )
            for s in scripts
            ]
    outs = [proc.communicate() for proc in procs]
    for proc, (_, err) in zip(procs, outs):
        assert proc.returncode == 0, err

    orders = sorted(int(out.strip()) for out, _ in outs)
    assert len(set(orders)) == len(names)
    deltas = {b - a for a, b in zip(orders, orders[1:])}
    assert deltas == {Constants.ORDER_STEP}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_order_override_bypasses_autoincrement(git_repo: Path) -> None:
    """An explicit `order=` wins over the PPID-scoped counter -- needed
    for steps whose real process ancestry (a batch-submitted job, a
    later stage of a manually re-invoked pipeline) doesn't reflect their
    logical pipeline position."""
    name = _unique_step_name("order_override")
    path = git_repo / f"{name}.py"
    path.write_text(
            "from log_tools.setup import runlog_setup\n"
            "with runlog_setup(order=4242):\n"
            '    print("pinned order")\n',
            )

    result = _run_step(path, cwd=git_repo)

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, name) == 4242


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_script_id_override(git_repo: Path) -> None:
    """An explicit `script_id=` wins over the filename-derived default --
    needed when one shared script self-registers multiple distinct
    identities (e.g. one call per cohort)."""
    name = _unique_step_name("filename_stem")
    override_id = _unique_step_name("overridden_id")
    path = git_repo / f"{name}.py"
    path.write_text(
            "from log_tools.setup import runlog_setup\n"
            f'with runlog_setup(script_id="{override_id}"):\n'
            '    print("overridden id")\n',
            )

    result = _run_step(path, cwd=git_repo)

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    assert _order_of(text, override_id) > 0
    assert f"] {name}" not in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_stale_order_state_is_discarded(git_repo: Path) -> None:
    """An order-state file older than the TTL is treated as a dead run
    and the counter restarts, rather than continuing a stale sequence."""
    from log_tools.setup import Constants, _order_state_path

    name = _unique_step_name("stale")
    script = _write_step_script(git_repo, name, 'print("fresh start")')

    state_path = _order_state_path(os.getpid())
    old_created_at = time.time() - (Constants.ORDER_STATE_TTL_SECONDS + 60)
    state_path.write_text(
            f"CREATED_AT={old_created_at}\n"
            f"NEXT_ORDER=9999\n"
            "some_stale_id=9990\n",
            )

    result = _run_step(script, cwd=git_repo)

    assert result.returncode == 0, result.stderr
    text = (git_repo / "RUN_LOG.md").read_text()
    order = _order_of(text, name)
    assert order == Constants.ORDER_STEP
