from __future__ import annotations

import configparser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MARKERS = {
    "arch",
    "calculators",
    "examples",
    "integration",
    "interface",
    "project",
    "public",
    "real_backend",
    "repository",
    "slab",
    "smoke",
    "unit",
}


def _marker_name(marker: str) -> str:
    return marker.split(":", 1)[0].strip()


def _pytest_ini_markers() -> list[str]:
    parser = configparser.ConfigParser()
    parser.read(REPO_ROOT / "pytest.ini")
    raw = parser.get("pytest", "markers", fallback="")
    return [_marker_name(line) for line in raw.splitlines() if line.strip()]


def test_required_pytest_markers_are_declared() -> None:
    markers = _pytest_ini_markers()
    missing = sorted(REQUIRED_MARKERS - set(markers))
    assert missing == [], f"pytest.ini is missing pytest markers: {missing}"


def test_pytest_marker_declarations_are_unique() -> None:
    markers = _pytest_ini_markers()
    assert len(markers) == len(set(markers)), "pytest.ini contains duplicate markers"
