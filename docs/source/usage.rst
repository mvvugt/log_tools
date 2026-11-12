Usage Guide
===========

``log_tools`` contains two things: the emitter and ``runlog``. Each
works entirely standalone (see below); the "Producing Recorded Output"
section further down covers how they combine.

Emitter (standalone)
---------------------

The emitter is a tagged logger: ``log_info``/``log_warn``/``log_error``/
``log_debug``. Every call always prints to stdout (info/debug) or
stderr (warn/error), regardless of anything else -- it needs no other
part of ``log_tools`` to be useful.

Python:

.. code-block:: bash

   python -c "from log_tools.emitter import log_info; log_info('hello from python')"

Bash:

.. code-block:: bash

   source "$(runlog-emitter-path)" && log_info "hello from bash"

Refer to README's "Bash-specific installation" section if you encounter
problems.
Both print immediately; nothing is written to disk unless
``RUNLOG_RECORD_FILE`` happens to be set in the environment (see
"Producing Recorded Output" below).

A fifth call, ``log_stage(name)``, marks a stage boundary rather than
logging a message: everything recorded after it, up to the next
``log_stage`` call, is grouped under ``name`` when ``runlog`` later
diffs this id's output against its previous run (see "Stage-Scoped
Diffing" below). It always records and prints like ``log_info``, tagged
``[stage]``.

