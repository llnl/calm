"""JSON sidecar I/O for slab provenance.

Why sidecars exist
------------------
CALM’s canonical provenance lives in the workspace database. However, users
frequently export structures to standalone files (e.g., POSCAR/CONTCAR) to run
external workflows. Once a structure leaves a workspace directory, the database
is no longer available, and the chain of crystallographic transforms would be
lost.

A small JSON *sidecar* file solves this portability problem: it lets a structure
file and its provenance travel together.

This module is therefore an *external interchange* convenience:

- It does **not** replace database persistence.
- It does **not** define the slab/transform schema.
- It provides a stable, explicit file format for optional provenance export.

Version-1 compatibility
-----------------------
Current CALM writers include a complete ``construction_controls`` record.
Standalone version-1 sidecars exported before that record was introduced may
omit it. The sidecar reader preserves that omission as unknown provenance and
never fills in current defaults. Present historical version-1 control mappings
are likewise preserved as opaque transport data rather than rewritten into the
current vocabulary. Current ``Atoms.info`` and project records use a stricter
admission profile and reject both forms as exact-current state.

Sidecar naming convention
-------------------------
Given a structure path ``p``:

- If ``p`` has a suffix (e.g. ``LiF.vasp``), the sidecar is
  ``LiF.vasp.transforms.json``.
- If ``p`` has no suffix (e.g. ``POSCAR``), the sidecar is
  ``POSCAR.transforms.json``.

This convention is robust for VASP-style filenames and avoids the
``Path.with_suffix`` edge case on suffix-less files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union

DEFAULT_SIDECAR_SUFFIX = ".transforms.json"


PathLike = Union[str, Path]


def transforms_sidecar_path(structure_path: PathLike) -> Path:
    """Compute the default JSON sidecar path for a structure file."""

    p = Path(structure_path)

    # For POSCAR-like files with no suffix, Path.with_suffix() raises.
    if p.suffix:
        return p.with_suffix(p.suffix + DEFAULT_SIDECAR_SUFFIX)
    return p.with_name(p.name + DEFAULT_SIDECAR_SUFFIX)


def write_transforms_sidecar(
    structure_path: PathLike,
    transforms: Any,
    *,
    sidecar_path: Optional[PathLike] = None,
    indent: int = 2,
) -> Path:
    """Write transforms provenance to a JSON sidecar.

    Parameters
    ----------
    structure_path:
        Path to the structure file (e.g. POSCAR).
    transforms:
        A compact version-1 transform object, a version-1 sidecar payload
        mapping, or the detailed transform object returned by the current slab
        kernel. Current kernel records must carry complete construction
        controls; older standalone payloads may omit them.
    sidecar_path:
        Optional explicit sidecar path. If omitted, uses
        :func:`transforms_sidecar_path`.
    indent:
        JSON indentation.

    Returns
    -------
    Path
        The written sidecar path.
    """

    if transforms is None:
        raise ValueError("transforms must not be None")

    sidecar = (
        Path(sidecar_path)
        if sidecar_path is not None
        else transforms_sidecar_path(structure_path)
    )
    payload = _to_payload(transforms)

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(payload, indent=indent, sort_keys=True),
        encoding="utf-8",
    )
    return sidecar


def read_transforms_sidecar(
    structure_path: PathLike,
    *,
    sidecar_path: Optional[PathLike] = None,
) -> Any:
    """Read one explicit version-1 transform provenance sidecar.

    Historical wrappers and arbitrary JSON mappings are rejected. A bare
    version-1 payload may omit ``construction_controls`` only at this external
    sidecar boundary; absence remains explicit unknown provenance.
    """

    sidecar = (
        Path(sidecar_path)
        if sidecar_path is not None
        else transforms_sidecar_path(structure_path)
    )
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid transforms sidecar: {sidecar}") from exc

    from calm.slab.oriented.transforms import from_transforms_sidecar_payload

    return from_transforms_sidecar_payload(payload)


def _to_payload(transforms: Any) -> dict[str, Any]:
    """Validate and normalize one version-1 sidecar payload."""

    from calm.slab.oriented.transforms import (
        OrientedSlabTransforms,
        from_transforms_payload,
        from_transforms_sidecar_payload,
    )

    if isinstance(transforms, OrientedSlabTransforms):
        return from_transforms_sidecar_payload(transforms.payload).payload
    if isinstance(transforms, Mapping):
        return from_transforms_sidecar_payload(transforms).payload

    # The public slab builder returns a detailed kernel provenance object.
    # Convert that explicit current type through the one canonical projection
    # rather than accepting arbitrary dataclasses or ``to_dict`` providers.
    required_kernel_fields = (
        "hkl_reduced",
        "layers",
        "S_conv_to_surface_col",
        "U_inplane_col",
        "P_supercell_row",
        "R_conv_to_slab",
        "R_slab_to_conv",
        "R_align",
        "L_c_tilt_row",
        "c_tilt_mn",
        "shear_info",
        "vacuum_info",
        "canonical_sign_fix",
        "supercell_reference",
        "miller_primitive",
        "construction_controls",
        "M_conv_to_slab_cart",
        "M_slab_to_conv_cart",
    )
    if all(hasattr(transforms, name) for name in required_kernel_fields):
        from calm.slab.oriented.model import _kernel_transforms_to_payload

        return from_transforms_payload(
            _kernel_transforms_to_payload(transforms)
        ).payload

    raise TypeError(
        "Unsupported transforms object; expected a compact version-1 transform "
        "object, a version-1 sidecar payload mapping, or the detailed transform "
        "object returned by the current slab builder. "
        f"Got: {type(transforms).__name__}"
    )
