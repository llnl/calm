"""calm.interface.model

Data models for the v2 interface pipeline.

Separation of concerns
----------------------
- `InterfacePrototype` is a *recipe* (no atomistic interface is built).
- `Interface` is the atomistic structure produced in the build stage.

The underlying lattice-match enumeration still leverages the existing
`calm.interface.types` and `calm.interface.matching.search` pipeline; v2 wraps
those internals into stable, serializable objects.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any, Literal, Mapping

if TYPE_CHECKING:
    try:
        from ase import Atoms  # type: ignore
    except ImportError:  # pragma: no cover - type-only

        class Atoms:  # type: ignore
            pass

    # Forward type imports for typing-only names to avoid runtime import cost
    from calm.interface.config import InterfaceBuildConfig  # type: ignore
    from calm.interface.results import StrainState  # type: ignore

import numpy as np

from calm.interface.matching.zur_mcgill import zur_mcgill_diagnostic_metadata
from calm.math2d.paired_lattice import determinantal_divisor_rank2

try:  # keep this module importable in lightweight/no-ASE environments
    from calm.slab.slab import Slab
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard

    class Slab:  # type: ignore[no-redef]
        pass


def _strict_positive_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _strict_boolean(name: str, value: object) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a boolean")
    return bool(value)


def _finite_nonnegative_real(name: str, value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite nonnegative real")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be a finite nonnegative real")
    return result


def _exact_integer_matrix_2d(name: str, value: object) -> np.ndarray:
    raw = np.asarray(value)
    if raw.shape != (2, 2):
        raise ValueError(f"{name} must be a 2x2 matrix")
    if np.issubdtype(raw.dtype, np.bool_):
        raise TypeError(f"{name} must contain exact integers, not booleans")
    if np.issubdtype(raw.dtype, np.integer):
        matrix = np.asarray(raw, dtype=np.int64)
    elif raw.dtype == object and all(
        isinstance(item, Integral) and not isinstance(item, (bool, np.bool_))
        for item in raw.ravel()
    ):
        matrix = np.asarray(raw, dtype=np.int64)
    else:
        raise TypeError(f"{name} must contain exact integers")
    return matrix


def _finite_matrix_2d(name: str, value: object) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must be a 2x2 matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


def _determinant_2d(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(matrix[1, 0])


def _validate_physical_recipe_handedness(
    name: str,
    slab: Any,
    recipe: "SupercellRecipe2D",
) -> None:
    """Validate ``R_sup @ B_parent @ N_tot`` when slab atoms are available."""

    atoms = getattr(slab, "atoms", None)
    if atoms is None:
        return
    cell = getattr(atoms, "cell", None)
    rows = getattr(cell, "array", None)
    if rows is None:
        return
    rows = np.asarray(rows, dtype=float)
    if rows.shape != (3, 3) or not np.all(np.isfinite(rows)):
        raise ValueError(f"{name} parent slab cell must be a finite 3x3 matrix")
    parent_basis = rows[:2, :2].T
    physical_basis = recipe.R_sup @ parent_basis @ recipe.N_tot
    scale = float(np.max(np.abs(physical_basis)))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError(f"{name} physical in-plane basis must be nonsingular")
    determinant = float(np.linalg.det(physical_basis / scale))
    if not math.isfinite(determinant) or determinant <= 1.0e-14:
        raise ValueError(
            f"{name} recipe must produce a right-handed physical in-plane basis"
        )


def _matrix_payload(matrix: np.ndarray) -> list[list[int]]:
    return [[int(value) for value in row] for row in np.asarray(matrix)]


def _exact_integer_tuple(
    name: str,
    values: object,
    *,
    length: int,
    positive: bool = False,
) -> tuple[int, ...]:
    try:
        entries = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer sequence") from exc
    if len(entries) != length:
        raise ValueError(f"{name} must contain {length} integers")
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
        for value in entries
    ):
        raise TypeError(f"{name} must contain exact integers")
    result = tuple(int(value) for value in entries)
    if positive and any(value <= 0 for value in result):
        raise ValueError(f"{name} must contain positive integers")
    return result


@dataclass(frozen=True)
class SupercellRecipe2D:
    """One build-ready two-dimensional slab supercell recipe.

    ``N_tot`` is the integer map used for atomistic construction. Coupled
    prototypes store primitive maps on both sides and use the same abstract
    interface-cell coordinates. ``R_sup`` is a Cartesian gauge; proper
    rotations are the default, while an improper gauge requires an explicit
    ``gauge_orientation="reflection_allowed"`` declaration.
    """

    k: int
    N_tot: np.ndarray
    R_sup: np.ndarray
    hnf_key_pg: tuple[int, int, int, int]
    cond: float
    S_red: np.ndarray | None = None
    G_red: np.ndarray | None = None
    gauge_orientation: Literal["proper", "reflection_allowed"] = "proper"

    def __post_init__(self) -> None:
        k = _strict_positive_integer("SupercellRecipe2D.k", self.k)
        integer_map = _exact_integer_matrix_2d("SupercellRecipe2D.N_tot", self.N_tot)
        determinant = _determinant_2d(integer_map)
        if determinant == 0:
            raise ValueError("SupercellRecipe2D.N_tot must be full rank")
        if abs(determinant) != k:
            raise ValueError("SupercellRecipe2D.k must equal abs(det(N_tot))")

        rotation = _finite_matrix_2d("SupercellRecipe2D.R_sup", self.R_sup)
        tolerance = 1.0e-10
        if not np.allclose(
            rotation.T @ rotation, np.eye(2), atol=tolerance, rtol=tolerance
        ):
            raise ValueError("SupercellRecipe2D.R_sup must be orthogonal")
        rotation_determinant = float(np.linalg.det(rotation))
        if not np.isclose(
            abs(rotation_determinant), 1.0, atol=tolerance, rtol=tolerance
        ):
            raise ValueError("SupercellRecipe2D.R_sup must have determinant +1 or -1")
        if self.gauge_orientation not in {"proper", "reflection_allowed"}:
            raise ValueError(
                "SupercellRecipe2D.gauge_orientation must be 'proper' or "
                "'reflection_allowed'"
            )
        if self.gauge_orientation == "proper" and rotation_determinant < 0.0:
            raise ValueError(
                "A proper SupercellRecipe2D gauge cannot contain a reflection"
            )
        key = _exact_integer_tuple(
            "SupercellRecipe2D.hnf_key_pg",
            self.hnf_key_pg,
            length=4,
        )
        condition = _finite_nonnegative_real("SupercellRecipe2D.cond", self.cond)
        reduced_basis = None
        if self.S_red is not None:
            reduced_basis = _finite_matrix_2d("SupercellRecipe2D.S_red", self.S_red)
        reduced_gram = None
        if self.G_red is not None:
            reduced_gram = _finite_matrix_2d("SupercellRecipe2D.G_red", self.G_red)

        object.__setattr__(self, "k", k)
        object.__setattr__(self, "N_tot", integer_map)
        object.__setattr__(self, "R_sup", rotation)
        object.__setattr__(self, "hnf_key_pg", key)
        object.__setattr__(self, "cond", condition)
        object.__setattr__(self, "S_red", reduced_basis)
        object.__setattr__(self, "G_red", reduced_gram)

    def to_dict(self) -> dict[str, Any]:
        """Return the sole supported persisted supercell representation."""

        return {
            "k": int(self.k),
            "N_tot": _matrix_payload(self.N_tot),
            "R_sup": np.asarray(self.R_sup, dtype=float).tolist(),
            "hnf_key_pg": list(self.hnf_key_pg),
            "cond": float(self.cond),
            "S_red": (
                None
                if self.S_red is None
                else np.asarray(self.S_red, dtype=float).tolist()
            ),
            "G_red": (
                None
                if self.G_red is None
                else np.asarray(self.G_red, dtype=float).tolist()
            ),
            "gauge_orientation": self.gauge_orientation,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SupercellRecipe2D":
        """Rehydrate one current coupled supercell recipe."""

        if not isinstance(payload, Mapping):
            raise TypeError("SupercellRecipe2D payload must be a mapping")
        required = ("k", "N_tot", "R_sup", "hnf_key_pg", "cond")
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError(
                "SupercellRecipe2D payload is missing fields: " + ", ".join(missing)
            )
        return cls(
            k=payload["k"],
            N_tot=payload["N_tot"],
            R_sup=payload["R_sup"],
            hnf_key_pg=payload["hnf_key_pg"],
            cond=payload["cond"],
            S_red=payload.get("S_red"),
            G_red=payload.get("G_red"),
            gauge_orientation=payload.get("gauge_orientation", "proper"),
        )


@dataclass(frozen=True)
class PairIdentity2D:
    """Versioned exact identity of one primitive coupled lattice pair."""

    key_version: int
    primitive_pair_key: tuple[int, ...]
    pair_symmetry_policy: Literal["proper", "full"]
    correspondence_orientation: Literal["proper", "all"]
    material_exchange_identified: bool

    def __post_init__(self) -> None:
        version = _strict_positive_integer(
            "PairIdentity2D.key_version", self.key_version
        )
        key = _exact_integer_tuple(
            "PairIdentity2D.primitive_pair_key",
            self.primitive_pair_key,
            length=8,
        )
        if self.pair_symmetry_policy not in {"proper", "full"}:
            raise ValueError(
                "PairIdentity2D.pair_symmetry_policy must be 'proper' or 'full'"
            )
        if self.correspondence_orientation not in {"proper", "all"}:
            raise ValueError(
                "PairIdentity2D.correspondence_orientation must be 'proper' or 'all'"
            )
        exchange = _strict_boolean(
            "PairIdentity2D.material_exchange_identified",
            self.material_exchange_identified,
        )
        object.__setattr__(self, "key_version", version)
        object.__setattr__(self, "primitive_pair_key", key)
        object.__setattr__(self, "material_exchange_identified", exchange)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_version": int(self.key_version),
            "primitive_pair_key": list(self.primitive_pair_key),
            "pair_symmetry_policy": self.pair_symmetry_policy,
            "correspondence_orientation": self.correspondence_orientation,
            "material_exchange_identified": bool(self.material_exchange_identified),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PairIdentity2D":
        """Rehydrate one exact pair identity from a persisted mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("PairIdentity2D payload must be a mapping")
        return cls(
            key_version=payload.get("key_version"),
            primitive_pair_key=payload.get("primitive_pair_key"),
            pair_symmetry_policy=payload.get("pair_symmetry_policy"),
            correspondence_orientation=payload.get("correspondence_orientation"),
            material_exchange_identified=payload.get("material_exchange_identified"),
        )


