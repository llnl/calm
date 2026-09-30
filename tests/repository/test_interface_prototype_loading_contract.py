"""Repository ownership contract for persisted interface-prototype loading."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "calm" / "project" / "application" / "interface_prototype_payload.py"
INTERFACE_ENERGY = ROOT / "calm" / "project" / "application" / "followups" / "interface_energy.py"
REFERENCE_ENERGY = ROOT / "calm" / "project" / "application" / "followups" / "reference_energy.py"
PROTOTYPE_ANALYSIS = ROOT / "calm" / "project" / "application" / "prototype_analysis.py"
REGISTRY_SEARCH = ROOT / "calm" / "project" / "application" / "followups" / "registry_search.py"


def test_interface_prototypes_have_one_named_current_loader() -> None:
    payload = PAYLOAD.read_text(encoding="utf-8")

    assert "def load_interface_prototype(" in payload
    assert "def _decode_interface_prototype_payload(" in payload
    assert "def _rehydrate_interface_prototype_record(" in payload
    assert "def rehydrate_interface_prototype(" not in payload
    assert "_validate_prototype_record_projections(" in payload
    assert "PairIdentity2D.from_dict" in payload
    assert "MatchSourceProvenance2D.from_dict" in payload


def test_partial_build_payload_interpreters_remain_retired() -> None:
    interface_energy = INTERFACE_ENERGY.read_text(encoding="utf-8")

    for retired in (
        "def _rehydrate_interface_prototype(",
        "def _prototype_interface_components(",
        "def _supercell_recipe_from_payload(",
        "def _prototype_slabs(",
        "def _payload_tuple(",
        "def _metric_float(",
    ):
        assert retired not in interface_energy

    assert "prototype = load_interface_prototype(" in interface_energy
    assert "def _prototype_build_components(" in interface_energy
    assert "prototype.supercell_a.N_tot" in interface_energy
    assert "prototype.supercell_b.N_tot" in interface_energy


def test_energy_registry_and_analysis_consume_loaded_prototypes() -> None:
    interface_energy = INTERFACE_ENERGY.read_text(encoding="utf-8")
    reference_energy = REFERENCE_ENERGY.read_text(encoding="utf-8")
    prototype_analysis = PROTOTYPE_ANALYSIS.read_text(encoding="utf-8")
    registry_search = REGISTRY_SEARCH.read_text(encoding="utf-8")

    strain_body = interface_energy.split(
        "def compute_strain_scan_energy_point(", 1
    )[1].split("def _compute_energy_with_calc(", 1)[0]
    assert strain_body.count("load_interface_prototype(") == 1
    assert "_build_loaded_interface_prototype(" in strain_body
    assert "_compute_strained_bulk_gamma(\n            prototype," in strain_body

    assert "prototype = load_interface_prototype(" in reference_energy
    assert "prototype.supercell_a.N_tot" in reference_energy
    assert "prototype.supercell_b.N_tot" in reference_energy
    assert "prototype.payload" not in reference_energy
    assert "def _extract_supercell_matrix(" not in reference_energy
    assert "def _extract_orthogonal_gauge(" not in reference_energy

    assert "load_interface_prototype(uow, prototype_uid)" in prototype_analysis
    assert "context.prototype.supercell_a.N_tot" in prototype_analysis
    assert "context.prototype.payload" not in prototype_analysis

    assert "prepare_interface_from_prototype_with_strain(" in registry_search
