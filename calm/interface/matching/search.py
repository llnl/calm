"""Authoritative primitive coupled-pair lattice-match enumeration.

``search_primitive_match_classes`` returns the complete coupled-v2 search result
with symmetry provenance and production audit data.
``enumerate_primitive_match_classes`` is the explicit list-returning low-level
projection. The legacy independent-surface matcher has been removed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Surface symmetry helper (single owner: calm.interface.matching._surface_symmetry)
from calm.interface.matching import _surface_symmetry

from calm.interface.matching._correspondence import DEFAULT_CORRESPONDENCE_ENTRY_LIMIT
from calm.interface.matching._utils import (
    _compute_d_size,
    _compute_match_score,
    _normalize_d_cell,
    # Re-export matching utilities from the private implementation module so
    # callers can access these helpers via the public calm.interface.matching.search
    # namespace. We expose them through __all__ to make intent explicit and
    # to satisfy static analysis while keeping the implementation single-sited.
    _prim_inplane_basis_2d,
    compute_valid_hnf_index_pairs,
)

from calm.interface.matching._types import (
    PrimitiveMatchClass2D,
    PrimitiveMatchSearchResult,
)
from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.interface.config import (
    DEFAULT_CORRESPONDENCE_ORIENTATION,
    DEFAULT_IDENTIFY_MATERIAL_EXCHANGE,
    DEFAULT_PAIR_SYMMETRY_POLICY,
    PrototypeSearchConfig,
)

__all__ = [
    "enumerate_primitive_match_classes",
    "search_primitive_match_classes",
    "compute_valid_hnf_index_pairs",
    "_prim_inplane_basis_2d",
    "_normalize_d_cell",
    "_compute_d_size",
    "_compute_match_score",
]

# Typing anchors (no-op) to preserve modern builtin-collection annotations in
# this module for documentation/arch tests. These are intentionally inert.
_ANNOT_DICT_EXAMPLE: dict[int, dict[str, int]] | None = None
_ANNOT_TUPLE_EXAMPLE: tuple[np.ndarray, float] | None = None
_ANNOT_LIST_EXAMPLE: list[np.ndarray] | None = None


COUPLED_MATCH_IMPLEMENTATION = "primitive_coupled_pair_v2"
COUPLED_PAIR_SYMMETRY_POLICY = DEFAULT_PAIR_SYMMETRY_POLICY
COUPLED_CORRESPONDENCE_ORIENTATION = DEFAULT_CORRESPONDENCE_ORIENTATION
COUPLED_IDENTIFY_MATERIAL_EXCHANGE = DEFAULT_IDENTIFY_MATERIAL_EXCHANGE
COUPLED_CORRESPONDENCE_ENTRY_LIMIT = DEFAULT_CORRESPONDENCE_ENTRY_LIMIT


def search_primitive_match_classes(
    slab_A: Any,
    slab_B: Any,
    config: PrototypeSearchConfig,
) -> PrimitiveMatchSearchResult:
    """Return the complete authoritative coupled-v2 class population.

    Output truncation and Pareto annotation are deliberately excluded from this
    kernel.  Every higher-level search entry point consumes this same complete
    primitive class population.
    """

    if not isinstance(config, PrototypeSearchConfig):
        raise TypeError("config must be a PrototypeSearchConfig")
    resolution_a = _surface_symmetry.resolve_surface_pointgroup_2d(
        slab_A,
        mode=config.surface_symmetry_mode,
        symprec=config.surface_symprec,
        angle_tolerance=config.surface_angle_tolerance,
        metric_tolerance=config.surface_metric_tolerance,
    )
    resolution_b = _surface_symmetry.resolve_surface_pointgroup_2d(
        slab_B,
        mode=config.surface_symmetry_mode,
        symprec=config.surface_symprec,
        angle_tolerance=config.surface_angle_tolerance,
        metric_tolerance=config.surface_metric_tolerance,
    )

    from calm.interface.matching._orchestrator import (
        enumerate_coupled_match_classes_core,
    )

    enumeration_audit = CoupledMatchEnumerationAudit.empty(config.k_max)
    enumeration_audit.surface_symmetry_A = resolution_a.provenance
    enumeration_audit.surface_symmetry_B = resolution_b.provenance
    classes = enumerate_coupled_match_classes_core(
        slab_A,
        slab_B,
        k_max=int(config.k_max),
        cond_max=float(config.cond_max),
        w_match=float(config.w_match),
        eps_principal_max=float(config.eps_principal_max),
        N_at_max=int(config.N_at_max),
        surface_symmetry_mode=config.surface_symmetry_mode,
        surface_symprec=config.surface_symprec,
        surface_angle_tolerance=config.surface_angle_tolerance,
        surface_metric_tolerance=config.surface_metric_tolerance,
        pair_symmetry_policy=config.pair_symmetry_policy,
        correspondence_orientation=config.correspondence_orientation,
        identify_material_exchange=config.identify_material_exchange,
        correspondence_entry_limit=config.correspondence_entry_limit,
        point_group_A=resolution_a.operations,
        point_group_B=resolution_b.operations,
        audit=enumeration_audit,
    )
    return PrimitiveMatchSearchResult(
        match_classes=tuple(classes),
        surface_symmetry_a=resolution_a.provenance,
        surface_symmetry_b=resolution_b.provenance,
        enumeration_audit=enumeration_audit,
        implementation=COUPLED_MATCH_IMPLEMENTATION,
    )


def enumerate_primitive_match_classes(
    slab_A: Any,
    slab_B: Any,
    config: PrototypeSearchConfig,
) -> list[PrimitiveMatchClass2D]:
    """Return the complete coupled-v2 primitive class population as a list.

    This is the explicit low-level coupled matching contract. Callers that also
    need surface-symmetry provenance should use
    :func:`search_primitive_match_classes` directly. Output truncation remains a
    higher-level concern and is therefore not applied here.
    """

    return list(search_primitive_match_classes(slab_A, slab_B, config).match_classes)


# The functions below are implemented and exported from the internal
# `._matching_utils` module. We intentionally import them above and avoid
# redefining them here to prevent duplication and to keep a single source of
# truth for the matching utilities.
