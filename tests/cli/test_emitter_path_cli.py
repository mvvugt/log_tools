"""End-to-end tests for the `runlog-emitter-path` CLI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..conftest import REPO_ROOT


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _run_emitter_path_cli() -> subprocess.CompletedProcess[str]:
    """Run `runlog-emitter-path` via `python -m`, install-free."""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    return subprocess.run(
            [sys.executable, "-m", "log_tools.cli.emitter_path"],
            capture_output=True, text=True, env=env,
            )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_prints_path_to_real_readable_emitter_sh() -> None:
    """`runlog-emitter-path` prints a path to a file containing `log_info`."""
    result = _run_emitter_path_cli()

    assert result.returncode == 0, result.stderr
    path = Path(result.stdout.strip())
    assert path.is_file()
    assert "log_info" in path.read_text()
