"""Check `.bumpversion.cfg` against the files it edits.

bump2version runs `str.format()` on each `search`/`replace` pattern, so
literal braces (e.g. Jinja's `{% ... %}` in `resources/conda/meta.yaml`)
must be doubled. These tests catch a pattern that cannot be formatted
or no longer matches its file, before a release is attempted.
"""
from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = REPO_ROOT / ".bumpversion.cfg"
FILE_SECTION_PREFIX = "bumpversion:file:"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _read_cfg() -> configparser.RawConfigParser:
    """Parse `.bumpversion.cfg` without `%` interpolation.

    Returns
    -------
    cfg : `configparser.RawConfigParser`
        The parsed config, as bump2version reads it.
    """
    cfg = configparser.RawConfigParser()
    cfg.read(CFG_PATH)
    return cfg


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _file_sections() -> list[str]:
    """List the `[bumpversion:file:...]` section names.

    Returns
    -------
    sections : `list` [`str`]
        Section names, one per file bump2version edits.
    """
    return [s for s in _read_cfg().sections()
            if s.startswith(FILE_SECTION_PREFIX)]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("section", _file_sections())
def test_search_pattern_matches_file(section: str) -> None:
    """Each `search` pattern formats cleanly and is found in its file."""
    cfg = _read_cfg()
    current = cfg.get("bumpversion", "current_version")
    search = cfg.get(section, "search", fallback="{current_version}")
    replace = cfg.get(section, "replace", fallback="{new_version}")
    path = REPO_ROOT / section[len(FILE_SECTION_PREFIX):]

    expected = search.format(current_version=current)
    replace.format(new_version="9.9.9")

    assert expected in path.read_text()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(shutil.which("bump2version") is None,
                    reason="bump2version not installed")
def test_bump2version_dry_run_succeeds() -> None:
    """`bump2version --dry-run patch` passes its file checks."""
    result = subprocess.run(
        ["bump2version", "--dry-run", "--allow-dirty", "patch"],
        cwd=REPO_ROOT, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr[-2000:]
