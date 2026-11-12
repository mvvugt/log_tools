log_tools
=========

A small, stdlib-only package for logging/pipeline-tracking tools. It
contains two things: the **emitter**, a tagged Python/Bash logger, and
**runlog**, which upserts each pipeline script's run into one compact,
project-wide Markdown log. The emitter integrates with runlog to
capture its calls into that same log across a whole pipeline.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   usage
   examples
   api
