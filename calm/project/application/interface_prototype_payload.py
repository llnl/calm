"""Schema and helpers for interface prototype build payloads.

This module centralizes the serialization and validation of the payload stored
on persisted Prototype records so rehydration and exact validation remain centralized.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any, Mapping

import numpy as np

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_VERSION,
    authoritative_pareto_metadata,
)
from calm.interface.matching.zur_mcgill import zur_mcgill_diagnostic_metadata

from ._json import json_native

if TYPE_CHECKING:
    from calm.interface.model import (
        InterfacePrototype,
        MatchSourceProvenance2D,
        PairIdentity2D,
        SupercellRecipe2D,
    )

    from ..domain.models import Prototype
    from ..ports.uow import UnitOfWork

SCHEMA_V2 = "calm.interface_prototype_build_payload/v2"
SCHEMA = SCHEMA_V2

IDENTITY_ALGORITHM_V2 = "primitive_coupled_pair_v2"


def interface_prototype_identity_algorithm(payload: Mapping[str, Any]) -> str:
    """Return the explicitly declared coupled prototype identity algorithm."""

    algorithm = payload.get("identity_algorithm")
    if algorithm != IDENTITY_ALGORITHM_V2:
        raise ValueError(
            "Interface prototype payloads must declare "
            "primitive_coupled_pair_v2 identity"
        )
    return IDENTITY_ALGORITHM_V2


_MISSING = object()


def _get_value(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        value = getattr(obj, name, _MISSING)
        if value is not _MISSING:
            return value
    return default


def _positive_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number <= 0.0:
        return None
    return number


def _supercell_area_A2(supercell: Any) -> float | None:
    if supercell is None:
        return None
    matrix = _get_value(supercell, "S_red", default=None)
    if matrix is None:
        return None
    try:
        if hasattr(matrix, "tolist"):
            matrix = matrix.tolist()
        a = float(matrix[0][0])
        b = float(matrix[0][1])
        c = float(matrix[1][0])
        d = float(matrix[1][1])
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    return _positive_finite_float(abs(a * d - b * c))


def infer_interface_area_A2(prototype: Any) -> float | None:
    """Return a positive interface area from explicit fields or supercells.

    The authoritative prototype column is preferred. Mapping-style inputs are
    accepted when they use the current coupled-v2 payload fields.
    """

    payload = _get_value(prototype, "payload", default=None)
    if not isinstance(payload, Mapping):
        payload = prototype if isinstance(prototype, Mapping) else {}
    metrics = payload.get("metrics") if isinstance(payload, Mapping) else None

    for value in (
        _get_value(
            prototype,
            "interface_area",
            "interface_area_A2",
            "area_A2",
            default=None,
        ),
        _get_value(
            payload,
            "interface_area",
            "interface_area_A2",
            "area_A2",
            default=None,
        ),
        _get_value(
            metrics,
            "interface_area",
            "interface_area_A2",
            "area_A2",
            default=None,
        ),
    ):
        area = _positive_finite_float(value)
        if area is not None:
            return area

    areas: list[float] = []
    for name in ("supercell_a", "supercell_b"):
        supercell = _get_value(prototype, name, default=None)
        if supercell is None:
            supercell = _get_value(payload, name, default=None)
        area = _supercell_area_A2(supercell)
        if area is not None:
            areas.append(area)
    if not areas:
        return None
    return sum(areas) / len(areas)


def serialize_interface_prototype(ip: Any) -> dict[str, Any]:
    """Serialize one current primitive coupled-pair prototype.

    Only :class:`~calm.interface.model.InterfacePrototype` is accepted. There
    is no fallback serializer for independent-surface candidates or incomplete
    prototype-like mappings.
    """

    from calm.interface.model import InterfacePrototype

    if not isinstance(ip, InterfacePrototype):
        raise TypeError("serialize_interface_prototype requires an InterfacePrototype")

    slab_a_uid = getattr(ip.slab_a, "project_slab_uid_full", None) or ip.slab_a_uid
    slab_b_uid = getattr(ip.slab_b, "project_slab_uid_full", None) or ip.slab_b_uid
    if not slab_a_uid or not slab_b_uid:
        raise ValueError("InterfacePrototype requires persisted slab identities")

    interface_area = infer_interface_area_A2(ip)
    if interface_area is None:
        raise ValueError("InterfacePrototype requires a positive finite interface area")

    pareto_payload = None
    if (
        ip.pareto_policy == STRAIN_SIZE_PARETO_POLICY
        and ip.pareto_policy_version == STRAIN_SIZE_PARETO_VERSION
        and ip.pareto_d_cell_key is not None
    ):
        pareto_payload = authoritative_pareto_metadata(
            is_member=bool(ip.is_pareto),
            rank=ip.pareto_rank,
            population_size=int(ip.pareto_population_size),
            population_scope=str(ip.pareto_population_scope or ""),
            d_cell_key=int(ip.pareto_d_cell_key),
        )

    payload = {
        "schema": SCHEMA_V2,
        "identity_algorithm": IDENTITY_ALGORITHM_V2,
        "interface_prototype_uid": ip.prototype_uid,
        "slab_a_uid": str(slab_a_uid),
        "slab_b_uid": str(slab_b_uid),
        "miller_a": list(ip.miller_a),
        "miller_b": list(ip.miller_b),
        "supercell_a": ip.supercell_a.to_dict(),
        "supercell_b": ip.supercell_b.to_dict(),
        "pair_identity": ip.pair_identity.to_dict(),
        "source_provenance": ip.source_provenance.to_dict(),
        "metrics": {
            "match_score": float(ip.match_score),
            "d_size": float(ip.d_size),
            "d_cell": float(ip.d_cell),
            "d_area": float(ip.d_area),
            "d_shape": float(ip.d_shape),
            "rel_da": float(ip.rel_da),
            "rel_db": float(ip.rel_db),
            "d_gamma_deg": float(ip.d_gamma_deg),
            "zur_mcgill_diagnostic": {
                **zur_mcgill_diagnostic_metadata(),
                "rel_da": float(ip.rel_da),
                "rel_db": float(ip.rel_db),
                "d_gamma_deg": float(ip.d_gamma_deg),
            },
            "n_atoms_interface": int(ip.n_atoms_interface),
            "interface_area_A2": float(interface_area),
        },
        "pareto": pareto_payload,
    }
    return json_native(payload)


def _validate_miller(name: str, value: Any) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain three exact integers")
    if any(isinstance(item, bool) or not isinstance(item, Integral) for item in value):
        raise TypeError(f"{name} must contain three exact integers")
    return tuple(int(item) for item in value)


def _validate_metrics(metrics: Any) -> None:
    if not isinstance(metrics, Mapping):
        raise TypeError("metrics must be a mapping")
    real_fields = (
        "match_score",
        "d_size",
        "d_cell",
        "d_area",
        "d_shape",
        "rel_da",
        "rel_db",
        "d_gamma_deg",
        "interface_area_A2",
    )
    required = (*real_fields, "n_atoms_interface")
    missing = [name for name in required if name not in metrics]
    if missing:
        raise ValueError("metrics are missing fields: " + ", ".join(missing))
    for name in real_fields:
        value = metrics[name]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"metrics.{name} must be a finite real")
        number = float(value)
        if not isfinite(number):
            raise ValueError(f"metrics.{name} must be finite")
        if number < 0.0:
            raise ValueError(f"metrics.{name} must be nonnegative")
    if float(metrics["interface_area_A2"]) <= 0.0:
        raise ValueError("metrics.interface_area_A2 must be positive")
    n_atoms = metrics["n_atoms_interface"]
    if isinstance(n_atoms, bool) or not isinstance(n_atoms, Integral):
        raise TypeError("metrics.n_atoms_interface must be a positive integer")
    if int(n_atoms) <= 0:
        raise ValueError("metrics.n_atoms_interface must be a positive integer")


@dataclass(frozen=True)
class _DecodedInterfacePrototypePayload:
    """One fully decoded current interface-prototype payload."""

    prototype_uid: str
    slab_a_uid: str
    slab_b_uid: str
    miller_a: tuple[int, int, int]
    miller_b: tuple[int, int, int]
    supercell_a: SupercellRecipe2D
    supercell_b: SupercellRecipe2D
    pair_identity: PairIdentity2D
    source_provenance: MatchSourceProvenance2D
    metrics: Mapping[str, Any]
    pareto: Mapping[str, Any] | None


def _required_nonempty_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid {key}")
    return value


def _decode_interface_prototype_payload(
    payload: Mapping[str, Any],
) -> _DecodedInterfacePrototypePayload:
    """Decode and validate the sole supported prototype payload once."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    if payload.get("schema") != SCHEMA_V2:
        raise ValueError(f"unsupported payload schema: {payload.get('schema')!r}")

    interface_prototype_identity_algorithm(payload)
    prototype_uid = _required_nonempty_string(payload, "interface_prototype_uid")
    slab_a_uid = _required_nonempty_string(payload, "slab_a_uid")
    slab_b_uid = _required_nonempty_string(payload, "slab_b_uid")
    miller_a = _validate_miller("miller_a", payload.get("miller_a"))
    miller_b = _validate_miller("miller_b", payload.get("miller_b"))
    metrics = payload.get("metrics")
    _validate_metrics(metrics)

    from calm.interface.model import (
        MatchSourceProvenance2D,
        PairIdentity2D,
        SupercellRecipe2D,
    )
    from calm.math2d.paired_lattice import determinantal_divisor_rank2

    for name in (
        "supercell_a",
        "supercell_b",
        "pair_identity",
        "source_provenance",
    ):
        if not isinstance(payload.get(name), Mapping):
            raise TypeError(f"{name} must be a mapping")

    supercell_a = SupercellRecipe2D.from_dict(payload["supercell_a"])
    supercell_b = SupercellRecipe2D.from_dict(payload["supercell_b"])
    pair_identity = PairIdentity2D.from_dict(payload["pair_identity"])
    provenance = MatchSourceProvenance2D.from_dict(payload["source_provenance"])

    primitive_pair = np.vstack([supercell_a.N_tot, supercell_b.N_tot])
    if determinantal_divisor_rank2(primitive_pair) != 1:
        raise ValueError("supercell maps must form a primitive pair")
    if not np.array_equal(
        primitive_pair @ provenance.representative_source_right_factor,
        provenance.representative_source_pair_matrix,
    ):
        raise ValueError(
            "source provenance does not reconstruct from the primitive pair"
        )
    if pair_identity.key_version <= 0:
        raise ValueError("pair identity version must be positive")

    pareto = payload.get("pareto")
    if pareto is not None:
        from calm.analysis.pareto import is_strain_size_pareto_metadata

        if not is_strain_size_pareto_metadata(pareto):
            raise ValueError("pareto must be a complete strain-size record")

    return _DecodedInterfacePrototypePayload(
        prototype_uid=prototype_uid,
        slab_a_uid=slab_a_uid,
        slab_b_uid=slab_b_uid,
        miller_a=miller_a,
        miller_b=miller_b,
        supercell_a=supercell_a,
        supercell_b=supercell_b,
        pair_identity=pair_identity,
        source_provenance=provenance,
        metrics=metrics,
        pareto=pareto,
    )


