"""Ownership guardrails for the internal package-root relocation."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "calm"


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function(relative: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(_source(relative))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {relative}")


def test_package_root_contains_only_composition_and_public_boundary_modules() -> None:
    root_modules = {
        path.name
        for path in PACKAGE_ROOT.glob("*.py")
    }
    assert root_modules == {
        "__init__.py",
        "_version.py",
        "api.py",
        "exceptions.py",
    }


def test_relocated_contracts_have_explicit_domain_owners_and_consumers() -> None:
    consumers = {
        "calm.structure.standardization": (
            "calm/bulk/provenance.py",
            "calm/symmetry/spglib_adapter.py",
        ),
        "calm.project.domain.contracts.campaign": (
            "calm/project/application/campaigns.py",
            "calm/public/workflows/campaigns.py",
        ),
        "calm.interface.matching.conditioning": (
            "calm/interface/config.py",
            "calm/interface/matching/_surface_orbits.py",
        ),
        "calm.project.domain.contracts.dataset": (
            "calm/project/application/datasets.py",
            "calm/public/inputs/settings.py",
        ),
        "calm.interface.energy.contract": (
            "calm/interface/energy/_kernel.py",
            "calm/public/inputs/settings.py",
        ),
        "calm.interface.refinement.contract": (
            "calm/project/application/followups/strain_scan.py",
            "calm/project/application/followups/registry_search.py",
        ),
        "calm.project.domain.contracts.refinement_result": (
            "calm/project/application/interface_derivation.py",
            "calm/project/infrastructure/db/repos/followups.py",
        ),
        "calm.project.domain.contracts.strain_state": (
            "calm/project/domain/contracts/derived_interface.py",
            "calm/project/application/derived_interfaces.py",
        ),
        "calm.project.domain.contracts.relaxation": (
            "calm/project/application/followups/relaxation.py",
            "calm/project/application/followups/relaxation_backends.py",
        ),
        "calm.project.domain.contracts.relaxed_reference": (
            "calm/project/application/followups/reference_energy.py",
            "calm/project/application/followups/energy_backends.py",
        ),
        "calm.interface.matching.zur_mcgill": (
            "calm/project/application/interface_prototype_payload.py",
            "calm/interface/model.py",
        ),
        "calm.symmetry.surface_group": (
            "calm/interface/results.py",
            "calm/symmetry/spglib_adapter.py",
        ),
        "calm.structure.characterization": (
            "calm/public/records/characterization.py",
            "calm/project/application/slabs.py",
        ),
        "calm.public.presentation.reporting": (
            "calm/public/project.py",
            "calm/public/workflows/energy.py",
        ),
    }
    for module, paths in consumers.items():
        assert all(module in _source(path) for path in paths), module


def test_retired_root_module_paths_are_absent_from_current_python_sources() -> None:
    retired = {
        "calm._bulk_standardization_contract",
        "calm._campaign_contract",
        "calm._conditioning_contract",
        "calm._dataset_contract",
        "calm._derived_interface_contract",
        "calm._energy_contract",
        "calm._energy_result_contract",
        "calm._json_contract",
        "calm._refinement_contract",
        "calm._refinement_result_contract",
        "calm._relaxation_contract",
        "calm._relaxed_reference_contract",
        "calm._slab_record_contract",
        "calm._strain_state_contract",
        "calm._surface_symmetry_group",
        "calm._surface_symmetry_resolver",
        "calm._zur_mcgill_contract",
        "calm.ase_adapter",
        "calm.io",
        "calm.reporting",
        "calm.structure_characterization",
    }
    sources = [
        path.read_text(encoding="utf-8")
        for path in (ROOT / "calm").rglob("*.py")
    ]
    joined = "\n".join(sources)
    for module in retired:
        assert module not in joined


def test_current_json_contract_is_the_shared_strict_serializer() -> None:
    campaign = _source("calm/project/domain/contracts/campaign.py")
    dataset = _source("calm/project/domain/contracts/dataset.py")
    payloads = _source("calm/project/infrastructure/db/payload_helpers.py")
    owner = _source("calm/serialization/json.py")

    for consumer in (campaign, dataset, payloads):
        assert "calm.serialization.json" in consumer
        assert "default=str" not in consumer
    assert "allow_nan=False" in owner
    assert "sort_keys=True" in owner
    assert "unsupported" in owner
    assert "def canonical_json(" not in campaign
    assert "def canonical_json(" not in dataset


def test_campaign_typed_spec_validation_is_reachable_from_public_writer() -> None:
    workflows = _source("calm/public/workflows/campaigns.py")
    campaign = _source("calm/project/domain/contracts/campaign.py")

    assert "validate_typed_campaign_spec(resolved_spec)" in workflows
    assert "json_native(spec)" in campaign
    assert "CAMPAIGN_SPEC_VERSION = 3" in campaign


def test_dataset_contract_is_exact_current_schema_and_split_v2_only() -> None:
    contract = _source("calm/project/domain/contracts/dataset.py")
    settings = _source("calm/public/inputs/settings.py")
    datasets = _source("calm/public/records/datasets.py")

    for retired in (
        "_SCHEMA_ALIASES",
        "DATASET_SPLIT_LEGACY_POLICY_VERSION",
        "DATASET_SPLIT_V1_COMPARISON_POLICY",
        "DATASET_SPLIT_LEGACY_STATUS",
        "DATASET_SPLIT_COMPLETE_V1_STATUS",
        "legacy_split_contract",
    ):
        assert retired not in contract
        assert retired not in settings
        assert retired not in datasets

    assert "DATASET_SPLIT_POLICY_VERSION = 2" in contract
    assert 'DATASET_SPLIT_COMPLETE_STATUS = "complete_v2"' in contract
    assert "must declare policy_version=2" in contract
    assert "Dataset split mappings must declare policy_version=2" in settings
    assert "dataset_split_contract()" in datasets
    assert "dataset_split_contract(split_policy_version)" not in datasets


def test_relaxation_and_registry_read_only_current_payloads() -> None:
    relaxation = _source("calm/project/domain/contracts/relaxation.py")
    refinement = _source("calm/interface/refinement/contract.py")
    results = _source("calm/project/domain/contracts/refinement_result.py")
    derivation = _source("calm/project/application/interface_derivation.py")

    assert "dft_ionic_v1" not in relaxation
    assert "LEGACY_FIXED_CELL_PROTOCOL" not in relaxation
    assert "protocol must not contain surrounding whitespace" in relaxation

    for retired in ("seed_vacuum_present", "default_vacuum"):
        assert retired not in refinement
        assert retired not in derivation
    derivation_tree = ast.parse(derivation)
    assert not any(
        isinstance(node, ast.keyword) and node.arg == "seed_vacuum"
        for node in ast.walk(derivation_tree)
    )
    assert "resolve_registry_vacuum" not in refinement
    assert "registry_result_state(payload)" in derivation
    assert 'payload["vacuum"]' in results
    assert 'payload["z_padding"]' in results
    assert 'payload["registry_shift_frac_a"]' in results
    strain_fields = results.split("_STRAIN_PAYLOAD_FIELDS", 1)[1].split(")", 1)[0]
    assert "target_uid_full" not in strain_fields

    derive = _function(
        "calm/project/runtime/workspace.py",
        "derive_interfaces_from_registry_search",
    )
    assert all(argument.arg != "vacuum" for argument in derive.args.kwonlyargs)
    assert "exact current follow-up payload" in ast.get_docstring(derive)


def test_bulk_and_relaxed_reference_contracts_have_one_current_owner() -> None:
    bulk_contract = _source("calm/structure/standardization.py")
    provenance = _source("calm/bulk/provenance.py")
    relaxed = _source("calm/project/domain/contracts/relaxed_reference.py")
    energy_backend = _source(
        "calm/project/application/followups/energy_backends.py"
    )

    assert "first_available_mapping_value" not in bulk_contract
    assert 'mapping_value(dataset, "international")' in provenance
    assert '("international", "international_symbol")' not in provenance

    assert "def exact_nonnegative_integer(" not in relaxed
    assert "from calm.project.domain.contracts.relaxation import" in relaxed
    assert "RELAXED_SURFACE_REFERENCE_KINDS" in energy_backend
    assert '{"relaxed_surface_a", "relaxed_surface_b"}' not in energy_backend


def test_zur_mcgill_contract_remains_explicitly_diagnostic_only() -> None:
    source = _source("calm/interface/matching/zur_mcgill.py")
    assert "ZUR_MCGILL_DIAGNOSTIC_ONLY = True" in source
    assert '"diagnostic_only": ZUR_MCGILL_DIAGNOSTIC_ONLY' in source
    assert "legacy" not in source.lower()
