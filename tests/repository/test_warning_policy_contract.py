from __future__ import annotations

import configparser
from pathlib import Path
import re

import conftest


REPO_ROOT = Path(__file__).resolve().parents[2]

def _pytest_ini_filterwarnings() -> list[str]:
    parser = configparser.ConfigParser()
    parser.read(REPO_ROOT / "pytest.ini")
    raw = parser.get("pytest", "filterwarnings", fallback="")
    return [line.strip() for line in raw.splitlines() if line.strip()]



def test_warning_filters_are_message_specific_and_justified() -> None:
    for rule in conftest.EXPECTED_TEST_WARNING_FILTERS:
        assert rule.action == "ignore"
        assert rule.rule_id
        assert rule.message
        assert rule.message not in {".*", ".+", ""}
        assert len(rule.message) >= 10
        assert rule.reason
        assert rule.tiers
        re.compile(rule.message)


def test_warning_filters_are_selected_only_for_declared_tiers() -> None:
    all_tiers = {tier for rule in conftest.EXPECTED_TEST_WARNING_FILTERS for tier in rule.tiers}

    for tier in all_tiers:
        selected = conftest.warning_filters_for_markers({tier})
        expected = tuple(
            rule for rule in conftest.EXPECTED_TEST_WARNING_FILTERS if tier in rule.tiers
        )
        assert selected == expected

    assert conftest.warning_filters_for_markers({"public", "integration", "repository"}) == ()


def test_warning_filters_have_no_global_tier() -> None:
    for rule in conftest.EXPECTED_TEST_WARNING_FILTERS:
        assert "all" not in rule.tiers
        assert "global" not in rule.tiers


def test_static_pytest_config_treats_unasserted_warnings_as_errors() -> None:
    assert _pytest_ini_filterwarnings() == ["error"]


def test_static_pytest_config_does_not_contain_global_warning_ignores() -> None:
    forbidden_patterns = {
        "ignore::Warning",
        "ignore::DeprecationWarning",
        "ignore::UserWarning",
        "default::Warning",
    }
    filter_lines = _pytest_ini_filterwarnings()

    for line in filter_lines:
        assert line not in forbidden_patterns


def test_warning_filter_identifiers_are_unique() -> None:
    ids = [rule.rule_id for rule in conftest.EXPECTED_TEST_WARNING_FILTERS]
    assert len(ids) == len(set(ids))
