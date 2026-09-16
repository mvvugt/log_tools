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
  ``pip install log_tools``), then call ``log_info``/``log_warn``/
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

Example Pipeline
-----------------

This is a **combined** example. ``resources/examples/pipeline/``
contains a small, runnable example pipeline exercising
``runlog_setup``/``runlog_setup()`` (a bash step and a python step,
both self-registering and using the emitter above) and ``runlog
record`` together. Run it with:

.. code-block:: bash

   ./resources/examples/pipeline/run_pipeline.sh

See ``resources/examples/README.md`` for details.
