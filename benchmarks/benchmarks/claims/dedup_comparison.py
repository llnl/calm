"""Literature-labelled adapters for a common coupled-match ledger.

This module is benchmark infrastructure, not part of CALM's public API.  Its
input is one admitted match description represented by an exact stacked
``(4, 2)`` integer matrix.  The top and bottom ``(2, 2)`` blocks describe the
A- and B-side surface supercells in CALM's column-basis convention.

Only :func:`calm_stage_keys` evaluates CALM's implemented exact equivalence.
The other adapters deliberately carry narrower fidelity labels:

* the InterOptimus and OgreInterface adapters are deterministic two-dimensional
  analogues of identifiable source-code rules;
* the Jelver adapter applies paper-described enumeration filters to an already
  generated ledger, rather than reproducing that program's enumeration; and
* the InterMat and InterMatch adapters are selectors, not deduplicators.

Keeping those distinctions in the data prevents a benchmark from presenting
paper-derived analogues as exact reproductions of external software.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from functools import reduce
from math import gcd
from numbers import Integral, Real
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from calm.interface.matching._pair_identity import canonicalize_primitive_pair_2d
from calm.interface.matching._types import PairIdentityPolicy2D
from calm.math2d.paired_lattice import (
    canonicalize_common_right_rank2,
    primitiveize_pair_matrix_2d,
)
from calm.symmetry.reduction import canonical_gauss_reduce_2d


MethodKind = Literal["equivalence", "heuristic_grouping", "filter", "selector"]
Fidelity = Literal[
    "implementation_exact",
    "source_derived_2d_analogue",
    "paper_derived_2d_analogue",
]
AdapterStatus = Literal["classified", "retained", "rejected", "selected", "not_applicable"]


@dataclass(frozen=True)
class MethodMetadata:
    """Stable scientific scope metadata attached to every adapter result."""

    method_id: str
    label: str
    method_kind: MethodKind
    fidelity: Fidelity
    reference: str
    implementation_basis: str
    candidate_universe: str
    source_revision: str
    source_repository: str | None
    representative_policy: str
    documented_deviations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "label": self.label,
            "method_kind": self.method_kind,
            "fidelity": self.fidelity,
            "reference": self.reference,
            "implementation_basis": self.implementation_basis,
            "candidate_universe": self.candidate_universe,
            "source_revision": self.source_revision,
            "source_repository": self.source_repository,
            "representative_policy": self.representative_policy,
            "documented_deviations": list(self.documented_deviations),
        }


METHOD_METADATA: Mapping[str, MethodMetadata] = {
    "zur_mcgill_descriptor": MethodMetadata(
        method_id="zur_mcgill_descriptor",
        label="Zur--McGill-style reduced-cell descriptor grouping",
        method_kind="heuristic_grouping",
        fidelity="paper_derived_2d_analogue",
        reference="Zur and McGill, J. Appl. Phys. 55, 378 (1984)",
        implementation_basis=(
            "independent Gauss reduction and quantized reduced Gram descriptors; "
            "this diagnostic grouping is not a published equivalence quotient"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="doi:10.1063/1.333084",
        source_repository=None,
        representative_policy="one class per quantized pair of reduced metrics",
        documented_deviations=(
            "benchmark-defined quantization",
            "no interface-level quotient is attributed to Zur and McGill",
        ),
    ),
    "calm": MethodMetadata(
        method_id="calm",
        label="CALM exact coupled identity",
        method_kind="equivalence",
        fidelity="implementation_exact",
        reference="CALM repository implementation",
        implementation_basis=(
            "primitiveize_pair_matrix_2d, canonicalize_common_right_rank2, "
            "and canonicalize_primitive_pair_2d"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="current CALM benchmark worktree",
        source_repository="CALM repository",
        representative_policy="lexicographically canonical exact coupled-pair key",
    ),
    "interoptimus_direction_signature": MethodMetadata(
        method_id="interoptimus_direction_signature",
        label="InterOptimus-inspired fixed-surface 2D direction grouping",
        method_kind="heuristic_grouping",
        fidelity="source_derived_2d_analogue",
        reference="Xie et al., J. Energy Chem. 2025; InterOptimus matching.py",
        implementation_basis=(
            "independent direction-orbit tests on both sides with an optional "
            "simultaneous exchange of the two matched directions; the external "
            "bulk-3D symmetry and StructureMatcher fallback are intentionally "
            "replaced by supplied fixed-surface 2D point groups"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="0.1.1@a5bce7e4188183e1c93f5dbaa5a83667d3e321b3",
        source_repository="https://github.com/HouGroup/InterOptimus",
        representative_policy="minimum exact direction-orbit tuple under simultaneous swap",
        documented_deviations=(
            "uses exact 2D integer directions instead of tolerant 3D Cartesian comparisons",
            "omits greedy clustering and StructureMatcher fallback",
            "uses supplied terminated-surface rather than bulk point-group operations",
        ),
    ),
    "interoptimus_greedy": MethodMetadata(
        method_id="interoptimus_greedy",
        label="InterOptimus-inspired fixed-surface 2D greedy clustering",
        method_kind="heuristic_grouping",
        fidelity="source_derived_2d_analogue",
        reference="Xie et al., J. Energy Chem. 2025; InterOptimus matching.py",
        implementation_basis=(
            "pairwise normalized-direction comparisons, simultaneous basis swap, "
            "and deterministic greedy assignment to the first representative"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="0.1.1@a5bce7e4188183e1c93f5dbaa5a83667d3e321b3",
        source_repository="https://github.com/HouGroup/InterOptimus",
        representative_policy=(
            "first representative after 2D Hencky von-Mises proxy, "
            "source-atom-count, and id sort"
        ),
        documented_deviations=(
            "uses supplied 2D terminated-surface instead of bulk 3D symmetries",
            "uses a 2D Hencky principal-strain proxy for external von Mises ordering",
            "omits StructureMatcher fallback",
        ),
    ),
    "ogre_style": MethodMetadata(
        method_id="ogre_style",
        label="OgreInterface-inspired fixed-surface 2D direction-and-scale signature",
        method_kind="heuristic_grouping",
        fidelity="source_derived_2d_analogue",
        reference="Moayedpour et al., J. Chem. Phys. 2021; OgreInterface source",
        implementation_basis=(
            "per-column primitive integer direction, integer scale factor, and "
            "side-specific supplied fixed-surface 2D symmetry-orbit representative; "
            "the external bulk-3D crystallographic signature is not reproduced"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="1.2.17@8ff0cbc99f81fcadaff77cb2242f3d050217c2ff",
        source_repository="https://github.com/DerekDardzinski/OgreInterface",
        representative_policy="ordered B-then-A direction-and-scale signature",
        documented_deviations=(
            "derives 2D primitive directions and scale factors from source matrices",
            "uses supplied terminated-surface rather than bulk 3D point groups",
            "uses unbounded Python integers rather than source int8 casts",
        ),
    ),
    "jelver_style": MethodMetadata(
        method_id="jelver_style",
        label="Jelver-style enumeration filters",
        method_kind="filter",
        fidelity="paper_derived_2d_analogue",
        reference="Jelver et al., Phys. Rev. B 96, 085306 (2017)",
        implementation_basis=(
            "lexicographic symmetry representatives, the published 2D Niggli "
            "inequalities on side A, and the global integer-content gcd test"
        ),
        candidate_universe="CALM-admitted fixed-surface 4x2 source-pair ledger",
        source_revision="doi:10.1103/PhysRevB.96.085306",
        source_repository=None,
        representative_policy="retain descriptions satisfying every paper-derived filter",
        documented_deviations=(
            "applies generation-time 3D filters post hoc to a fixed-surface 2D ledger",
        ),
    ),
    "intermat_source": MethodMetadata(
        method_id="intermat_source",
        label="InterMat current-source first-accepted selector",
        method_kind="selector",
        fidelity="source_derived_2d_analogue",
        reference="InterMat generate.py and JARVIS ZSLGenerator source",
        implementation_basis=(
            "lowest=True returns the first accepted match in native ZSL "
            "enumeration; a complete native admitted population and supplied "
            "native_zsl_rank values are therefore required"
        ),
        candidate_universe="complete native InterMat/JARVIS accepted-match population",
        source_revision=(
            "InterMat@a05d9f1cd9f2808dd2c11656a4e12d476e77b689; "
            "inspected JARVIS-Tools v2024.3.24@"
            "90d7d7ebe06b946ec4e8514b2f90156e86b21c87"
        ),
        source_repository="https://github.com/usnistgov/intermat",
        representative_policy="smallest supplied native ZSL traversal rank",
        documented_deviations=(
            "does not reconstruct JARVIS enumeration or acceptance from a CALM ledger",
            "the inspected external implementation is "
            "jarvis/analysis/interface/zur.py from the official "
            "https://github.com/usnistgov/jarvis JARVIS-Tools v2024.3.24 "
            "release at commit "
            "90d7d7ebe06b946ec4e8514b2f90156e86b21c87; this benchmark inspection "
            "target is not represented as an InterMat dependency pin",
        ),
    ),
    "intermat_paper_style": MethodMetadata(
        method_id="intermat_paper_style",
        label="InterMat paper-operationalized geometric selector",
        method_kind="selector",
        fidelity="paper_derived_2d_analogue",
        reference="Choudhary et al., Digital Discovery 3, 1365 (2024)",
        implementation_basis=(
            "independent Gauss reduction; configurable per-vector length, maximum "
            "endpoint-area, and included-angle admission filters defaulting to the "
            "paper's 8 percent, 300 square angstrom, and 1 degree values; followed "
            "by minimum aggregate vector-length mismatch over the admitted subset"
        ),
        candidate_universe="caller-supplied common admitted population",
        source_revision="doi:10.1039/D4DD00031E",
        source_repository="https://github.com/usnistgov/intermat",
        representative_policy="minimum benchmark-declared length-mismatch norm",
        documented_deviations=(
            "paper does not define the scalarization of two length mismatches",
            "uses the maximum of the two unstrained endpoint areas for the "
            "paper's maximum-area filter",
            "applies paper-described filters post hoc to a CALM-admitted common ledger",
            "differs from current first-accepted source behavior",
        ),
    ),
    "intermatch_style": MethodMetadata(
        method_id="intermatch_style",
        label="InterMatch-style elastic selector",
        method_kind="selector",
        fidelity="paper_derived_2d_analogue",
        reference="Gerber et al., Nature Communications 14, 7921 (2023)",
        implementation_basis=(
            "source-supercell-atom-count-first selection inside a declared strain "
            "ceiling, with precomputed comparable elastic energies as a required input"
        ),
        candidate_universe="caller-supplied common admitted population with elastic data",
        source_revision="1.0.0@6ab5de5039358446b9654aba5debb339fdf877b2",
        source_repository="https://github.com/eg587/InterMatch",
        representative_policy="source atom count first, then elastic energy, under strain ceiling",
        documented_deviations=(
            "uses a deterministic paper-style lexicographic policy instead "
            "of released order-dependent code",
            "derives the declared strained-side principal stretch changes "
            "from CALM logarithmic strains",
            "requires caller-supplied comparable elastic energies",
        ),
    ),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _exact_matrix(value: Any, *, shape: tuple[int, int], name: str) -> np.ndarray:
    # Object conversion preserves booleans in nested Python inputs; ordinary
    # NumPy coercion would silently turn ``True`` into the integer one.
    array = np.asarray(value, dtype=object)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    output = np.empty(shape, dtype=np.int_)
    for index, entry in np.ndenumerate(array):
        if isinstance(entry, (bool, np.bool_)) or not isinstance(entry, Integral):
            raise TypeError(f"{name} must contain exact integers")
        output[index] = int(entry)
    return output


def _float_matrix(value: Any, *, name: str) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite values")
    return array


def _optional_finite(value: Any, *, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real or None")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _record_identifier(record: Mapping[str, Any], source: np.ndarray) -> str:
    for name in ("record_id", "source_id", "match_id", "audit_index"):
        value = record.get(name)
        if value is not None:
            result = str(value).strip()
            if result:
                return result
    payload = json.dumps(source.tolist(), separators=(",", ":")).encode("utf-8")
    return "source-" + hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True)
class LedgerEntry:
    """Normalized, mapping-friendly view of one admitted source description."""

    record_id: str
    source_pair_matrix: np.ndarray
    source_basis_A: np.ndarray | None = None
    source_basis_B: np.ndarray | None = None
    source_gram_A: np.ndarray | None = None
    source_gram_B: np.ndarray | None = None
    principal_log_strains: tuple[float, float] | None = None
    d_cell: float | None = None
    atom_count: int | None = None
    source_atom_count: int | None = None
    elastic_energy: float | None = None
    native_zsl_rank: int | None = None

    @classmethod
    def from_record(cls, record: LedgerEntry | Mapping[str, Any]) -> LedgerEntry:
        """Normalize either a trace record mapping or an existing entry."""

        if isinstance(record, cls):
            return record
        if not isinstance(record, Mapping):
            raise TypeError("record must be a LedgerEntry or mapping")
        source = _exact_matrix(
            record["source_pair_matrix"],
            shape=(4, 2),
            name="source_pair_matrix",
        )
        if _det2(source[:2]) == 0 or _det2(source[2:]) == 0:
            raise ValueError("both source_pair_matrix blocks must be nonsingular")

        basis_a_value = record.get("source_basis_A")
        basis_b_value = record.get("source_basis_B")
        gram_a_value = record.get("source_gram_A")
        gram_b_value = record.get("source_gram_B")
        basis_a = (
            None
            if basis_a_value is None
            else _float_matrix(basis_a_value, name="source_basis_A")
        )
        basis_b = (
            None
            if basis_b_value is None
            else _float_matrix(basis_b_value, name="source_basis_B")
        )
        gram_a = (
            None
            if gram_a_value is None
            else _float_matrix(gram_a_value, name="source_gram_A")
        )
        gram_b = (
            None
            if gram_b_value is None
            else _float_matrix(gram_b_value, name="source_gram_B")
        )
        if gram_a is None and basis_a is not None:
            gram_a = basis_a.T @ basis_a
        if gram_b is None and basis_b is not None:
            gram_b = basis_b.T @ basis_b
        for name, gram, basis in (
            ("A", gram_a, basis_a),
            ("B", gram_b, basis_b),
        ):
            if gram is None:
                continue
            scale = max(1.0, float(np.max(np.abs(gram))))
            if not np.allclose(gram, gram.T, rtol=1.0e-12, atol=1.0e-12 * scale):
                raise ValueError(f"source_gram_{name} must be symmetric")
            if float(np.linalg.eigvalsh(0.5 * (gram + gram.T))[0]) <= 0.0:
                raise ValueError(f"source_gram_{name} must be positive definite")
            if basis is not None and not np.allclose(
                gram,
                basis.T @ basis,
                rtol=1.0e-10,
                atol=1.0e-10 * scale,
            ):
                raise ValueError(
                    f"source_gram_{name} must equal source_basis_{name}.T @ "
                    f"source_basis_{name}"
                )

        strain_value = record.get("principal_log_strains")
        strains: tuple[float, float] | None = None
        if strain_value is not None:
            array = np.asarray(strain_value, dtype=float)
            if array.shape != (2,) or not np.all(np.isfinite(array)):
                raise ValueError("principal_log_strains must contain two finite values")
            strains = (float(array[0]), float(array[1]))

        def optional_positive_integer(name: str) -> int | None:
            value = record.get(name)
            if value is None:
                return None
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
                raise TypeError(f"{name} must be a positive integer or None")
            result = int(value)
            if result <= 0:
                raise ValueError(f"{name} must be positive")
            return result

        atom_count = optional_positive_integer("atom_count")
        source_atom_count = optional_positive_integer("source_atom_count")
        native_rank_value = record.get("native_zsl_rank")
        if native_rank_value is None:
            native_zsl_rank = None
        elif isinstance(native_rank_value, (bool, np.bool_)) or not isinstance(
            native_rank_value,
            Integral,
        ):
            raise TypeError("native_zsl_rank must be a nonnegative integer or None")
        elif int(native_rank_value) < 0:
            raise ValueError("native_zsl_rank must be nonnegative")
        else:
            native_zsl_rank = int(native_rank_value)

        return cls(
            record_id=_record_identifier(record, source),
            source_pair_matrix=source,
            source_basis_A=basis_a,
            source_basis_B=basis_b,
            source_gram_A=gram_a,
            source_gram_B=gram_b,
            principal_log_strains=strains,
            d_cell=_optional_finite(record.get("d_cell"), name="d_cell"),
            atom_count=atom_count,
            source_atom_count=source_atom_count,
            elastic_energy=_optional_finite(
                record.get("elastic_energy"),
                name="elastic_energy",
            ),
            native_zsl_rank=native_zsl_rank,
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_value(
            {
                "record_id": self.record_id,
                "source_pair_matrix": self.source_pair_matrix,
                "source_basis_A": self.source_basis_A,
                "source_basis_B": self.source_basis_B,
                "source_gram_A": self.source_gram_A,
                "source_gram_B": self.source_gram_B,
                "principal_log_strains": self.principal_log_strains,
                "d_cell": self.d_cell,
                "atom_count": self.atom_count,
                "source_atom_count": self.source_atom_count,
                "elastic_energy": self.elastic_energy,
                "native_zsl_rank": self.native_zsl_rank,
            }
        )


@dataclass(frozen=True)
class AdapterOutcome:
    """JSON-serializable classification or filter result for one ledger row."""

    metadata: MethodMetadata
    record_id: str
    status: AdapterStatus
    class_key: tuple[Any, ...] | None = None
    retained: bool | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_value(
            {
                "method": self.metadata.to_dict(),
                "record_id": self.record_id,
                "status": self.status,
                "class_key": self.class_key,
                "retained": self.retained,
                "diagnostics": dict(self.diagnostics),
            }
        )


@dataclass(frozen=True)
class SelectionOutcome:
    """Deterministic collection-level selector result."""

    metadata: MethodMetadata
    status: AdapterStatus
    selected_record_ids: tuple[str, ...] = ()
    score_by_record_id: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    reason: str | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_value(
            {
                "method": self.metadata.to_dict(),
                "status": self.status,
                "selected_record_ids": self.selected_record_ids,
                "score_by_record_id": dict(self.score_by_record_id),
                "reason": self.reason,
                "diagnostics": dict(self.diagnostics),
            }
        )


@dataclass(frozen=True)
class ClusteringOutcome:
    """Collection-level class assignment from a possibly non-transitive rule."""

    metadata: MethodMetadata
    status: AdapterStatus
    class_by_record_id: Mapping[str, str] = field(default_factory=dict)
    representative_by_class_id: Mapping[str, str] = field(default_factory=dict)
    members_by_class_id: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    reason: str | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_value(
            {
                "method": self.metadata.to_dict(),
                "status": self.status,
                "class_by_record_id": dict(self.class_by_record_id),
                "representative_by_class_id": dict(self.representative_by_class_id),
                "members_by_class_id": dict(self.members_by_class_id),
                "reason": self.reason,
                "diagnostics": dict(self.diagnostics),
            }
        )


def _entry(record: LedgerEntry | Mapping[str, Any]) -> LedgerEntry:
    return LedgerEntry.from_record(record)


def _flat_key(matrix: np.ndarray) -> tuple[int, ...]:
    return tuple(int(value) for value in np.asarray(matrix).ravel())


def _det2(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(matrix[1, 0])


def _default_policy() -> PairIdentityPolicy2D:
    return PairIdentityPolicy2D(
        pair_symmetry="full",
        correspondence_orientation="proper",
        identify_material_exchange=False,
    )


def calm_stage_keys(
    record: LedgerEntry | Mapping[str, Any],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    policy: PairIdentityPolicy2D | None = None,
) -> AdapterOutcome:
    """Return CALM's exact source, saturation, common-right, and final keys."""

    item = _entry(record)
    selected_policy = _default_policy() if policy is None else policy
    if not isinstance(selected_policy, PairIdentityPolicy2D):
        raise TypeError("policy must be PairIdentityPolicy2D or None")
    source = item.source_pair_matrix
    determinant_a = _det2(source[:2])
    determinant_b = _det2(source[2:])
    orientation_sign = 1 if determinant_a * determinant_b > 0 else -1
    if selected_policy.correspondence_orientation == "proper" and orientation_sign < 0:
        return AdapterOutcome(
            metadata=METHOD_METADATA["calm"],
            record_id=item.record_id,
            status="rejected",
            retained=False,
            diagnostics={
                "reason": "relative_orientation_not_proper",
                "source_key": _flat_key(source),
                "relative_orientation_sign": orientation_sign,
            },
        )

    factorization = primitiveize_pair_matrix_2d(source)
    primitive = np.asarray(factorization.primitive_matrix, dtype=int)
    common_right = canonicalize_common_right_rank2(primitive)
    final = canonicalize_primitive_pair_2d(
        primitive,
        point_group_A=point_group_A,
        point_group_B=point_group_B,
        policy=selected_policy,
    )
    return AdapterOutcome(
        metadata=METHOD_METADATA["calm"],
        record_id=item.record_id,
        status="classified",
        class_key=tuple(int(value) for value in final.key),
        retained=True,
        diagnostics={
            "source_key": _flat_key(source),
            "saturated_key": _flat_key(primitive),
            "common_right_key": tuple(int(value) for value in common_right.key),
            "surface_symmetry_key": tuple(int(value) for value in final.key),
            "repeat_index": int(factorization.repeat_index),
            "maximal_minors": tuple(int(value) for value in factorization.maximal_minors),
            "source_right_factor": _flat_key(factorization.source_right_factor),
            "relative_orientation_sign": orientation_sign,
        },
    )


