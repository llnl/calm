"""C6 parity between the production kernel and project-centered public API.

The qualification runs the same atomistic surface pair and ``SearchSettings``
through four independently observed layers:

1. direct :func:`calm.interface.pipeline.find_prototypes` execution;
2. the first completed :meth:`calm.Project.search_interfaces` result;
3. the completed-search resume/reuse path; and
4. a newly reopened project reading the persisted run and prototypes.

Pass/fail requires exact equality of policy-qualified pair identities, primitive
build recipes, bounded source provenance, authoritative Pareto metadata, and
ranked identity order.  Floating diagnostics are compared with declared
absolute and relative tolerances.  CALM imports remain local to execution so
claim-suite schema and CLI discovery stay import-light.
"""

from __future__ import annotations

import json
import math
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._support import write_csv_atomic, write_jsonl_atomic
from .claim_ids import ClaimId, ClaimStatus
from .manifest import (
    artifact_record,
    build_manifest,
    canonical_json_bytes,
    sha256_bytes,
    write_json_atomic,
)
from .schemas import (
    PUBLIC_API_PARITY_COMPARISON_SCHEMA,
    PUBLIC_API_PARITY_FIXTURE_SCHEMA,
    PUBLIC_API_PARITY_INVENTORY_SCHEMA,
    PUBLIC_API_PARITY_SUMMARY_SCHEMA,
    ClaimResult,
)


PUBLIC_MATCH_IMPLEMENTATION = "primitive_coupled_pair_v2"
DEFAULT_PROFILE = "standard"
SUPPORTED_PROFILES = ("smoke", "standard")
DEFAULT_FLOAT_ATOL = 1.0e-12
DEFAULT_FLOAT_RTOL = 1.0e-12

_PAIR_IDENTITY_FIELDS = (
    "key_version",
    "primitive_pair_key",
    "pair_symmetry_policy",
    "correspondence_orientation",
    "material_exchange_identified",
)
_FLOAT_METRIC_FIELDS = (
    "score",
    "d_cell",
    "d_area",
    "d_shape",
    "d_size",
    "rel_da",
    "rel_db",
    "d_gamma_deg",
)
_INTEGER_METRIC_FIELDS = (
    "n_atoms_interface",
    "k_a",
    "k_b",
)
_PARETO_FIELDS = (
    "is_pareto",
    "pareto_rank",
    "pareto_policy",
    "pareto_policy_version",
    "pareto_population_scope",
    "pareto_population_size",
    "pareto_d_cell_key",
)


