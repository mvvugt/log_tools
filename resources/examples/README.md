# Example code

This directory holds runnable examples for `log_tools`.

## `pipeline/`

A small, self-contained example pipeline demonstrating real `runlog`
usage end to end: a bash "fetch" step and a python "process" step, each
self-registering its own `RUN_LOG.md` entry via `runlog_setup`/
`runlog_setup()` (id/order derived automatically from the step itself,
recording through the `log_tools` emitter), plus a plain `runlog
record` step for output that's already in hand.

To run it (after `pip install -e .` from the repo root, so `runlog`,
`runlog-setup-path`, and `runlog-emitter-path` are on `PATH`):

```bash
./resources/examples/pipeline/run_pipeline.sh
```

It writes its own throwaway `RUN_LOG.md` under a temp directory (never
the real project log) and prints it at the end, so running the script
is a complete demonstration by itself. See
`resources/examples/pipeline/run_pipeline.sh` and
`resources/examples/pipeline/steps/` for the source.

## Notebooks

This directory will also contain example Jupyter notebooks that users
can use to learn the API. Please note, the notebooks are also built
into the documentation (via `nbsphinx`/`nbsphinx-link`, see
`resources/ci_cd/sphinx.txt`), so should not contain __any__
identifiable data. Use dummy or synthetic data if you want to
illustrate examples with identifiable data.

No example notebooks exist yet -- this exists so the convention is in
place once there's real content to walk through.