def _intrinsic_basis(gram: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (gram + gram.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if float(eigenvalues[0]) <= 0.0:
        raise ValueError("source Gram matrices must be positive definite")
    # G = L L.T, so A = L.T satisfies A.T @ A = G.
    return np.linalg.cholesky(symmetric).T


def _reduced_metric_signature(
    gram: np.ndarray,
    *,
    reduction_tolerance: float,
    signature_scale: float,
) -> tuple[int, int, int]:
    reduced_gram = _independently_reduced_gram(
        gram,
        reduction_tolerance=reduction_tolerance,
    )
    return (
        int(np.rint(signature_scale * float(reduced_gram[0, 0]))),
        int(np.rint(signature_scale * float(reduced_gram[0, 1]))),
        int(np.rint(signature_scale * float(reduced_gram[1, 1]))),
    )


def _independently_reduced_gram(
    gram: np.ndarray,
    *,
    reduction_tolerance: float,
) -> np.ndarray:
    reduced, _unimodular, _embedding = canonical_gauss_reduce_2d(
        _intrinsic_basis(gram),
        tol=reduction_tolerance,
        warn_on_handedness_repair=False,
    )
    array = np.asarray(reduced, dtype=float)
    return array.T @ array


def zur_mcgill_descriptor_key(
    record: LedgerEntry | Mapping[str, Any],
    *,
    reduction_tolerance: float = 1.0e-12,
    signature_scale: float = 1.0e10,
) -> AdapterOutcome:
    """Group independently reduced cell metrics as a diagnostic baseline.

    Zur and McGill compare reduced-vector lengths and included angles; they do
    not publish this quantized pair key as an interface equivalence relation.
    The adapter is intentionally named and labelled as a descriptor baseline.
    """

    if not math.isfinite(reduction_tolerance) or reduction_tolerance <= 0.0:
        raise ValueError("reduction_tolerance must be finite and positive")
    if not math.isfinite(signature_scale) or signature_scale <= 0.0:
        raise ValueError("signature_scale must be finite and positive")
    item = _entry(record)
    if item.source_gram_A is None or item.source_gram_B is None:
        return AdapterOutcome(
            metadata=METHOD_METADATA["zur_mcgill_descriptor"],
            record_id=item.record_id,
            status="not_applicable",
            retained=None,
            diagnostics={
                "reason": "source_gram_A_and_source_gram_B_required",
                "reduction_tolerance": reduction_tolerance,
                "signature_scale": signature_scale,
            },
        )
    signature_a = _reduced_metric_signature(
        item.source_gram_A,
        reduction_tolerance=reduction_tolerance,
        signature_scale=signature_scale,
    )
    signature_b = _reduced_metric_signature(
        item.source_gram_B,
        reduction_tolerance=reduction_tolerance,
        signature_scale=signature_scale,
    )
    return AdapterOutcome(
        metadata=METHOD_METADATA["zur_mcgill_descriptor"],
        record_id=item.record_id,
        status="classified",
        class_key=(signature_a, signature_b),
        retained=True,
        diagnostics={
            "reduction_tolerance": reduction_tolerance,
            "signature_scale": signature_scale,
            "descriptor": "quantized_entries_G11_G12_G22_after_independent_reduction",
            "published_equivalence_quotient": False,
        },
    )


def _validated_operations(
    operations: Sequence[np.ndarray],
    *,
    name: str,
) -> tuple[np.ndarray, ...]:
    if len(operations) == 0:
        raise ValueError(f"{name} must be nonempty")
    unique: dict[tuple[int, ...], np.ndarray] = {}
    for index, operation in enumerate(operations):
        matrix = _exact_matrix(operation, shape=(2, 2), name=f"{name}[{index}]")
        if abs(_det2(matrix)) != 1:
            raise ValueError(f"{name}[{index}] must be unimodular")
        unique[_flat_key(matrix)] = matrix
    identity = _flat_key(np.eye(2, dtype=int))
    if identity not in unique:
        raise ValueError(f"{name} must contain the identity operation")
    return tuple(unique[key] for key in sorted(unique))


def _primitive_direction(vector: np.ndarray, *, unoriented: bool) -> tuple[int, int]:
    values = (int(vector[0]), int(vector[1]))
    content = gcd(abs(values[0]), abs(values[1]))
    if content == 0:
        raise ValueError("supercell direction cannot be zero")
    reduced = (values[0] // content, values[1] // content)
    if unoriented:
        reduced = min(reduced, (-reduced[0], -reduced[1]))
    return reduced


def _direction_orbit_key(
    vector: np.ndarray,
    operations: Sequence[np.ndarray],
    *,
    unoriented: bool,
) -> tuple[int, int]:
    return min(
        _primitive_direction(operation @ vector, unoriented=unoriented)
        for operation in operations
    )


def interoptimus_direction_signature(
    record: LedgerEntry | Mapping[str, Any],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
) -> AdapterOutcome:
    """Classify by four independent direction orbits and simultaneous swap.

    The external implementation tests normalized Cartesian directions with a
    tolerance and may fall back to ``StructureMatcher``.  This exact-integer 2D
    adapter isolates its direction-index branch; it is not an implementation of
    the structure-matching fallback.
    """

    item = _entry(record)
    group_a = _validated_operations(point_group_A, name="point_group_A")
    group_b = _validated_operations(point_group_B, name="point_group_B")
    block_a = item.source_pair_matrix[:2]
    block_b = item.source_pair_matrix[2:]
    a = tuple(
        _direction_orbit_key(block_a[:, index], group_a, unoriented=True)
        for index in range(2)
    )
    b = tuple(
        _direction_orbit_key(block_b[:, index], group_b, unoriented=True)
        for index in range(2)
    )
    direct = (a[0], a[1], b[0], b[1])
    swapped = (a[1], a[0], b[1], b[0])
    key = min(direct, swapped)
    return AdapterOutcome(
        metadata=METHOD_METADATA["interoptimus_direction_signature"],
        record_id=item.record_id,
        status="classified",
        class_key=key,
        retained=True,
        diagnostics={
            "simultaneous_swap_selected": key == swapped and swapped != direct,
            "direction_sign_ignored": True,
            "symmetry_domain": "supplied_fixed_surface_2d_point_groups",
            "external_bulk_3d_symmetry_included": False,
            "structure_matcher_fallback_included": False,
        },
    )


def _primitive_surface_basis(item: LedgerEntry, *, side: Literal["A", "B"]) -> np.ndarray:
    basis = item.source_basis_A if side == "A" else item.source_basis_B
    block = item.source_pair_matrix[:2] if side == "A" else item.source_pair_matrix[2:]
    if basis is None:
        raise ValueError(f"source_basis_{side} is required")
    try:
        primitive = np.asarray(basis, dtype=float) @ np.linalg.inv(
            np.asarray(block, dtype=float)
        )
    except np.linalg.LinAlgError as exc:  # guarded by LedgerEntry validation
        raise ValueError(f"source block {side} must be nonsingular") from exc
    if not np.all(np.isfinite(primitive)):
        raise ValueError(f"derived primitive surface basis {side} is not finite")
    return primitive


def _unit_direction(vector: np.ndarray) -> np.ndarray:
    array = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        raise ValueError("physical supercell directions must be nonzero")
    return array / norm


@dataclass(frozen=True)
class _PreparedInterOptimus2D:
    entry: LedgerEntry
    unit_A: tuple[np.ndarray, np.ndarray]
    unit_B: tuple[np.ndarray, np.ndarray]
    orbit_A: tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]
    orbit_B: tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]
    substrate_angle_cosine: float


def _prepare_interoptimus_entry(
    entry: LedgerEntry,
    *,
    group_a: Sequence[np.ndarray],
    group_b: Sequence[np.ndarray],
) -> _PreparedInterOptimus2D:
    if entry.source_basis_A is None or entry.source_basis_B is None:
        raise ValueError("both source bases are required")
    primitive_a = _primitive_surface_basis(entry, side="A")
    primitive_b = _primitive_surface_basis(entry, side="B")
    block_a = entry.source_pair_matrix[:2]
    block_b = entry.source_pair_matrix[2:]
    unit_a = tuple(_unit_direction(entry.source_basis_A[:, index]) for index in range(2))
    unit_b = tuple(_unit_direction(entry.source_basis_B[:, index]) for index in range(2))
    orbit_a = tuple(
        tuple(
            _unit_direction(primitive_a @ (operation @ block_a[:, index]))
            for operation in group_a
        )
        for index in range(2)
    )
    orbit_b = tuple(
        tuple(
            _unit_direction(primitive_b @ (operation @ block_b[:, index]))
            for operation in group_b
        )
        for index in range(2)
    )
    return _PreparedInterOptimus2D(
        entry=entry,
        unit_A=(unit_a[0], unit_a[1]),
        unit_B=(unit_b[0], unit_b[1]),
        orbit_A=(orbit_a[0], orbit_a[1]),
        orbit_B=(orbit_b[0], orbit_b[1]),
        substrate_angle_cosine=float(np.dot(unit_b[0], unit_b[1])),
    )


def _orbit_contains_parallel_direction(
    orbit: Sequence[np.ndarray],
    target: np.ndarray,
    *,
    cross_tolerance: float,
) -> bool:
    return any(
        abs(float(unit[0] * target[1] - unit[1] * target[0])) < cross_tolerance
        for unit in orbit
    )


def _interoptimus_pairwise_equivalent(
    first: _PreparedInterOptimus2D,
    second: _PreparedInterOptimus2D,
    *,
    cross_tolerance: float,
) -> bool:
    def correspondence(order: tuple[int, int]) -> bool:
        return all(
            _orbit_contains_parallel_direction(
                first.orbit_A[index],
                second.unit_A[order[index]],
                cross_tolerance=cross_tolerance,
            )
            and _orbit_contains_parallel_direction(
                first.orbit_B[index],
                second.unit_B[order[index]],
                cross_tolerance=cross_tolerance,
            )
            for index in range(2)
        )

    return correspondence((0, 1)) or correspondence((1, 0))


def cluster_interoptimus_style(
    records: Sequence[LedgerEntry | Mapping[str, Any]],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    cross_tolerance: float = 1.0e-2,
    angle_cosine_tolerance: float = 1.0e-1,
) -> ClusteringOutcome:
    """Greedily cluster a cohort using an InterOptimus-inspired pair test.

    The pair predicate follows the direction-index branch of the pinned source:
    corresponding normalized directions may be related independently by a
    symmetry operation, and the two columns may be swapped simultaneously on
    both sides.  Because a tolerance predicate need not be transitive, this
    adapter retains greedy representative assignment rather than manufacturing
    a canonical key.  The missing atomistic ``StructureMatcher`` fallback is
    recorded explicitly.
    """

    if not math.isfinite(cross_tolerance) or cross_tolerance <= 0.0:
        raise ValueError("cross_tolerance must be finite and positive")
    if not math.isfinite(angle_cosine_tolerance) or angle_cosine_tolerance <= 0.0:
        raise ValueError("angle_cosine_tolerance must be finite and positive")
    entries = tuple(_entry(record) for record in records)
    if not entries:
        return ClusteringOutcome(
            metadata=METHOD_METADATA["interoptimus_greedy"],
            status="not_applicable",
            reason="no_records",
            diagnostics={
                "cross_tolerance": cross_tolerance,
                "angle_cosine_tolerance": angle_cosine_tolerance,
            },
        )
    _require_unique_record_ids(entries)
    missing = tuple(
        entry.record_id
        for entry in entries
        if (
            entry.source_basis_A is None
            or entry.source_basis_B is None
            or entry.principal_log_strains is None
            or entry.source_atom_count is None
        )
    )
    if missing:
        return ClusteringOutcome(
            metadata=METHOD_METADATA["interoptimus_greedy"],
            status="not_applicable",
            reason=(
                "source_bases_principal_log_strains_and_source_atom_count_required"
            ),
            diagnostics={
                "missing_record_ids": missing,
                "cross_tolerance": cross_tolerance,
                "angle_cosine_tolerance": angle_cosine_tolerance,
            },
        )
    group_a = _validated_operations(point_group_A, name="point_group_A")
    group_b = _validated_operations(point_group_B, name="point_group_B")

    prepared = tuple(
        _prepare_interoptimus_entry(
            entry,
            group_a=group_a,
            group_b=group_b,
        )
        for entry in entries
    )

    def ordering_key(item: _PreparedInterOptimus2D) -> tuple[float, float, str]:
        strains = item.entry.principal_log_strains
        assert strains is not None
        first, second = strains
        von_mises_proxy = math.sqrt(
            max(0.0, first * first - first * second + second * second)
        )
        assert item.entry.source_atom_count is not None
        return (
            von_mises_proxy,
            float(item.entry.source_atom_count),
            item.entry.record_id,
        )

    ordered = tuple(sorted(prepared, key=ordering_key))
    representatives: list[_PreparedInterOptimus2D] = []
    members: list[list[str]] = []
    assignment: dict[str, str] = {}
    pair_tests = 0
    angle_prefilter_rejections = 0
    for item in ordered:
        assigned_index: int | None = None
        for index, representative in enumerate(representatives):
            if (
                abs(
                    representative.substrate_angle_cosine
                    - item.substrate_angle_cosine
                )
                >= angle_cosine_tolerance
            ):
                angle_prefilter_rejections += 1
                continue
            pair_tests += 1
            if _interoptimus_pairwise_equivalent(
                representative,
                item,
                cross_tolerance=cross_tolerance,
            ):
                assigned_index = index
                break
        if assigned_index is None:
            assigned_index = len(representatives)
            representatives.append(item)
            members.append([])
        class_id = f"IO{assigned_index:06d}"
        assignment[item.entry.record_id] = class_id
        members[assigned_index].append(item.entry.record_id)

    representative_by_class = {
        f"IO{index:06d}": representative.entry.record_id
        for index, representative in enumerate(representatives)
    }
    members_by_class = {
        f"IO{index:06d}": tuple(sorted(class_members))
        for index, class_members in enumerate(members)
    }
    return ClusteringOutcome(
        metadata=METHOD_METADATA["interoptimus_greedy"],
        status="classified",
        class_by_record_id=dict(sorted(assignment.items())),
        representative_by_class_id=representative_by_class,
        members_by_class_id=members_by_class,
        diagnostics={
            "cross_tolerance": cross_tolerance,
            "angle_cosine_tolerance": angle_cosine_tolerance,
            "angle_prefilter_rejections": angle_prefilter_rejections,
            "pair_tests": pair_tests,
            "cluster_count": len(representatives),
            "ordering": (
                "2d_hencky_von_mises_proxy",
                "source_atom_count",
                "record_id",
            ),
            "von_mises_proxy": "sqrt(e1^2-e1*e2+e2^2)",
            "symmetry_domain": "supplied_fixed_surface_2d_point_groups",
            "direction_sign_ignored": True,
            "structure_matcher_fallback_included": False,
            "relation_may_be_nontransitive": True,
        },
    )


def _direction_and_scale(
    vector: np.ndarray,
    operations: Sequence[np.ndarray],
) -> tuple[int, tuple[int, int]]:
    values = (int(vector[0]), int(vector[1]))
    scale = gcd(abs(values[0]), abs(values[1]))
    if scale == 0:
        raise ValueError("supercell direction cannot be zero")
    direction = np.asarray((values[0] // scale, values[1] // scale), dtype=int)
    orbit = min(
        _primitive_direction(operation @ direction, unoriented=False)
        for operation in operations
    )
    return scale, orbit


def ogre_style_key(
    record: LedgerEntry | Mapping[str, Any],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
) -> AdapterOutcome:
    """Classify by an OgreInterface-inspired 2D direction-and-scale signature."""

    item = _entry(record)
    group_a = _validated_operations(point_group_A, name="point_group_A")
    group_b = _validated_operations(point_group_B, name="point_group_B")
    block_a = item.source_pair_matrix[:2]
    block_b = item.source_pair_matrix[2:]
    side_a = tuple(_direction_and_scale(block_a[:, index], group_a) for index in range(2))
    side_b = tuple(_direction_and_scale(block_b[:, index], group_b) for index in range(2))
    # OgreInterface's source signature lists substrate before film and retains
    # vector order.  Here B is the substrate analogue and A the film analogue.
    key = (side_b[0], side_b[1], side_a[0], side_a[1])
    return AdapterOutcome(
        metadata=METHOD_METADATA["ogre_style"],
        record_id=item.record_id,
        status="classified",
        class_key=key,
        retained=True,
        diagnostics={
            "side_order": ("B", "A"),
            "column_order_preserved": True,
            "integer_width": "python_int",
            "symmetry_domain": "supplied_fixed_surface_2d_point_groups",
            "external_bulk_3d_signature_included": False,
        },
    )


def _vector_orbit_key(vector: np.ndarray, operations: Sequence[np.ndarray]) -> tuple[int, int]:
    return min(tuple(int(value) for value in operation @ vector) for operation in operations)


def _cell_orbit_key(block: np.ndarray, operations: Sequence[np.ndarray]) -> tuple[int, ...]:
    # The paper orders a cell as the pair (u1, u2).  CALM stores generators in
    # columns, so transpose before flattening to keep every component of u1
    # ahead of every component of u2 in the lexicographic comparison.
    return min(
        tuple(int(value) for value in (operation @ block).T.ravel())
        for operation in operations
    )


def _column_pair_key(block: np.ndarray) -> tuple[int, ...]:
    """Return the vector-major key ``(u1, u2)`` for a column-basis cell."""

    return tuple(int(value) for value in np.asarray(block).T.ravel())


def _niggli_2d_side_a(item: LedgerEntry, *, tolerance: float) -> bool | None:
    gram = item.source_gram_A
    if gram is None:
        return None
    scale = max(1.0, float(np.max(np.abs(gram))))
    slack = tolerance * scale
    return bool(
        float(gram[0, 0]) <= float(gram[1, 1]) + slack
        and float(gram[0, 1]) <= 0.5 * float(gram[0, 0]) + slack
    )


def jelver_style_filter(
    record: LedgerEntry | Mapping[str, Any],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    tolerance: float = 1.0e-12,
) -> AdapterOutcome:
    """Apply a 2D analogue of the filters described by Jelver et al.

    The paper applies these rules while generating three-dimensional lattice
    vectors and surface-cell pairs.  Applying them after CALM has generated a
    2D source ledger is therefore an explicit benchmark analogue.  Consistent
    with the paper, the Niggli inequalities are applied only to side A.
    """

    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and nonnegative")
    item = _entry(record)
    group_a = _validated_operations(point_group_A, name="point_group_A")
    group_b = _validated_operations(point_group_B, name="point_group_B")
    block_a = item.source_pair_matrix[:2]
    block_b = item.source_pair_matrix[2:]

    vector_symmetry_a = bool(
        tuple(int(value) for value in block_a[:, 1])
        == _vector_orbit_key(block_a[:, 1], group_a)
    )
    vector_symmetry_b = bool(
        tuple(int(value) for value in block_b[:, 1])
        == _vector_orbit_key(block_b[:, 1], group_b)
    )
    cell_symmetry_a = bool(
        _column_pair_key(block_a) == _cell_orbit_key(block_a, group_a)
    )
    cell_symmetry_b = bool(
        _column_pair_key(block_b) == _cell_orbit_key(block_b, group_b)
    )
    symmetry_a = vector_symmetry_a and cell_symmetry_a
    symmetry_b = vector_symmetry_b and cell_symmetry_b
    niggli_a = _niggli_2d_side_a(item, tolerance=tolerance)
    integer_content = reduce(
        gcd,
        (abs(int(value)) for value in item.source_pair_matrix.ravel()),
        0,
    )
    globally_primitive = integer_content == 1

    if niggli_a is None:
        return AdapterOutcome(
            metadata=METHOD_METADATA["jelver_style"],
            record_id=item.record_id,
            status="not_applicable",
            retained=None,
            diagnostics={
                "reason": "source_gram_A_or_source_basis_A_required_for_niggli_test",
                "symmetry_canonical_A": symmetry_a,
                "symmetry_canonical_B": symmetry_b,
                "second_vector_symmetry_canonical_A": vector_symmetry_a,
                "second_vector_symmetry_canonical_B": vector_symmetry_b,
                "cell_symmetry_canonical_A": cell_symmetry_a,
                "cell_symmetry_canonical_B": cell_symmetry_b,
                "cell_lexicographic_order": "first_vector_then_second_vector",
                "global_integer_content": integer_content,
                "global_gcd_pass": globally_primitive,
            },
        )

    retained = bool(symmetry_a and symmetry_b and niggli_a and globally_primitive)
    return AdapterOutcome(
        metadata=METHOD_METADATA["jelver_style"],
        record_id=item.record_id,
        status="retained" if retained else "rejected",
        retained=retained,
        diagnostics={
            "symmetry_canonical_A": symmetry_a,
            "symmetry_canonical_B": symmetry_b,
            "second_vector_symmetry_canonical_A": vector_symmetry_a,
            "second_vector_symmetry_canonical_B": vector_symmetry_b,
            "cell_symmetry_canonical_A": cell_symmetry_a,
            "cell_symmetry_canonical_B": cell_symmetry_b,
            "cell_lexicographic_order": "first_vector_then_second_vector",
            "niggli_side": "A",
            "niggli_pass_A": niggli_a,
            "global_integer_content": integer_content,
            "global_gcd_pass": globally_primitive,
        },
    )


def _require_unique_record_ids(entries: Sequence[LedgerEntry]) -> None:
    identifiers = [entry.record_id for entry in entries]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("record_id values must be unique for collection selectors")


def _angle_from_gram(gram: np.ndarray) -> float:
    denominator = math.sqrt(float(gram[0, 0]) * float(gram[1, 1]))
    if denominator <= 0.0:
        raise ValueError("source Gram matrices must be positive definite")
    cosine = float(gram[0, 1]) / denominator
    return math.acos(max(-1.0, min(1.0, cosine)))


def select_intermat_source(
    records: Sequence[LedgerEntry | Mapping[str, Any]],
    *,
    native_zsl_rank_by_id: Mapping[str, int] | None = None,
) -> SelectionOutcome:
    """Select the first accepted match in a supplied native ZSL traversal.

    Current InterMat delegates to JARVIS with ``lowest=True``.  That flag stops
    at the first passing match; it is not a global post-hoc mismatch minimum.
    A CALM ledger does not contain the native JARVIS traversal rank, so absence
    of that provenance is reported as ``not_applicable``.
    """

    entries = tuple(_entry(record) for record in records)
    if not entries:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermat_source"],
            status="not_applicable",
            reason="no_records",
        )
    _require_unique_record_ids(entries)
    supplied = (
        {}
        if native_zsl_rank_by_id is None
        else {
            str(identifier): value
            for identifier, value in native_zsl_rank_by_id.items()
        }
    )
    ranks: dict[str, int] = {}
    missing: list[str] = []
    for entry in entries:
        value = supplied.get(entry.record_id, entry.native_zsl_rank)
        if value is None:
            missing.append(entry.record_id)
            continue
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise TypeError("native ZSL ranks must be nonnegative integers")
        rank = int(value)
        if rank < 0:
            raise ValueError("native ZSL ranks must be nonnegative integers")
        ranks[entry.record_id] = rank
    if missing:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermat_source"],
            status="not_applicable",
            reason="native_zsl_rank_required_for_every_record",
            diagnostics={"missing_record_ids": tuple(missing)},
        )
    if len(ranks) != len(set(ranks.values())):
        raise ValueError(
            "native ZSL ranks must be unique to identify a first accepted match"
        )
    first_rank = min(ranks.values())
    selected = tuple(
        identifier for identifier, rank in ranks.items() if rank == first_rank
    )
    return SelectionOutcome(
        metadata=METHOD_METADATA["intermat_source"],
        status="selected",
        selected_record_ids=selected,
        score_by_record_id={
            identifier: (float(rank),) for identifier, rank in ranks.items()
        },
        diagnostics={
            "score_order": ("native_zsl_rank",),
            "selection_semantics": "first_accepted_native_zsl_match",
        },
    )


def select_intermat_paper_style(
    records: Sequence[LedgerEntry | Mapping[str, Any]],
    *,
    length_norm: Literal["l1", "l2", "linf"] = "l2",
    reduction_tolerance: float = 1.0e-12,
    max_length_mismatch: float = 0.08,
    max_area: float = 300.0,
    max_angle_mismatch_degrees: float = 1.0,
) -> SelectionOutcome:
    """Apply the paper's filters, then select minimum vector-length mismatch.

    The default admission thresholds are the values reported by Choudhary
    et al.: 8 percent per-vector lattice mismatch, a 300 square angstrom
    maximum cell area, and a 1 degree included-angle mismatch.  Because the
    paper does not state which endpoint area controls when the two unstrained
    areas differ, this fixed-ledger operationalization requires both endpoint
    areas to be within ``max_area``.  The paper also does not state how to
    aggregate unequal vector mismatches, so ``length_norm`` remains an explicit
    benchmark policy rather than an attributed InterMat detail.

    This selector acts only on the caller-supplied common population.  It does
    not reconstruct InterMat/JARVIS enumeration and must not be interpreted as
    native-package parity.
    """

    if length_norm not in {"l1", "l2", "linf"}:
        raise ValueError("length_norm must be 'l1', 'l2', or 'linf'")
    if not math.isfinite(reduction_tolerance) or reduction_tolerance <= 0.0:
        raise ValueError("reduction_tolerance must be finite and positive")
    if not math.isfinite(max_length_mismatch) or max_length_mismatch < 0.0:
        raise ValueError("max_length_mismatch must be finite and nonnegative")
    if not math.isfinite(max_area) or max_area <= 0.0:
        raise ValueError("max_area must be finite and positive")
    if (
        not math.isfinite(max_angle_mismatch_degrees)
        or not 0.0 <= max_angle_mismatch_degrees <= 180.0
    ):
        raise ValueError(
            "max_angle_mismatch_degrees must be finite and between 0 and 180"
        )
    admission_parameters = {
        "max_length_mismatch": max_length_mismatch,
        "max_area_angstrom2": max_area,
        "max_angle_mismatch_degrees": max_angle_mismatch_degrees,
        "area_filter": "max(unstrained_endpoint_area_A,unstrained_endpoint_area_B)",
    }
    entries = tuple(_entry(record) for record in records)
    if not entries:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermat_paper_style"],
            status="not_applicable",
            reason="no_records",
            diagnostics={
                "length_norm": length_norm,
                "reduction_tolerance": reduction_tolerance,
                **admission_parameters,
            },
        )
    _require_unique_record_ids(entries)
    missing = tuple(
        entry.record_id
        for entry in entries
        if entry.source_gram_A is None or entry.source_gram_B is None
    )
    if missing:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermat_paper_style"],
            status="not_applicable",
            reason="source_gram_A_and_source_gram_B_required",
            diagnostics={
                "missing_record_ids": missing,
                "length_norm": length_norm,
                "reduction_tolerance": reduction_tolerance,
                **admission_parameters,
            },
        )

    scores: dict[str, tuple[float, ...]] = {}
    rejection_counts = {
        "per_vector_length_mismatch": 0,
        "maximum_endpoint_area": 0,
        "included_angle_mismatch": 0,
    }
    machine_slack = 64.0 * np.finfo(float).eps
    length_slack = machine_slack * max(1.0, max_length_mismatch)
    area_slack = machine_slack * max(1.0, max_area)
    angle_slack = machine_slack * max(1.0, max_angle_mismatch_degrees)
    for entry in entries:
        gram_a = _independently_reduced_gram(
            np.asarray(entry.source_gram_A, dtype=float),
            reduction_tolerance=reduction_tolerance,
        )
        gram_b = _independently_reduced_gram(
            np.asarray(entry.source_gram_B, dtype=float),
            reduction_tolerance=reduction_tolerance,
        )
        lengths_a = np.sqrt(np.diag(gram_a))
        lengths_b = np.sqrt(np.diag(gram_b))
        if np.any(lengths_a <= 0.0) or np.any(lengths_b <= 0.0):
            raise ValueError("source Gram matrices must have positive diagonal entries")
        mismatches = np.abs(lengths_b / lengths_a - 1.0)
        if length_norm == "l1":
            aggregate = float(np.sum(mismatches))
        elif length_norm == "l2":
            aggregate = float(np.linalg.norm(mismatches))
        else:
            aggregate = float(np.max(mismatches))
        angle_mismatch = abs(_angle_from_gram(gram_b) - _angle_from_gram(gram_a))
        angle_mismatch_degrees = math.degrees(angle_mismatch)
        area_a = math.sqrt(float(np.linalg.det(gram_a)))
        area_b = math.sqrt(float(np.linalg.det(gram_b)))
        maximum_endpoint_area = max(area_a, area_b)
        length_admitted = bool(
            np.all(mismatches <= max_length_mismatch + length_slack)
        )
        area_admitted = maximum_endpoint_area <= max_area + area_slack
        angle_admitted = (
            angle_mismatch_degrees
            <= max_angle_mismatch_degrees + angle_slack
        )
        if not length_admitted:
            rejection_counts["per_vector_length_mismatch"] += 1
        if not area_admitted:
            rejection_counts["maximum_endpoint_area"] += 1
        if not angle_admitted:
            rejection_counts["included_angle_mismatch"] += 1
        if not (length_admitted and area_admitted and angle_admitted):
            continue
        mean_area = 0.5 * (area_a + area_b)
        scores[entry.record_id] = (
            aggregate,
            float(np.max(mismatches)),
            angle_mismatch,
            mean_area,
        )

    if not scores:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermat_paper_style"],
            status="not_applicable",
            reason="no_record_passes_paper_admission_filters",
            diagnostics={
                "length_norm": length_norm,
                "reduction_tolerance": reduction_tolerance,
                **admission_parameters,
                "input_record_count": len(entries),
                "admitted_record_count": 0,
                "rejection_counts_nonexclusive": rejection_counts,
                "candidate_universe": "caller_supplied_common_admitted_population",
                "native_parity": False,
            },
        )

    best_score = min(scores.values())
    selected = tuple(
        sorted(
            identifier
            for identifier, score in scores.items()
            if score == best_score
        )
    )
    return SelectionOutcome(
        metadata=METHOD_METADATA["intermat_paper_style"],
        status="selected",
        selected_record_ids=selected,
        score_by_record_id=scores,
        diagnostics={
            "length_norm": length_norm,
            "reduction_tolerance": reduction_tolerance,
            **admission_parameters,
            "cell_preparation": "independent_canonical_gauss_reduction",
            "input_record_count": len(entries),
            "admitted_record_count": len(scores),
            "rejection_counts_nonexclusive": rejection_counts,
            "candidate_universe": "caller_supplied_common_admitted_population",
            "native_parity": False,
            "score_order": (
                "aggregate_absolute_length_mismatch",
                "maximum_absolute_length_mismatch",
                "absolute_angle_mismatch_radians",
                "mean_cell_area",
            ),
        },
    )


