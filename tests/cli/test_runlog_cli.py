"""
End-to-end tests for the `runlog` CLI (`log_tools.cli.runlog`).

Each test invokes the real CLI as a subprocess (see `run_cli` in
`tests.conftest`) rather than calling internal functions directly, so
these exercise argument parsing and process wiring, not just domain logic.
"""
from __future__ import annotations

from pathlib import Path

from ..conftest import commit_hash, git_repo, run_cli  # noqa: F401 (fixture)


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
def test_tagged_only_filters_recorded_text(git_repo: Path) -> None:
    """`--tagged-only` on `record` filters non-tagged lines before writing."""
    log_file = git_repo / "RUN_LOG.md"

    result = run_cli(
            [
                    "record", "--id", "s1", "--order", "0",
                    "--root", str(git_repo), "--log-file", str(log_file),
                    "--tagged-only", "--text", "[info] kept\nnoise dropped",
                    ],
            cwd=git_repo,
            )

    assert result.returncode == 0, result.stderr
    text = log_file.read_text()
    assert "[info] kept" in text
    assert "noise dropped" not in text


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
