"""Canonical normalization helpers for interface-candidate rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from calm.public.projections.strain import project_candidate_strain_metrics


def normalize_candidate_row(
    item: Any, *, rank: int | None = None, is_pareto: bool | None = None
) -> dict[str, Any]:
    """Return the canonical complete public row for one interface candidate."""

    m = item if isinstance(item, dict) else (getattr(item, "__dict__", {}) or {})
    r = project_candidate_strain_metrics(m)
    cid = r.get("candidate_id") or r.get("id") or r.get("uid")
    rank_v = rank if rank is not None else r.get("rank")
    pareto_value = is_pareto if is_pareto is not None else r.get("is_pareto")
    out = {
        "candidate_id": cid,
        "rank": rank_v,
        "score": r.get("score") or r.get("match_score"),
        "d_cell": r.get("d_cell"),
        "d_area": r.get("d_area"),
        "d_shape": r.get("d_shape"),
        "d_size": r.get("d_size"),
        "rel_da": r.get("rel_da"),
        "rel_db": r.get("rel_db"),
        "d_gamma_deg": r.get("d_gamma_deg"),
        "max_principal_strain": r.get("max_principal_strain"),
        "n_atoms_estimate": r.get("n_atoms_estimate")
        or r.get("n_atoms_interface")
        or r.get("n_atoms")
        or r.get("natoms"),
        "material_a": r.get("material_a"),
        "material_b": r.get("material_b"),
        "is_pareto": None if pareto_value is None else bool(pareto_value),
        "candidate_uid": r.get("candidate_uid") or r.get("uid"),
        "prototype_uid": r.get("prototype_uid") or r.get("prototype"),
        "area_A2": r.get("area_A2") or r.get("area"),
        "authority": r.get("authority") or r.get("_authority"),
    }

    for key in (
        "uid",
        "search_id",
        "search_name",
        "run_uid",
        "run_id",
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
        "project_prototype_uid",
        "project_prototype_id",
        "eps1",
        "eps2",
        "strain_norm",
        "isotropic_strain_signed",
        "isotropic_strain_norm",
        "deviatoric_strain_norm",
        "pareto_rank",
        "pareto_policy",
        "pareto_policy_version",
        "pareto_population_scope",
        "pareto_population_size",
        "pareto_d_cell_key",
        "pareto_status",
    ):
        if key in r:
            out[key] = r.get(key)
        else:
            value = getattr(item, key, None)
            if value is not None:
                out[key] = value

    if r.get("candidate_uid"):
        out["candidate_uid"] = r.get("candidate_uid")
    if r.get("prototype_uid"):
        out["prototype_uid"] = r.get("prototype_uid")
    if r.get("search_id"):
        out["search_id"] = r.get("search_id")
    if r.get("search_name"):
        out["search_name"] = r.get("search_name")
    return out


def normalize_candidate_rows(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalize candidate values through the shared complete row authority."""

    rows: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            row = dict(item)
        elif hasattr(item, "to_dict"):
            row = dict(item.to_dict())
        else:
            row = {
                key: value
                for key, value in vars(item).items()
                if not key.startswith("_")
            }
        rows.append(
            normalize_candidate_row(
                row,
                rank=row.get("rank"),
                is_pareto=row.get("is_pareto"),
            )
        )
    return rows
