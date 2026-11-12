"""End-to-end packaging test: build the sdist and wheel, inspect contents.

Builds with `python -m build --no-isolation` into `tmp_path`, so it uses
the current environment's setuptools/wheel and needs no network. Skipped
when the `build` package is not installed.
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

pytest.importorskip("build")

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = ("mr_src/", "lipid_src/", "templates/", "graphify-out/")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.fixture(scope="module")
def dist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the sdist and wheel once for this module.

    Parameters
    ----------
    tmp_path_factory : `pytest.TempPathFactory`
        Pytest's session-scoped temp dir factory.

    Returns
    -------
    dist_dir : `pathlib.Path`
        Directory holding exactly one `.tar.gz` and one `.whl`.
    """
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation",
         "--outdir", str(out), str(REPO_ROOT)],
        capture_output=True, text=True)
    assert result.returncode == 0, (
        f"build failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return out


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _one(dist_dir: Path, pattern: str) -> Path:
    """Return the single file in `dist_dir` matching `pattern`.

    Parameters
    ----------
    dist_dir : `pathlib.Path`
        The build output directory.
    pattern : `str`
        Glob pattern, e.g. ``"*.whl"``.

    Returns
    -------
    path : `pathlib.Path`
        The one matching file.
    """
    matches = sorted(dist_dir.glob(pattern))
    assert len(matches) == 1, matches
    return matches[0]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _wheel_names(dist_dir: Path) -> list[str]:
    """List the member names of the built wheel.

    Parameters
    ----------
    dist_dir : `pathlib.Path`
        The build output directory.

    Returns
    -------
    names : `list` [`str`]
        Paths inside the wheel archive.
    """
    with zipfile.ZipFile(_one(dist_dir, "*.whl")) as whl:
        return whl.namelist()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_wheel_ships_shell_files(dist_dir: Path) -> None:
    """`emitter.sh` and `setup.sh` are packaged as data in the wheel."""
    names = _wheel_names(dist_dir)

    assert "log_tools/emitter.sh" in names
    assert "log_tools/setup.sh" in names


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_wheel_version_matches_version_file(dist_dir: Path) -> None:
    """The wheel's METADATA version equals the repo's `VERSION` file."""
    expected = (REPO_ROOT / "VERSION").read_text().strip()
    with zipfile.ZipFile(_one(dist_dir, "*.whl")) as whl:
        meta_name = next(n for n in whl.namelist()
                         if n.endswith(".dist-info/METADATA"))
        meta = Parser().parsestr(whl.read(meta_name).decode())

    assert meta["Version"] == expected
    assert meta["Requires-Python"] == ">=3.9"
    assert "Programming Language :: Python :: 3.14" in meta.get_all(
        "Classifier")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_wheel_has_no_private_or_test_files(dist_dir: Path) -> None:
    """Only the `log_tools` package (plus dist-info) goes into the wheel."""
    names = _wheel_names(dist_dir)
    bad = [n for n in names
           if n.startswith(PRIVATE_PREFIXES + ("tests/",))]

    assert bad == []
    assert all(n.startswith(("log_tools/", "log_tools-")) for n in names)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_sdist_has_no_private_files(dist_dir: Path) -> None:
    """The sdist carries no untracked private dirs or handoff notes."""
    with tarfile.open(_one(dist_dir, "*.tar.gz")) as sdist:
        names = [n.split("/", 1)[1] for n in sdist.getnames() if "/" in n]
    bad = [n for n in names
           if n.startswith(PRIVATE_PREFIXES) or n.endswith("handoff.md")]

    assert bad == []
    assert "log_tools/setup.sh" in names
    assert "log_tools/emitter.sh" in names
