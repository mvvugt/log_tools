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
   * - ``-t``, ``--tagged-only``
     - Only record lines matching an ``[info]``/``[warn]``/``[error]``/
       ``[debug]`` tag.

``run`` Arguments
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Argument
     - Description
   * - ``command``
     - Command and arguments to run, after ``--``.

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