@dataclass(frozen=True)
class MatchSourceProvenance2D:
    """Bounded source-state provenance for a primitive match class."""

    source_count: int
    minimum_source_indices: tuple[int, int]
    source_index_pairs: tuple[tuple[int, int], ...]
    repeat_indices: tuple[int, ...]
    representative_source_H_A: np.ndarray
    representative_source_H_B: np.ndarray
    representative_source_N_A: np.ndarray
    representative_source_N_B: np.ndarray
    representative_correspondence_U_B: np.ndarray
    representative_source_pair_matrix: np.ndarray
    representative_source_right_factor: np.ndarray

    def __post_init__(self) -> None:
        source_count = _strict_positive_integer(
            "MatchSourceProvenance2D.source_count", self.source_count
        )
        minimum_values = _exact_integer_tuple(
            "MatchSourceProvenance2D.minimum_source_indices",
            self.minimum_source_indices,
            length=2,
            positive=True,
        )
        minimum = (minimum_values[0], minimum_values[1])
        pairs = tuple(
            sorted(
                {
                    tuple(
                        _exact_integer_tuple(
                            "MatchSourceProvenance2D.source_index_pairs entry",
                            pair,
                            length=2,
                            positive=True,
                        )
                    )
                    for pair in self.source_index_pairs
                }
            )
        )
        if not pairs:
            raise ValueError(
                "MatchSourceProvenance2D.source_index_pairs cannot be empty"
            )
        if minimum not in pairs:
            raise ValueError(
                "minimum_source_indices must be included in source_index_pairs"
            )
        if source_count < len(pairs):
            raise ValueError(
                "source_count cannot be smaller than the recorded source pairs"
            )
        repeats = tuple(
            sorted(
                {
                    _exact_integer_tuple(
                        "MatchSourceProvenance2D.repeat_indices entry",
                        (value,),
                        length=1,
                        positive=True,
                    )[0]
                    for value in self.repeat_indices
                }
            )
        )
        if not repeats:
            raise ValueError("repeat_indices cannot be empty")

        source_h_a = _exact_integer_matrix_2d(
            "representative_source_H_A", self.representative_source_H_A
        )
        source_h_b = _exact_integer_matrix_2d(
            "representative_source_H_B", self.representative_source_H_B
        )
        expected_minimum = min(pairs, key=lambda pair: (max(pair), pair))
        if minimum != expected_minimum:
            raise ValueError(
                "minimum_source_indices must be the deterministic minimum "
                "recorded source pair"
            )
        representative_pair = (
            abs(_determinant_2d(source_h_a)),
            abs(_determinant_2d(source_h_b)),
        )
        if representative_pair not in pairs:
            raise ValueError("The representative source HNF indices must be recorded")
        source_n_a = _exact_integer_matrix_2d(
            "representative_source_N_A", self.representative_source_N_A
        )
        source_n_b = _exact_integer_matrix_2d(
            "representative_source_N_B", self.representative_source_N_B
        )
        correspondence = _exact_integer_matrix_2d(
            "representative_correspondence_U_B",
            self.representative_correspondence_U_B,
        )
        if abs(_determinant_2d(correspondence)) != 1:
            raise ValueError("representative_correspondence_U_B must be unimodular")
        source_pair = np.asarray(self.representative_source_pair_matrix)
        if source_pair.shape != (4, 2):
            raise ValueError("representative_source_pair_matrix must have shape (4, 2)")
        if not np.issubdtype(source_pair.dtype, np.integer):
            raise TypeError(
                "representative_source_pair_matrix must contain exact integers"
            )
        source_pair = np.asarray(source_pair, dtype=np.int64)
        expected_pair = np.vstack([source_n_a, source_n_b @ correspondence])
        if not np.array_equal(source_pair, expected_pair):
            raise ValueError(
                "representative_source_pair_matrix is inconsistent with the "
                "source maps and correspondence"
            )
        right_factor = _exact_integer_matrix_2d(
            "representative_source_right_factor",
            self.representative_source_right_factor,
        )
        representative_repeat = abs(_determinant_2d(right_factor))
        if representative_repeat not in repeats:
            raise ValueError("The representative source repeat index must be recorded")

        object.__setattr__(self, "source_count", source_count)
        object.__setattr__(self, "minimum_source_indices", minimum)
        object.__setattr__(self, "source_index_pairs", pairs)
        object.__setattr__(self, "repeat_indices", repeats)
        object.__setattr__(self, "representative_source_H_A", source_h_a)
        object.__setattr__(self, "representative_source_H_B", source_h_b)
        object.__setattr__(self, "representative_source_N_A", source_n_a)
        object.__setattr__(self, "representative_source_N_B", source_n_b)
        object.__setattr__(self, "representative_correspondence_U_B", correspondence)
        object.__setattr__(self, "representative_source_pair_matrix", source_pair)
        object.__setattr__(self, "representative_source_right_factor", right_factor)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_count": int(self.source_count),
            "minimum_source_indices": list(self.minimum_source_indices),
            "source_index_pairs": [list(pair) for pair in self.source_index_pairs],
            "repeat_indices": list(self.repeat_indices),
            "representative_source_H_A": _matrix_payload(
                self.representative_source_H_A
            ),
            "representative_source_H_B": _matrix_payload(
                self.representative_source_H_B
            ),
            "representative_source_N_A": _matrix_payload(
                self.representative_source_N_A
            ),
            "representative_source_N_B": _matrix_payload(
                self.representative_source_N_B
            ),
            "representative_correspondence_U_B": _matrix_payload(
                self.representative_correspondence_U_B
            ),
            "representative_source_pair_matrix": [
                [int(value) for value in row]
                for row in self.representative_source_pair_matrix
            ],
            "representative_source_right_factor": _matrix_payload(
                self.representative_source_right_factor
            ),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MatchSourceProvenance2D":
        """Rehydrate bounded source provenance from a persisted mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("MatchSourceProvenance2D payload must be a mapping")
        return cls(
            source_count=payload.get("source_count"),
            minimum_source_indices=payload.get("minimum_source_indices"),
            source_index_pairs=payload.get("source_index_pairs"),
            repeat_indices=payload.get("repeat_indices"),
            representative_source_H_A=payload.get("representative_source_H_A"),
            representative_source_H_B=payload.get("representative_source_H_B"),
            representative_source_N_A=payload.get("representative_source_N_A"),
            representative_source_N_B=payload.get("representative_source_N_B"),
            representative_correspondence_U_B=payload.get(
                "representative_correspondence_U_B"
            ),
            representative_source_pair_matrix=payload.get(
                "representative_source_pair_matrix"
            ),
            representative_source_right_factor=payload.get(
                "representative_source_right_factor"
            ),
        )


@dataclass(frozen=True)
class InterfacePrototype:
    """A lattice-matched interface recipe without atomistic construction."""

    prototype_uid: str

    slab_a_uid: str
    slab_b_uid: str

    miller_a: tuple[int, int, int]
    miller_b: tuple[int, int, int]

    supercell_a: SupercellRecipe2D
    supercell_b: SupercellRecipe2D

    # Ranking metrics recomputed from the primitive coupled relation.
    match_score: float
    d_size: float
    d_cell: float
    d_area: float
    d_shape: float
    rel_da: float
    rel_db: float
    d_gamma_deg: float

    # Convenience (not part of identity)
    n_atoms_interface: int
    slab_a: Slab = field(repr=False, compare=False)
    slab_b: Slab = field(repr=False, compare=False)

    # Exact primitive coupled-pair identity and bounded source provenance.
    pair_identity: PairIdentity2D
    source_provenance: MatchSourceProvenance2D

    # Authoritative full-population Pareto provenance. These fields do not
    # participate in crystallographic identity.
    is_pareto: bool = False
    pareto_rank: int | None = None
    pareto_policy: str | None = None
    pareto_policy_version: int | None = None
    pareto_population_scope: str | None = None
    pareto_population_size: int = 0
    pareto_d_cell_key: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.prototype_uid, str) or not self.prototype_uid:
            raise ValueError("InterfacePrototype.prototype_uid must be non-empty")
        if not isinstance(self.pair_identity, PairIdentity2D):
            raise TypeError("InterfacePrototype.pair_identity must be a PairIdentity2D")
        if not isinstance(self.source_provenance, MatchSourceProvenance2D):
            raise TypeError(
                "InterfacePrototype.source_provenance must be a MatchSourceProvenance2D"
            )

        _validate_physical_recipe_handedness(
            "Coupled-v2 side-A", self.slab_a, self.supercell_a
        )
        _validate_physical_recipe_handedness(
            "Coupled-v2 side-B", self.slab_b, self.supercell_b
        )

        primitive_build_pair = np.vstack(
            [self.supercell_a.N_tot, self.supercell_b.N_tot]
        )
        if determinantal_divisor_rank2(primitive_build_pair) != 1:
            raise ValueError(
                "Coupled-v2 prototype supercell maps must form a primitive pair"
            )
        provenance = self.source_provenance
        if not np.array_equal(
            primitive_build_pair @ provenance.representative_source_right_factor,
            provenance.representative_source_pair_matrix,
        ):
            raise ValueError(
                "Coupled-v2 source provenance must reconstruct from the "
                "primitive build pair"
            )

    # ---------------------------------------------------------------------
    # Stable public facade properties
    # ---------------------------------------------------------------------

    @property
    def hnf_key_a(self) -> tuple[int, int, int, int]:
        """Canonical 2×2 HNF key (point-group reduced) for slab A."""

        return self.supercell_a.hnf_key_pg

    @property
    def hnf_key_b(self) -> tuple[int, int, int, int]:
        """Canonical 2×2 HNF key (point-group reduced) for slab B."""

        return self.supercell_b.hnf_key_pg

    @property
    def identity_algorithm(self) -> str:
        """Return the sole supported scientific identity algorithm."""

        return "primitive_coupled_pair_v2"

    def to_dict(
        self,
        *,
        rank: int | None = None,
        include_fingerprints: bool = False,
        fingerprint_ndigits: int = 10,
    ) -> dict[str, Any]:
        """Return a JSON-serializable summary of the prototype.

        This method is intended as a stable façade for example scripts and
        downstream tools that want a consistent field naming scheme.

        Parameters
        ----------
        rank
            Optional rank to include in the output.
        include_fingerprints
            When True, include deterministic signature/fingerprint payloads.
            These are intended **only** for evidence/regression and should not
            be used for algorithmic pruning/ranking.
        fingerprint_ndigits
            Number of decimals used when rounding floating-point values in the
            included signature/fingerprint payloads.

        Returns
        -------
        dict
            JSON-serializable dictionary containing key metrics and identifiers.
        """

        out: dict[str, Any] = {
            "prototype_uid": self.prototype_uid,
            "identity_algorithm": self.identity_algorithm,
            "score": float(self.match_score),
            "d_cell": float(self.d_cell),
            "d_area": float(self.d_area),
            "d_shape": float(self.d_shape),
            "d_size": float(self.d_size),
            "rel_da": float(self.rel_da),
            "rel_db": float(self.rel_db),
            "d_gamma_deg": float(self.d_gamma_deg),
            "zur_mcgill_diagnostic": {
                **zur_mcgill_diagnostic_metadata(),
                "rel_da": float(self.rel_da),
                "rel_db": float(self.rel_db),
                "d_gamma_deg": float(self.d_gamma_deg),
            },
            "n_atoms_interface": int(self.n_atoms_interface),
            "is_pareto": bool(self.is_pareto),
            "pareto_rank": self.pareto_rank,
            "pareto_policy": self.pareto_policy,
            "pareto_policy_version": (
                None
                if self.pareto_policy_version is None
                else int(self.pareto_policy_version)
            ),
            "pareto_population_scope": self.pareto_population_scope,
            "pareto_population_size": int(self.pareto_population_size),
            "pareto_d_cell_key": self.pareto_d_cell_key,
            "hnf_key_a": list(map(int, self.hnf_key_a)),
            "hnf_key_b": list(map(int, self.hnf_key_b)),
            # `SupercellRecipe2D.k` is an integer (k-max / search bound).
            # Older experimental code represented this as a 2-tuple; we
            # intentionally serialize as an int for a stable JSON schema.
            "k_a": int(self.supercell_a.k),
            "k_b": int(self.supercell_b.k),
            "miller_a": list(map(int, self.miller_a)),
            "miller_b": list(map(int, self.miller_b)),
        }
        out["pair_identity"] = self.pair_identity.to_dict()
        out["source_provenance"] = self.source_provenance.to_dict()
        if rank is not None:
            out["rank"] = int(rank)

        if include_fingerprints:
            # NOTE: These are optional evidence payloads. They are not used by
            # any matching/ranking code-paths.
            nd = int(fingerprint_ndigits)
            out["signature"] = self.signature(ndigits=nd)
            # `fingerprint()` returns a JSON payload (for evidence ledgers).
            # `fingerprint_hash()` returns a compact deterministic SHA256.
            out["fingerprint"] = self.fingerprint_hash(ndigits=nd)
        return out

    def signature(self, *, ndigits: int = 10) -> str:
        """Deterministic signature for evidence/regression.

        The signature is a SHA256 hash of a rounded, JSON-serialized payload
        derived from the prototype's stable façade fields.

        Notes
        -----
        This is **not** a mathematical invariant; it is a regression aid.
        """
        nd = int(ndigits)

        payload: dict[str, Any] = {
            "prototype_uid": self.prototype_uid,
            "hnf_key_a": list(map(int, self.hnf_key_a)),
            "hnf_key_b": list(map(int, self.hnf_key_b)),
            "miller_a": list(map(int, self.miller_a)),
            "miller_b": list(map(int, self.miller_b)),
            "k_a": int(self.supercell_a.k),
            "k_b": int(self.supercell_b.k),
            "score": round(float(self.match_score), nd),
            "d_cell": round(float(self.d_cell), nd),
            "d_area": round(float(self.d_area), nd),
            "d_shape": round(float(self.d_shape), nd),
            "d_size": round(float(self.d_size), nd),
            "rel_da": round(float(self.rel_da), nd),
            "rel_db": round(float(self.rel_db), nd),
            "d_gamma_deg": round(float(self.d_gamma_deg), nd),
            "n_atoms_interface": int(self.n_atoms_interface),
        }
        payload["pair_identity"] = self.pair_identity.to_dict()

        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(blob).hexdigest()

    def fingerprint(
        self, *, ndigits: int = 10, rank: int | None = None
    ) -> dict[str, Any]:
        """Return a JSON-serializable *fingerprint payload* for evidence.

        This method intentionally returns a **payload** (not a hash), because
        some evidence scripts want to embed the payload directly.

        Notes
        -----
        - `rank` is included *only* in this payload for evidence tables.
        - Hash-based regression fingerprints should use :meth:`fingerprint_hash`,
          which intentionally ignores `rank`.
        """
        nd = int(ndigits)
        payload: dict[str, Any] = {
            "prototype_uid": str(self.prototype_uid),
            "hnf_key_a": list(map(int, self.hnf_key_a)),
            "hnf_key_b": list(map(int, self.hnf_key_b)),
            "k_a": int(self.supercell_a.k),
            "k_b": int(self.supercell_b.k),
            "miller_a": list(map(int, self.miller_a)),
            "miller_b": list(map(int, self.miller_b)),
            "score": round(float(self.match_score), nd),
            "d_cell": round(float(self.d_cell), nd),
            "d_area": round(float(self.d_area), nd),
            "d_shape": round(float(self.d_shape), nd),
            "d_size": round(float(self.d_size), nd),
            "rel_da": round(float(self.rel_da), nd),
            "rel_db": round(float(self.rel_db), nd),
            "d_gamma_deg": round(float(self.d_gamma_deg), nd),
            "n_atoms_interface": int(self.n_atoms_interface),
        }
        payload["pair_identity"] = self.pair_identity.to_dict()
        if rank is not None:
            payload["rank"] = int(rank)
        return payload

    def fingerprint_hash(self, *, ndigits: int = 10) -> str:
        """Deterministic SHA256 of :meth:`fingerprint` (rank-invariant)."""
        payload = self.fingerprint(ndigits=int(ndigits), rank=None)
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(blob).hexdigest()


@dataclass
class Interface:
    """An atomistic interface model built from a prototype.

    Notes
    -----
    This is part of CALM's **public API** and is intentionally tolerant of
    partially-populated instances. In particular:

    * Workflow wrappers and tests may construct lightweight/dummy ``Interface``
      objects that only carry ``atoms`` and a small amount of metadata.
    * Fully-built interfaces produced by :func:`calm.interface.pipeline.build_interface`
      populate ``prototype``, ``strain_state``, and (optionally) ``build_config``.

    The additional ``slab_*`` identifiers and Miller indices are provided for
    convenience and backwards compatibility.
    """

    # Core identifiers
    build_uid: str
    prototype_uid: str

    # Primary payload
    atoms: Atoms

    # Optional, but commonly useful metadata (public API)
    slab_a_uid: str | None = None
    slab_b_uid: str | None = None
    miller_a: tuple[int, int, int] | None = None
    miller_b: tuple[int, int, int] | None = None

    # Optional workflow / provenance
    strained_uid: str | None = None
    strain_state: StrainState | None = None
    build_config: InterfaceBuildConfig | None = None
    prototype: InterfacePrototype | None = None

    # Optional derived / internal fields
    lower_indices: np.ndarray | None = None
    upper_indices: np.ndarray | None = None
    slab_a: Slab | None = None
    slab_b: Slab | None = None

    def __post_init__(self) -> None:
        # Populate convenience fields from the attached prototype (if present).
        proto = self.prototype
        if proto is None:
            return

        if self.slab_a_uid is None:
            self.slab_a_uid = getattr(proto, "slab_a_uid", None)
        if self.slab_b_uid is None:
            self.slab_b_uid = getattr(proto, "slab_b_uid", None)
        if self.miller_a is None:
            self.miller_a = getattr(proto, "miller_a", None)
        if self.miller_b is None:
            self.miller_b = getattr(proto, "miller_b", None)

    @property
    def uid(self) -> str:
        return self.build_uid

    def area(self) -> float:
        """Return the in-plane interface area in Å²."""

        if self.atoms is None:
            raise ValueError("Interface.atoms is None; cannot compute area")

        cell = self.atoms.cell.array
        a1 = cell[0, :]
        a2 = cell[1, :]
        return float(np.linalg.norm(np.cross(a1, a2)))

    @property
    def area_A2(self) -> float:
        return self.area()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict.

        This method is intentionally robust to partially-populated instances.
        """

        out: dict[str, Any] = {
            "uid": self.uid,
            "prototype_uid": self.prototype_uid,
            "build_uid": self.build_uid,
        }

        if self.slab_a_uid is not None:
            out["slab_a_uid"] = self.slab_a_uid
        if self.slab_b_uid is not None:
            out["slab_b_uid"] = self.slab_b_uid
        if self.miller_a is not None:
            out["miller_a"] = self.miller_a
        if self.miller_b is not None:
            out["miller_b"] = self.miller_b

        if self.strained_uid is not None:
            out["strained_uid"] = self.strained_uid

        if self.strain_state is not None:
            out["strain_state"] = self.strain_state.to_dict()
        if self.build_config is not None:
            out["build_config"] = self.build_config.to_dict()
        if self.prototype is not None:
            out["prototype"] = self.prototype.to_dict()

        return out
