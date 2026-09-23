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

PIPELINE_SCRIPT = (
        REPO_ROOT / "resources" / "examples" / "pipeline" / "run_pipeline.sh"
        )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(
        shutil.which("runlog") is None,
        reason="requires `log_tools` installed on PATH (pip install -e .)",
        )
def test_example_pipeline_runs_and_records_all_steps() -> None:
    """`run_pipeline.sh` exits 0 and prints every recorded step id."""
    result = subprocess.run(
            [str(PIPELINE_SCRIPT)], capture_output=True, text=True,
            )

    assert result.returncode == 0, result.stderr
    for step_id in (
            "fetch_data", "process_data", "prepare_stages", "bulk_counts",
            "external_tool", "flaky_step", "cluster_job_cohort_a",
            "cluster_job_cohort_b", "pipeline_summary",
            ):
        assert step_id in result.stdout, step_id
    assert "Pipeline finished at" in result.stdout


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(
        shutil.which("runlog") is None,
        reason="requires `log_tools` installed on PATH (pip install -e .)",
        )
def test_example_pipeline_demonstrates_diffing_features() -> None:
    """`run_pipeline.sh` prints a content diff, a stage-scoped diff (only
    the changed stage), a log_count summary, and an error-resolved note."""
    result = subprocess.run(
            [str(PIPELINE_SCRIPT)], capture_output=True, text=True,
            )

    assert result.returncode == 0, result.stderr
    assert "changes vs previous run of 'fetch_data'" in result.stdout
    assert "stage `build`:" in result.stdout
    # `validate`'s content is unchanged across runs -- only its emitter
    # timestamps differ -- so it must not be diffed.
    assert "stage `validate`:" not in result.stdout
    assert "files processed: 9" in result.stdout
    assert "files failed: 1" in result.stdout
    assert "error resolved" in result.stdout
    assert "RESULT: 3 chunks processed" in result.stdout

    # -i/--include-pattern kept external_tool's noisy raw lines out of
    # its recorded RUN_LOG.md section, even though runlog run still
    # streamed them live to stdout above.
    section_start = result.stdout.index("## [45] external_tool")
    section_end = result.stdout.index("## [50] flaky_step", section_start)
    section = result.stdout[section_start:section_end]
    assert "RESULT: 3 chunks processed" in section
    assert "reading config (ignore this)" not in section
