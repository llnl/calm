"""Shared named-view contract for persisted and in-memory candidates."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from calm.public.collections.views import (
    ResolvedTableProjection,
    ViewSpec,
    resolve_table_projection,
    resolve_view_spec,
)
from calm.public.projections.candidate import normalize_candidate_rows


CANDIDATE_SUMMARY_COLUMNS = (
    "candidate_id",
    "d_cell",
    "d_area",
    "d_shape",
    "max_principal_strain",
    "n_atoms_estimate",
    "score",
    "is_pareto",
)

CANDIDATE_STRAIN_COLUMNS = (
    "candidate_id",
    "miller_a",
    "miller_b",
    "d_cell",
    "d_area",
    "d_shape",
    "eps1",
    "eps2",
    "max_principal_strain",
    "strain_norm",
    "isotropic_strain_signed",
    "isotropic_strain_norm",
    "deviatoric_strain_norm",
    "n_atoms_estimate",
    "is_pareto",
)

CANDIDATE_PROVENANCE_COLUMNS = (
    "rank",
    "candidate_id",
    "candidate_uid",
    "prototype_uid",
    "project_prototype_uid",
    "project_prototype_id",
    "search_id",
    "search_name",
    "run_uid",
    "run_id",
    "surface_a_uid_full",
    "surface_b_uid_full",
    "authority",
    "is_pareto",
    "pareto_rank",
    "pareto_policy",
    "pareto_policy_version",
    "pareto_population_scope",
    "pareto_population_size",
    "pareto_d_cell_key",
    "pareto_status",
)

CANDIDATE_ALL_COLUMNS = (
    "rank",
    "candidate_id",
    "candidate_uid",
    "prototype_uid",
    "project_prototype_uid",
    "project_prototype_id",
    "uid",
    "search_id",
    "search_name",
    "run_uid",
    "run_id",
    "material_a",
    "material_b",
    "surface_a",
    "surface_b",
    "surface_a_label",
    "surface_b_label",
    "surface_a_uid_full",
    "surface_b_uid_full",
    "surface_a_id_short",
    "surface_b_id_short",
    "miller_a",
    "miller_b",
    "termination_a",
    "termination_b",
    "termination_shift_a",
    "termination_shift_b",
    "score",
    "d_cell",
    "d_area",
    "d_shape",
    "d_size",
    "rel_da",
    "rel_db",
    "d_gamma_deg",
    "eps1",
    "eps2",
    "max_principal_strain",
    "strain_norm",
    "isotropic_strain_signed",
    "isotropic_strain_norm",
    "deviatoric_strain_norm",
    "n_atoms_estimate",
    "area_A2",
    "gap",
    "k_a",
    "k_b",
    "hnf_key_a",
    "hnf_key_b",
    "identity_algorithm",
    "pair_identity",
    "source_provenance",
    "zur_mcgill_diagnostic",
    "tags",
    "n_candidates",
    "is_pareto",
    "pareto_rank",
    "pareto_policy",
    "pareto_policy_version",
    "pareto_population_scope",
    "pareto_population_size",
    "pareto_d_cell_key",
    "pareto_status",
    "authority",
)

CANDIDATE_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=CANDIDATE_SUMMARY_COLUMNS,
        description="Concise geometric comparison of interface candidates.",
    ),
    ViewSpec(
        name="strain",
        columns=CANDIDATE_STRAIN_COLUMNS,
        description="Detailed candidate strain diagnostics.",
    ),
    ViewSpec(
        name="provenance",
        columns=CANDIDATE_PROVENANCE_COLUMNS,
        description="Candidate identity, authority, and Pareto-policy provenance.",
    ),
    ViewSpec(
        name="all",
        columns=CANDIDATE_ALL_COLUMNS,
        aliases=("full",),
        description="Complete normalized public candidate row.",
    ),
)


def resolve_candidate_projection(
    rows: Iterable[Any],
    *,
    view: str | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> ResolvedTableProjection:
    """Resolve candidates through the shared named-view registry."""

    spec = resolve_view_spec(
        CANDIDATE_VIEW_SPECS,
        view=view,
        default_view="summary",
    )
    return resolve_table_projection(
        spec,
        normalize_candidate_rows(rows),
        include=include,
        exclude=exclude,
    )
