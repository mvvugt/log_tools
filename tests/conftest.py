"""
Shared pytest fixtures for the `log_tools` test suite.

Tests exercise real `git` subprocesses against throwaway temp repos rather
than mocking git, per this project's testing standards (tests independent
of the code under test, not a re-implementation of its assumptions).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in `cwd`, raising on failure."""
    return subprocess.run(
            ["git", *args], cwd=cwd, check=True,
            capture_output=True, text=True,
            )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with one committed file, `tracked.txt`.

    Returns
    -------
    root : `Path`
        The repo's working-tree root (== `tmp_path`).
    """
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.name", "Test User", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    (tmp_path / "tracked.txt").write_text("hello\n")
    _git("add", "tracked.txt", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)
    return tmp_path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def commit_hash(root: Path) -> str:
    """Return the short commit hash for `root`'s current HEAD."""
    return _git("rev-parse", "--short", "HEAD", cwd=root).stdout.strip()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def make_dirty(root: Path) -> None:
    """Modify the repo's tracked file so `git status` reports it dirty."""
    (root / "tracked.txt").write_text("changed\n")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def run_cli(
        args: list[str], *, cwd: Path, input: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
    """Run the `runlog` CLI as a subprocess via `python -m`.

    Parameters
    ----------
    args : `list[str]`
        Arguments after the subcommand, e.g. ``["record", "--id", ...]``.
    cwd : `Path`
        Working directory for the subprocess (relevant for default
        ``--root`` resolution).
    input : `str` or `None`, optional
        Text piped to stdin.

    Notes
    -----
    Invoked as ``python -m log_tools.cli.runlog`` with `REPO_ROOT` on
    `PYTHONPATH`, so it exercises the real CLI entry point without
    requiring the package to be `pip install`-ed into the test
    environment.
    """
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    return subprocess.run(
            [sys.executable, "-m", "log_tools.cli.runlog", *args],
            cwd=cwd, input=input, capture_output=True, text=True, env=env,
            )
