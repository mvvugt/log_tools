"""Unit tests for `log_tools.functions`."""
from __future__ import annotations

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from log_tools.functions import atomic_write, get_git_info

from .conftest import commit_hash, make_dirty, make_non_script_dirty


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_git_info_non_repo_returns_unknown(tmp_path: Path) -> None:
    """A directory outside any git working tree resolves to (unknown, False)."""
    commit, dirty = get_git_info(tmp_path)

    assert commit == "unknown"
    assert dirty is False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_git_info_clean_repo(git_repo: Path) -> None:
    """A clean repo resolves the real short commit hash and dirty=False."""
    commit, dirty = get_git_info(git_repo)

    assert commit == commit_hash(git_repo)
    assert dirty is False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_git_info_dirty_repo(git_repo: Path) -> None:
    """An uncommitted change to a tracked script file is reported as dirty."""
    make_dirty(git_repo)

    commit, dirty = get_git_info(git_repo)

    assert commit == commit_hash(git_repo)
    assert dirty is True


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_git_info_non_script_change_not_dirty(git_repo: Path) -> None:
    """An uncommitted change to a non-script file is not reported as dirty.

    Regression test: without filtering by extension, a project's own
    run-log file (e.g. `RUN_LOG.md`) being rewritten every run would
    permanently flag every subsequent run as dirty.
    """
    make_non_script_dirty(git_repo)

    commit, dirty = get_git_info(git_repo)

    assert commit == commit_hash(git_repo)
    assert dirty is False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_get_git_info_dirty_repo_untracked_script(git_repo: Path) -> None:
    """A new, untracked script file is reported as dirty."""
    (git_repo / "new_script.py").write_text("print('hi')\n")

    _, dirty = get_git_info(git_repo)

    assert dirty is True


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    """Missing parent directories are created."""
    target = tmp_path / "nested" / "dir" / "out.md"

    atomic_write(target, "content")

    assert target.read_text() == "content"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_overwrites_existing_file(tmp_path: Path) -> None:
    """A pre-existing file at the destination is fully replaced."""
    target = tmp_path / "out.md"
    target.write_text("old")

    atomic_write(target, "new")

    assert target.read_text() == "new"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_leaves_no_tmp_file(tmp_path: Path) -> None:
    """The temp file used for the atomic swap is not left behind."""
    target = tmp_path / "out.md"

    atomic_write(target, "content")

    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_concurrent_writers_do_not_crash(tmp_path: Path) -> None:
    """Many concurrent writers to one path (e.g. SGE array tasks sharing
    RUN_LOG.md) raise nothing, leave no temp files, and the result is
    one writer's complete payload, never a mix."""
    target = tmp_path / "RUN_LOG.md"
    payloads = [f"writer {i}\n" * 2000 for i in range(16)]

    def _write_many(payload: str) -> None:
        """Write `payload` to `target` repeatedly."""
        for _ in range(25):
            atomic_write(target, payload)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(_write_many, payloads))

    assert target.read_text() in payloads
    assert list(tmp_path.glob("*.tmp")) == []


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_preserves_existing_mode(tmp_path: Path) -> None:
    """Replacing an existing file keeps its permission bits."""
    target = tmp_path / "out.md"
    target.write_text("old")
    target.chmod(0o640)

    atomic_write(target, "new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o640


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_atomic_write_new_file_follows_umask(tmp_path: Path) -> None:
    """A newly created file gets the usual `0o666 & ~umask` mode, not
    the owner-only mode of a raw temp file."""
    target = tmp_path / "out.md"
    old_umask = os.umask(0o022)
    try:
        atomic_write(target, "content")
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(target.stat().st_mode) == 0o644
