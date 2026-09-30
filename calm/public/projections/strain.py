"""Exact public strain projection for persisted interface candidates.

Current coupled-v2 prototype payloads preserve the unsigned affine-invariant
quantities ``d_cell``, ``d_area``, and ``d_shape``.  They do not preserve the
signed principal Hencky strain pair.  Public projections may therefore recover
absolute diagnostics exactly, but must not manufacture signed principal
strains from those invariants.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import Any


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def project_candidate_strain_metrics(row: Any) -> dict[str, Any]:
    """Return one candidate row with scientifically valid strain diagnostics.

    A complete supplied ``eps1``/``eps2`` pair is treated as authoritative and
    supports signed diagnostics.  Otherwise, the current persisted invariants
    recover only unsigned quantities.  In particular,

    ``max(|eps1|, |eps2|) = (|d_area| + |d_shape|) / (2 * sqrt(2))``.

    Existing derived values are overwritten whenever their authoritative
    inputs are available.  This prevents an earlier projection alias from
    surviving through ``setdefault`` or row-merging behavior.
    """

    if isinstance(row, Mapping):
        out = dict(row)
    elif hasattr(row, "to_dict"):
        out = dict(row.to_dict())
    else:
        out = {
            key: value for key, value in vars(row).items() if not key.startswith("_")
        }
    eps1 = _finite_float(out.get("eps1"))
    eps2 = _finite_float(out.get("eps2"))
    d_cell = _finite_float(out.get("d_cell"))
    d_area = _finite_float(out.get("d_area"))
    d_shape = _finite_float(out.get("d_shape"))

    if eps1 is not None and eps2 is not None:
        out["eps1"] = eps1
        out["eps2"] = eps2
        out["max_principal_strain"] = max(abs(eps1), abs(eps2))
        out["strain_norm"] = math.hypot(eps1, eps2)
        out["isotropic_strain_signed"] = 0.5 * (eps1 + eps2)
        out["isotropic_strain_norm"] = abs(eps1 + eps2) / math.sqrt(2.0)
        out["deviatoric_strain_norm"] = abs(eps1 - eps2) / math.sqrt(2.0)
        return out

    # A partial signed pair cannot support signed public interpretation.
    out.pop("eps1", None)
    out.pop("eps2", None)
    out.pop("isotropic_strain_signed", None)

    if d_area is not None:
        out["isotropic_strain_norm"] = abs(d_area) / 2.0
    if d_shape is not None:
        out["deviatoric_strain_norm"] = abs(d_shape) / 2.0
    if d_area is not None and d_shape is not None:
        out["max_principal_strain"] = (abs(d_area) + abs(d_shape)) / (
            2.0 * math.sqrt(2.0)
        )
        if d_cell is None:
            out["strain_norm"] = 0.5 * math.hypot(d_area, d_shape)
    if d_cell is not None:
        out["strain_norm"] = abs(d_cell) / 2.0

    return out
