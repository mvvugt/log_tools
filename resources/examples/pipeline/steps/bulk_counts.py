#!/usr/bin/env python3
"""Toy high-cardinality-loop step for the runlog example pipeline.

Mirrors the per-file loop in ``mrsrc/extract_results.sh``, but actually
exercises ``log_count``/``log_count_summary``: rather than emitting one
``log_info`` row per synthetic "file" (which would bloat the recorded
output with near-identical lines), each iteration only increments an
in-process counter, and one summary line per outcome is recorded after
the loop. Self-registers via ``runlog_setup()``.
"""
from __future__ import annotations

import sys

from log_tools.emitter import log_count, log_count_summary, log_info
from log_tools.setup import runlog_setup


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main(argv: list[str]) -> int:
    """Pretend to process a batch of files, recording only a summary.

    Parameters
    ----------
    argv : `list[str]`
        Unused; accepted for a consistent step-script signature.

    Returns
    -------
    exit_code : `int`
        Always `0`.
    """
    del argv
    with runlog_setup():
        toy_files = [f"sample_{i}.tsv" for i in range(1, 11)]
        log_info(f"Processing {len(toy_files)} files")
        for name in toy_files:
            if name.endswith("_9.tsv"):
                log_count("files_failed")
            else:
                log_count("files_ok")
        log_count_summary("files_ok", label="files processed")
        log_count_summary("files_failed", label="files failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