def select_intermatch_style(
    records: Sequence[LedgerEntry | Mapping[str, Any]],
    *,
    elastic_energy_by_id: Mapping[str, float] | None = None,
    max_abs_deformation: float = 0.10,
    strained_side: Literal["A", "B"] = "A",
) -> SelectionOutcome:
    """Apply an InterMatch-inspired atom-count/elastic-energy selector.

    ``strained_side`` selects A-to-B or B-to-A principal stretch changes for
    the deformation gate. Comparable nonnegative elastic energies are
    mandatory for strain-eligible records. When they are absent, the adapter
    returns ``not_applicable`` rather than substituting a geometric score and
    mislabelling it as an InterMatch comparison.
    """

    if not math.isfinite(max_abs_deformation) or max_abs_deformation < 0.0:
        raise ValueError("max_abs_deformation must be finite and nonnegative")
    if strained_side not in {"A", "B"}:
        raise ValueError("strained_side must be 'A' or 'B'")

    strain_sign = 1.0 if strained_side == "A" else -1.0

    def maximum_stretch_change(entry: LedgerEntry) -> float:
        return max(
            abs(math.expm1(strain_sign * value))
            for value in entry.principal_log_strains or ()
        )

    entries = tuple(_entry(record) for record in records)
    if not entries:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermatch_style"],
            status="not_applicable",
            reason="no_records",
            diagnostics={
                "max_abs_deformation": max_abs_deformation,
                "strained_side": strained_side,
            },
        )
    _require_unique_record_ids(entries)

    missing_fields = tuple(
        entry.record_id
        for entry in entries
        if entry.source_atom_count is None or entry.principal_log_strains is None
    )
    if missing_fields:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermatch_style"],
            status="not_applicable",
            reason="source_atom_count_and_principal_log_strains_required",
            diagnostics={
                "missing_record_ids": missing_fields,
                "max_abs_deformation": max_abs_deformation,
                "strained_side": strained_side,
            },
        )

    eligible = tuple(
        entry
        for entry in entries
        if maximum_stretch_change(entry) <= max_abs_deformation
    )
    if not eligible:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermatch_style"],
            status="not_applicable",
            reason="no_record_within_strain_ceiling",
            diagnostics={
                "max_abs_deformation": max_abs_deformation,
                "strained_side": strained_side,
            },
        )

    supplied = (
        {}
        if elastic_energy_by_id is None
        else {
            str(identifier): value
            for identifier, value in elastic_energy_by_id.items()
        }
    )
    energies: dict[str, float] = {}
    missing: list[str] = []
    for entry in eligible:
        value = supplied.get(entry.record_id, entry.elastic_energy)
        if value is None:
            missing.append(entry.record_id)
            continue
        energy = _optional_finite(
            value,
            name=f"elastic_energy[{entry.record_id!r}]",
        )
        assert energy is not None
        if energy < 0.0:
            raise ValueError("elastic energies must be nonnegative")
        energies[entry.record_id] = energy
    if missing:
        return SelectionOutcome(
            metadata=METHOD_METADATA["intermatch_style"],
            status="not_applicable",
            reason="comparable_elastic_energy_required_for_every_eligible_record",
            diagnostics={
                "missing_record_ids": tuple(missing),
                "max_abs_deformation": max_abs_deformation,
                "strained_side": strained_side,
                "strain_eligible_record_count": len(eligible),
            },
        )

    scores = {
        entry.record_id: (
            float(entry.source_atom_count),
            energies[entry.record_id],
            maximum_stretch_change(entry),
        )
        for entry in eligible
    }
    best_score = min(scores.values())
    selected = tuple(
        sorted(
            identifier
            for identifier, score in scores.items()
            if score == best_score
        )
    )
    return SelectionOutcome(
        metadata=METHOD_METADATA["intermatch_style"],
        status="selected",
        selected_record_ids=selected,
        score_by_record_id=scores,
        diagnostics={
            "max_abs_deformation": max_abs_deformation,
            "strained_side": strained_side,
            "eligible_record_count": len(eligible),
            "score_order": (
                "source_atom_count",
                "elastic_energy",
                "maximum_absolute_principal_stretch_change",
            ),
            "energy_semantics": "caller_supplied_comparable_elastic_energy",
            "deformation_semantics": (
                "max_i abs(exp(epsilon_i)-1) for A_to_B"
                if strained_side == "A"
                else "max_i abs(exp(-epsilon_i)-1) for B_to_A"
            ),
        },
    )


