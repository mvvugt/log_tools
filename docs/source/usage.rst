Usage Guide
===========

``runlog`` provides two subcommands. ``run`` wraps a command: runs it,
streams its output live, captures it, and records it -- the exit code is
passed through unchanged. ``record`` is the primitive underneath ``run``,
for when the output text is already in hand.

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

Producing Recorded Output
--------------------------

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
