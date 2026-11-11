"""
End-to-end tests for the `runlog` CLI (`log_tools.cli.runlog`).

Each test invokes the real CLI as a subprocess (see `run_cli` in
`tests.conftest`) rather than calling internal functions directly, so
these exercise argument parsing and process wiring, not just domain logic.
"""
from __future__ import annotations

from pathlib import Path

from ..conftest import REPO_ROOT, commit_hash, run_cli


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_text_writes_log(git_repo: Path) -> None:
    """`record --text` upserts an entry into the given `--log-file`."""
    log_file = git_repo / "RUN_LOG.md"

    result = run_cli(
            [
                    "record", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--text", "hello from cli",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 0, result.stderr
    text = log_file.read_text()
    assert "s1" in text
    assert "hello from cli" in text
    assert commit_hash(git_repo) in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_stdin_writes_log(git_repo: Path) -> None:
    """`record --stdin` reads the recorded text from stdin."""
    log_file = git_repo / "RUN_LOG.md"

    result = run_cli(
            [
                    "record", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--stdin",
                    ],
            cwd=git_repo, input="piped output\n",
            )

    assert result.returncode == 0, result.stderr
    assert "piped output" in log_file.read_text()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_streams_output_and_propagates_exit_code(git_repo: Path) -> None:
    """`run -- CMD` streams the child's stdout live and records it, and the
    CLI process exits with the child's exit code."""
    log_file = git_repo / "RUN_LOG.md"

    result = run_cli(
            [
                    "run", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--", "python3", "-c",
                    "print('streamed'); import sys; sys.exit(7)",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 7
    assert "streamed" in result.stdout
    text = log_file.read_text()
    assert "streamed" in text
    assert "- status: failed" in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_include_pattern_filters_recorded_text(git_repo: Path) -> None:
    """`--include-pattern` on `record` filters non-matching lines before
    writing."""
    log_file = git_repo / "RUN_LOG.md"

    result = run_cli(
            [
                    "record", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--include-pattern", r"^\[[A-Za-z]+\]",
                    "--text", "[info] kept\nnoise dropped",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 0, result.stderr
    output_block = log_file.read_text().split("Output:")[-1]
    assert "[info] kept" in output_block
    assert "noise dropped" not in output_block


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_records_only_emitter_output_via_bash(git_repo: Path) -> None:
    """A bash script sourcing emitter.sh has only its log_* lines recorded,
    a plain `echo` is not, and a `no-record` call is excluded while a
    plain `log_error` in the same script is always included."""
    log_file = git_repo / "RUN_LOG.md"
    emitter_sh = REPO_ROOT / "log_tools" / "emitter.sh"
    script = (
            f'source "{emitter_sh}"; '
            'log_info "kept"; '
            'log_info "excluded" no-record; '
            'echo "plain echo not recorded"; '
            'log_error "always kept"'
            )

    result = run_cli(
            [
                    "run", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--", "bash", "-c", script,
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 0, result.stderr
    output_block = log_file.read_text().split("Output:")[-1]
    assert "kept" in output_block
    assert "always kept" in output_block
    assert "excluded" not in output_block
    assert "plain echo not recorded" not in output_block


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_with_no_command_is_a_usage_error(git_repo: Path) -> None:
    """`run` with nothing after `--` is rejected by argument parsing."""
    result = run_cli(
            [
                    "run", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 2
    assert "no command given" in result.stderr


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_default_root_resolved_from_cwd_git_repo(git_repo: Path) -> None:
    """Omitting `--root` resolves it via `git rev-parse --show-toplevel`."""
    result = run_cli(
            ["record", "--id", "s1", "--order", "0", "--text", "hi"],
            cwd=git_repo,
            )

    assert result.returncode == 0, result.stderr
    default_log = git_repo / "RUN_LOG.md"
    assert default_log.is_file()
    assert "hi" in default_log.read_text()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_failed_flag_skips_diff_and_marks_status(
        git_repo: Path,
        ) -> None:
    """`record --failed` renders `- status: failed` and skips the diff
    against the previous successful run, matching `run`'s own failure
    handling."""
    log_file = git_repo / "RUN_LOG.md"
    common = [
            "record", "--id", "s1", "--order", "0",
            "--root", str(git_repo), "--log-file", str(log_file),
            ]

    result = run_cli(common + ["--text", "first ok run"], cwd=git_repo)
    assert result.returncode == 0, result.stderr

    result = run_cli(
            common + ["--failed", "--text", "boom"], cwd=git_repo,
            )
    assert result.returncode == 0, result.stderr

    text = log_file.read_text()
    assert "- status: failed" in text
    assert "boom" in text
    assert "```diff" not in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_without_failed_flag_defaults_to_success(
        git_repo: Path,
        ) -> None:
    """Omitting `--failed` preserves the existing default (non-failed)
    behaviour -- a diff is still rendered against a prior run."""
    log_file = git_repo / "RUN_LOG.md"
    common = [
            "record", "--id", "s1", "--order", "0",
            "--root", str(git_repo), "--log-file", str(log_file),
            ]

    run_cli(common + ["--text", "line one"], cwd=git_repo)
    result = run_cli(common + ["--text", "line two"], cwd=git_repo)

    assert result.returncode == 0, result.stderr
    text = log_file.read_text()
    assert "- status: failed" not in text
    assert "```diff" in text


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_missing_root_outside_git_repo_errors(tmp_path: Path) -> None:
    """Without `--root` and outside any git working tree, the CLI exits
    with a clear error instead of guessing."""
    non_repo_dir = tmp_path / "not_a_repo"
    non_repo_dir.mkdir()

    result = run_cli(
            ["record", "--id", "s1", "--order", "0", "--text", "hi"],
            cwd=non_repo_dir,
            )

    assert result.returncode != 0
    assert "not inside a git working tree" in result.stderr


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_run_keeps_child_exit_code_when_record_fails(git_repo: Path) -> None:
    """`run` returns the child's exit code even if recording fails (the
    log file's parent is a regular file), warning instead of crashing."""
    blocker = git_repo / "not_a_dir"
    blocker.write_text("")

    result = run_cli(
            [
                    "run", "--id", "s1", "--order", "0",
                    "--root", str(git_repo),
                    "--log-file", str(blocker / "RUN_LOG.md"),
                    "--", "python3", "-c", "import sys; sys.exit(5)",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 5
    assert "Traceback" not in result.stderr
    assert "'s1' finished with exit code 5" in result.stderr
    assert "NOT recorded" in result.stderr


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_record_failure_exits_nonzero_with_error(git_repo: Path) -> None:
    """`record` itself reports a failed write as a clean error, exit 1."""
    blocker = git_repo / "not_a_dir"
    blocker.write_text("")

    result = run_cli(
            [
                    "record", "--id", "s1", "--order", "0",
                    "--root", str(git_repo),
                    "--log-file", str(blocker / "RUN_LOG.md"),
                    "--text", "hello",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "[ERROR]" in result.stderr
    assert "NOT recorded" in result.stderr
    assert "own results are unaffected" in result.stderr
