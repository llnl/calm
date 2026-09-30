"""Shared named-view contracts for refinement and energetic result records."""

from __future__ import annotations

from math import isclose
from numbers import Real
from typing import Any, Iterable, Mapping

from calm.public.collections.views import ViewSpec


STRAIN_PARTITION_SUMMARY_COLUMNS = (
    "prototype_id",
    "alpha",
    "is_selected",
    "potential_energy_density_eV_per_A2",
    "gamma_eV_per_A2",
    "gamma_J_per_m2",
)

STRAIN_PARTITION_PROVENANCE_COLUMNS = (
    "run_id",
    "followup_id",
    "prototype_id",
    "target_kind",
    "target_metric",
    "target_alpha",
    "target_value",
    "energy_reference",
)

STRAIN_PARTITION_ALL_COLUMNS = (
    "run_id",
    "followup_id",
    "prototype_id",
    "target_kind",
    "target_alpha",
    "target_metric",
    "target_value",
    "alpha",
    "is_selected",
    "side_a_principal_log_strains",
    "side_b_principal_log_strains",
    "side_a_max_abs_principal_log_strain",
    "side_b_max_abs_principal_log_strain",
    "side_a_airm_distance",
    "side_b_airm_distance",
    "potential_energy_eV",
    "area_A2",
    "interface_area_A2",
    "potential_energy_density_eV_per_A2",
    "gamma_eV_per_A2",
    "gamma_J_per_m2",
    "n_fu_slab_A",
    "n_fu_slab_B",
    "mu_bulk_A_eV_per_fu",
    "mu_bulk_B_eV_per_fu",
    "energy_reference",
)

STRAIN_PARTITION_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=STRAIN_PARTITION_SUMMARY_COLUMNS,
        description="Reader-facing strain-partition scan points.",
    ),
    ViewSpec(
        name="provenance",
        columns=STRAIN_PARTITION_PROVENANCE_COLUMNS,
        description="Run, target, and objective provenance for the scan.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=STRAIN_PARTITION_ALL_COLUMNS,
        description="Complete public strain-partition point projection.",
    ),
)


REGISTRY_SEARCH_SUMMARY_COLUMNS = (
    "prototype_id",
    "registry_shift_frac_a",
    "gap_A",
    "vacuum_A",
    "score",
    "n_steps",
    "n_accepted",
)

REGISTRY_SEARCH_PROVENANCE_COLUMNS = (
    "run_id",
    "followup_id",
    "prototype_id",
    "target_kind",
    "objective",
    "objective_units",
    "registry_provenance_status",
)

REGISTRY_SEARCH_ALL_COLUMNS = (
    "run_id",
    "followup_id",
    "prototype_id",
    "target_kind",
    "registry_shift_frac_a",
    "z_padding",
    "vacuum",
    "objective",
    "objective_units",
    "score",
    "n_steps",
    "n_accepted",
    "registry_provenance_status",
)

REGISTRY_SEARCH_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=REGISTRY_SEARCH_SUMMARY_COLUMNS,
        description="Reader-facing registry-search outcome per target.",
    ),
    ViewSpec(
        name="provenance",
        columns=REGISTRY_SEARCH_PROVENANCE_COLUMNS,
        description="Run, target, objective, and exact-current provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=REGISTRY_SEARCH_ALL_COLUMNS,
        description="Complete public registry-search result projection.",
    ),
)


RELAXATION_SUMMARY_COLUMNS = (
    "id_short",
    "status",
    "target_uid_full",
    "converged",
    "n_steps",
    "final_energy_eV",
    "max_force_eV_per_A",
)

RELAXATION_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "target_kind",
    "relaxed_interface_uid",
    "optimizer_reported_converged",
    "residual_satisfied",
    "max_optimizer_residual",
    "termination_reason",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "authority",
)

RELAXATION_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "status",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "target_kind",
    "relaxed_interface_uid",
    "final_energy_eV",
    "n_steps",
    "converged",
    "optimizer_reported_converged",
    "residual_satisfied",
    "max_force_eV_per_A",
    "max_optimizer_residual",
    "termination_reason",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "payload",
    "authority",
)

RELAXATION_RESULT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=RELAXATION_SUMMARY_COLUMNS,
        description="Reader-facing structural-relaxation outcomes.",
    ),
    ViewSpec(
        name="provenance",
        columns=RELAXATION_PROVENANCE_COLUMNS,
        description="Relaxation run, target, backend, and artifact provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=RELAXATION_ALL_COLUMNS,
        description="Complete public structural-relaxation result projection.",
    ),
)


RAW_ENERGY_SUMMARY_COLUMNS = (
    "id_short",
    "status",
    "target_uid_full",
    "target_kind",
    "quantity",
    "energy_eV",
)

RAW_ENERGY_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "target_kind",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "authority",
)

RAW_ENERGY_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "kind",
    "status",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "prototype_id_short",
    "target_uid_full",
    "target_id_short",
    "target_kind",
    "best_energy",
    "param1",
    "param2",
    "n_points",
    "quantity",
    "energy_eV",
    "energy",
    "units",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "payload",
    "created_at",
    "updated_at",
    "authority",
)

