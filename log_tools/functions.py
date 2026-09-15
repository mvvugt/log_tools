"""
log_tools.functions

Helpers genuinely shared across more than one tool in this package (not a
dumping ground for any single tool's domain logic -- see `log_tools.runlog`
for that).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_git_info(root: Path) -> tuple[str, bool]:
    """Return the short commit hash and dirty flag for a git repo.

    Parameters
    ----------
    root : `Path`
        Path inside (or at the top of) the git working tree.

    Returns
    -------
    commit : `str`
        Short commit hash, or ``"unknown"`` if `root` is not a git repo or
        git is not available.
    dirty : `bool`
        `True` if the working tree has uncommitted changes; `False` if
        clean or unknown.
    """
    try:
        commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                check=True, capture_output=True, text=True,
                ).stdout.strip()
        status = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                check=True, capture_output=True, text=True,
                ).stdout
        return commit, bool(status.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def resolve_git_root(root: Path | None) -> Path:
    """Resolve the git working-tree root, defaulting from cwd.

    Parameters
    ----------
    root : `Path` or `None`
        Explicit root, if already known/given.

    Returns
    -------
    root : `Path`
        `root` unchanged if given, else the result of
        `git rev-parse --show-toplevel` run from cwd.

    Raises
    ------
    RuntimeError
        If `root` is `None` and cwd is not inside a git working tree.
    """
    if root is not None:
        return root
    try:
        top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                check=True, capture_output=True, text=True,
                ).stdout.strip()
        return Path(top)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
                "--root not given and cwd is not inside a git "
                "working tree",
                ) from exc


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically.

    Parameters
    ----------
    path : `Path`
        Destination file path. Parent directories are created if needed.
    content : `str`
        Text to write.

    Notes
    -----
    Writes to a temp file in the same directory as `path`, then moves it
    into place with `os.replace`, so a crash mid-write cannot corrupt the
    destination file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    os.replace(tmp_path, path)
