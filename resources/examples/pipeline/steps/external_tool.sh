#!/usr/bin/env bash
# Toy stand-in for a third-party CLI that knows nothing about log_tools
# (no runlog_setup, no emitter calls) -- mirrors ex_src/rv_gen.sh's
# `clinvar-filter`/`marvelous` calls, external tools wrapped from the
# outside via `runlog run` instead of self-registering. Prints a mix of
# noisy progress lines and a couple of "RESULT:"-prefixed lines;
# run_pipeline.sh wraps this with `runlog run -i '^RESULT:'` so only the
# RESULT lines (plus whatever the emitter would have captured -- none,
# here) end up recorded, instead of the full noisy output.
set -euo pipefail

echo "starting up..."
echo "reading config (ignore this)"
for i in 1 2 3; do
    echo "processing chunk ${i}/3"
done
echo "RESULT: 3 chunks processed"
echo "RESULT: 0 errors"
echo "shutting down..."