A sixth pair, ``log_count(key)`` / ``log_count_summary(key)``, batches
high-cardinality events -- e.g. one call per file in a loop -- into a
single recorded summary line instead of one row per event (see "Batched
Summary Counts" below).

``runlog`` (standalone)
------------------------

``runlog`` provides two subcommands. ``run`` wraps a command: runs it,
streams its output live, captures it, and records it -- the exit code is
passed through unchanged. ``record`` is the primitive underneath ``run``,
for when the output text is already in hand. Neither requires the
wrapped/recorded script to use the emitter at all -- a script that
never touches the emitter still gets its full raw output recorded (see
``run``'s ``--raw-on-failure`` and the fallback behaviour described
under "Producing Recorded Output").

Log File Format
---------------

Every recorded id gets exactly one section in ``RUN_LOG.md``, replaced
on each run and sorted by ``--order``:

.. code-block:: text

   ## [20] process_data (`python3 process_data.py /data`)
   - first run: 2026-09-01 09:12:03
   - last run: 2026-09-23 12:47:25
   - commit: `160016e` (dirty)
   - status: failed

   Δ vs previous run (was `9b4110c`):
   ```diff
   ...
   ```

   Output:
   ```text
   ...
   ```

- **Title** -- ``[order] id``, plus the label (for ``runlog run``, the
  wrapped command line) in backticks when there is one.
- **first run** -- set on the first ``record()`` for this id and never
  changed afterwards, including after a failed run. A log written
  before this field existed falls back to that section's ``last run``.
- **last run** -- the time of the latest ``record()`` call.
- **commit** -- the short ``HEAD`` hash of ``--root``'s repository.
  ``(dirty)`` is added only when a ``.py`` or ``.sh`` file (tracked or
  untracked) has uncommitted changes. Changes to other files, such as
  data, notebooks or ``RUN_LOG.md`` itself, do not count (see
  ``DIRTY_CHECK_EXTENSIONS`` in :doc:`api/functions`).
- **status** -- ``- status: failed`` appears only for a failed run.
- **Δ vs previous run** -- only when the output changed since the
  previous run, and never on a failed run. Emitter timestamps are
  ignored when comparing, so a line that only differs in when it was
  logged is not a change; changed lines are still shown with their
  timestamps. The diff is recomputed on
  every ``record()`` and not kept, so it disappears the next time any
  id is recorded.
- **Output** -- what was recorded (see "Producing Recorded Output").

See :doc:`examples` for real sections produced by the example pipeline.

Shared Options
--------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Description
   * - ``--id``
     - Identifier for the step; keys its section in the log (required).
   * - ``--order``
     - Sort key controlling this section's position in the log (required).
   * - ``--root``
     - Git working-tree root used to resolve the commit hash/dirty flag
       (default: resolved via ``git rev-parse --show-toplevel`` from cwd).
       See "Log File Format" for what counts as dirty.
   * - ``--log-file``
     - Log file path (default: ``<root>/RUN_LOG.md``).
   * - ``-i``, ``--include-pattern``
     - Additionally include raw output lines matching this regex in the
       recorded output, on top of whatever the emitter (see below)
       already recorded.

``run`` Arguments
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Description
   * - ``command``
     - Command and arguments to run, after ``--``.
   * - ``--raw-on-failure``
     - On a failed run, also append the full raw captured output as a
       safety net, in case a crash never went through the emitter (e.g.
       an unhandled traceback). Off by default.

``run`` Worked Example
------------------------

``run`` is for a step that isn't a `log_tools`-aware script -- a
third-party CLI you can't add ``runlog_setup``/emitter calls to. Wrap it
from the outside instead. Unlike ``runlog_setup``, ``run`` does not read
``RUNLOG_ROOT``/``RUNLOG_LOG_FILE``, so ``--root``/``--log-file`` are
passed explicitly (matching ``ex_src/rv_gen.sh``'s pattern of wrapping
external tools such as ``clinvar-filter``/``marvelous`` this way,
alongside self-registering steps in the same pipeline):

.. code-block:: bash

   runlog run --id clinvar_filter --order 40 --root "${ROOT}" -- \
       mamba run --no-capture-output -n clinvar-build clinvar-filter \
       "${CLINVAR_DB}" -g "${genes[@]}" -o "${OUT_DIR}/clinvar_variants.tsv"

Since the wrapped tool never touches the emitter, its full raw output is
recorded by default. Add ``-i/--include-pattern`` to instead record only
the lines matching a regex (e.g. a tool's own ``RESULT:``-prefixed
summary lines) out of an otherwise noisy raw output -- see
``resources/examples/pipeline/steps/external_tool.sh`` for a complete
runnable version of this pattern.

``record`` Arguments
---------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Description
   * - ``--text``
     - Output text to record (mutually exclusive with ``--stdin``).
   * - ``--stdin``
     - Read output text to record from stdin.
   * - ``--failed``
     - Mark this run as failed (skips the diff vs the previous run,
       same as ``run`` does on a non-zero exit). Off by default.

Self-Registering (``runlog_setup``)
------------------------------------

An alternative to wrapping a step externally with ``runlog run``: call
``runlog_setup()``/``runlog_setup`` at the step script's own top, and it
registers itself -- no orchestrator ``--id``/``--order`` wrapping needed.

- **``script_id``** is derived from the script's own filename (Python:
  ``Path(sys.argv[0]).stem``; Bash: the calling script's basename).
- **``order``** is derived from a counter scoped to the current
  pipeline run, identified by the calling script's parent PID -- sibling
  steps invoked directly by one orchestrator process share a PPID for
  the run's duration, so no orchestrator changes are needed in the
  common case. Re-registering the same ``script_id`` within the same
  run reuses its existing order.
- **Raw output capture** works the same as ``run``'s
  ``--raw-on-failure`` safety net, but is on by default here (there is
  no flag to opt in for an in-process crash): the script's own
  stdout/stderr are captured so an unhandled exception still leaves the
  full raw output behind.
- **Log file/root location** come from ``RUNLOG_LOG_FILE``/
  ``RUNLOG_ROOT`` environment variables, optionally exported once by an
  orchestrator, falling back to the same git-toplevel/``RUN_LOG.md``
  defaults used elsewhere.

Python:

.. code-block:: python

   from log_tools.setup import runlog_setup
   from log_tools.emitter import log_info

   with runlog_setup():
       log_info("doing work")

Bash:

.. code-block:: bash

   source "$(runlog-setup-path)"
   runlog_setup
   log_info "doing work"

Producing Recorded Output
--------------------------

This section covers **combined** usage -- the emitter and ``runlog``
working together. For either on its own, see the standalone sections
above.

``runlog run`` sets ``RUNLOG_RECORD_FILE`` (a temp file path) in the
child process's environment. Scripts call the official emitter functions
instead of hand-typing tagged prefixes, so what ends up in ``RUN_LOG.md``
is decided by the call itself, not guessed from text shape:

- **Python** -- ``from log_tools.emitter import log_info, log_warn,
  log_error, log_debug``.
- **Bash** -- ``source "$(runlog-emitter-path)"`` (after
  ``pip install runlog-tools``), then call ``log_info``/``log_warn``/
  ``log_error``/``log_debug`` directly.

``log_info``/``log_warn`` record by default (pass ``record=False`` in
Python, or ``"no-record"`` as the second Bash argument, to opt a call
out). ``log_debug`` is the opposite -- off by default, opt in with
``record=True`` / a ``"record"`` second argument. ``log_error`` always
records. If a script never touches the emitter, ``runlog run`` falls
back to recording the full raw captured output, so untouched scripts
keep working unchanged.

Stage-Scoped Diffing
----------------------

By default, ``record()`` diffs a script id's entire recorded output
against its previous run as one blob. That's the wrong granularity for a
script whose single execution has several logically independent
sections -- e.g. one that prepares job configs for several unrelated
job types, only some of which are touched on a given run. A whole-output
diff would show the entire output changing even though only one section
actually did.

Call ``log_stage(name)`` between such sections to opt in to per-stage
diffing:

.. code-block:: bash

   log_stage "prepare"
   log_info "preparing job configs"
   ...
   log_stage "submit"
   log_info "submitting jobs"

``record()`` then diffs each stage independently:

- A stage present in both the previous and current run is diffed on its
  own -- a change in one stage no longer buries a diff in an unrelated
  one.
- A stage that appears for the first time is not diffed at all (there is
  nothing meaningful to diff it against); its content still shows up
  normally under ``Output:``.
- A stage that was present previously but is absent this run gets a
  one-line ``not present this run`` note instead of a diff.

A script that never calls ``log_stage`` is unaffected -- its output is
treated as a single implicit stage and diffed exactly as before.

Batched Summary Counts
-----------------------

A loop that calls ``log_info`` once per item (e.g. once per file) bloats
the recorded output for high-cardinality steps -- ``runlog``'s log ends
up with hundreds of near-identical rows instead of something useful.
Call ``log_count(key)`` in place of ``log_info`` inside the loop, then
``log_count_summary(key)`` once after it to record a single summary line
instead:

.. code-block:: bash

   for f in "${files[@]}"; do
       if process "${f}"; then
           log_count "files_ok"
       else
           log_count "files_failed"
       fi
   done
   log_count_summary "files_ok" "files processed"
   log_count_summary "files_failed" "files failed"

``log_count`` only increments an in-process counter -- it prints and
records nothing by itself. ``log_count_summary`` prints and records one
``"<label or key>: <count>"`` line (like ``log_info``, always recorded),
then resets that key's counter to 0. A key never passed to ``log_count``
summarizes as ``0``.

Failure Handling
------------------

A failed run should never produce a noisy diff against a working
previous run, and a genuine crash should still leave something behind
even if the script never touched the emitter:

- ``runlog run`` marks a run failed automatically on a non-zero exit
  code; ``runlog record --failed`` is the equivalent for output that's
  already in hand (both are what ``runlog_setup`` delegates to
  internally). A failed run's diff against the previous run is skipped
  entirely -- see ``record()``'s ``failed`` parameter.
- ``run``'s ``--raw-on-failure`` (off by default) appends the full raw
  captured output under a divider, as a safety net for a crash that
  never went through the emitter (e.g. an unhandled traceback).
  ``runlog_setup``/``runlog_setup()`` do this unconditionally on
  failure -- there is no flag to opt out, since there's no external
  wrapper to catch the crash otherwise.
- If a script's *previous* run had failed and this run succeeds,
  ``record()`` shows ``- error resolved`` instead of a raw diff of the
  error output disappearing.

``resources/examples/pipeline/steps/flaky_step.sh`` exercises all three:
run it once expecting failure, then again expecting success, via
``resources/examples/pipeline/run_pipeline.sh``.

Cluster / Multi-Submission Pipelines
---------------------------------------

``runlog_setup``'s automatic id/order derivation assumes sibling steps
share a parent process (an orchestrator script invoking them directly).
Two real scenarios break that assumption, both needing the
``RUNLOG_SCRIPT_ID``/``RUNLOG_ORDER`` env var overrides (read by both
Bash and Python ``runlog_setup``) or the ``script_id``/``order``
parameters (Python, see "Self-Registering" above; an explicit parameter
wins over the env var) instead.

.. note::

   Because Python honours the same env vars, an ``export``-ed
   ``RUNLOG_SCRIPT_ID`` in a Bash wrapper is inherited by any Python
   ``runlog_setup`` step the wrapper runs, so both write to the same
   section and the wrapper (whose teardown runs last) overwrites it.
   When a wrapper and its child both self-register, set the wrapper's
   values without ``export`` (e.g. ``RUNLOG_SCRIPT_ID=step_job`` on its
   own line), or pass ``script_id=`` in the child.


- **A script submitted to a batch scheduler** (e.g. SLURM's ``sbatch``):
  its ``$PPID`` at execution time is the scheduler's, not the
  submitting shell's, so the PPID-scoped auto-order counter can't relate
  it to its pipeline siblings. Set ``RUNLOG_ORDER`` explicitly (e.g.
  ``mrsrc/prepare_mr.sh`` does ``export RUNLOG_ORDER=20`` before calling
  ``runlog_setup``).
- **One script invoked multiple times with a distinct logical identity
  each time** (e.g. once per cohort/dataset): the auto-derived,
  basename-based id would collide across calls, silently overwriting one
  call's section with the next. Set ``RUNLOG_SCRIPT_ID`` explicitly per
  call. ``mrsrc/extract_results.sh`` requires its caller to submit it via
  ``sbatch --export=ALL,RUNLOG_SCRIPT_ID=<id>,RUNLOG_ORDER=<n>`` for
  exactly this reason, failing fast if either is unset rather than
  silently falling back to a scheduler-assigned script name.

.. code-block:: bash

   # From an orchestrator submitting the same script twice, e.g. per
   # cohort -- mirrors sbatch --export=ALL,RUNLOG_SCRIPT_ID=...,RUNLOG_ORDER=...
   RUNLOG_SCRIPT_ID=extract_cohort_a RUNLOG_ORDER=70 ./extract_results.sh
   RUNLOG_SCRIPT_ID=extract_cohort_b RUNLOG_ORDER=71 ./extract_results.sh

When several such scripts must run in a fixed order relative to each
other (e.g. a "gather" step that combines every cohort's output),
chain their batch-scheduler submissions with a dependency instead of
relying on wall-clock timing -- ``mrsrc/extract_results_gather.sh`` is
submitted with ``sbatch --dependency=afterok:<extraction job ids>`` so
it only starts once every extraction job it depends on has finished
successfully.

``resources/examples/pipeline/steps/cluster_job.sh`` exercises the
``RUNLOG_SCRIPT_ID``/``RUNLOG_ORDER`` override end to end (without
needing an actual scheduler) via
``resources/examples/pipeline/run_pipeline.sh``.

Example Pipeline
-----------------

This is a **combined** example, and the single place every feature
above is exercised together. ``resources/examples/pipeline/`` contains
a runnable pipeline covering: both emitter styles (standalone calls and
all four levels' recording toggles), ``runlog_setup``/``runlog_setup()``
self-registration, ``runlog run`` wrapping an external tool with
``-i/--include-pattern``, ``runlog record``, ``log_stage``,
``log_count``/``log_count_summary``, the ``RUNLOG_SCRIPT_ID``/
``RUNLOG_ORDER`` overrides, and failure handling (including the "error
resolved" note) -- run twice so real diffs are produced, not just
first-run entries. Run it with:

.. code-block:: bash

   ./resources/examples/pipeline/run_pipeline.sh

See :doc:`examples` for a step-by-step walkthrough with the
``RUN_LOG.md`` output each step produces.
