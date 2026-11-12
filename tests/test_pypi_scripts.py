"""End-to-end tests for `resources/pypi/upload_test.sh` and `upload.sh`.

Each script is copied into a fake repo under `tmp_path` (it `cd`s to its
own `../..`), and a stub `python` on `PATH` records every call instead
of building or uploading. Nothing touches the real repo or the network.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPI_DIR = REPO_ROOT / "resources" / "pypi"
STUB_PYTHON = """#!/usr/bin/env bash
echo "$*" >> "${CALLS_FILE}"
if [[ "$1 $2" == "-m build" ]]; then
    mkdir -p dist && touch dist/pkg-0.1.0.tar.gz dist/pkg-0.1.0-py3-none-any.whl
fi
if [[ -n "${FAIL_ON:-}" && "$*" == *"${FAIL_ON}"* ]]; then
    exit 1
fi
"""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _run(tmp_path: Path, script: str, fail_on: str = "",
         version: str = "0.1.0") -> tuple[subprocess.CompletedProcess,
                                          list[str], Path]:
    """Run a copied upload script against a stub `python`.

    Parameters
    ----------
    tmp_path : `pathlib.Path`
        Per-test temp dir; becomes the fake repo root.
    script : `str`
        Script file name in `resources/pypi/`.
    fail_on : `str`, optional, default: `""`
        If set, the stub exits 1 for a call containing this text.
    version : `str`, optional, default: `"0.1.0"`
        Content of the fake repo's `VERSION` file (the stub always
        builds `0.1.0` files).

    Returns
    -------
    result : `subprocess.CompletedProcess`
        The finished script run.
    calls : `list` [`str`]
        Argument lines passed to the stub `python`, in order.
    root : `pathlib.Path`
        The fake repo root.
    """
    root = tmp_path / "repo"
    (root / "resources" / "pypi").mkdir(parents=True)
    shutil.copy(PYPI_DIR / script, root / "resources" / "pypi" / script)
    (root / "VERSION").write_text(f"{version}\n")
    (root / "dist").mkdir()
    (root / "dist" / "stale-0.0.1.tar.gz").touch()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python"
    stub.write_text(STUB_PYTHON)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    calls_file = tmp_path / "calls.txt"
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
           "CALLS_FILE": str(calls_file), "FAIL_ON": fail_on}
    result = subprocess.run(
        ["bash", str(root / "resources" / "pypi" / script)],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    calls = (calls_file.read_text().splitlines()
             if calls_file.exists() else [])
    return result, calls, root


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize(("script", "upload_call"), [
    ("upload_test.sh", "-m twine upload --repository testpypi dist/*"),
    ("upload.sh", "-m twine upload dist/*"),
])
def test_builds_checks_then_uploads(tmp_path: Path, script: str,
                                    upload_call: str) -> None:
    """Clean `dist/`, build, `twine check`, then upload to the right index."""
    result, calls, root = _run(tmp_path, script)

    assert result.returncode == 0, result.stderr
    assert len(calls) == 3
    assert calls[0] == "-m build"
    assert calls[1].startswith("-m twine check ")
    assert "stale-0.0.1" not in calls[1]
    upload_files = calls[2].split()[-2:]
    assert all(f.startswith(str(root / "dist")) or f.startswith("dist/")
               for f in upload_files)
    expected_head = upload_call.rsplit(" ", 1)[0]
    assert calls[2].startswith(expected_head)
    assert not (root / "dist" / "stale-0.0.1.tar.gz").exists()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("script", ["upload_test.sh", "upload.sh"])
def test_failed_twine_check_blocks_upload(tmp_path: Path,
                                          script: str) -> None:
    """A failing `twine check` stops the script before any upload."""
    result, calls, _ = _run(tmp_path, script, fail_on="twine check")

    assert result.returncode != 0
    assert not any("twine upload" in call for call in calls)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.skipif(shutil.which("shellcheck") is None,
                    reason="shellcheck not installed")
@pytest.mark.parametrize("script", ["upload_test.sh", "upload.sh"])
def test_shellcheck_clean(script: str) -> None:
    """Both upload scripts pass `shellcheck` with no warnings."""
    result = subprocess.run(["shellcheck", str(PYPI_DIR / script)],
                            capture_output=True, text=True)

    assert result.returncode == 0, result.stdout


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.mark.parametrize("script", ["upload_test.sh", "upload.sh"])
def test_version_mismatch_blocks_upload(tmp_path: Path, script: str) -> None:
    """Built files not matching `VERSION` stop the script before upload."""
    result, calls, _ = _run(tmp_path, script, version="9.9.9")

    assert result.returncode != 0
    assert "9.9.9" in result.stderr
    assert not any("twine upload" in call for call in calls)
