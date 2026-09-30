"""Public oriented-slab construction and registry helpers.

The authoritative constructor accepts :class:`calm.bulk.Bulk` and delegates to
CALM's exact primitive-bulk slab kernel.  This module adds the compact
``Atoms.info`` transform payload used by persistence workflows and exposes the
registered-position helper used by interface search.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, overload

import numpy as np

from calm.serialization.scientific import scientific_json_native as _json_native
from calm.slab.oriented import builder as _ops
from calm.slab.oriented.transforms import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    OrientedSlabTransforms,
    from_transforms_payload,
    put_transforms_payload_in_atoms_info,
    to_transforms_payload,
)
from calm.slab.oriented.sidecar import (
    read_transforms_sidecar,
    write_transforms_sidecar,
)

OrientedSlabResult = _ops.OrientedSlabResult


def _kernel_transforms_to_payload(kernel_transforms: Any) -> dict[str, Any]:
    """Project the exact kernel provenance into the compact public payload."""
    rotation = np.asarray(kernel_transforms.R_conv_to_slab, dtype=float)
    if rotation.shape != (3, 3):
        raise ValueError("R_conv_to_slab must have shape (3, 3)")

    hkl = tuple(int(value) for value in kernel_transforms.hkl_reduced)
    if len(hkl) != 3:
        raise ValueError("hkl_reduced must contain three integers")

    extra: dict[str, Any] = {
        "layers": int(kernel_transforms.layers),
        "S_conv_to_surface_col": _json_native(kernel_transforms.S_conv_to_surface_col),
        "U_inplane_col": _json_native(kernel_transforms.U_inplane_col),
        "P_supercell_row": _json_native(kernel_transforms.P_supercell_row),
        "R_conv_to_slab": _json_native(kernel_transforms.R_conv_to_slab),
        "R_slab_to_conv": _json_native(kernel_transforms.R_slab_to_conv),
        "R_align": _json_native(kernel_transforms.R_align),
        "M_conv_to_slab_cart": _json_native(kernel_transforms.M_conv_to_slab_cart()),
        "M_slab_to_conv_cart": _json_native(kernel_transforms.M_slab_to_conv_cart()),
        "supercell_reference": kernel_transforms.supercell_reference,
        "miller_primitive": _json_native(kernel_transforms.miller_primitive),
        "construction_controls": _json_native(kernel_transforms.construction_controls),
    }
    for name in (
        "L_c_tilt_row",
        "c_tilt_mn",
        "shear_info",
        "vacuum_info",
        "canonical_sign_fix",
    ):
        value = getattr(kernel_transforms, name)
        if value is not None:
            extra[name] = _json_native(value)

    payload = to_transforms_payload(
        OrientedSlabTransforms(U=rotation, hkl=hkl, extra=extra)
    )
    return from_transforms_payload(payload).payload


def _attach_transforms_payload(result: Any) -> None:
    """Attach current transform provenance to returned ASE objects."""
    payload = _kernel_transforms_to_payload(result.transforms)
    for atoms in (result.block, result.slab):
        put_transforms_payload_in_atoms_info(
            atoms,
            payload,
            key=ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
        )


def build_oriented_slab(*args: Any, **kwargs: Any) -> OrientedSlabResult:
    """Build an exact primitive-bulk oriented slab and attach provenance."""
    result = _ops.build_oriented_slab(*args, **kwargs)
    _attach_transforms_payload(result)
    return result


@overload
def compute_registered_positions(
    atoms: Any,
    translation_frac: Sequence[float],
    *,
    eps: float = 1e-12,
    wrap_xy: bool = True,
    clamp_z: bool = True,
    inplace: bool = False,
) -> Any: ...


@overload
def compute_registered_positions(
    positions: np.ndarray,
    translation_frac: Sequence[float],
    *,
    cell: np.ndarray,
    eps: float = 1e-12,
    wrap_xy: bool = True,
    clamp_z: bool = True,
) -> np.ndarray: ...


def compute_registered_positions(  # noqa: C901
    obj: Any,
    translation_frac: Sequence[float],
    *,
    cell: Optional[np.ndarray] = None,
    eps: float = 1e-12,
    wrap_xy: bool = True,
    clamp_z: bool = True,
    inplace: bool = False,
) -> Any:
    """Apply a registry translation while wrapping only x/y and clamping z.

    ``obj`` may be an ASE ``Atoms``-like object or an ``(N, 3)`` Cartesian
    position array.  Array inputs require the ASE row-convention ``cell``.
    """
    translation = np.asarray(translation_frac, dtype=float).reshape(-1)
    if translation.size == 2:
        tx, ty = float(translation[0]), float(translation[1])
        tz = 0.0
    elif translation.size == 3:
        tx, ty, tz = (float(value) for value in translation)
    else:
        raise ValueError(
            f"translation_frac must have length 2 or 3; got {translation.size}"
        )

    if hasattr(obj, "get_scaled_positions") and hasattr(obj, "set_scaled_positions"):
        out = obj if inplace else obj.copy()
        scaled = np.asarray(out.get_scaled_positions(wrap=False), dtype=float)
        if scaled.ndim != 2 or scaled.shape[1] != 3:
            raise ValueError(
                f"Expected scaled positions shape (N, 3); got {scaled.shape}"
            )
        scaled += np.array([tx, ty, tz], dtype=float)
        if wrap_xy:
            scaled[:, :2] -= np.floor(scaled[:, :2])
        if clamp_z:
            scaled[:, 2] = np.clip(scaled[:, 2], 0.0, 1.0 - eps)
        out.set_scaled_positions(scaled)
        return out

    positions = np.asarray(obj, dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise TypeError(
            "compute_registered_positions expected an ASE Atoms-like object "
            "or an (N, 3) positions array"
        )
    if cell is None:
        raise TypeError("When passing a positions array, you must provide cell=...")

    cell_array = np.asarray(cell, dtype=float)
    if cell_array.shape != (3, 3):
        raise ValueError(f"cell must be shape (3, 3); got {cell_array.shape}")

    fractional = positions @ np.linalg.inv(cell_array)
    fractional += np.array([tx, ty, tz], dtype=float)
    if wrap_xy:
        fractional[:, :2] -= np.floor(fractional[:, :2])
    if clamp_z:
        fractional[:, 2] = np.clip(fractional[:, 2], 0.0, 1.0 - eps)
    return fractional @ cell_array


__all__ = [
    "OrientedSlabResult",
    "OrientedSlabTransforms",
    "build_oriented_slab",
    "compute_registered_positions",
    "to_transforms_payload",
    "from_transforms_payload",
    "read_transforms_sidecar",
    "write_transforms_sidecar",
]
