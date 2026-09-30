"""calm.keys.uid

Deterministic, content-addressed identifiers.

Serialization boundary
----------------------
``canonical_json`` and ``hash_obj`` retain CALM's historical version-1
behavior.  They are not aliases for the type-tagged version-2 canonical-byte
contract in :mod:`calm.keys._canonical_v2`; migration must opt in explicitly.

Design goals
------------
- Stable across platforms (canonical JSON + SHA256).
- No reliance on object identity or filesystem paths.
- Explicit rounding rules for float stability.

Stage B scope
-------------
This module provides UID building blocks for the v2 pipeline:
Bulk -> Slab -> find_prototypes -> compute_strain_state -> build ->
compute_interfacial_energy.

Workspace persistence (Stage C+) uses these UIDs as primary keys.

Stage D groundwork
------------------
Stage D introduces the concept of *bulk states* (reference vs relaxed). To keep
UIDs stable and de-duplicated while allowing multiple bulk states per material,
we add:

- `reference_bulk_uid(material_uid)`:
    Deterministic UID for the reference bulk state of a given material.

- `slab_spec_uid_for_bulk(spec, bulk_uid, bulk_kind=...)`:
    A slab spec UID that can be anchored to a bulk state when the bulk is not
    the reference. This avoids collisions where the same SlabSpec applied to
    different relaxed cells would otherwise share the same slab_uid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from calm.structure.standardization import (
    exact_bool,
    exact_pbc3,
    finite_cell_rows,
    fingerprint_decimals,
    positive_finite_float,
    rounded_finite_array,
    wrap_fractional_positions,
)

# ---------------------------
# Canonical JSON + hashing
# ---------------------------


def _canonicalize(  # noqa: C901
    obj: Any,
    *,
    float_decimals: int = 12,
) -> Any:
    """Convert `obj` into a JSON-serializable canonical representation."""
    if obj is None:
        return None

    # Primitive types
    if isinstance(obj, (bool, int, str)):
        return obj

    if isinstance(obj, float):
        # Round to stabilize across minor FP noise.
        x = round(obj, int(float_decimals))
        if abs(x) < 10 ** (-int(float_decimals)):
            x = 0.0
        return x

    # numpy scalars
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return _canonicalize(float(obj), float_decimals=float_decimals)

    # dataclasses
    if is_dataclass(obj):
        return _canonicalize(asdict(obj), float_decimals=float_decimals)

    # numpy arrays
    if isinstance(obj, np.ndarray):
        arr = np.asarray(obj)
        if np.issubdtype(arr.dtype, np.integer):
            return arr.astype(int).tolist()
        return np.round(arr.astype(float), int(float_decimals)).tolist()

    # mappings
    if isinstance(obj, Mapping):
        # Sort keys for stable serialization.
        return {
            str(k): _canonicalize(v, float_decimals=float_decimals)
            for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))
        }

    # sequences
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v, float_decimals=float_decimals) for v in obj]

    # sets (sorted)
    if isinstance(obj, (set, frozenset)):
        return sorted(
            [_canonicalize(v, float_decimals=float_decimals) for v in obj],
            key=lambda x: json.dumps(x, sort_keys=True),
        )

    # fallback: repr
    return repr(obj)


def canonical_json(obj: Any, *, float_decimals: int = 12) -> str:
    """Return the frozen legacy version-1 canonical JSON string for ``obj``."""
    canon = _canonicalize(obj, float_decimals=float_decimals)
    return json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash_obj(obj: Any, *, float_decimals: int = 12) -> str:
    """Return the frozen legacy version-1 object digest."""

    return hashlib.sha256(
        canonical_json(obj, float_decimals=float_decimals).encode("utf-8")
    ).hexdigest()


def wrap01(x: float) -> float:
    """Wrap a float into [0, 1)."""
    y = float(x) % 1.0
    # Map 1.0 -> 0.0 if it arises from floating error
    if abs(y - 1.0) < 1e-15:
        y = 0.0
    return y


# ---------------------------
# Bulk / slab / interface UIDs
# ---------------------------


def material_uid_from_conv_atoms(
    conv_atoms: Any,
    *,
    symprec: float = 1e-5,
    no_idealize: bool = False,
    float_decimals: int = 12,
) -> str:
    """Hash one already-standardized conventional-cell representation.

    The result is atom-order and periodic-wrap invariant at the requested
    rounding precision.  Its interpretation is parameterized by ``symprec`` and
    ``no_idealize``; it is not a proof that all crystallographically equivalent
    input representations receive the same identifier.
    """

    precision = fingerprint_decimals(float_decimals)
    tolerance = positive_finite_float("symprec", symprec)
    preserve_metric = exact_bool("no_idealize", no_idealize)
    cell = rounded_finite_array(
        finite_cell_rows(conv_atoms.cell.array),
        decimals=precision,
    )
    fractional = wrap_fractional_positions(conv_atoms.get_scaled_positions(wrap=False))
    fractional = rounded_finite_array(fractional, decimals=precision)
    fractional[fractional == 1.0] = 0.0
    symbols = list(conv_atoms.get_chemical_symbols())
    if len(symbols) != fractional.shape[0]:
        raise ValueError("chemical symbols must match the number of atoms.")

    atoms = list(zip(symbols, fractional.tolist()))
    atoms.sort(key=lambda item: (item[0], *item[1]))
    pbc = exact_pbc3(conv_atoms.pbc, require_all=False)
    payload = {
        "cell": cell.tolist(),
        "atoms": [
            {"symbol": symbol, "frac": [float(value) for value in frac]}
            for symbol, frac in atoms
        ],
        "pbc": pbc.tolist(),
        "symprec": tolerance,
        "no_idealize": preserve_metric,
    }
    return "mat:" + hash_obj(payload, float_decimals=precision)


def reference_bulk_uid(material_uid: str) -> str:
    """Deterministic bulk_uid for the *reference* bulk state of a material.

    Convention:
      material_uid = "mat:<X>" -> bulk_uid = "bulk:<X>"
      otherwise                -> bulk_uid = "bulk:<material_uid>"
    """
    m = str(material_uid)
    if m.startswith("mat:"):
        return "bulk:" + m[4:]
    return "bulk:" + m


_SLAB_SPEC_BOUNDED_GAUGE_DEFAULTS: dict[str, Any] = {
    "primitive_max_denominator": 12,
    "primitive_reduction_max_iter": 100,
    "stacking_search_radius": 2,
    "c_tilt_search": 6,
    "c_tilt_singular_tolerance": 1e-12,
}


def _slab_spec_uid_payload(spec: Any) -> Any:
    """Return a migration-safe slab-spec identity payload.

    WP-07c added explicit bounded-gauge controls to ``SlabSpec``.  Their
    historical defaults were already active in the implementation, so default
    values are omitted from the identity payload to preserve pre-WP-07c slab
    specification UIDs.  Nondefault controls remain identity-affecting.
    """
    if is_dataclass(spec):
        payload: Any = asdict(spec)
    elif isinstance(spec, Mapping):
        payload = dict(spec)
    else:
        return spec
    for name, default in _SLAB_SPEC_BOUNDED_GAUGE_DEFAULTS.items():
        if name in payload and payload[name] == default:
            payload.pop(name)
    if payload.get("target_width") is not None:
        from calm.slab.oriented._thickness import target_width_policy_metadata

        payload.update(target_width_policy_metadata())
    return payload


def slab_spec_uid(spec: Any, *, float_decimals: int = 12) -> str:
    """UID for a slab specification *independent* of bulk state."""
    payload = _slab_spec_uid_payload(spec)
    return "sspec:" + hash_obj(payload, float_decimals=float_decimals)


def slab_spec_uid_for_bulk(
    spec: Any,
    *,
    bulk_uid: str,
    bulk_kind: str = "reference",
    float_decimals: int = 12,
) -> str:
    """UID for a slab specification anchored to a bulk state when needed.

    Why?
    ----
    A SlabSpec is a pure configuration object and is safe to hash. However, the
    resulting slab structure also depends on the *bulk cell* it is applied to.
    For relaxed bulk states (kind != "reference"), we must prevent collisions
    where the same SlabSpec applied to different relaxed cells yields different
    slabs but the same slab_uid.

    Policy:
    - If bulk_kind == "reference": return slab_spec_uid(spec).
    - Else: return "sspec:" + hash_obj({"spec": spec, "bulk_uid": bulk_uid}).

    The UID remains stable across platforms via canonical JSON.
    """
    if str(bulk_kind) == "reference":
        return slab_spec_uid(spec, float_decimals=float_decimals)
    payload = {
        "spec": _slab_spec_uid_payload(spec),
        "bulk_uid": str(bulk_uid),
        "bulk_kind": str(bulk_kind),
    }
    return "sspec:" + hash_obj(payload, float_decimals=float_decimals)


def slab_uid(
    *,
    material_uid: str,
    miller: Sequence[int],
    slab_spec_uid: str,
) -> str:
    hkl = (int(miller[0]), int(miller[1]), int(miller[2]))
    h, k, l = hkl  # noqa: E741 - canonical Miller index triple (h,k,l)
    return f"slab:{material_uid}:{h},{k},{l}:{slab_spec_uid}"


def _prototype_uid_v3_payload(
    *,
    slab_uid_a: str,
    slab_uid_b: str,
    primitive_pair_key: Sequence[int],
    pair_key_version: int,
    pair_symmetry_policy: str,
    correspondence_orientation: str,
    material_exchange_identified: bool,
) -> dict[str, Any]:
    """Return the exact domain-separated coupled-prototype identity payload."""

    if not isinstance(slab_uid_a, str) or not slab_uid_a:
        raise ValueError("slab_uid_a must be a non-empty string")
    if not isinstance(slab_uid_b, str) or not slab_uid_b:
        raise ValueError("slab_uid_b must be a non-empty string")
    if isinstance(pair_key_version, (bool, np.bool_)) or not isinstance(
        pair_key_version, (int, np.integer)
    ):
        raise TypeError("pair_key_version must be a positive integer")
    key_version = int(pair_key_version)
    if key_version <= 0:
        raise ValueError("pair_key_version must be a positive integer")

    try:
        raw_key = tuple(primitive_pair_key)
    except TypeError as exc:
        raise TypeError("primitive_pair_key must be an integer sequence") from exc
    if len(raw_key) != 8:
        raise ValueError("primitive_pair_key must contain exactly eight integers")
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer))
        for value in raw_key
    ):
        raise TypeError("primitive_pair_key must contain exact integers")
    pair_key = tuple(int(value) for value in raw_key)

    if pair_symmetry_policy not in {"proper", "full"}:
        raise ValueError("pair_symmetry_policy must be 'proper' or 'full'")
    if correspondence_orientation not in {"proper", "all"}:
        raise ValueError("correspondence_orientation must be 'proper' or 'all'")
    if not isinstance(material_exchange_identified, (bool, np.bool_)):
        raise TypeError("material_exchange_identified must be a boolean")
    exchange = bool(material_exchange_identified)

    slab_uids = (slab_uid_a, slab_uid_b)
    if exchange:
        slab_uids = tuple(sorted(slab_uids))

    return {
        "identity_algorithm": "primitive_coupled_pair_v2",
        "slab_uids": list(slab_uids),
        "primitive_pair_key": list(pair_key),
        "pair_key_version": key_version,
        "pair_symmetry_policy": pair_symmetry_policy,
        "correspondence_orientation": correspondence_orientation,
        "material_exchange_identified": exchange,
    }


def prototype_uid_v3(
    *,
    slab_uid_a: str,
    slab_uid_b: str,
    primitive_pair_key: Sequence[int],
    pair_key_version: int,
    pair_symmetry_policy: str,
    correspondence_orientation: str,
    material_exchange_identified: bool,
) -> str:
    """Return a coupled-prototype UID from exact primitive pair identity.

    Ranking diagnostics, source repetition, and discovery order are excluded.
    The A/B slab order remains significant unless material exchange was
    explicitly included in the pair-identity policy.
    """

    payload = _prototype_uid_v3_payload(
        slab_uid_a=slab_uid_a,
        slab_uid_b=slab_uid_b,
        primitive_pair_key=primitive_pair_key,
        pair_key_version=pair_key_version,
        pair_symmetry_policy=pair_symmetry_policy,
        correspondence_orientation=correspondence_orientation,
        material_exchange_identified=material_exchange_identified,
    )
    return "proto:v3:" + hash_obj(payload)


def strain_model_uid(model: Any, *, float_decimals: int = 12) -> str:
    return "smodel:" + hash_obj(model, float_decimals=float_decimals)


def strained_uid(*, prototype_uid: str, strain_model_uid: str) -> str:
    return f"strain:{prototype_uid}:{strain_model_uid}"


def build_uid(
    *,
    strained_uid: str,
    translation_frac: Sequence[float],
    z_padding: float,
    vacuum_padding: float | None = None,
    round_decimals: int = 8,
) -> str:
    if len(translation_frac) != 2:
        raise ValueError("translation_frac must have length 2")
    t1 = round(wrap01(float(translation_frac[0])), int(round_decimals))
    t2 = round(wrap01(float(translation_frac[1])), int(round_decimals))
    zp = round(float(z_padding), int(round_decimals))
    vp = (
        None
        if vacuum_padding is None
        else round(float(vacuum_padding), int(round_decimals))
    )
    # Avoid -0.0
    if abs(t1) < 10 ** (-int(round_decimals)):
        t1 = 0.0
    if abs(t2) < 10 ** (-int(round_decimals)):
        t2 = 0.0
    if abs(zp) < 10 ** (-int(round_decimals)):
        zp = 0.0
    if vp is not None and abs(vp) < 10 ** (-int(round_decimals)):
        vp = 0.0
    suffix = f"build:{strained_uid}:t={t1},{t2}:zp={zp}"
    if vp is not None:
        suffix += f":vac={vp}"
    return suffix


def energy_config_uid(econf: Any, *, float_decimals: int = 12) -> str:
    return "econf:" + hash_obj(econf, float_decimals=float_decimals)


def calculator_uid(calc_spec: Mapping[str, Any], *, float_decimals: int = 12) -> str:
    # NOTE: CalculatorSpec.fingerprint() may use a different convention. This UID is
    # used for generic calc provenance (e.g., ASE calculators) and includes a prefix.
    return "calc:" + hash_obj(dict(calc_spec), float_decimals=float_decimals)


def energy_uid(*, build_uid: str, calc_uid: str, econf_uid: str) -> str:
    return f"energy:{build_uid}:{calc_uid}:{econf_uid}"