def validate_interface_prototype_payload(
    payload: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Validate the sole supported primitive coupled-pair payload."""

    try:
        _decode_interface_prototype_payload(payload)
    except (TypeError, ValueError) as exc:
        return False, f"invalid coupled prototype payload: {exc}"
    return True, None


def _record_projection(record: Any, name: str) -> Any:
    value = getattr(record, name, _MISSING)
    if value is _MISSING:
        raise ValueError(f"Prototype record is missing {name} projection")
    return value


def _require_equal_projection(
    *,
    name: str,
    observed: Any,
    authoritative: Any,
) -> None:
    if observed != authoritative:
        raise ValueError(
            f"Prototype {name} projection is inconsistent with its current payload"
        )


def _string_projection(record: Any, name: str) -> str:
    value = _record_projection(record, name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Prototype record {name} projection must be non-empty")
    return value


def _finite_real_projection(record: Any, name: str) -> float:
    value = _record_projection(record, name)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"Prototype record {name} projection must be a finite real")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"Prototype record {name} projection must be finite")
    return result


def _integer_projection(record: Any, name: str) -> int:
    value = _record_projection(record, name)
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"Prototype record {name} projection must be an integer")
    return int(value)


def _boolean_projection(record: Any, name: str) -> bool:
    value = _record_projection(record, name)
    if not isinstance(value, bool):
        raise TypeError(f"Prototype record {name} projection must be a boolean")
    return value


def _optional_integer_projection(record: Any, name: str) -> int | None:
    value = _record_projection(record, name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"Prototype record {name} projection must be an integer or None"
        )
    return int(value)


def _validate_prototype_record_projections(
    record: Any,
    decoded: _DecodedInterfacePrototypePayload,
) -> None:
    """Verify indexed SQL projections agree with the authoritative payload."""

    metrics = decoded.metrics
    _require_equal_projection(
        name="side-A slab identity",
        observed=_string_projection(record, "slab_a_uid_full"),
        authoritative=decoded.slab_a_uid,
    )
    _require_equal_projection(
        name="side-B slab identity",
        observed=_string_projection(record, "slab_b_uid_full"),
        authoritative=decoded.slab_b_uid,
    )
    _require_equal_projection(
        name="match_score",
        observed=_finite_real_projection(record, "match_score"),
        authoritative=float(metrics["match_score"]),
    )
    _require_equal_projection(
        name="n_atoms",
        observed=_integer_projection(record, "natoms"),
        authoritative=int(metrics["n_atoms_interface"]),
    )
    _require_equal_projection(
        name="interface_area",
        observed=_finite_real_projection(record, "interface_area"),
        authoritative=float(metrics["interface_area_A2"]),
    )
    _require_equal_projection(
        name="hencky_norm",
        observed=_finite_real_projection(record, "hencky_norm"),
        authoritative=0.5 * float(metrics["d_cell"]),
    )

    pareto = decoded.pareto
    expected_member = False if pareto is None else bool(pareto["is_member"])
    expected_rank = None if pareto is None else pareto["rank"]
    _require_equal_projection(
        name="Pareto membership",
        observed=_boolean_projection(record, "is_pareto"),
        authoritative=expected_member,
    )
    _require_equal_projection(
        name="Pareto rank",
        observed=_optional_integer_projection(record, "pareto_rank"),
        authoritative=expected_rank,
    )


def _rehydrate_interface_prototype_record(
    uow: UnitOfWork,
    prototype_record: Prototype,
) -> InterfacePrototype:
    """Return one fully validated current persisted interface prototype."""

    from calm.interface.model import InterfacePrototype

    payload = getattr(prototype_record, "payload", None)
    try:
        decoded = _decode_interface_prototype_payload(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid coupled-v2 prototype payload: {exc}") from exc

    _validate_prototype_record_projections(prototype_record, decoded)

    slab_a = uow.slabs.get_by_uid_full(decoded.slab_a_uid)
    slab_b = uow.slabs.get_by_uid_full(decoded.slab_b_uid)
    if slab_a is None or slab_b is None:
        raise ValueError(
            "Coupled-v2 prototype slabs could not be resolved: "
            f"{decoded.slab_a_uid}, {decoded.slab_b_uid}"
        )

    metrics = decoded.metrics
    pareto = decoded.pareto
    return InterfacePrototype(
        prototype_uid=decoded.prototype_uid,
        slab_a_uid=decoded.slab_a_uid,
        slab_b_uid=decoded.slab_b_uid,
        miller_a=decoded.miller_a,
        miller_b=decoded.miller_b,
        supercell_a=decoded.supercell_a,
        supercell_b=decoded.supercell_b,
        match_score=float(metrics["match_score"]),
        d_size=float(metrics["d_size"]),
        d_cell=float(metrics["d_cell"]),
        d_area=float(metrics["d_area"]),
        d_shape=float(metrics["d_shape"]),
        rel_da=float(metrics["rel_da"]),
        rel_db=float(metrics["rel_db"]),
        d_gamma_deg=float(metrics["d_gamma_deg"]),
        n_atoms_interface=int(metrics["n_atoms_interface"]),
        slab_a=slab_a,
        slab_b=slab_b,
        pair_identity=decoded.pair_identity,
        source_provenance=decoded.source_provenance,
        is_pareto=False if pareto is None else bool(pareto["is_member"]),
        pareto_rank=None if pareto is None else pareto["rank"],
        pareto_policy=None if pareto is None else str(pareto["policy"]),
        pareto_policy_version=None if pareto is None else int(pareto["version"]),
        pareto_population_scope=(
            None if pareto is None else str(pareto["population_scope"])
        ),
        pareto_population_size=(
            0 if pareto is None else int(pareto["population_size"])
        ),
        pareto_d_cell_key=(None if pareto is None else int(pareto["d_cell_key"])),
    )


def load_interface_prototype(
    uow: UnitOfWork,
    prototype_uid_full: str,
) -> InterfacePrototype:
    """Load one current persisted prototype through the authoritative decoder."""

    prototype_record = uow.prototypes.get_by_uid_full(prototype_uid_full)
    if prototype_record is None:
        raise KeyError(f"Prototype not found: {prototype_uid_full}")
    return _rehydrate_interface_prototype_record(uow, prototype_record)
