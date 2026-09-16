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

DIRTY_CHECK_EXTENSIONS: tuple[str, ...] = (".py", ".sh")
"""File extensions that count towards `get_git_info`'s dirty flag."""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _is_script_status_line(line: str) -> bool:
    """Whether a `git status --porcelain` line's path is a script file.

    Parameters
    ----------
    line : `str`
        One non-empty line from ``git status --porcelain`` output, e.g.
        ``" M foo.py"`` or ``"R  old.py -> new.sh"``.

    Returns
    -------
    is_script : `bool`
        `True` if the line's path (the rename destination, if a rename)
        ends with one of `DIRTY_CHECK_EXTENSIONS`.
    """
    path = line[3:].split(" -> ")[-1].strip().strip('"')
    return path.endswith(DIRTY_CHECK_EXTENSIONS)


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
        `True` if a tracked or untracked script file (`.py`/`.sh`, see
        `DIRTY_CHECK_EXTENSIONS`) has uncommitted changes; `False`
        otherwise (including when only non-script files, e.g. a run-log
        Markdown file rewritten by this very tool, are uncommitted --
        without this filter, that self-rewrite would permanently flag
        every subsequent run as dirty).
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
        dirty = any(
                _is_script_status_line(line)
                for line in status.splitlines() if line.strip()
                )
        return commit, dirty
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
