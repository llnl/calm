"""Enumeration accounting for primitive coupled-pair interface searches.

:class:`CoupledMatchEnumerationAudit` is the sole production audit model. It
distinguishes one-sided comparison reduction from intentional member and
correspondence expansion and final exact primitive-pair aggregation.

All per-index arrays use 1-based HNF indexing: entry ``i`` corresponds to
``k = i + 1``. Pair counters are assigned to ``max(k_A, k_B)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any

from calm.symmetry.surface_group import SurfaceSymmetryProvenance


def _cumsum(vals: list[int]) -> list[int]:
    """Simple cumulative sum without a numpy dependency."""
    out: list[int] = []
    total = 0
    for v in vals:
        total += int(v)
        out.append(total)
    return out


COUPLED_MATCH_AUDIT_SCHEMA_V1 = "calm.coupled_match_enumeration_audit/v1"
COUPLED_MATCH_AUDIT_SCHEMA_V2 = "calm.coupled_match_enumeration_audit/v2"
COUPLED_MATCH_AUDIT_SCHEMA = COUPLED_MATCH_AUDIT_SCHEMA_V2
COUPLED_MATCH_IMPLEMENTATION = "primitive_coupled_pair_v2"


def _validated_nonnegative_count(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a nonnegative integer")
    count = int(value)
    if count < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return count


@dataclass(frozen=True)
class CoupledSearchSpaceCounts:
    """Global HNF-pair populations through the configured preliminary filters."""

    raw_hnf_pairs: int
    searchable_hnf_pairs: int
    area_admissible_hnf_pairs: int
    atom_lower_bound_admissible_hnf_pairs: int
    orbit_prefilter_surviving_hnf_pairs: int

    @classmethod
    def zeros(cls) -> "CoupledSearchSpaceCounts":
        return cls(
            raw_hnf_pairs=0,
            searchable_hnf_pairs=0,
            area_admissible_hnf_pairs=0,
            atom_lower_bound_admissible_hnf_pairs=0,
            orbit_prefilter_surviving_hnf_pairs=0,
        )

    def validate(self) -> None:
        values = tuple(
            _validated_nonnegative_count(getattr(self, name), name=name)
            for name in (
                "raw_hnf_pairs",
                "searchable_hnf_pairs",
                "area_admissible_hnf_pairs",
                "atom_lower_bound_admissible_hnf_pairs",
                "orbit_prefilter_surviving_hnf_pairs",
            )
        )
        if any(left < right for left, right in zip(values, values[1:])):
            raise ValueError(
                "search-space counts must be nonincreasing after each bound"
            )

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return {
            "raw_hnf_pairs": int(self.raw_hnf_pairs),
            "searchable_hnf_pairs": int(self.searchable_hnf_pairs),
            "area_admissible_hnf_pairs": int(self.area_admissible_hnf_pairs),
            "atom_lower_bound_admissible_hnf_pairs": int(
                self.atom_lower_bound_admissible_hnf_pairs
            ),
            "orbit_prefilter_surviving_hnf_pairs": int(
                self.orbit_prefilter_surviving_hnf_pairs
            ),
        }


@dataclass(frozen=True)
class CoupledIdentityReductionCounts:
    """Global exact cardinalities through the coupled identity quotient."""

    admitted_descriptions: int
    unique_admitted_source_pairs: int
    unique_admitted_primitive_pairs: int
    unique_admitted_common_right_classes: int
    unique_final_pair_classes: int

    @classmethod
    def zeros(cls) -> "CoupledIdentityReductionCounts":
        return cls(
            admitted_descriptions=0,
            unique_admitted_source_pairs=0,
            unique_admitted_primitive_pairs=0,
            unique_admitted_common_right_classes=0,
            unique_final_pair_classes=0,
        )

    def validate(self) -> None:
        values = tuple(
            _validated_nonnegative_count(getattr(self, name), name=name)
            for name in (
                "admitted_descriptions",
                "unique_admitted_source_pairs",
                "unique_admitted_primitive_pairs",
                "unique_admitted_common_right_classes",
                "unique_final_pair_classes",
            )
        )
        if any(left < right for left, right in zip(values, values[1:])):
            raise ValueError(
                "identity-reduction counts must be nonincreasing through the "
                "coupled quotient"
            )

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return {
            "admitted_descriptions": int(self.admitted_descriptions),
            "unique_admitted_source_pairs": int(
                self.unique_admitted_source_pairs
            ),
            "unique_admitted_primitive_pairs": int(
                self.unique_admitted_primitive_pairs
            ),
            "unique_admitted_common_right_classes": int(
                self.unique_admitted_common_right_classes
            ),
            "unique_final_pair_classes": int(self.unique_final_pair_classes),
        }


def _validated_count_arrays(
    owner: object,
    *,
    k_max: int,
    names: tuple[str, ...],
) -> None:
    for name in names:
        values = getattr(owner, name)
        if len(values) != k_max:
            raise ValueError(
                f"{name} must have length k_max={k_max}, got {len(values)}"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0
            for value in values
        ):
            raise ValueError(f"{name} must contain nonnegative integers")


def _count_rows(
    owner: object,
    *,
    k_max: int,
    names: tuple[str, ...],
    cumulative: bool,
) -> list[dict[str, int]]:
    columns = {
        name: (
            _cumsum(getattr(owner, name))
            if cumulative
            else [int(value) for value in getattr(owner, name)]
        )
        for name in names
    }
    return [
        {
            "k": index + 1,
            **{name: columns[name][index] for name in names},
        }
        for index in range(k_max)
    ]


@dataclass
class CoupledSurfaceEnumerationCountsByK:
    """Surface-orbit accounting for coupled-v2 without discarding members."""

    k_max: int
    hnf_generated: list[int]
    reduction_failed: list[int]
    condition_rejected: list[int]
    admitted_members: list[int]
    comparison_orbits: list[int]

    _COUNT_NAMES = (
        "hnf_generated",
        "reduction_failed",
        "condition_rejected",
        "admitted_members",
        "comparison_orbits",
    )

    @classmethod
    def zeros(cls, k_max: int) -> "CoupledSurfaceEnumerationCountsByK":
        limit = int(k_max)
        if limit < 0:
            raise ValueError("k_max must be >= 0")
        return cls(
            k_max=limit,
            hnf_generated=[0] * limit,
            reduction_failed=[0] * limit,
            condition_rejected=[0] * limit,
            admitted_members=[0] * limit,
            comparison_orbits=[0] * limit,
        )

    def validate(self) -> None:
        _validated_count_arrays(
            self,
            k_max=self.k_max,
            names=self._COUNT_NAMES,
        )
        for index in range(self.k_max):
            if self.hnf_generated[index] != (
                self.reduction_failed[index]
                + self.condition_rejected[index]
                + self.admitted_members[index]
            ):
                raise ValueError(
                    "surface HNF accounting must partition every generated HNF"
                )
            if self.comparison_orbits[index] > self.admitted_members[index]:
                raise ValueError("comparison_orbits cannot exceed admitted_members")

    def rows(self, *, cumulative: bool = False) -> list[dict[str, int]]:
        self.validate()
        rows = _count_rows(
            self,
            k_max=self.k_max,
            names=self._COUNT_NAMES,
            cumulative=cumulative,
        )
        for row in rows:
            row["comparison_symmetry_reduction"] = (
                row["admitted_members"] - row["comparison_orbits"]
            )
        return rows

    def totals(self) -> dict[str, int]:
        rows = self.rows(cumulative=True)
        if not rows:
            names = (*self._COUNT_NAMES, "comparison_symmetry_reduction")
            return {name: 0 for name in names}
        return {name: int(value) for name, value in rows[-1].items() if name != "k"}


@dataclass
class CoupledPairEnumerationCountsByK:
    """Pair expansion, correspondence, and primitive aggregation accounting."""

    k_max: int
    area_bound_rejected: list[int]
    index_pairs_scheduled: list[int]
    atom_lower_bound_rejected: list[int]
    orbit_pairs_considered: list[int]
    orbit_prefilter_rejected: list[int]
    orbit_prefilter_inconclusive: list[int]
    orbit_prefilter_admitted: list[int]
    member_pairs_expanded: list[int]
    correspondence_domains: list[int]
    correspondence_column_pairs_tested: list[int]
    unimodular_correspondences_tested: list[int]
    strain_admissible_correspondences: list[int]
    correspondence_limit_failures: list[int]
    unique_source_pairs_primitiveized: list[int]
    nonprimitive_repetitions: list[int]
    primitiveization_cache_hits: list[int]
    primitive_atom_rejected: list[int]
    strict_strain_rejected: list[int]
    candidates_admitted: list[int]
    primitive_classes_created: list[int]
    sources_aggregated_by_pair_key: list[int]

    _COUNT_NAMES = (
        "area_bound_rejected",
        "index_pairs_scheduled",
        "atom_lower_bound_rejected",
        "orbit_pairs_considered",
        "orbit_prefilter_rejected",
        "orbit_prefilter_inconclusive",
        "orbit_prefilter_admitted",
        "member_pairs_expanded",
        "correspondence_domains",
        "correspondence_column_pairs_tested",
        "unimodular_correspondences_tested",
        "strain_admissible_correspondences",
        "correspondence_limit_failures",
        "unique_source_pairs_primitiveized",
        "nonprimitive_repetitions",
        "primitiveization_cache_hits",
        "primitive_atom_rejected",
        "strict_strain_rejected",
        "candidates_admitted",
        "primitive_classes_created",
        "sources_aggregated_by_pair_key",
    )

    @classmethod
    def zeros(cls, k_max: int) -> "CoupledPairEnumerationCountsByK":
        limit = int(k_max)
        if limit < 0:
            raise ValueError("k_max must be >= 0")
        values = {name: [0] * limit for name in cls._COUNT_NAMES}
        return cls(k_max=limit, **values)

    def increment(self, k: int, name: str, amount: int = 1) -> None:
        if name not in self._COUNT_NAMES:
            raise KeyError(f"unsupported coupled-pair audit counter: {name}")
        index = int(k) - 1
        if index < 0 or index >= self.k_max:
            raise ValueError(f"k must be in [1, {self.k_max}]")
        if isinstance(amount, bool) or not isinstance(amount, Integral):
            raise ValueError("audit increments must be nonnegative integers")
        value = int(amount)
        if value < 0:
            raise ValueError("audit increments must be nonnegative integers")
        getattr(self, name)[index] += value

    def validate(self) -> None:
        _validated_count_arrays(
            self,
            k_max=self.k_max,
            names=self._COUNT_NAMES,
        )
        for index in range(self.k_max):
            if self.orbit_pairs_considered[index] != (
                self.orbit_prefilter_rejected[index]
                + self.orbit_prefilter_inconclusive[index]
                + self.orbit_prefilter_admitted[index]
            ):
                raise ValueError("every orbit pair must have one prefilter disposition")
            if self.member_pairs_expanded[index] != self.correspondence_domains[index]:
                raise ValueError(
                    "every expanded member pair must construct one correspondence domain"
                )
            if self.strain_admissible_correspondences[index] != (
                self.unique_source_pairs_primitiveized[index]
                + self.primitiveization_cache_hits[index]
            ):
                raise ValueError(
                    "every admitted correspondence must reach primitiveization"
                )
            if self.strain_admissible_correspondences[index] != (
                self.primitive_atom_rejected[index]
                + self.strict_strain_rejected[index]
                + self.candidates_admitted[index]
            ):
                raise ValueError(
                    "every admitted correspondence must have one final disposition"
                )
            if self.candidates_admitted[index] != (
                self.primitive_classes_created[index]
                + self.sources_aggregated_by_pair_key[index]
            ):
                raise ValueError(
                    "every admitted candidate must create or join one primitive class"
                )

    def rows(self, *, cumulative: bool = False) -> list[dict[str, int]]:
        self.validate()
        return _count_rows(
            self,
            k_max=self.k_max,
            names=self._COUNT_NAMES,
            cumulative=cumulative,
        )

    def totals(self) -> dict[str, int]:
        rows = self.rows(cumulative=True)
        if not rows:
            return {name: 0 for name in self._COUNT_NAMES}
        return {name: int(value) for name, value in rows[-1].items() if name != "k"}


@dataclass
class CoupledMatchEnumerationAudit:
    """Versioned production accounting for the primitive coupled matcher."""

    k_max: int
    surface_A: CoupledSurfaceEnumerationCountsByK
    surface_B: CoupledSurfaceEnumerationCountsByK
    pairs: CoupledPairEnumerationCountsByK
    surface_symmetry_A: SurfaceSymmetryProvenance | None = None
    surface_symmetry_B: SurfaceSymmetryProvenance | None = None
    search_space: CoupledSearchSpaceCounts | None = None
    identity_reduction: CoupledIdentityReductionCounts | None = None
    schema: str = COUPLED_MATCH_AUDIT_SCHEMA
    implementation: str = COUPLED_MATCH_IMPLEMENTATION

    @classmethod
    def empty(cls, k_max: int) -> "CoupledMatchEnumerationAudit":
        limit = int(k_max)
        return cls(
            k_max=limit,
            surface_A=CoupledSurfaceEnumerationCountsByK.zeros(limit),
            surface_B=CoupledSurfaceEnumerationCountsByK.zeros(limit),
            pairs=CoupledPairEnumerationCountsByK.zeros(limit),
            search_space=CoupledSearchSpaceCounts.zeros(),
            identity_reduction=CoupledIdentityReductionCounts.zeros(),
        )

    def validate(self) -> None:
        if self.schema not in {
            COUPLED_MATCH_AUDIT_SCHEMA_V1,
            COUPLED_MATCH_AUDIT_SCHEMA_V2,
        }:
            raise ValueError("unsupported coupled-match audit schema")
        if self.implementation != COUPLED_MATCH_IMPLEMENTATION:
            raise ValueError("unsupported coupled-match audit implementation")
        for label, counts in (
            ("surface_A", self.surface_A),
            ("surface_B", self.surface_B),
            ("pairs", self.pairs),
        ):
            if counts.k_max != int(self.k_max):
                raise ValueError(f"{label}.k_max mismatch")
            counts.validate()
        if (self.surface_symmetry_A is None) != (self.surface_symmetry_B is None):
            raise ValueError(
                "surface symmetry provenance must be recorded for both slabs or neither"
            )
        if self.schema == COUPLED_MATCH_AUDIT_SCHEMA_V1:
            if self.search_space is not None or self.identity_reduction is not None:
                raise ValueError(
                    "v1 audits cannot contain v2 global reduction accounting"
                )
            return

        if self.search_space is None or self.identity_reduction is None:
            raise ValueError(
                "v2 audits require search-space and identity-reduction accounting"
            )
        self.search_space.validate()
        self.identity_reduction.validate()

        surface_a_totals = self.surface_A.totals()
        surface_b_totals = self.surface_B.totals()
        expected_raw_pairs = (
            surface_a_totals["hnf_generated"]
            * surface_b_totals["hnf_generated"]
        )
        expected_searchable_pairs = (
            surface_a_totals["admitted_members"]
            * surface_b_totals["admitted_members"]
        )
        if self.search_space.raw_hnf_pairs != expected_raw_pairs:
            raise ValueError(
                "raw_hnf_pairs must equal the product of generated one-sided HNFs"
            )
        if self.search_space.searchable_hnf_pairs != expected_searchable_pairs:
            raise ValueError(
                "searchable_hnf_pairs must equal the product of admitted one-sided HNFs"
            )

        pair_totals = self.pairs.totals()
        if (
            self.search_space.orbit_prefilter_surviving_hnf_pairs
            != pair_totals["member_pairs_expanded"]
        ):
            raise ValueError(
                "orbit-prefilter-surviving HNF pairs must equal "
                "member_pairs_expanded"
            )
        if (
            self.identity_reduction.admitted_descriptions
            != pair_totals["candidates_admitted"]
        ):
            raise ValueError(
                "identity-reduction admitted_descriptions must equal "
                "candidates_admitted"
            )
        if (
            self.identity_reduction.unique_admitted_source_pairs
            > pair_totals["unique_source_pairs_primitiveized"]
        ):
            raise ValueError(
                "admitted unique source pairs cannot exceed all primitiveized "
                "source pairs"
            )
        if (
            self.identity_reduction.unique_final_pair_classes
            != pair_totals["primitive_classes_created"]
        ):
            raise ValueError(
                "identity-reduction final classes must equal "
                "primitive_classes_created"
            )

    def to_dict(self, *, cumulative: bool = False) -> dict[str, Any]:
        self.validate()
        payload: dict[str, Any] = {
            "schema": self.schema,
            "implementation": self.implementation,
            "k_max": int(self.k_max),
            "surface_A": self.surface_A.rows(cumulative=cumulative),
            "surface_B": self.surface_B.rows(cumulative=cumulative),
            "pairs": self.pairs.rows(cumulative=cumulative),
            "totals": {
                "surface_A": self.surface_A.totals(),
                "surface_B": self.surface_B.totals(),
                "pairs": self.pairs.totals(),
            },
        }
        if self.surface_symmetry_A is not None:
            payload["surface_symmetry_A"] = self.surface_symmetry_A.to_dict()
            payload["surface_symmetry_B"] = self.surface_symmetry_B.to_dict()
        if self.search_space is not None:
            payload["search_space"] = self.search_space.to_dict()
        if self.identity_reduction is not None:
            payload["identity_reduction"] = self.identity_reduction.to_dict()
        return payload
