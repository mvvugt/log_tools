#!/usr/bin/env python3
"""Toy "process" step for the runlog example pipeline.

See ``resources/examples/pipeline/run_pipeline.sh``. Reads the TSV
written by ``steps/fetch_data.sh`` and logs a summary through
``log_tools.emitter``, self-registering its own RUN_LOG.md entry via
``runlog_setup`` (id/order derived automatically; location via
``RUNLOG_LOG_FILE``/``RUNLOG_ROOT``, set once by ``run_pipeline.sh``).
"""
from __future__ import annotations

import csv
import sys

from log_tools.emitter import log_error, log_info
from log_tools.setup import runlog_setup


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main(argv: list[str]) -> int:
    """Sum the ``count`` column of ``<work_dir>/raw_counts.tsv``.

    Parameters
    ----------
    argv : `list[str]`
        Command-line arguments (excluding the program name); expects
        exactly one entry, the work directory produced by
        ``fetch_data.sh``.

    Returns
    -------
    exit_code : `int`
        `0` on success, `1` if the work directory argument is missing.
    """
    if len(argv) != 1:
        log_error("usage: process_data.py WORK_DIR")
        return 1

    with runlog_setup():
        in_path = f"{argv[0]}/raw_counts.tsv"
        log_info(f"Reading {in_path}")
        with open(in_path, newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))

        total = sum(int(row["count"]) for row in rows)
        log_info(f"Processed {len(rows)} samples, total count = {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
