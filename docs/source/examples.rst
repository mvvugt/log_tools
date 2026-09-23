Examples
========

``resources/examples/pipeline/`` contains one runnable example pipeline
that exercises every ``log_tools`` feature together. This page walks
through each step and shows the ``RUN_LOG.md`` sections it produces.

Running It
----------

Install the package first (``pip install -e .`` from the repo root), so
``runlog``, ``runlog-setup-path`` and ``runlog-emitter-path`` are on
``PATH``. Then run:

.. code-block:: bash

   ./resources/examples/pipeline/run_pipeline.sh

The script writes a throwaway ``RUN_LOG.md`` under a temp directory
(never the real project log) and deletes it on exit. It runs in two
passes:

- **Pass 1** runs every step once, producing first-run entries.
- **Pass 2** re-runs ``fetch_data.sh``, ``process_data.py``,
  ``prepare_stages.sh`` and ``flaky_step.sh`` with slightly changed
  inputs, so real diffs are produced.

Each diff is printed straight after its own step. This is needed
because a diff block is not persisted: the next step's ``record()``
call re-renders the file without it (see ``Entry.diff`` in
:doc:`api/runlog`). The final ``RUN_LOG.md`` printed at the end
therefore contains no diff blocks, by design.

.. note::

   The output below was captured from a real run. The temp directory
   path is shortened to ``<work_dir>`` and long command-line labels to
   ``<repo>/...``; everything else is unchanged. Commit hashes and
   timestamps will differ on your machine.

Steps
-----

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Step
     - Order
     - What it demonstrates
   * - ``fetch_data.sh``
     - 10 (auto)
     - Self-registering Bash step (``runlog_setup``). Uses all four
       emitter levels and the ``no-record``/``record`` toggles.
   * - ``process_data.py``
     - 20 (auto)
     - Self-registering Python step (``runlog_setup()``). Same emitter
       coverage, with the ``record=`` keyword.
   * - ``prepare_stages.sh``
     - 30 (auto)
     - ``log_stage`` splits the output into ``validate`` and ``build``
       stages, diffed separately.
   * - ``bulk_counts.py``
     - 40 (auto)
     - ``log_count``/``log_count_summary`` turn a 10-item loop into
       one summary line per outcome.
   * - ``external_tool.sh``
     - 45
     - A plain script with no ``runlog_setup``, standing in for a
       third-party CLI. Wrapped with ``runlog run -i '^RESULT:'``.
   * - ``flaky_step.sh``
     - 50 (auto)
     - Fails in pass 1 and succeeds in pass 2: failure handling and
       the ``error resolved`` note.
   * - ``cluster_job.sh``
     - 60, 61
     - One script run twice with different ``RUNLOG_SCRIPT_ID``/
       ``RUNLOG_ORDER`` values, as a batch scheduler would.
   * - ``runlog record``
     - 900
     - A one-line ``pipeline_summary`` entry recorded from ``--text``.

"(auto)" means the order comes from the PPID-scoped counter (see
:doc:`usage`, "Self-Registering"). The auto counter starts at 10 and
steps by 10.

Self-Registering Steps (``fetch_data.sh``, ``process_data.py``)
----------------------------------------------------------------

Neither step is told its id or order: both come from ``runlog_setup``.
In pass 2, ``fetch_data.sh`` is asked for 4 samples instead of 3. Its
section straight after that run:

.. code-block:: text

   ## [10] fetch_data
   - first run: 2026-09-23 12:47:23
   - last run: 2026-09-23 12:47:25
   - commit: `160016e`

   Δ vs previous run (was `160016e`):
   ```diff
   @@ -1,3 +1,3 @@
   -[info]  2026-09-23 12:47:23 Fetching toy dataset into <work_dir>/raw_counts.tsv
   -[debug] 2026-09-23 12:47:23 n_samples requested: 3
   -[info]  2026-09-23 12:47:23 Wrote 4 lines to <work_dir>/raw_counts.tsv
   +[info]  2026-09-23 12:47:25 Fetching toy dataset into <work_dir>/raw_counts.tsv
   +[debug] 2026-09-23 12:47:25 n_samples requested: 4
   +[info]  2026-09-23 12:47:25 Wrote 5 lines to <work_dir>/raw_counts.tsv
   ```

   Output:
   ```text
   [info]  2026-09-23 12:47:25 Fetching toy dataset into <work_dir>/raw_counts.tsv
   [debug] 2026-09-23 12:47:25 n_samples requested: 4
   [info]  2026-09-23 12:47:25 Wrote 5 lines to <work_dir>/raw_counts.tsv
   ```

