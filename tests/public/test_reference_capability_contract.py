from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from calm.interface.energy.contract import UnsupportedReferenceWorkflowError
from calm.project.application.followups.reference_energy import (
    _count_formula_units,
    _interface_alpha,
)
from calm.public.errors import (
    UnsupportedReferenceWorkflowError as PublicUnsupportedReferenceWorkflowError,
)
from calm.public.project import Project
from calm.public.inputs.settings import EnergyConvention, ReferenceEnergyCapability


ROOT = Path(__file__).resolve().parents[2]


def _convention(formula: str) -> EnergyConvention:
    return EnergyConvention(formula=formula, n_interfaces=2)


def test_reference_capability_contract_is_formula_specific() -> None:
    excess = _convention("interface_excess_strained_bulk").reference_capability()
    assert isinstance(excess, ReferenceEnergyCapability)
    assert excess.calculated_references_supported
    assert not excess.manual_references_required
    assert excess.reference_kinds == ("strained_bulk_a", "strained_bulk_b")
    assert "n_formula_units_a" in excess.manual_reference_fields
    assert any("non-stoichiometric" in value for value in excess.limitations)

    separation = _convention(
        "work_of_separation_unrelaxed_surfaces"
    ).reference_capability()
    assert separation.calculated_references_supported
    assert separation.reference_kinds == (
        "isolated_surface_a",
        "isolated_surface_b",
    )
    assert any("unrelaxed" in value for value in separation.limitations)

    adhesion = _convention(
        "work_of_adhesion_relaxed_surfaces"
    ).reference_capability()
    assert adhesion.calculated_references_supported
    assert not adhesion.manual_references_required
    assert adhesion.reference_kinds == (
        "relaxed_surface_a",
        "relaxed_surface_b",
    )
    assert adhesion.manual_reference_fields == (
        "surface_a_total_energy_eV",
        "surface_b_total_energy_eV",
    )
    assert "first-class calculated references" in adhesion.summary()


def test_relaxed_adhesion_formula_is_first_class() -> None:
    assert PublicUnsupportedReferenceWorkflowError is UnsupportedReferenceWorkflowError
    capability = _convention(
        "work_of_adhesion_relaxed_surfaces"
    ).reference_capability()
    capability.raise_for_calculated_references()
    assert capability.reference_kinds == (
        "relaxed_surface_a",
        "relaxed_surface_b",
    )


def test_surface_relaxation_control_is_scoped_to_reference_workflow() -> None:
    reference_parameters = inspect.signature(
        Project.evaluate_reference_energies
    ).parameters
    relaxation_parameters = inspect.signature(Project.relax_interfaces).parameters

    assert "surface_relaxation" in reference_parameters
    assert "surface_relaxation" not in relaxation_parameters


def test_calculated_reference_preconditions_use_typed_capability_errors() -> None:
    class _Atoms:
        def get_chemical_symbols(self):
            return ["A", "A", "B"]

    with pytest.raises(
        UnsupportedReferenceWorkflowError,
        match="non-stoichiometric reservoir terms",
    ):
        _count_formula_units(
            _Atoms(),
            {"A": 1, "B": 1},
            label="interface side A",
        )

    class _Interface:
        strain_alpha = 0.5
        params = {"relaxation_settings": {"relax_cell": True}}

    assert _interface_alpha(_Interface()) == 0.5


def test_greenfield_contract_assigns_reference_capability_documentation() -> None:
    example = (ROOT / "examples" / "08_evaluate_interface_energetics.py").read_text(
        encoding="utf-8"
    )
    documentation = json.loads(
        (ROOT / "engineering" / "architecture" / "current-documentation-site.json").read_text(
            encoding="utf-8"
        )
    )
    requirement = documentation["content_requirements"]["reference_capabilities"]

    assert "convention.reference_capability()" in example
    assert "capability.raise_for_calculated_references()" in example
    assert requirement["owners"] == [
        "reference/supported-scope.md",
        "reference/calculator-support.md",
    ]
    assert requirement["source"] == "runtime EnergyConvention.reference_capability()"
    assert "work_of_adhesion_relaxed_surfaces" in requirement["must_cover"]
    assert "independently relaxed fixed-cell surfaces" in requirement["must_cover"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    examples_readme = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for summary in (readme, examples_readme):
        assert "manual-only" not in summary
        assert "independently relaxed fixed-cell" in summary
