"""Repository guardrails for prepared registry evaluation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_KERNEL = ROOT / "calm" / "interface" / "building" / "_kernel.py"
INTERFACE_ENERGY = ROOT / "calm" / "project" / "application" / "followups" / "interface_energy.py"
REGISTRY_SEARCH = ROOT / "calm" / "project" / "application" / "followups" / "registry_search.py"


def test_prepared_interface_owns_translation_independent_geometry() -> None:
    source = BUILD_KERNEL.read_text(encoding="utf-8")

    assert "class PreparedInterfaceStructure" in source
    assert "def prepare_interface_atoms(" in source
    assert "def build_prepared_interface_atoms(" in source
    assert "template_atoms" in source
    assert "prepared.upper_indices" in source
    assert "array.setflags(write=False)" in source


def test_registry_prepares_persistence_calculator_and_area_before_monte_carlo() -> None:
    interface_source = INTERFACE_ENERGY.read_text(encoding="utf-8")
    registry_source = REGISTRY_SEARCH.read_text(encoding="utf-8")

    assert "def prepare_interface_from_prototype_with_strain(" in interface_source
    assert "class _PreparedRegistryEvaluator" in registry_source
    assert "def _prepare_registry_energy_evaluator(" in registry_source
    assert "evaluator = _prepare_registry_energy_evaluator(" in registry_source
    assert "return _registry_energy_density(evaluator, translation)" in registry_source
    energy_body = registry_source.split("def _registry_energy_density(", 1)[1].split(
        "class RegistrySearchOrchestrator", 1
    )[0]
    assert "with uow_context" not in energy_body
    assert "build_prepared_interface_atoms" in energy_body
