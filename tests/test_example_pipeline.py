"""
End-to-end test for the example pipeline in
`resources/examples/pipeline/` (see `resources/examples/README.md`).

Unlike the rest of the suite, this exercises the *installed* `runlog`
console script and `runlog-emitter-path` directly -- exactly what the
example script itself does -- rather than `python -m
log_tools.cli.runlog`. It therefore only runs meaningfully once
`log_tools` is installed on `PATH` (e.g. `pip install -e ".[dev]"`,
this repo's documented dev flow) and is skipped otherwise.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from .conftest import REPO_ROOT

PIPELINE_SCRIPT = REPO_ROOT / "resources" / "examples" / "pipeline" / "run_pipeline.sh"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(
        shutil.which("runlog") is None,
        reason="requires `log_tools` installed on PATH (pip install -e .)",
        )
def test_example_pipeline_runs_and_records_all_steps() -> None:
    """`run_pipeline.sh` exits 0 and prints all three recorded step ids."""
    result = subprocess.run(
            [str(PIPELINE_SCRIPT)], capture_output=True, text=True,
            )

    assert result.returncode == 0, result.stderr
    assert "fetch_data" in result.stdout
    assert "process_data" in result.stdout
    assert "pipeline_summary" in result.stdout
    assert "Pipeline finished at" in result.stdout