def evaluate_record_adapters(
    record: LedgerEntry | Mapping[str, Any],
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    policy: PairIdentityPolicy2D | None = None,
    jelver_tolerance: float = 1.0e-12,
    descriptor_reduction_tolerance: float = 1.0e-12,
    descriptor_signature_scale: float = 1.0e10,
) -> Mapping[str, AdapterOutcome]:
    """Evaluate every record-level classifier/filter with one shared input."""

    item = _entry(record)
    return {
        "zur_mcgill_descriptor": zur_mcgill_descriptor_key(
            item,
            reduction_tolerance=descriptor_reduction_tolerance,
            signature_scale=descriptor_signature_scale,
        ),
        "calm": calm_stage_keys(
            item,
            point_group_A=point_group_A,
            point_group_B=point_group_B,
            policy=policy,
        ),
        "interoptimus_direction_signature": interoptimus_direction_signature(
            item,
            point_group_A=point_group_A,
            point_group_B=point_group_B,
        ),
        "ogre_style": ogre_style_key(
            item,
            point_group_A=point_group_A,
            point_group_B=point_group_B,
        ),
        "jelver_style": jelver_style_filter(
            item,
            point_group_A=point_group_A,
            point_group_B=point_group_B,
            tolerance=jelver_tolerance,
        ),
    }


__all__ = [
    "AdapterOutcome",
    "ClusteringOutcome",
    "LedgerEntry",
    "METHOD_METADATA",
    "MethodMetadata",
    "SelectionOutcome",
    "calm_stage_keys",
    "cluster_interoptimus_style",
    "evaluate_record_adapters",
    "interoptimus_direction_signature",
    "jelver_style_filter",
    "ogre_style_key",
    "select_intermat_paper_style",
    "select_intermat_source",
    "select_intermatch_style",
    "zur_mcgill_descriptor_key",
]
