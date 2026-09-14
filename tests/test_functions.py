"""Unit tests for `log_tools.functions`."""
from __future__ import annotations

from pathlib import Path

from log_tools.functions import atomic_write, get_git_info

from .conftest import commit_hash, make_dirty


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
    """An uncommitted change to a tracked file is reported as dirty."""
    make_dirty(git_repo)

    commit, dirty = get_git_info(git_repo)

    assert commit == commit_hash(git_repo)
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
