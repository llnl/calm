#!/usr/bin/env python3
"""Validate CALM's current public table-view ownership inventory."""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-public-table-views.json"
)
_SCHEMA_VERSION = "calm.public_table_views.v8"
_TOP_LEVEL_KEYS = {
    "authorities",
    "current_export_behavior",
    "current_view_owners",
    "known_defects",
    "retired_table_presets",
    "projection_foundation",
    "schema_version",
    "target_invariants",
    "temporary_example_schema_constants",
}
_OWNER_KEYS = {
    "default_view",
    "qualified_name",
    "recognized_views",
    "row_schema_owner",
    "source",
    "target_views",
    "unknown_view_behavior",
}
_ALLOWED_UNKNOWN_BEHAVIORS = {
    "all_fallback",
    "canonical_row_fallback",
    "delegated",
    "ignored_by_base",
    "raises",
    "summary_fallback",
}
_EXPECTED_EXPORT_BEHAVIOR = {
    "collection_dataframe_columns": "resolved_named_view_schema",
    "collection_display_columns": "resolved_named_view_schema",
    "collection_empty_csv": "resolved_named_view_header",
    "collection_include_exclude": "validated_after_named_view_resolution",
    "collection_rows": "homogeneous_ordered_schema",
    "collection_unknown_view": "raises_with_supported_views",
    "collection_write_table_columns": "resolved_named_view_schema",
    "direct_renderer_columns": "explicit_include_or_sorted_union",
    "dynamic_empty_collection_csv": "declared_base_header_plus_domain_columns",
    "public_schema_selector": "named_view_only",
    "result_dataframe_columns": "resolved_named_view_schema",
    "result_display_columns": "resolved_named_view_schema",
    "result_empty_csv": "resolved_named_view_header",
    "result_include_exclude": "validated_after_named_view_resolution",
    "result_rows": "homogeneous_ordered_schema",
    "result_unknown_view": "raises_with_supported_views",
    "result_write_table_columns": "resolved_named_view_schema",
    "retired_table_selector": "rejected_by_signature",
}
_EXPECTED_FOUNDATION = {
    "dynamic_schema_policy": "declared_base_plus_domain_extra_columns",
    "projection_type": "calm.public.collections.views.ResolvedTableProjection",
    "public_schema_selector": "named_view_only",
    "renderer_schema_policy": "format_only_with_explicit_include",
    "result_projection_mixin": "calm.public.records.tabular.TabularResultMixin",
    "shared_collection_methods": [
        "to_dataframe",
        "to_rows",
        "to_table",
        "write_table",
    ],
    "shared_result_methods": [
        "to_dataframe",
        "to_rows",
        "to_table",
        "write_table",
    ],
    "spec_type": "calm.public.collections.views.ViewSpec",
    "unknown_collection_view": "raises_with_supported_views",
    "unknown_result_view": "raises_with_supported_views",
}
_CANDIDATE_TARGET_VIEWS = ["all", "provenance", "strain", "summary"]
_INTERFACE_TARGET_VIEWS = [
    "all",
    "construction",
    "provenance",
    "strain",
    "summary",
]
_RESULT_TARGET_VIEWS = ["all", "provenance", "summary"]
_CAMPAIGN_TARGET_VIEWS = ["all", "provenance", "summary"]
_CAMPAIGN_RESULT_TARGET_VIEWS = [
    "all",
    "comparison",
    "provenance",
    "summary",
]
_DATASET_TARGET_VIEWS = ["all", "provenance", "summary"]
_DATASET_ITEM_TARGET_VIEWS = ["all", "learning", "provenance", "summary"]
_PROHIBITED_TARGET_VIEW_NAMES = {"decision"}
_MIGRATED_COLLECTION_OWNERS = {
    "CampaignCollection",
    "CampaignRunCollection",
    "CandidateCollection",
    "DatasetCollection",
    "DatasetItemCollection",
    "EnergyResultCollection",
    "InterfaceCollection",
    "MaterialCollection",
    "ReferenceEnergyResultCollection",
    "RelaxationResultCollection",
    "SurfaceCollection",
    "ThermodynamicResultCollection",
    "SearchCollection",
    "RunCollection",
    "FollowupCollection",
    "ArtifactCollection",
    "EdgeCollection",
}
_MIGRATED_NON_COLLECTION_OWNERS = {
    "CampaignWorkflowResult",
    "EnergyWorkflowResult",
    "InterfaceSearchResult",
    "ReferenceEnergyWorkflowResult",
    "RegistrySearchRun",
    "RelaxationWorkflowResult",
    "StrainPartitionScan",
}
_MIGRATED_DELEGATING_OWNERS = {"ProjectDataset"}
_MIGRATED_RESULT_OWNERS = {
    "EnergyResultCollection",
    "EnergyWorkflowResult",
    "ReferenceEnergyResultCollection",
    "ReferenceEnergyWorkflowResult",
    "RegistrySearchRun",
    "RelaxationResultCollection",
    "RelaxationWorkflowResult",
    "StrainPartitionScan",
    "ThermodynamicResultCollection",
}
_MIGRATED_EXAMPLE_SCHEMA_CONSTANTS = {
    "examples/01_optimize_materials.py": "MATERIAL_CHARACTERIZATION_COLUMNS",
    "examples/02_generate_surfaces.py": "SURFACE_CHARACTERIZATION_COLUMNS",
    "examples/03_search_interfaces.py": "CANDIDATE_SUMMARY_COLUMNS",
    "examples/05_build_interfaces.py": "BUILD_CANDIDATE_COLUMNS",
}