RAW_ENERGY_RESULT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=RAW_ENERGY_SUMMARY_COLUMNS,
        description="Reader-facing raw total-energy results.",
    ),
    ViewSpec(
        name="provenance",
        columns=RAW_ENERGY_PROVENANCE_COLUMNS,
        description="Raw-energy run, target, backend, and artifact provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=RAW_ENERGY_ALL_COLUMNS,
        description="Complete public raw-energy result projection.",
    ),
)


REFERENCE_ENERGY_SUMMARY_COLUMNS = (
    "id_short",
    "status",
    "target_uid_full",
    "reference_kind",
    "side",
    "energy_eV",
    "energy_eV_per_formula_unit",
)

REFERENCE_ENERGY_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "reference_uid_full",
    "reference_kind",
    "side",
    "formula_id",
    "reference_formula_units",
    "interface_formula_units",
    "source_bulk_uid_full",
    "source_slab_uid_full",
    "structure_fingerprint",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "authority",
)

REFERENCE_ENERGY_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "status",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "source_interface_uid_full",
    "reference_uid_full",
    "reference_kind",
    "side",
    "formula_id",
    "energy_eV",
    "energy_eV_per_formula_unit",
    "reference_formula_units",
    "interface_formula_units",
    "source_bulk_uid_full",
    "source_slab_uid_full",
    "structure_fingerprint",
    "backend",
    "backend_identity",
    "settings",
    "artifact_refs",
    "failure",
    "payload",
    "authority",
)

REFERENCE_ENERGY_RESULT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=REFERENCE_ENERGY_SUMMARY_COLUMNS,
        description="Reader-facing calculated reference-energy results.",
    ),
    ViewSpec(
        name="provenance",
        columns=REFERENCE_ENERGY_PROVENANCE_COLUMNS,
        description="Reference identity, source, backend, and artifact provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=REFERENCE_ENERGY_ALL_COLUMNS,
        description="Complete public reference-energy result projection.",
    ),
)


THERMODYNAMIC_SUMMARY_COLUMNS = (
    "id_short",
    "status",
    "target_uid_full",
    "quantity",
    "value_eV_per_A2",
    "value_J_per_m2",
)

THERMODYNAMIC_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "target_kind",
    "raw_energy_followup_uid",
    "formula_id",
    "normalization_area_A2",
    "n_interfaces",
    "reference_source",
    "normalization_area_source_status",
    "calculator_compatibility",
    "failure",
    "authority",
)

THERMODYNAMIC_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "status",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "target_uid_full",
    "target_kind",
    "raw_energy_followup_uid",
    "quantity",
    "formula_id",
    "value_eV_per_A2",
    "value_J_per_m2",
    "normalization_area_A2",
    "n_interfaces",
    "convention",
    "references",
    "reference_source",
    "components",
    "units",
    "normalization_area_source_status",
    "calculator_compatibility",
    "failure",
    "payload",
    "authority",
)

THERMODYNAMIC_RESULT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=THERMODYNAMIC_SUMMARY_COLUMNS,
        description="Reader-facing derived interfacial thermodynamic results.",
    ),
    ViewSpec(
        name="provenance",
        columns=THERMODYNAMIC_PROVENANCE_COLUMNS,
        description="Thermodynamic formula, reference, and calculator provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=THERMODYNAMIC_ALL_COLUMNS,
        description="Complete public thermodynamic result projection.",
    ),
)


def _ordered_union(*groups: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


ENERGY_WORKFLOW_SUMMARY_COLUMNS = (
    "result_kind",
    *_ordered_union(RAW_ENERGY_SUMMARY_COLUMNS, THERMODYNAMIC_SUMMARY_COLUMNS),
)
ENERGY_WORKFLOW_PROVENANCE_COLUMNS = (
    "result_kind",
    *_ordered_union(
        RAW_ENERGY_PROVENANCE_COLUMNS,
        THERMODYNAMIC_PROVENANCE_COLUMNS,
    ),
)
ENERGY_WORKFLOW_ALL_COLUMNS = (
    "result_kind",
    *_ordered_union(RAW_ENERGY_ALL_COLUMNS, THERMODYNAMIC_ALL_COLUMNS),
)

ENERGY_WORKFLOW_COMBINED_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=ENERGY_WORKFLOW_SUMMARY_COLUMNS,
        description="Combined raw-energy and thermodynamic result summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=ENERGY_WORKFLOW_PROVENANCE_COLUMNS,
        description="Combined raw-energy and thermodynamic provenance.",
    ),
    ViewSpec(
        name="all",
        aliases=("full",),
        columns=ENERGY_WORKFLOW_ALL_COLUMNS,
        description="Complete combined energy-workflow projection.",
    ),
)


def strain_partition_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return detached scan rows with an explicit selected-point projection."""

    normalized: list[dict[str, Any]] = []
    for value in rows:
        row = dict(value)
        alpha = row.get("alpha")
        target = row.get("target_alpha")
        selected = False
        if (
            isinstance(alpha, Real)
            and not isinstance(alpha, bool)
            and isinstance(target, Real)
            and not isinstance(target, bool)
        ):
            selected = isclose(float(alpha), float(target), rel_tol=0.0, abs_tol=1e-12)
        row["is_selected"] = selected
        normalized.append(row)
    return normalized


def registry_search_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return detached registry rows with reader-facing length-unit aliases."""

    normalized: list[dict[str, Any]] = []
    for value in rows:
        row = dict(value)
        row["gap_A"] = row.get("z_padding")
        row["vacuum_A"] = row.get("vacuum")
        normalized.append(row)
    return normalized
