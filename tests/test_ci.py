"""Tests for `.gitlab-ci.yml`: pipeline triggers and the test matrix."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

CI_FILE = Path(__file__).resolve().parents[1] / ".gitlab-ci.yml"
EXPECTED_MATRIX = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]
EXPECTED_RULES = [
    '$CI_PIPELINE_SOURCE == "merge_request_event" && '
    "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME == $CI_DEFAULT_BRANCH",
    "$CI_COMMIT_TAG",
    "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH",
]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@pytest.fixture(scope="module")
def ci_config() -> dict[str, Any]:
    """Load `.gitlab-ci.yml` as a dict.

    Returns
    -------
    config : `dict` [`str`, `Any`]
        The parsed CI configuration.
    """
    with CI_FILE.open() as handle:
        return yaml.safe_load(handle)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _normalise(rule: str) -> str:
    """Collapse runs of whitespace so rule strings compare reliably.

    Parameters
    ----------
    rule : `str`
        A `workflow:rules:if` expression.

    Returns
    -------
    rule : `str`
        The expression with single spaces only.
    """
    return " ".join(rule.split())


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_workflow_rules_limit_pipeline_triggers(
        ci_config: dict[str, Any]) -> None:
    """Pipelines run only for MRs into default, tags and the default branch."""
    rules = ci_config["workflow"]["rules"]
    found = [_normalise(rule["if"]) for rule in rules]

    assert found == [_normalise(rule) for rule in EXPECTED_RULES]
    for rule in rules:
        assert rule.get("when", "always") != "never"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_test_job_python_matrix(ci_config: dict[str, Any]) -> None:
    """The `test` job runs on every supported Python, 3.9 to 3.14."""
    matrix = ci_config["test"]["parallel"]["matrix"]

    assert len(matrix) == 1
    assert matrix[0]["PYTHON_VERSION"] == EXPECTED_MATRIX


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def test_pages_job_default_branch_only(ci_config: dict[str, Any]) -> None:
    """The `pages` deploy job still runs on the default branch only."""
    rules = ci_config["pages"]["rules"]

    assert [_normalise(rule["if"]) for rule in rules] == [
        "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH"]