def _load_contract(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"could not read public table-view contract: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("public table-view contract must be a JSON object")
        return {}
    return payload


def _mapping(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        errors.append(f"{name} must be a JSON object")
        return {}
    if list(value) != sorted(value):
        errors.append(f"{name} keys must be sorted")
    return value


def _string_list(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    value = payload.get(name)
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        qualifier = "possibly empty" if allow_empty else "nonempty"
        errors.append(f"{name} must be a {qualifier} string list")
        return []
    if value != sorted(value):
        errors.append(f"{name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return list(value)


def _load_symbol(qualified_name: str) -> Any:
    module_name, separator, symbol_name = qualified_name.rpartition(".")
    if not separator:
        raise ValueError(f"invalid qualified name {qualified_name!r}")
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def _source_path(reference: str) -> str:
    return reference.partition(":")[0]


def _literal_sequences(path: Path) -> dict[str, list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sequences: dict[str, list[str]] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or not isinstance(
            value, (ast.List, ast.Tuple)
        ):
            continue
        try:
            materialized = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
        if isinstance(materialized, (list, tuple)) and all(
            isinstance(item, str) for item in materialized
        ):
            sequences[target.id] = list(materialized)
    return sequences


def validate(
    repo_root: Path = REPO_ROOT,
    *,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    """Return the public table-view inventory validation result."""

    root = Path(repo_root)
    root_text = str(root.resolve())
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    contract_file = contract_path or (
        root
        / "engineering"
        / "architecture"
        / "current-public-table-views.json"
    )
    errors: list[str] = []
    payload = _load_contract(contract_file, errors)
    if not payload:
        return {"errors": errors, "schema": None}

    if set(payload) != _TOP_LEVEL_KEYS:
        errors.append(
            f"contract keys must be exactly {sorted(_TOP_LEVEL_KEYS)}, "
            f"observed {sorted(payload)}"
        )
    if payload.get("schema_version") != _SCHEMA_VERSION:
        errors.append(f"schema_version must be {_SCHEMA_VERSION!r}")

    authorities = _mapping(payload, "authorities", errors)
    expected_authorities = {
        "canonical_projection_root",
        "collection_base",
        "collection_projection",
        "database_schema",
        "renderer",
        "sql_view_objects",
    }
    if set(authorities) != expected_authorities:
        errors.append("authorities has an unexpected field set")
    for name in expected_authorities - {"sql_view_objects"}:
        reference = authorities.get(name)
        if not isinstance(reference, str) or not reference:
            errors.append(f"authorities.{name} must be a nonempty string")
            continue
        if not (root / _source_path(reference)).exists():
            errors.append(f"authorities.{name} path does not exist")
    if authorities.get("sql_view_objects") is not False:
        errors.append("authorities.sql_view_objects must be false")
    database = root / str(authorities.get("database_schema") or "")
    if database.is_file() and "create view" in database.read_text().casefold():
        errors.append("database schema unexpectedly defines a SQL view")

    export_behavior = _mapping(payload, "current_export_behavior", errors)
    if dict(export_behavior) != _EXPECTED_EXPORT_BEHAVIOR:
        errors.append("current_export_behavior does not match the characterized state")

    foundation = _mapping(payload, "projection_foundation", errors)
    if dict(foundation) != _EXPECTED_FOUNDATION:
        errors.append("projection_foundation does not match the shared foundation")
    else:
        try:
            projection_type = _load_symbol(str(foundation["projection_type"]))
            result_mixin = _load_symbol(
                str(foundation["result_projection_mixin"])
            )
            spec_type = _load_symbol(str(foundation["spec_type"]))
        except (AttributeError, ImportError, ValueError) as exc:
            errors.append(f"could not load projection foundation types: {exc}")
        else:
            from calm.public.collections.views import (
                ResolvedTableProjection,
                ViewSpec,
            )
            from calm.public.records.tabular import TabularResultMixin

            if projection_type is not ResolvedTableProjection:
                errors.append(
                    "projection_type does not resolve to ResolvedTableProjection"
                )
            if result_mixin is not TabularResultMixin:
                errors.append(
                    "result_projection_mixin does not resolve to "
                    "TabularResultMixin"
                )
            if spec_type is not ViewSpec:
                errors.append("spec_type does not resolve to ViewSpec")

    owners = _mapping(payload, "current_view_owners", errors)
    for owner_name, raw_owner in owners.items():
        if not isinstance(raw_owner, dict):
            errors.append(f"current_view_owners.{owner_name} must be an object")
            continue
        if set(raw_owner) != _OWNER_KEYS:
            errors.append(f"current_view_owners.{owner_name} has unexpected fields")
        current_views = _string_list(raw_owner, "recognized_views", errors)
        target_views = _string_list(raw_owner, "target_views", errors)
        default_view = raw_owner.get("default_view")
        if default_view not in current_views:
            errors.append(f"{owner_name} default_view must be recognized")
        if "all" not in target_views:
            errors.append(f"{owner_name} target_views must contain 'all'")
        if default_view == "summary" and "summary" not in target_views:
            errors.append(
                f"{owner_name} target_views must retain 'summary' as the "
                "ordinary reader-facing view"
            )
        prohibited = sorted(
            set(target_views) & _PROHIBITED_TARGET_VIEW_NAMES
        )
        if prohibited:
            errors.append(
                f"{owner_name} target_views contain prohibited abstract names: "
                + ", ".join(repr(name) for name in prohibited)
            )
        if owner_name in {"CandidateCollection", "InterfaceSearchResult"} and (
            target_views != _CANDIDATE_TARGET_VIEWS
        ):
            errors.append(
                f"{owner_name} target_views must be "
                f"{_CANDIDATE_TARGET_VIEWS!r}"
            )
        if owner_name == "InterfaceCollection" and (
            target_views != _INTERFACE_TARGET_VIEWS
        ):
            errors.append(
                f"InterfaceCollection target_views must be "
                f"{_INTERFACE_TARGET_VIEWS!r}"
            )
        if owner_name in {"CampaignCollection", "CampaignRunCollection"} and (
            target_views != _CAMPAIGN_TARGET_VIEWS
        ):
            errors.append(
                f"{owner_name} target_views must be "
                f"{_CAMPAIGN_TARGET_VIEWS!r}"
            )
        if owner_name == "CampaignWorkflowResult" and (
            target_views != _CAMPAIGN_RESULT_TARGET_VIEWS
        ):
            errors.append(
                "CampaignWorkflowResult target_views must be "
                f"{_CAMPAIGN_RESULT_TARGET_VIEWS!r}"
            )
        if owner_name == "DatasetCollection" and (
            target_views != _DATASET_TARGET_VIEWS
        ):
            errors.append(
                f"DatasetCollection target_views must be {_DATASET_TARGET_VIEWS!r}"
            )
        if owner_name in {"DatasetItemCollection", "ProjectDataset"} and (
            target_views != _DATASET_ITEM_TARGET_VIEWS
        ):
            errors.append(
                f"{owner_name} target_views must be "
                f"{_DATASET_ITEM_TARGET_VIEWS!r}"
            )
        if owner_name in _MIGRATED_RESULT_OWNERS and (
            target_views != _RESULT_TARGET_VIEWS
        ):
            errors.append(
                f"{owner_name} target_views must be "
                f"{_RESULT_TARGET_VIEWS!r}"
            )
        behavior = raw_owner.get("unknown_view_behavior")
        if behavior not in _ALLOWED_UNKNOWN_BEHAVIORS:
            errors.append(f"{owner_name} has invalid unknown_view_behavior")

        qualified_name = raw_owner.get("qualified_name")
        source = raw_owner.get("source")
        row_owner = raw_owner.get("row_schema_owner")
        if not isinstance(row_owner, str) or not row_owner:
            errors.append(f"{owner_name} row_schema_owner must be nonempty")
        if not isinstance(source, str) or not (root / source).is_file():
            errors.append(f"{owner_name} source does not exist")
            continue
        if not isinstance(qualified_name, str):
            errors.append(f"{owner_name} qualified_name must be a string")
            continue
        try:
            owner = _load_symbol(qualified_name)
            signature = inspect.signature(owner.to_rows)
            table_signature = inspect.signature(owner.to_table)
        except (AttributeError, ImportError, TypeError, ValueError) as exc:
            errors.append(f"could not inspect {qualified_name}: {exc}")
            continue
        if "table" in table_signature.parameters:
            errors.append(
                f"{owner_name}.to_table must not expose the retired table selector"
            )
        view = signature.parameters.get("view")
        observed_default = None if view is None else view.default
        if observed_default != default_view:
            errors.append(
                f"{owner_name}.to_rows view default is {observed_default!r}, "
                f"expected {default_view!r}"
            )
        observed_source = inspect.getsourcefile(owner)
        if observed_source is None or Path(observed_source).resolve() != (
            root / source
        ).resolve():
            errors.append(f"{owner_name} source does not match qualified_name")

        from calm.public.collections.base import _BaseCollection
        from calm.public.collections.views import ViewSpec

        if inspect.isclass(owner) and issubclass(owner, _BaseCollection):
            specs = getattr(owner, "_view_specs", ())
            if not specs or any(not isinstance(spec, ViewSpec) for spec in specs):
                errors.append(f"{owner_name} must declare ViewSpec values")
                continue
            observed_views = sorted(
                name
                for spec in specs
                for name in (spec.name, *spec.aliases)
            )
            if observed_views != current_views:
                errors.append(
                    f"{owner_name} recognized_views do not match _view_specs"
                )
            canonical_views = tuple(spec.name for spec in specs)
            if owner.available_views() != canonical_views:
                errors.append(
                    f"{owner_name}.available_views does not match canonical specs"
                )
            if owner_name in _MIGRATED_COLLECTION_OWNERS:
                if sorted(canonical_views) != target_views:
                    errors.append(
                        f"{owner_name} canonical views do not match target_views"
                    )
                undeclared = [spec.name for spec in specs if not spec.columns]
                if undeclared:
                    errors.append(
                        f"{owner_name} migrated views must declare base columns: "
                        + ", ".join(repr(name) for name in undeclared)
                    )
                invalid_extensible = [
                    spec.name
                    for spec in specs
                    if spec.allow_extra_columns
                    and spec.name not in {"all", "comparison", "learning"}
                ]
                if invalid_extensible:
                    errors.append(
                        f"{owner_name} has invalid extensible views: "
                        + ", ".join(repr(name) for name in invalid_extensible)
                    )
                missing_extensibility = [
                    spec.name
                    for spec in specs
                    if spec.name in {"comparison", "learning"}
                    and not spec.allow_extra_columns
                ]
                if missing_extensibility:
                    errors.append(
                        f"{owner_name} dynamic views must permit domain columns: "
                        + ", ".join(
                            repr(name) for name in missing_extensibility
                        )
                    )
            if behavior != "raises":
                errors.append(
                    f"{owner_name} shared collection views must reject unknown names"
                )
        elif owner_name in (
            _MIGRATED_NON_COLLECTION_OWNERS | _MIGRATED_DELEGATING_OWNERS
        ):
            specs = getattr(owner, "_view_specs", ())
            if not specs or any(not isinstance(spec, ViewSpec) for spec in specs):
                errors.append(f"{owner_name} must declare shared ViewSpec values")
                continue
            observed_views = sorted(
                name
                for spec in specs
                for name in (spec.name, *spec.aliases)
            )
            if observed_views != current_views:
                errors.append(
                    f"{owner_name} recognized_views do not match _view_specs"
                )
            canonical_views = tuple(spec.name for spec in specs)
            if owner.available_views() != canonical_views:
                errors.append(
                    f"{owner_name}.available_views does not match canonical specs"
                )
            if sorted(canonical_views) != target_views:
                errors.append(
                    f"{owner_name} canonical views do not match target_views"
                )
            undeclared = [spec.name for spec in specs if not spec.columns]
            if undeclared:
                errors.append(
                    f"{owner_name} migrated views must declare base columns: "
                    + ", ".join(repr(name) for name in undeclared)
                )
            invalid_extensible = [
                spec.name
                for spec in specs
                if spec.allow_extra_columns
                and spec.name not in {"all", "comparison", "learning"}
            ]
            if invalid_extensible:
                errors.append(
                    f"{owner_name} has invalid extensible views: "
                    + ", ".join(repr(name) for name in invalid_extensible)
                )
            missing_extensibility = [
                spec.name
                for spec in specs
                if spec.name in {"comparison", "learning"}
                and not spec.allow_extra_columns
            ]
            if missing_extensibility:
                errors.append(
                    f"{owner_name} dynamic views must permit domain columns: "
                    + ", ".join(repr(name) for name in missing_extensibility)
                )
            expected_behavior = (
                "delegated"
                if owner_name in _MIGRATED_DELEGATING_OWNERS
                else "raises"
            )
            if behavior != expected_behavior:
                errors.append(
                    f"{owner_name} shared views must use "
                    f"{expected_behavior!r} unknown-view behavior"
                )

    notebook = importlib.import_module("calm.project.presentation.notebook")
    for symbol in ("TablePreset", "_TABLE_PRESETS", "_infer_table_name"):
        if hasattr(notebook, symbol):
            errors.append(f"renderer must not expose retired symbol {symbol}")
    from calm.project.presentation.notebook import TableView, display_table

    if "table" in inspect.signature(display_table).parameters:
        errors.append("display_table must not expose the retired table selector")
    if "table" in getattr(TableView, "__dataclass_fields__", {}):
        errors.append("TableView must not expose the retired table selector")

    retired_presets = _string_list(payload, "retired_table_presets", errors)
    expected_retired = [
        "artifacts",
        "bulks",
        "calculators",
        "edges",
        "followups",
        "interfaces",
        "prototypes",
        "runs",
        "slabs",
    ]
    if retired_presets != expected_retired:
        errors.append("retired_table_presets must preserve the retired preset inventory")
    for owner_name, raw_owner in owners.items():
        target_views = raw_owner.get("target_views", [])
        leaked = sorted(set(target_views) & set(retired_presets))
        if leaked:
            errors.append(
                f"{owner_name} target views leak retired persistence names: "
                + ", ".join(repr(name) for name in leaked)
            )

    known_defects = _string_list(
        payload, "known_defects", errors, allow_empty=True
    )
    if known_defects:
        errors.append("known_defects must be empty after table-view consolidation")
    _string_list(payload, "target_invariants", errors)

    example_schemas = _mapping(
        payload,
        "temporary_example_schema_constants",
        errors,
    )
    for relative, constant in _MIGRATED_EXAMPLE_SCHEMA_CONSTANTS.items():
        if relative in example_schemas:
            errors.append(
                f"{relative} must not remain a temporary example schema owner"
            )
        path = root / relative
        if path.is_file() and constant in _literal_sequences(path):
            errors.append(
                f"{relative}:{constant} must be owned by the collection view registry"
            )

    for relative, constants in example_schemas.items():
        path = root / relative
        if not path.is_file() or not isinstance(constants, dict):
            errors.append(f"invalid temporary example schema source {relative!r}")
            continue
        observed = _literal_sequences(path)
        for constant, columns in constants.items():
            if observed.get(constant) != columns:
                errors.append(
                    f"{relative}:{constant} does not match the temporary "
                    "schema inventory"
                )

    return {
        "errors": errors,
        "foundation_methods": list(
            payload.get("projection_foundation", {}).get(
                "shared_collection_methods", []
            )
        ),
        "result_foundation_methods": list(
            payload.get("projection_foundation", {}).get(
                "shared_result_methods", []
            )
        ),
        "known_defects": len(payload.get("known_defects", [])),
        "retired_table_presets": retired_presets,
        "owners": sorted(owners),
        "schema": payload.get("schema_version"),
        "temporary_example_schemas": sum(
            len(value) if isinstance(value, dict) else 0
            for value in example_schemas.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CALM's public table-view ownership inventory."
    )
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    args = parser.parse_args()
    result = validate(contract_path=args.contract)
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        return 1
    print(
        "Public table-view architecture verified: "
        f"{len(result['owners'])} owners, "
        f"{len(result['foundation_methods'])} shared collection exports, "
        f"{len(result['result_foundation_methods'])} shared result exports, "
        f"{len(result['retired_table_presets'])} retired presets, "
        f"{result['temporary_example_schemas']} temporary example schemas, "
        f"{result['known_defects']} remaining defects."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
