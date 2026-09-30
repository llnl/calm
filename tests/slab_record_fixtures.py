"""Current slab-record fixtures shared by persistence and public tests."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from math import sqrt
from typing import Any

from calm.project.domain.contracts.slab_record import (
    SLAB_RECORD_SCHEMA,
    SLAB_RECORD_VERSION,
    canonical_slab_record_payload,
)
from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    slab_identity_payload,
)
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from oriented_slab_fixtures import current_compact_transforms


def current_surface_symmetry() -> dict[str, Any]:
    return {
        "policy": "validated_surface_pointgroup",
        "policy_version": 1,
        "mode": "identity_only",
        "status": "identity_only",
        "operation_count": 1,
        "symprec": 2e-5,
        "angle_tolerance": 3e-8,
        "metric_tolerance": 4e-5,
        "max_metric_residual": 0.0,
        "backend": None,
        "backend_version": None,
        "failure_type": None,
        "failure_message": None,
    }


def termination_digest(name: str, orientation: str = "plus_surface_normal") -> dict[str, Any]:
    digest = sha256(f"{orientation}:{name}".encode("utf-8")).hexdigest()
    return {
        "version": 2,
        "scheme": "decorated_periodic_halfspace_v2",
        "orientation": orientation,
        "digest": f"sha256:{digest}",
    }


def current_termination_identity(name: str = "top") -> dict[str, Any]:
    top = termination_digest(name)
    bottom = termination_digest(f"{name}-bottom", "minus_surface_normal")
    pair_payload = {
        "version": 2,
        "scheme": "ordered_termination_pair_v2",
        "top": top,
        "bottom": bottom,
    }
    pair_digest = sha256(
        json.dumps(
            pair_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    return {
        "version": 2,
        "scheme": "decorated_periodic_halfspace_v2",
        "primary": top,
        "top": top,
        "bottom": bottom,
        "pair": {
            "version": 2,
            "scheme": "ordered_termination_pair_v2",
            "digest": f"sha256:{pair_digest}",
        },
        "decorated_stacking_period_layers": 3,
        "stacking_translation_order": 1,
        "stacking_translation_frac": [0.0, 0.0],
        "cut_fractional": 0.5,
        "layer_tolerance_A": 0.3,
        "position_tolerance_frac": 1e-6,
        "stacking_tolerance_frac": 1e-8,
        "surface_symmetry": current_surface_symmetry(),
    }


def current_tilt() -> dict[str, Any]:
    return {
        "tilt_xy": [0.25, -0.5],
        "tilt_magnitude": (0.25**2 + 0.5**2) ** 0.5,
        "has_residual_tilt": True,
        "orthogonalize_c_applied": False,
        "integer_c_tilt_reduction_applied": True,
        "c_tilt_mn": [1, -2],
    }


def current_atoms(
    *,
    with_tilt: bool = True,
    miller: tuple[int, int, int] = (1, 0, 0),
    interface_ready: bool = False,
) -> dict[str, Any]:
    from current_structure_fixtures import current_atoms_payload

    info = {
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY: current_compact_transforms(
            hkl=miller,
            interface_ready=interface_ready,
        )
    }
    if with_tilt and not interface_ready:
        info["calm:tilt"] = current_tilt()
    return current_atoms_payload(
        numbers=(1,),
        cell=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0) if interface_ready else (0.25, -0.5, 1.0),
        ),
        scaled_positions=((0.0, 0.0, 0.0),),
        pbc=(True, True, False),
        info=info,
    )


def current_slab_payload(
    *,
    bulk_uid_full: str = "bulk:test",
    miller: tuple[int, int, int] = (1, 0, 0),
    label: str | None = None,
    shift: int = 0,
    top: str | None = None,
    bottom: str | None = None,
    identity: dict[str, Any] | None = None,
    atoms: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    user_payload: dict[str, Any] | None = None,
    formula: str | None = None,
    slab_thickness_A: float | None = None,
    vacuum_A: float | None = None,
    layers: int | None = None,
    characterization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    area_A2 = None
    if atoms is not None:
        atoms = dict(atoms)
        info_raw = atoms.get("info")
        if info_raw is None:
            info: Any = {}
        elif isinstance(info_raw, Mapping):
            info = dict(info_raw)
        else:
            info = info_raw
        if isinstance(info, dict):
            if vacuum_A is not None and vacuum_A > 0.0:
                cell = [list(row) for row in atoms["cell"]]
                cell[2][0] = 0.0
                cell[2][1] = 0.0
                atoms["cell"] = cell
                info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = current_compact_transforms(
                    hkl=miller,
                    interface_ready=True,
                )
            else:
                info.setdefault(
                    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
                    current_compact_transforms(hkl=miller),
                )
            atoms["info"] = info
        cell = atoms["cell"]
        a = [float(value) for value in cell[0]]
        b = [float(value) for value in cell[1]]
        cross = (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )
        area_A2 = sqrt(sum(value * value for value in cross))
    structure = {
        "atoms": atoms,
        "n_atoms": None if atoms is None else len(atoms["numbers"]),
        "area_A2": area_A2,
        "formula": formula,
        "slab_thickness_A": slab_thickness_A,
        "vacuum_A": vacuum_A,
        "layers": layers,
        "characterization": characterization,
    }
    return canonical_slab_record_payload(
        {
            "schema": SLAB_RECORD_SCHEMA,
            "version": SLAB_RECORD_VERSION,
            "params": dict(params or {}),
            "user_payload": dict(user_payload or {}),
            "termination": {
                "label": label,
                "shift": shift,
                "top": top,
                "bottom": bottom,
                "identity": identity,
            },
            "structure": structure,
        },
        bulk_uid_full=bulk_uid_full,
        miller=miller,
    )


def current_slab_uid(
    *,
    bulk_uid_full: str,
    miller: tuple[int, int, int],
    payload: dict[str, Any],
) -> str:
    return persisted_entity_uid_v2(
        "slab",
        slab_identity_payload(
            bulk_uid_full=bulk_uid_full,
            miller=miller,
            payload=payload,
        ),
    )
