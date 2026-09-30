"""Content contracts for the greenfield documentation home and install pages."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib

from calm.calculators.registry import default_registry


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
HOME = DOCS / "index.md"
INSTALL = DOCS / "install.md"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
STUB_MARKER = "Greenfield reconstruction:"


def _headings(path: Path) -> list[str]:
    return [
        line[3:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_home_and_install_pages_are_complete_and_follow_the_contract() -> None:
    contract = _contract()
    assert _headings(HOME) == contract["page_anatomy"]["home"]
    assert _headings(INSTALL) == contract["page_anatomy"]["install"]
    minimum_words = {HOME: 650, INSTALL: 900}
    for path in (HOME, INSTALL):
        text = path.read_text(encoding="utf-8")
        assert STUB_MARKER not in text
        assert "calm-lede" in text
        assert "```" in text
        assert len(text.split()) >= minimum_words[path]


def test_home_routes_every_reader_mode_and_states_scientific_boundaries() -> None:
    text = HOME.read_text(encoding="utf-8")
    for target in (
        "learn/first-interface.md",
        "use/projects.md",
        "understand/surface-models.md",
        "reference/public-api.md",
        "reference/supported-scope.md",
        "install.md",
    ):
        assert target in text
    for phrase in (
        "calculator-free",
        "constructed and unrelaxed",
        "does not infer",
        "does not prove",
        "scientifically suitable",
        "All supported imports originate from `calm`",
    ):
        assert phrase in text
    assert "assets/figures/site/calm-workflow-map.svg" in text
    assert text.count("calm-workflow-map.svg") == 2


def test_install_page_matches_supported_python_and_dependency_layers() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    text = INSTALL.read_text(encoding="utf-8")
    assert pyproject["project"]["requires-python"] == ">=3.10,<3.13"
    for token in (
        "Python 3.10–3.12",
        "**Base**",
        "**Science**",
        "**Calculator provider**",
        "python -m pip install -e .",
        'python -m pip install -e ".[science]"',
        "environments/calm-science.yml",
        "--profile base",
        "--profile science",
    ):
        assert token in text
    assert "pip install calm" in text
    assert "not yet a supported installation instruction" in text
    assert "conda-recipe/" not in text


def test_install_page_tracks_every_registered_provider_and_work_directory_rule() -> None:
    text = INSTALL.read_text(encoding="utf-8")
    families = default_registry().families()
    assert families == ("ase", "chgnet", "grace", "lammps", "mace")
    for family in families:
        assert f"`{family}`" in text
        assert f"--provider {family}" in text
    assert "examples/work/first-interface" in text
    assert "examples/work/refine-relax-evaluate" in text
    assert "--work-dir calm-" not in text


def test_public_entry_pages_contain_no_phase_or_reconstruction_language() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "README.md", HOME, INSTALL, DOCS / "reference/calculator-support.md")
    )
    lowered = combined.lower()
    for phrase in (
        "greenfield reconstruction",
        "final g8",
        "remain the final g8 writing scope",
        "will provide the final user installation paths",
    ):
        assert phrase not in lowered


def test_install_commands_use_the_active_python_interpreter() -> None:
    text = INSTALL.read_text(encoding="utf-8")
    assert "python -m pip" in text
    assert "pip install -e" not in text.replace("python -m pip install -e", "")
    assert sys.version_info.major == 3
