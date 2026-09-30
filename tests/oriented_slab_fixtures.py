"""Exact-current oriented-slab provenance fixtures shared across tests."""

from __future__ import annotations

from typing import Any


def current_construction_controls(
    *,
    reduce_c_tilt: bool = True,
) -> dict[str, Any]:
    """Return one fresh exact-current bounded-gauge control record."""

    return {
        "policy": "bounded_surface_gauges",
        "policy_version": 1,
        "construction_path": "primitive_bulk",
        "primitive_max_denominator": 12,
        "primitive_reduction_max_iter": 100,
        "stacking_search_radius": 2,
        "stacking_boundary_policy": "fail_if_best_candidate_is_on_boundary",
        "c_tilt_enabled": reduce_c_tilt,
        "c_tilt_search": 6,
        "c_tilt_singular_tolerance": 1e-12,
        "c_tilt_boundary_policy": (
            "fail_if_best_candidate_is_on_boundary"
            if reduce_c_tilt
            else "not_applied"
        ),
    }


def current_compact_transforms(
    *,
    hkl: tuple[int, int, int] = (1, 0, 0),
    interface_ready: bool = False,
) -> dict[str, Any]:
    """Return one fresh exact-current compact transform payload."""

    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    payload = {
        "version": 1,
        "hkl": list(hkl),
        "U": identity,
        "R_conv_to_slab": identity,
        "R_slab_to_conv": identity,
        "M_conv_to_slab_cart": identity,
        "M_slab_to_conv_cart": identity,
        "construction_controls": current_construction_controls(),
    }
    if interface_ready:
        payload["vacuum_info"] = {
            "vacuum_per_side": 8.0,
            "orthogonal_vacuum_axis": True,
            "cell_policy": "interface_ready_slab_cell",
            "cell_policy_version": 1,
            "canonicalization_mode": "already_orthogonal",
            "canonicalization_applies_physical_strain": False,
            "interface_ready": True,
        }
    return payload


__all__ = ["current_compact_transforms", "current_construction_controls"]