def _canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _json_native(value: Any) -> Any:
    """Return a deterministic JSON-native copy without importing NumPy."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("parity evidence cannot contain non-finite floats")
        return float(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_native(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_native(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return _json_native(item())
    raise TypeError(
        "public API parity evidence contains unsupported value "
        f"{type(value).__name__}"
    )


def _mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


def _pair_identity(value: Any) -> dict[str, Any]:
    identity = _mapping(value, field_name="pair_identity")
    missing = [name for name in _PAIR_IDENTITY_FIELDS if name not in identity]
    if missing:
        raise ValueError(f"pair_identity is missing fields: {missing}")
    version = identity["key_version"]
    key = identity["primitive_pair_key"]
    symmetry = identity["pair_symmetry_policy"]
    orientation = identity["correspondence_orientation"]
    exchange = identity["material_exchange_identified"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise ValueError("pair_identity.key_version must be a positive integer")
    if (
        not isinstance(key, (list, tuple))
        or len(key) != 8
        or any(isinstance(item, bool) or not isinstance(item, int) for item in key)
    ):
        raise ValueError("pair_identity.primitive_pair_key must contain eight integers")
    if symmetry not in {"proper", "full"}:
        raise ValueError("pair_identity.pair_symmetry_policy is invalid")
    if orientation not in {"proper", "all"}:
        raise ValueError("pair_identity.correspondence_orientation is invalid")
    if not isinstance(exchange, bool):
        raise ValueError("pair_identity.material_exchange_identified must be boolean")
    return {
        "key_version": int(version),
        "primitive_pair_key": [int(item) for item in key],
        "pair_symmetry_policy": str(symmetry),
        "correspondence_orientation": str(orientation),
        "material_exchange_identified": bool(exchange),
    }


def _identity_token(identity: Mapping[str, Any]) -> str:
    return json.dumps(
        _json_native(dict(identity)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _row_from_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        row = to_dict()
        if isinstance(row, Mapping):
            return dict(row)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    raise TypeError(f"cannot project {type(value).__name__} to a parity row")


def _nested_or_attribute(row: Mapping[str, Any], source: Any, name: str) -> Any:
    if name in row:
        return row[name]
    return getattr(source, name, None)


def _normal_supercell(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        raise ValueError(f"{field_name} is missing")
    row = _row_from_object(value)
    required = ("k", "N_tot", "R_sup", "hnf_key_pg", "cond")
    missing = [name for name in required if name not in row]
    if missing:
        raise ValueError(f"{field_name} is missing fields: {missing}")
    return _json_native(
        {
            "k": row["k"],
            "N_tot": row["N_tot"],
            "R_sup": row["R_sup"],
            "hnf_key_pg": row["hnf_key_pg"],
            "cond": row["cond"],
            "S_red": row.get("S_red"),
            "G_red": row.get("G_red"),
            "gauge_orientation": row.get("gauge_orientation", "proper"),
        }
    )


def _normal_source_provenance(value: Any) -> dict[str, Any]:
    if value is None:
        raise ValueError("source_provenance is missing")
    row = _row_from_object(value)
    required = (
        "source_count",
        "minimum_source_indices",
        "source_index_pairs",
        "repeat_indices",
        "representative_source_H_A",
        "representative_source_H_B",
        "representative_source_N_A",
        "representative_source_N_B",
        "representative_correspondence_U_B",
        "representative_source_pair_matrix",
        "representative_source_right_factor",
    )
    missing = [name for name in required if name not in row]
    if missing:
        raise ValueError(f"source_provenance is missing fields: {missing}")
    return _json_native({name: row[name] for name in required})


def _coalesce(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return None


def normalize_scientific_record(value: Any, *, rank: int) -> dict[str, Any]:
    """Normalize one direct or persisted candidate for exact parity checks."""

    row = _row_from_object(value)
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        for key, item in payload.items():
            row.setdefault(key, item)
        metrics = payload.get("metrics")
        if isinstance(metrics, Mapping):
            for key, item in metrics.items():
                row.setdefault(key, item)
        pareto_metadata = payload.get("pareto")
        if isinstance(pareto_metadata, Mapping):
            persisted_pareto_fields = {
                "is_pareto": pareto_metadata.get("is_member"),
                "pareto_rank": pareto_metadata.get("rank"),
                "pareto_policy": pareto_metadata.get("policy"),
                "pareto_policy_version": pareto_metadata.get("version"),
                "pareto_population_scope": pareto_metadata.get(
                    "population_scope"
                ),
                "pareto_population_size": pareto_metadata.get(
                    "population_size"
                ),
                "pareto_d_cell_key": pareto_metadata.get("d_cell_key"),
            }
            for key, item in persisted_pareto_fields.items():
                if item is not None:
                    row.setdefault(key, item)

    identity = _pair_identity(_nested_or_attribute(row, value, "pair_identity"))
    identity_algorithm = _coalesce(row, "identity_algorithm")
    if identity_algorithm is None:
        identity_algorithm = getattr(value, "identity_algorithm", None)
    if identity_algorithm != PUBLIC_MATCH_IMPLEMENTATION:
        raise ValueError(
            "candidate did not report primitive_coupled_pair_v2 identity: "
            f"{identity_algorithm!r}"
        )

    supercell_a = _normal_supercell(
        _nested_or_attribute(row, value, "supercell_a"),
        field_name="supercell_a",
    )
    supercell_b = _normal_supercell(
        _nested_or_attribute(row, value, "supercell_b"),
        field_name="supercell_b",
    )
    source_provenance = _normal_source_provenance(
        _nested_or_attribute(row, value, "source_provenance")
    )

    score = _coalesce(row, "score", "match_score")
    n_atoms = _coalesce(
        row, "n_atoms_interface", "n_atoms_estimate", "natoms", "n_atoms"
    )
    # Persisted prototype rows have two different identifiers:
    #
    # * ``interface_prototype_uid`` is the scientific v3 identity emitted by
    #   the production pipeline and stored inside the payload;
    # * ``prototype_uid``/``uid_full`` is the repository storage-row v2 UID.
    #
    # Direct ``InterfacePrototype`` objects expose only the scientific UID as
    # ``prototype_uid``.  Prefer the payload field when it exists so parity is
    # evaluated on the same scientific identity rather than on a storage key.
    prototype_uid = _coalesce(
        row,
        "interface_prototype_uid",
        "prototype_uid_full",
        "candidate_uid",
    )
    if prototype_uid in (None, "") and "interface_prototype_uid" not in row:
        prototype_uid = _coalesce(row, "prototype_uid", "uid_full", "uid")
    slab_a_uid = _coalesce(
        row,
        "slab_a_uid",
        "slab_a_uid_full",
        "surface_a_uid_full",
    )
    slab_b_uid = _coalesce(
        row,
        "slab_b_uid",
        "slab_b_uid_full",
        "surface_b_uid_full",
    )
    if prototype_uid in (None, ""):
        prototype_uid = getattr(value, "prototype_uid", None)
    if slab_a_uid in (None, ""):
        slab_a_uid = getattr(value, "slab_a_uid", None)
    if slab_b_uid in (None, ""):
        slab_b_uid = getattr(value, "slab_b_uid", None)
    for field_name, uid in (
        ("prototype_uid", prototype_uid),
        ("slab_a_uid", slab_a_uid),
        ("slab_b_uid", slab_b_uid),
    ):
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError(f"candidate {field_name} is missing")

    float_metrics = {
        "score": score,
        "d_cell": row.get("d_cell"),
        "d_area": row.get("d_area"),
        "d_shape": row.get("d_shape"),
        "d_size": row.get("d_size"),
        "rel_da": row.get("rel_da"),
        "rel_db": row.get("rel_db"),
        "d_gamma_deg": row.get("d_gamma_deg"),
    }
    for name, item in float_metrics.items():
        if item is None:
            raise ValueError(f"candidate metric {name} is missing")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"candidate metric {name} is not finite")
        float_metrics[name] = number

    if isinstance(n_atoms, bool) or not isinstance(n_atoms, int) or n_atoms <= 0:
        raise ValueError("candidate n_atoms_interface must be a positive integer")

    pareto = {name: row.get(name) for name in _PARETO_FIELDS}
    for name in _PARETO_FIELDS:
        if pareto[name] is None:
            pareto[name] = getattr(value, name, None)
    if (
        isinstance(pareto["pareto_population_size"], bool)
        or not isinstance(pareto["pareto_population_size"], int)
        or pareto["pareto_population_size"] <= 0
    ):
        raise ValueError("candidate Pareto population size must be positive")
    if not isinstance(pareto["is_pareto"], (bool, int)):
        raise ValueError("candidate is_pareto must be boolean")
    pareto["is_pareto"] = bool(pareto["is_pareto"])
    if pareto["pareto_rank"] is not None:
        if (
            isinstance(pareto["pareto_rank"], bool)
            or not isinstance(pareto["pareto_rank"], int)
            or pareto["pareto_rank"] < 0
        ):
            raise ValueError("candidate pareto_rank must be nonnegative or null")
        pareto["pareto_rank"] = int(pareto["pareto_rank"])
    if not isinstance(pareto["pareto_policy"], str) or not pareto[
        "pareto_policy"
    ]:
        raise ValueError("candidate pareto_policy is missing")
    if (
        isinstance(pareto["pareto_policy_version"], bool)
        or not isinstance(pareto["pareto_policy_version"], int)
        or pareto["pareto_policy_version"] <= 0
    ):
        raise ValueError("candidate Pareto policy version must be positive")
    if not isinstance(pareto["pareto_population_scope"], str) or not pareto[
        "pareto_population_scope"
    ]:
        raise ValueError("candidate Pareto population scope is missing")
    if (
        isinstance(pareto["pareto_d_cell_key"], bool)
        or not isinstance(pareto["pareto_d_cell_key"], int)
        or pareto["pareto_d_cell_key"] < 0
    ):
        raise ValueError("candidate Pareto d_cell key must be nonnegative")

    exact = {
        "identity_algorithm": PUBLIC_MATCH_IMPLEMENTATION,
        "pair_identity": identity,
        "prototype_uid": str(prototype_uid or ""),
        "slab_a_uid": str(slab_a_uid or ""),
        "slab_b_uid": str(slab_b_uid or ""),
        "supercell_a": supercell_a,
        "supercell_b": supercell_b,
        "source_provenance": source_provenance,
        "n_atoms_interface": int(n_atoms),
        "k_a": int(supercell_a["k"]),
        "k_b": int(supercell_b["k"]),
        "pareto": _json_native(pareto),
    }
    return {
        "rank": int(rank),
        "identity_token": _identity_token(identity),
        "identity_sha256": _canonical_digest(identity),
        "exact": exact,
        "metrics": float_metrics,
    }


def build_inventory(
    records: Sequence[Any],
    *,
    stage: str,
    pareto_population_size: int,
) -> dict[str, Any]:
    normalized = tuple(
        normalize_scientific_record(record, rank=index)
        for index, record in enumerate(records)
    )
    by_identity: dict[str, dict[str, Any]] = {}
    for record in normalized:
        token = str(record["identity_token"])
        if token in by_identity:
            raise ValueError(f"{stage} contains duplicate pair identity {token}")
        by_identity[token] = record
    if normalized:
        observed_sizes = {
            int(record["exact"]["pareto"]["pareto_population_size"])
            for record in normalized
        }
        if observed_sizes != {int(pareto_population_size)}:
            raise ValueError(
                f"{stage} candidate Pareto population sizes disagree with stage "
                f"metadata: {sorted(observed_sizes)} != {pareto_population_size}"
            )
    elif int(pareto_population_size) != 0:
        # A zero retained limit may produce no candidate rows while a complete
        # Pareto population exists.  That scenario is intentionally excluded
        # from the current fixtures; make the ambiguity explicit if introduced.
        raise ValueError(
            f"{stage} has no retained records but Pareto population size is "
            f"{pareto_population_size}"
        )
    ordered_tokens = [str(record["identity_token"]) for record in normalized]
    sorted_records = [by_identity[token] for token in sorted(by_identity)]
    return {
        "schema": PUBLIC_API_PARITY_INVENTORY_SCHEMA,
        "stage": stage,
        "candidate_count": len(normalized),
        "pareto_population_size": int(pareto_population_size),
        "ordered_identity_sha256": _canonical_digest(ordered_tokens),
        "identity_set_sha256": _canonical_digest(sorted(by_identity)),
        "scientific_record_sha256": _canonical_digest(sorted_records),
        "records": list(normalized),
    }


def _isclose(first: float, second: float, *, atol: float, rtol: float) -> bool:
    return abs(first - second) <= atol + rtol * max(abs(first), abs(second))


def compare_inventories(
    reference: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    float_atol: float = DEFAULT_FLOAT_ATOL,
    float_rtol: float = DEFAULT_FLOAT_RTOL,
) -> dict[str, Any]:
    """Compare two normalized inventories and return explicit violations."""

    ref_by = {
        str(record["identity_token"]): record for record in reference["records"]
    }
    obs_by = {
        str(record["identity_token"]): record for record in observed["records"]
    }
    missing = sorted(set(ref_by) - set(obs_by))
    unexpected = sorted(set(obs_by) - set(ref_by))
    exact_mismatches: list[dict[str, Any]] = []
    metric_mismatches: list[dict[str, Any]] = []
    for token in sorted(set(ref_by).intersection(obs_by)):
        ref_record = ref_by[token]
        obs_record = obs_by[token]
        if ref_record["exact"] != obs_record["exact"]:
            exact_mismatches.append(
                {
                    "identity_token": token,
                    "reference_exact_sha256": _canonical_digest(ref_record["exact"]),
                    "observed_exact_sha256": _canonical_digest(obs_record["exact"]),
                }
            )
        for name in _FLOAT_METRIC_FIELDS:
            first = float(ref_record["metrics"][name])
            second = float(obs_record["metrics"][name])
            if not _isclose(first, second, atol=float_atol, rtol=float_rtol):
                metric_mismatches.append(
                    {
                        "identity_token": token,
                        "field": name,
                        "reference": first,
                        "observed": second,
                        "absolute_difference": abs(first - second),
                    }
                )
    count_equal = int(reference["candidate_count"]) == int(
        observed["candidate_count"]
    )
    population_equal = int(reference["pareto_population_size"]) == int(
        observed["pareto_population_size"]
    )
    order_equal = reference["ordered_identity_sha256"] == observed[
        "ordered_identity_sha256"
    ]
    passed = (
        count_equal
        and population_equal
        and order_equal
        and not missing
        and not unexpected
        and not exact_mismatches
        and not metric_mismatches
    )
    return {
        "schema": PUBLIC_API_PARITY_COMPARISON_SCHEMA,
        "reference_stage": reference["stage"],
        "observed_stage": observed["stage"],
        "passed": passed,
        "candidate_count_equal": count_equal,
        "pareto_population_size_equal": population_equal,
        "ranked_identity_order_equal": order_equal,
        "missing_identity_tokens": missing,
        "unexpected_identity_tokens": unexpected,
        "exact_mismatches": exact_mismatches,
        "metric_mismatches": metric_mismatches,
        "float_atol": float_atol,
        "float_rtol": float_rtol,
    }


@dataclass(frozen=True)
class PublicApiParityFixture:
    """One atomistic public-workflow parity fixture."""

    fixture_id: str
    description: str
    material_a: str
    material_b: str
    miller_a: tuple[int, int, int]
    miller_b: tuple[int, int, int]
    termination_shift_a: int
    termination_shift_b: int
    settings: Mapping[str, Any]
    expected_population: str = "nonempty"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id must be nonempty")
        if self.material_a not in {"LiF", "Li2O"} or self.material_b not in {
            "LiF",
            "Li2O",
        }:
            raise ValueError("fixture materials must be LiF or Li2O")
        if self.expected_population not in {"nonempty", "empty", "any"}:
            raise ValueError("expected_population must be nonempty, empty, or any")
        for name, miller in (("miller_a", self.miller_a), ("miller_b", self.miller_b)):
            if len(miller) != 3 or not any(int(value) for value in miller):
                raise ValueError(f"{name} must be a nonzero three-index tuple")
        if self.termination_shift_a < 0 or self.termination_shift_b < 0:
            raise ValueError("termination shifts must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PUBLIC_API_PARITY_FIXTURE_SCHEMA,
            "fixture_id": self.fixture_id,
            "description": self.description,
            "material_a": self.material_a,
            "material_b": self.material_b,
            "miller_a": list(self.miller_a),
            "miller_b": list(self.miller_b),
            "termination_shift_a": self.termination_shift_a,
            "termination_shift_b": self.termination_shift_b,
            "settings": _json_native(dict(self.settings)),
            "expected_population": self.expected_population,
            "tags": list(self.tags),
        }

    def sha256(self) -> str:
        return _canonical_digest(self.to_dict())


def _settings(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "max_principal_strain": 0.15,
        "max_supercell_index": 5,
        "max_atoms": 1000,
        "max_candidates": 500,
        "mismatch_weight": 0.5,
        "surface_symmetry_mode": "discover",
    }
    values.update(overrides)
    return values


def default_public_api_fixtures() -> tuple[PublicApiParityFixture, ...]:
    return (
        PublicApiParityFixture(
            fixture_id="lif_100_homointerface",
            description="High-symmetry LiF(100) homointerface.",
            material_a="LiF",
            material_b="LiF",
            miller_a=(1, 0, 0),
            miller_b=(1, 0, 0),
            termination_shift_a=0,
            termination_shift_b=0,
            settings=_settings(max_principal_strain=1.0e-10),
            tags=("homointerface", "high_symmetry", "exact_strain"),
        ),
        PublicApiParityFixture(
            fixture_id="lif_li2o_100_heterointerface",
            description="LiF(100) versus O-terminated Li2O(100).",
            material_a="LiF",
            material_b="Li2O",
            miller_a=(1, 0, 0),
            miller_b=(1, 0, 0),
            termination_shift_a=0,
            termination_shift_b=1,
            settings=_settings(),
            tags=("heterointerface", "two_materials"),
        ),
        PublicApiParityFixture(
            fixture_id="li2o_100_termination_pair",
            description="Two distinct Li2O(100) termination records.",
            material_a="Li2O",
            material_b="Li2O",
            miller_a=(1, 0, 0),
            miller_b=(1, 0, 0),
            termination_shift_a=0,
            termination_shift_b=1,
            settings=_settings(max_principal_strain=1.0e-10),
            tags=("termination_pair", "same_material"),
        ),
        PublicApiParityFixture(
            fixture_id="lif_111_termination_pair",
            description="Two polar LiF(111) termination records.",
            material_a="LiF",
            material_b="LiF",
            miller_a=(1, 1, 1),
            miller_b=(1, 1, 1),
            termination_shift_a=0,
            termination_shift_b=1,
            settings=_settings(max_principal_strain=1.0e-10),
            tags=("termination_pair", "polar_surface", "hexagonal_net"),
        ),
        PublicApiParityFixture(
            fixture_id="lif_li2o_110_heterointerface",
            description="Rectangular LiF(110) versus Li2O(110).",
            material_a="LiF",
            material_b="Li2O",
            miller_a=(1, 1, 0),
            miller_b=(1, 1, 0),
            termination_shift_a=0,
            termination_shift_b=0,
            settings=_settings(),
            tags=("heterointerface", "rectangular_net"),
            expected_population="any",
        ),
        PublicApiParityFixture(
            fixture_id="lif_li2o_100_truncated",
            description="Retain only the deterministic top-ranked candidate.",
            material_a="LiF",
            material_b="Li2O",
            miller_a=(1, 0, 0),
            miller_b=(1, 0, 0),
            termination_shift_a=0,
            termination_shift_b=1,
            settings=_settings(max_candidates=1),
            tags=("output_limit", "pareto_provenance"),
        ),
        PublicApiParityFixture(
            fixture_id="lif_li2o_100_atom_limit_empty",
            description="Atom-count rejection produces a completed empty search.",
            material_a="LiF",
            material_b="Li2O",
            miller_a=(1, 0, 0),
            miller_b=(1, 0, 0),
            termination_shift_a=0,
            termination_shift_b=1,
            settings=_settings(max_atoms=1),
            expected_population="empty",
            tags=("empty_result", "atom_count_rejection"),
        ),
    )


@dataclass(frozen=True)
class PublicApiParityConfig:
    """Configuration for the C6 atomistic parity matrix."""

    profile: str = DEFAULT_PROFILE
    fixture_ids: tuple[str, ...] = ()
    structure_lif: str | Path | None = None
    structure_li2o: str | Path | None = None
    layers: int = 4
    vacuum: float = 15.0
    float_atol: float = DEFAULT_FLOAT_ATOL
    float_rtol: float = DEFAULT_FLOAT_RTOL
    reset_project: bool = True

    def __post_init__(self) -> None:
        if self.profile not in SUPPORTED_PROFILES:
            raise ValueError(f"profile must be one of {SUPPORTED_PROFILES}")
        if self.layers <= 0:
            raise ValueError("layers must be positive")
        if not math.isfinite(self.vacuum) or self.vacuum < 0:
            raise ValueError("vacuum must be finite and nonnegative")
        if not math.isfinite(self.float_atol) or self.float_atol < 0:
            raise ValueError("float_atol must be finite and nonnegative")
        if not math.isfinite(self.float_rtol) or self.float_rtol < 0:
            raise ValueError("float_rtol must be finite and nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "fixture_ids": list(self.fixture_ids),
            "structure_lif": (
                None if self.structure_lif is None else str(self.structure_lif)
            ),
            "structure_li2o": (
                None if self.structure_li2o is None else str(self.structure_li2o)
            ),
            "layers": self.layers,
            "vacuum": self.vacuum,
            "float_atol": self.float_atol,
            "float_rtol": self.float_rtol,
            "reset_project": self.reset_project,
        }


def select_public_api_fixtures(
    config: PublicApiParityConfig,
) -> tuple[PublicApiParityFixture, ...]:
    fixtures = default_public_api_fixtures()
    by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    if config.fixture_ids:
        unknown = sorted(set(config.fixture_ids) - set(by_id))
        if unknown:
            raise ValueError(f"unknown public API parity fixtures: {unknown}")
        return tuple(by_id[item] for item in dict.fromkeys(config.fixture_ids))
    if config.profile == "smoke":
        selected = (
            "lif_100_homointerface",
            "lif_li2o_100_heterointerface",
            "lif_li2o_100_atom_limit_empty",
        )
        return tuple(by_id[item] for item in selected)
    return fixtures


def _default_structure_path(repository_root: Path, filename: str) -> Path:
    return repository_root / "examples" / "Structures" / filename


def _material_label(material: str) -> str:
    return f"benchmark_{material}"


def _surface_selector(project: Any, fixture: PublicApiParityFixture, side: str) -> Any:
    material = getattr(fixture, f"material_{side}")
    miller = getattr(fixture, f"miller_{side}")
    shift = getattr(fixture, f"termination_shift_{side}")
    return project.surface(
        material=_material_label(material),
        miller=miller,
        termination_shift=int(shift),
    )


def _inventory_from_direct(result: Any) -> dict[str, Any]:
    return build_inventory(
        list(result.prototypes),
        stage="direct_kernel",
        pareto_population_size=int(result.pareto_population_size),
    )


def _candidate_pareto_population(records: Sequence[Any]) -> int:
    if not records:
        return 0
    values = set()
    for record in records:
        row = _row_from_object(record)
        value = row.get("pareto_population_size")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                "persisted candidate is missing authoritative Pareto population size"
            )
        values.add(int(value))
    if len(values) != 1:
        raise ValueError(
            f"persisted candidates disagree on Pareto population size: {sorted(values)}"
        )
    return next(iter(values))


def _inventory_from_search(search: Any, *, stage: str) -> dict[str, Any]:
    records = search.candidates().records()
    return build_inventory(
        records,
        stage=stage,
        pareto_population_size=_candidate_pareto_population(records),
    )


def _validate_search_run(
    project: Any,
    search: Any,
    *,
    fixture: PublicApiParityFixture,
    surface_a: Any,
    surface_b: Any,
    settings: Any,
) -> dict[str, Any]:
    run_uid = getattr(search.record, "run_uid_full", None)
    if not run_uid:
        raise ValueError("persisted search is missing run_uid_full")
    run = project.run(str(run_uid))
    spec = dict(getattr(run, "spec", {}) or {})
    progress = dict(getattr(run, "progress", {}) or {})
    if getattr(run, "status", None) != "done":
        raise ValueError(f"search run is not done: {getattr(run, 'status', None)!r}")
    if spec.get("implementation") != PUBLIC_MATCH_IMPLEMENTATION:
        raise ValueError("run spec does not identify primitive_coupled_pair_v2")
    if spec.get("settings") != settings.to_dict():
        raise ValueError("run spec settings differ from requested SearchSettings")
    search_identity = str(getattr(search.record, "search_identity", "") or "")
    if not search_identity or spec.get("search_identity") != search_identity:
        raise ValueError("run spec search identity is missing or inconsistent")
    expected_uids = {
        "surface_a": str(getattr(surface_a, "uid_full", "") or ""),
        "surface_b": str(getattr(surface_b, "uid_full", "") or ""),
    }
    for field, uid in expected_uids.items():
        surface_spec = spec.get(field)
        if (
            not isinstance(surface_spec, Mapping)
            or str(surface_spec.get("uid_full")) != uid
        ):
            raise ValueError(f"run spec {field} identity is inconsistent")
    count = len(search.candidates())
    if progress.get("phase") != "complete" or progress.get("n_candidates") != count:
        raise ValueError(
            "run progress is incomplete or candidate count is inconsistent"
        )
    if fixture.expected_population == "empty" and count != 0:
        raise ValueError(f"fixture expected an empty population, observed {count}")
    if fixture.expected_population == "nonempty" and count <= 0:
        raise ValueError("fixture expected a nonempty population")
    return {
        "run_uid_full": str(run_uid),
        "run_status": str(run.status),
        "search_identity": search_identity,
        "run_spec": _json_native(spec),
        "run_progress": _json_native(progress),
    }


@dataclass(frozen=True)
class PublicApiParityArtifacts:
    manifest: Path
    claim_result: Path
    summary: Path
    summary_csv: Path
    fixture_results: Path
    inventories: Path
    comparisons: Path
    project_database: Path
    result: ClaimResult

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.summary_csv,
            self.fixture_results,
            self.inventories,
            self.comparisons,
        )


def run_public_api_parity_qualification(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: PublicApiParityConfig,
) -> PublicApiParityArtifacts:
    """Execute C6 across the selected atomistic public-workflow fixtures."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    repository = Path(repository_root).resolve()
    fixtures = select_public_api_fixtures(config)
    structure_paths = {
        "LiF": Path(config.structure_lif).expanduser().resolve()
        if config.structure_lif is not None
        else _default_structure_path(repository, "LiF.poscar"),
        "Li2O": Path(config.structure_li2o).expanduser().resolve()
        if config.structure_li2o is not None
        else _default_structure_path(repository, "Li2O.poscar"),
    }
    for material, path in structure_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{material} structure not found: {path}")

    project_dir = root / "public_api_parity.calm"
    if project_dir.exists():
        if not config.reset_project:
            raise FileExistsError(
                f"parity project already exists: {project_dir}; enable reset_project"
            )
        shutil.rmtree(project_dir)

    # Scientific imports are intentionally local to execution.
    from calm import Material, SearchSettings, open_project
    from calm.interface.pipeline import find_prototypes

    project = open_project(project_dir)
    used_materials = sorted(
        {fixture.material_a for fixture in fixtures}.union(
            fixture.material_b for fixture in fixtures
        )
    )
    for material in used_materials:
        label = _material_label(material)
        project.add_material(
            Material.from_file(structure_paths[material], name=label),
            name=label,
        )
    millers = sorted(
        {
            tuple(fixture.miller_a)
            for fixture in fixtures
        }.union(tuple(fixture.miller_b) for fixture in fixtures)
    )
    project.generate_surfaces(
        [_material_label(material) for material in used_materials],
        millers=millers,
        layers=config.layers,
        vacuum=config.vacuum,
    )

    fixture_results: list[dict[str, Any]] = []
    inventories: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    fixture_runtime: dict[str, float] = {}
    surface_uids_by_fixture: dict[str, dict[str, str]] = {}
    immediate_searches: dict[str, dict[str, Any]] = {}

    for fixture in fixtures:
        started = time.perf_counter()
        surface_a = _surface_selector(project, fixture, "a")
        surface_b = _surface_selector(project, fixture, "b")
        surface_uids_by_fixture[fixture.fixture_id] = {
            "surface_a": str(surface_a.uid_full),
            "surface_b": str(surface_b.uid_full),
        }
        settings = SearchSettings(**dict(fixture.settings))
        settings.validate()
        slab_a = surface_a.to_surface().to_slab()
        slab_b = surface_b.to_surface().to_slab()
        direct_result = find_prototypes(
            slab_a,
            slab_b,
            config=settings.to_internal_config(),
        )
        direct_inventory = _inventory_from_direct(direct_result)
        search = project.search_interfaces(
            surface_a,
            surface_b,
            settings=settings,
            name=fixture.fixture_id,
            resume=False,
        )
        run_evidence = _validate_search_run(
            project,
            search,
            fixture=fixture,
            surface_a=surface_a,
            surface_b=surface_b,
            settings=settings,
        )
        persisted_inventory = _inventory_from_search(
            search,
            stage="project_search",
        )
        resumed = project.search_interfaces(
            surface_a,
            surface_b,
            settings=settings,
            name=fixture.fixture_id,
            resume=True,
        )
        resumed_inventory = _inventory_from_search(
            resumed,
            stage="project_resume",
        )
        resumed_run_uid = str(getattr(resumed.record, "run_uid_full", "") or "")
        if resumed_run_uid != run_evidence["run_uid_full"]:
            raise ValueError("completed-search resume path changed the run UID")

        fixture_inventories = (
            direct_inventory,
            persisted_inventory,
            resumed_inventory,
        )
        inventories.extend(
            {
                "fixture_id": fixture.fixture_id,
                **inventory,
            }
            for inventory in fixture_inventories
        )
        local_comparisons = (
            compare_inventories(
                direct_inventory,
                persisted_inventory,
                float_atol=config.float_atol,
                float_rtol=config.float_rtol,
            ),
            compare_inventories(
                direct_inventory,
                resumed_inventory,
                float_atol=config.float_atol,
                float_rtol=config.float_rtol,
            ),
        )
        comparisons.extend(
            {"fixture_id": fixture.fixture_id, **comparison}
            for comparison in local_comparisons
        )
        immediate_searches[fixture.fixture_id] = {
            "fixture": fixture,
            "settings": settings,
            "run_evidence": run_evidence,
            "direct_inventory": direct_inventory,
            "persisted_inventory": persisted_inventory,
            "resumed_inventory": resumed_inventory,
            "comparisons": list(local_comparisons),
        }
        fixture_runtime[fixture.fixture_id] = time.perf_counter() - started

    # Create a genuinely new Project/workspace object and re-read every search.
    reopened = open_project(project_dir)
    for fixture in fixtures:
        immediate = immediate_searches[fixture.fixture_id]
        reopened_search = reopened.search(fixture.fixture_id)
        reopened_inventory = _inventory_from_search(
            reopened_search,
            stage="reopened_project",
        )
        run_uid = str(getattr(reopened_search.record, "run_uid_full", "") or "")
        if run_uid != immediate["run_evidence"]["run_uid_full"]:
            raise ValueError("reopened project resolved a different run UID")
        reopened_run = reopened.run(run_uid)
        if getattr(reopened_run, "status", None) != "done":
            raise ValueError("reopened run is not complete")
        inventories.append(
            {"fixture_id": fixture.fixture_id, **reopened_inventory}
        )
        reopened_comparison = compare_inventories(
            immediate["direct_inventory"],
            reopened_inventory,
            float_atol=config.float_atol,
            float_rtol=config.float_rtol,
        )
        comparisons.append(
            {"fixture_id": fixture.fixture_id, **reopened_comparison}
        )
        all_comparisons = (*immediate["comparisons"], reopened_comparison)
        passed = all(bool(item["passed"]) for item in all_comparisons)
        fixture_results.append(
            {
                "schema": PUBLIC_API_PARITY_FIXTURE_SCHEMA,
                "fixture": fixture.to_dict(),
                "fixture_sha256": fixture.sha256(),
                "surface_uids": surface_uids_by_fixture[fixture.fixture_id],
                "run_evidence": immediate["run_evidence"],
                "direct_candidate_count": immediate["direct_inventory"][
                    "candidate_count"
                ],
                "direct_pareto_population_size": immediate["direct_inventory"][
                    "pareto_population_size"
                ],
                "project_candidate_count": immediate["persisted_inventory"][
                    "candidate_count"
                ],
                "reopened_candidate_count": reopened_inventory["candidate_count"],
                "direct_identity_set_sha256": immediate["direct_inventory"][
                    "identity_set_sha256"
                ],
                "project_identity_set_sha256": immediate["persisted_inventory"][
                    "identity_set_sha256"
                ],
                "reopened_identity_set_sha256": reopened_inventory[
                    "identity_set_sha256"
                ],
                "comparison_count": len(all_comparisons),
                "failed_comparison_count": sum(
                    not bool(item["passed"]) for item in all_comparisons
                ),
                "elapsed_seconds": fixture_runtime[fixture.fixture_id],
                "passed": passed,
            }
        )

    summary_rows = tuple(
        {
            "schema": PUBLIC_API_PARITY_SUMMARY_SCHEMA,
            "fixture_id": row["fixture"]["fixture_id"],
            "tags": json.dumps(row["fixture"]["tags"], separators=(",", ":")),
            "expected_population": row["fixture"]["expected_population"],
            "direct_candidate_count": row["direct_candidate_count"],
            "direct_pareto_population_size": row["direct_pareto_population_size"],
            "project_candidate_count": row["project_candidate_count"],
            "reopened_candidate_count": row["reopened_candidate_count"],
            "failed_comparison_count": row["failed_comparison_count"],
            "elapsed_seconds": row["elapsed_seconds"],
            "passed": row["passed"],
        }
        for row in fixture_results
    )
    fixture_results_path = write_jsonl_atomic(
        root / "public_api_parity_fixture_results.jsonl",
        fixture_results,
    )
    inventories_path = write_jsonl_atomic(
        root / "public_api_parity_inventories.jsonl",
        inventories,
    )
    comparisons_path = write_jsonl_atomic(
        root / "public_api_parity_comparisons.jsonl",
        comparisons,
    )
    summary_csv_path = write_csv_atomic(
        root / "public_api_parity_summary.csv",
        summary_rows,
    )

    all_passed = all(bool(row["passed"]) for row in fixture_results)
    result = ClaimResult(
        claim_id=ClaimId.C6_PUBLIC_API_PARITY,
        status=ClaimStatus.PASS if all_passed else ClaimStatus.FAIL,
        summary=(
            "Direct kernel, initial Project search, completed-search resume, and "
            "reopened project inventories agree exactly for every fixture."
            if all_passed
            else "One or more public-workflow fixtures disagree with the direct "
            "production-kernel inventory."
        ),
        evidence_files=(
            "public_api_parity_summary.json",
            "public_api_parity_summary.csv",
            "public_api_parity_fixture_results.jsonl",
            "public_api_parity_inventories.jsonl",
            "public_api_parity_comparisons.jsonl",
        ),
        metrics={
            "fixture_count": len(fixture_results),
            "passed_fixture_count": sum(bool(row["passed"]) for row in fixture_results),
            "failed_fixture_count": sum(
                not bool(row["passed"]) for row in fixture_results
            ),
            "comparison_count": len(comparisons),
            "failed_comparison_count": sum(
                not bool(row["passed"]) for row in comparisons
            ),
            "empty_fixture_count": sum(
                row["fixture"]["expected_population"] == "empty"
                for row in fixture_results
            ),
            "termination_pair_fixture_count": sum(
                "termination_pair" in row["fixture"]["tags"]
                for row in fixture_results
            ),
        },
        notes=(
            "The same persisted GeneratedSurface records and SearchSettings are "
            "used for direct and project-backed execution.",
            "Exact parity covers policy-qualified pair identity, primitive build "
            "recipes, bounded source provenance, candidate ordering, prototype and "
            "surface UIDs, and authoritative Pareto metadata.",
            "Floating diagnostics are compared separately with declared absolute "
            "and relative tolerances.",
            "The standard matrix includes homointerface, heterointerface, distinct "
            "termination, output-limit, and completed-empty-search cases.",
        ),
    )
    claim_result_path = write_json_atomic(root / "claim_result.json", result.to_dict())
    summary_payload = {
        "schema": PUBLIC_API_PARITY_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "implementation": PUBLIC_MATCH_IMPLEMENTATION,
        "config": config.to_dict(),
        "project_path": str(project_dir),
        "fixture_count": len(fixture_results),
        "comparison_count": len(comparisons),
        "passed_fixture_count": sum(bool(row["passed"]) for row in fixture_results),
        "failed_fixture_count": sum(not bool(row["passed"]) for row in fixture_results),
        "all_passed": all_passed,
        "pass_criterion": (
            "Exact pair-identity set and order, primitive recipes, source provenance, "
            "prototype/surface identities, Pareto metadata, and tolerance-qualified "
            "metrics must agree between direct, project, resume, and reopened stages."
        ),
        "fixtures": list(summary_rows),
    }
    summary_path = write_json_atomic(
        root / "public_api_parity_summary.json",
        summary_payload,
    )

    artifact_paths = (
        claim_result_path,
        summary_path,
        summary_csv_path,
        fixture_results_path,
        inventories_path,
        comparisons_path,
    )
    artifact_records = [
        artifact_record(
            path,
            relative_to=root,
            media_type="text/csv" if path.suffix == ".csv" else "application/json",
        )
        for path in artifact_paths
    ]
    database_path = project_dir / "calm.sqlite"
    if database_path.is_file():
        artifact_records.append(
            artifact_record(
                database_path,
                relative_to=root,
                media_type="application/vnd.sqlite3",
            )
        )
    manifest = build_manifest(
        repository_root=repository,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C6_PUBLIC_API_PARITY,),
        artifacts=tuple(artifact_records),
        fixture_hashes={
            fixture.fixture_id: fixture.sha256() for fixture in fixtures
        },
        policy_settings={
            "float_atol": config.float_atol,
            "float_rtol": config.float_rtol,
            "layers": config.layers,
            "vacuum": config.vacuum,
            "implementation": PUBLIC_MATCH_IMPLEMENTATION,
        },
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return PublicApiParityArtifacts(
        manifest=manifest_path,
        claim_result=claim_result_path,
        summary=summary_path,
        summary_csv=summary_csv_path,
        fixture_results=fixture_results_path,
        inventories=inventories_path,
        comparisons=comparisons_path,
        project_database=database_path,
        result=result,
    )