Points to note:

- ``first run`` stays at the pass-1 time; ``last run`` moves on.
- The ``[debug]`` line is recorded because the step opts it in with
  ``record``. Debug lines are not recorded by default.
- A Python step's section title also shows its command line as a
  label, e.g. ``## [20] process_data (`<repo>/.../process_data.py
  <work_dir>`)``.

.. warning::

   **Known limitation: timestamp noise.** Every emitter line starts
   with a timestamp, and diffs currently compare lines including it.
   A re-run in a different second therefore shows *every* line as
   changed. Above, the first line (``Fetching toy dataset ...``) only
   differs by its timestamp. A fix (ignoring the timestamp when
   diffing) is tracked as a follow-up.

Stage-Scoped Diffs (``prepare_stages.sh``)
------------------------------------------

The step calls ``log_stage "validate"`` and ``log_stage "build"``. In
pass 2 it builds 4 artifacts instead of 3, so only ``build`` really
changes. The diff is split per stage:

.. code-block:: text

   ## [30] prepare_stages
   - first run: 2026-09-23 12:47:24
   - last run: 2026-09-23 12:47:25
   - commit: `160016e`

   Δ vs previous run (was `160016e`):
   stage `validate`:
   ```diff
   @@ -1,2 +1,2 @@
   -[info]  2026-09-23 12:47:24 Checking <work_dir> is writable
   -[info]  2026-09-23 12:47:24 Checked expected input files are present
   +[info]  2026-09-23 12:47:25 Checking <work_dir> is writable
   +[info]  2026-09-23 12:47:25 Checked expected input files are present
   ```
   stage `build`:
   ```diff
   @@ -1,4 +1,5 @@
   -[info]  2026-09-23 12:47:24 Building 3 artifact(s)
   -[info]  2026-09-23 12:47:24 Built artifact_1
   -[info]  2026-09-23 12:47:24 Built artifact_2
   -[info]  2026-09-23 12:47:24 Built artifact_3
   +[info]  2026-09-23 12:47:25 Building 4 artifact(s)
   +[info]  2026-09-23 12:47:25 Built artifact_1
   +[info]  2026-09-23 12:47:25 Built artifact_2
   +[info]  2026-09-23 12:47:25 Built artifact_3
   +[info]  2026-09-23 12:47:25 Built artifact_4
   ```

   Output:
   ```text
   [stage] 2026-09-23 12:47:25 validate
   [info]  2026-09-23 12:47:25 Checking <work_dir> is writable
   [info]  2026-09-23 12:47:25 Checked expected input files are present
   [stage] 2026-09-23 12:47:25 build
   [info]  2026-09-23 12:47:25 Building 4 artifact(s)
   [info]  2026-09-23 12:47:25 Built artifact_1
   [info]  2026-09-23 12:47:25 Built artifact_2
   [info]  2026-09-23 12:47:25 Built artifact_3
   [info]  2026-09-23 12:47:25 Built artifact_4
   ```

.. warning::

   The ``validate`` stage should not appear in this diff: its content
   is unchanged apart from timestamps. It shows up only because of the
   timestamp limitation described above. Once that is fixed, only
   ``stage `build`:`` will be listed.

Batched Counts (``bulk_counts.py``)
-----------------------------------

The step loops over 10 fake files, calling ``log_count`` once per file
instead of ``log_info``. Two ``log_count_summary`` calls then record
one line per outcome:

.. code-block:: text

   ## [40] bulk_counts (`<repo>/.../bulk_counts.py`)
   - first run: 2026-09-23 12:47:24
   - last run: 2026-09-23 12:47:24
   - commit: `160016e`

   Output:
   ```text
   [info]  2026-09-23 12:47:24 Processing 10 files
   [info]  2026-09-23 12:47:24 files processed: 9
   [info]  2026-09-23 12:47:24 files failed: 1
   ```

Wrapping an External Tool (``external_tool.sh``)
------------------------------------------------

This script never touches the emitter, so it is wrapped from outside:

.. code-block:: bash

   runlog run --id external_tool --order 45 --root "${root}" \
       --log-file "${log_file}" -i '^RESULT:' -- \
       "${steps_dir}/external_tool.sh"

``runlog run`` does not read ``RUNLOG_ROOT``/``RUNLOG_LOG_FILE``, so
``--root``/``--log-file`` are passed explicitly. The tool prints eight
lines (``starting up...``, ``processing chunk 1/3`` and so on);
``-i '^RESULT:'`` keeps only its two result lines:

.. code-block:: text

   ## [45] external_tool (`<repo>/.../external_tool.sh`)
   - first run: 2026-09-23 12:47:24
   - last run: 2026-09-23 12:47:24
   - commit: `160016e`

   Output:
   ```text
   RESULT: 3 chunks processed
   RESULT: 0 errors
   ```

Failure and Recovery (``flaky_step.sh``)
----------------------------------------

In pass 1 the orchestrator runs ``flaky_step.sh fail || true``. The
step exits non-zero, so its section gets ``- status: failed``, no diff
and, because ``runlog_setup`` always keeps raw output on failure, the
full raw output under a divider. The ``|| true`` only keeps the
orchestrator going under ``set -e``; the failure is recorded either
way.

In pass 2 it succeeds. Instead of a raw diff of the error tail
disappearing, ``record()`` notes ``- error resolved``:

.. code-block:: text

   ## [50] flaky_step
   - first run: 2026-09-23 12:47:24
   - last run: 2026-09-23 12:47:25
   - commit: `160016e`

   Δ vs previous run (was `160016e`):
   - error resolved
   ```diff
   @@ -1,2 +1,2 @@
   -[info]  2026-09-23 12:47:24 attempting the flaky operation (mode=fail)
   -[error] 2026-09-23 12:47:24 flaky operation failed
   +[info]  2026-09-23 12:47:25 attempting the flaky operation (mode=succeed)
   +[info]  2026-09-23 12:47:25 flaky operation succeeded
   ```

   Output:
   ```text
   [info]  2026-09-23 12:47:25 attempting the flaky operation (mode=succeed)
   [info]  2026-09-23 12:47:25 flaky operation succeeded
   ```

``first run`` keeps the time of the failed pass-1 run: a failure still
counts as a run.

Explicit Id/Order Overrides (``cluster_job.sh``)
------------------------------------------------

The same script is run twice, as a batch scheduler would run one job
per cohort:

.. code-block:: bash

   RUNLOG_SCRIPT_ID=cluster_job_cohort_a RUNLOG_ORDER=60 \
       "${steps_dir}/cluster_job.sh" cohort_a
   RUNLOG_SCRIPT_ID=cluster_job_cohort_b RUNLOG_ORDER=61 \
       "${steps_dir}/cluster_job.sh" cohort_b

Without the overrides, both calls would get the same filename-based
id, and the second would overwrite the first. With them, each gets its
own section:

.. code-block:: text

   ## [60] cluster_job_cohort_a
   - first run: 2026-09-23 12:47:24
   - last run: 2026-09-23 12:47:24
   - commit: `160016e`

   Output:
   ```text
   [info]  2026-09-23 12:47:24 Processing dataset 'cohort_a' as cluster_job_cohort_a
   [info]  2026-09-23 12:47:24 Done with 'cohort_a'
   ```

   ## [61] cluster_job_cohort_b
   ...

See :doc:`usage`, "Cluster / Multi-Submission Pipelines", for the
real-world ``sbatch --export=...`` equivalent.

Recording Text Directly (``runlog record``)
-------------------------------------------

The last entry is recorded without running anything, from text already
in hand:

.. code-block:: bash

   runlog record --id pipeline_summary --order 900 --log-file "${log_file}" \
       --text "Pipeline finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

.. code-block:: text

   ## [900] pipeline_summary
   - first run: 2026-09-23 12:47:25
   - last run: 2026-09-23 12:47:25
   - commit: `160016e`

   Output:
   ```text
   Pipeline finished at 2026-09-23T10:47:25Z
   ```
