"""Read-only public view of interface-search enumeration accounting."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import Any

from calm.interface.matching.audit import (
    COUPLED_MATCH_AUDIT_SCHEMA_V2,
    CoupledIdentityReductionCounts,
    CoupledMatchEnumerationAudit,
    CoupledPairEnumerationCountsByK,
    CoupledSearchSpaceCounts,
    CoupledSurfaceEnumerationCountsByK,
)
from calm.symmetry.surface_group import SurfaceSymmetryProvenance

_SURFACE_COUNT_NAMES = (
    "hnf_generated",
    "reduction_failed",
    "condition_rejected",
    "admitted_members",
    "comparison_orbits",
)

_PAIR_COUNT_NAMES = (
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

_SEARCH_SPACE_COUNT_NAMES = (
    "raw_hnf_pairs",
    "searchable_hnf_pairs",
    "area_admissible_hnf_pairs",
    "atom_lower_bound_admissible_hnf_pairs",
    "orbit_prefilter_surviving_hnf_pairs",
)

_IDENTITY_REDUCTION_COUNT_NAMES = (
    "admitted_descriptions",
    "unique_admitted_source_pairs",
    "unique_admitted_primitive_pairs",
    "unique_admitted_common_right_classes",
    "unique_final_pair_classes",
)


def _as_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    return dict(value)


def _exact_nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a nonnegative integer.")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} must be a nonnegative integer.")
    return parsed


def _counts_from_rows(
    rows: Any,
    *,
    section: str,
    k_max: int,
    count_names: tuple[str, ...],
) -> dict[str, list[int]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError(f"{section} must be a sequence of row mappings.")
    if len(rows) != k_max:
        raise ValueError(f"{section} must contain exactly k_max={k_max} rows.")

    columns = {name: [] for name in count_names}
    for index, raw_row in enumerate(rows, start=1):
        row = _as_mapping(raw_row, name=f"{section}[{index - 1}]")
        if (
            _exact_nonnegative_int(row.get("k"), name=f"{section}[{index - 1}].k")
            != index
        ):
            raise ValueError(f"{section} rows must use consecutive 1-based k values.")
        for name in count_names:
            columns[name].append(
                _exact_nonnegative_int(
                    row.get(name),
                    name=f"{section}[{index - 1}].{name}",
                )
            )
    return columns


def _symmetry_from_mapping(value: Any, *, name: str) -> SurfaceSymmetryProvenance:
    row = _as_mapping(value, name=name)
    return SurfaceSymmetryProvenance(**row)


def _global_counts(
    value: Any,
    *,
    name: str,
    fields: tuple[str, ...],
) -> dict[str, int]:
    row = _as_mapping(value, name=name)
    if set(row) != set(fields):
        raise ValueError(f"{name} must contain exactly: {', '.join(fields)}")
    return {
        field: _exact_nonnegative_int(row[field], name=f"{name}.{field}")
        for field in fields
    }


def _normalized_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, InterfaceSearchEnumerationAudit):
        return value.to_dict(cumulative=False)
    if isinstance(value, CoupledMatchEnumerationAudit):
        return value.to_dict(cumulative=False)
    if not isinstance(value, Mapping):
        raise TypeError(
            "enumeration audit must be an InterfaceSearchEnumerationAudit, "
            "CoupledMatchEnumerationAudit, or mapping."
        )

    payload = dict(value)
    k_max = _exact_nonnegative_int(payload.get("k_max"), name="k_max")
    surface_a_columns = _counts_from_rows(
        payload.get("surface_A"),
        section="surface_A",
        k_max=k_max,
        count_names=_SURFACE_COUNT_NAMES,
    )
    surface_b_columns = _counts_from_rows(
        payload.get("surface_B"),
        section="surface_B",
        k_max=k_max,
        count_names=_SURFACE_COUNT_NAMES,
    )
    pair_columns = _counts_from_rows(
        payload.get("pairs"),
        section="pairs",
        k_max=k_max,
        count_names=_PAIR_COUNT_NAMES,
    )

    symmetry_a_raw = payload.get("surface_symmetry_A")
    symmetry_b_raw = payload.get("surface_symmetry_B")
    if (symmetry_a_raw is None) != (symmetry_b_raw is None):
        raise ValueError(
            "surface symmetry provenance must be present for both surfaces or neither."
        )

    search_space_raw = payload.get("search_space")
    identity_reduction_raw = payload.get("identity_reduction")
    if str(payload.get("schema") or "") == COUPLED_MATCH_AUDIT_SCHEMA_V2:
        search_space = CoupledSearchSpaceCounts(
            **_global_counts(
                search_space_raw,
                name="search_space",
                fields=_SEARCH_SPACE_COUNT_NAMES,
            )
        )
        identity_reduction = CoupledIdentityReductionCounts(
            **_global_counts(
                identity_reduction_raw,
                name="identity_reduction",
                fields=_IDENTITY_REDUCTION_COUNT_NAMES,
            )
        )
    else:
        search_space = (
            None
            if search_space_raw is None
            else CoupledSearchSpaceCounts(
                **_global_counts(
                    search_space_raw,
                    name="search_space",
                    fields=_SEARCH_SPACE_COUNT_NAMES,
                )
            )
        )
        identity_reduction = (
            None
            if identity_reduction_raw is None
            else CoupledIdentityReductionCounts(
                **_global_counts(
                    identity_reduction_raw,
                    name="identity_reduction",
                    fields=_IDENTITY_REDUCTION_COUNT_NAMES,
                )
            )
        )

    audit = CoupledMatchEnumerationAudit(
        schema=str(payload.get("schema") or ""),
        implementation=str(payload.get("implementation") or ""),
        k_max=k_max,
        surface_A=CoupledSurfaceEnumerationCountsByK(
            k_max=k_max,
            **surface_a_columns,
        ),
        surface_B=CoupledSurfaceEnumerationCountsByK(
            k_max=k_max,
            **surface_b_columns,
        ),
        pairs=CoupledPairEnumerationCountsByK(
            k_max=k_max,
            **pair_columns,
        ),
        surface_symmetry_A=(
            None
            if symmetry_a_raw is None
            else _symmetry_from_mapping(
                symmetry_a_raw,
                name="surface_symmetry_A",
            )
        ),
        surface_symmetry_B=(
            None
            if symmetry_b_raw is None
            else _symmetry_from_mapping(
                symmetry_b_raw,
                name="surface_symmetry_B",
            )
        ),
        search_space=search_space,
        identity_reduction=identity_reduction,
    )
    audit.validate()
    normalized = audit.to_dict(cumulative=False)

    supplied_totals = payload.get("totals")
    if supplied_totals is not None:
        supplied = _as_mapping(supplied_totals, name="totals")
        if supplied != normalized["totals"]:
            raise ValueError(
                "enumeration audit totals do not match the per-index rows."
            )
    return normalized


def _cumulative_rows(rows: list[dict[str, int]]) -> list[dict[str, int]]:
    if not rows:
        return []
    keys = [key for key in rows[0] if key != "k"]
    running = {key: 0 for key in keys}
    output: list[dict[str, int]] = []
    for row in rows:
        for key in keys:
            running[key] += int(row[key])
        output.append({"k": int(row["k"]), **running})
    return output


@dataclass(frozen=True)
class InterfaceSearchEnumerationAudit:
    """Immutable public accounting for one completed interface search.

    The persisted payload stores noncumulative rows. Cumulative rows are derived
    on request so the original per-index accounting remains available.
    """

    _payload_json: str

    @classmethod
    def from_value(cls, value: Any) -> "InterfaceSearchEnumerationAudit":
        payload = _normalized_payload(value)
        return cls(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    def _payload(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    @property
    def schema(self) -> str:
        return str(self._payload()["schema"])

    @property
    def implementation(self) -> str:
        return str(self._payload()["implementation"])

    @property
    def k_max(self) -> int:
        return int(self._payload()["k_max"])

    @property
    def totals(self) -> dict[str, dict[str, int]]:
        payload = self._payload()["totals"]
        return {
            section: {key: int(value) for key, value in counts.items()}
            for section, counts in payload.items()
        }

    @property
    def surface_symmetry_a(self) -> dict[str, Any] | None:
        value = self._payload().get("surface_symmetry_A")
        return None if value is None else dict(value)

    @property
    def surface_symmetry_b(self) -> dict[str, Any] | None:
        value = self._payload().get("surface_symmetry_B")
        return None if value is None else dict(value)

    @property
    def search_space(self) -> dict[str, int] | None:
        """Return global HNF-pair populations, or ``None`` for v1 audits."""

        value = self._payload().get("search_space")
        if value is None:
            return None
        return {key: int(count) for key, count in value.items()}

    @property
    def identity_reduction(self) -> dict[str, int] | None:
        """Return exact coupled-identity populations, or ``None`` for v1."""

        value = self._payload().get("identity_reduction")
        if value is None:
            return None
        return {key: int(count) for key, count in value.items()}

    def _rows(self, section: str, *, cumulative: bool) -> list[dict[str, int]]:
        rows = [
            {key: int(value) for key, value in row.items()}
            for row in self._payload()[section]
        ]
        return _cumulative_rows(rows) if cumulative else rows

    def surface_a_rows(self, *, cumulative: bool = False) -> list[dict[str, int]]:
        """Return per-index enumeration accounting for surface A."""

        return self._rows("surface_A", cumulative=cumulative)

    def surface_b_rows(self, *, cumulative: bool = False) -> list[dict[str, int]]:
        """Return per-index enumeration accounting for surface B."""

        return self._rows("surface_B", cumulative=cumulative)

    def pair_rows(self, *, cumulative: bool = False) -> list[dict[str, int]]:
        """Return per-index coupled-pair and correspondence accounting."""

        return self._rows("pairs", cumulative=cumulative)

    def to_dict(self, *, cumulative: bool = False) -> dict[str, Any]:
        """Return a detached JSON-serializable representation."""

        payload = self._payload()
        if cumulative:
            payload["surface_A"] = self.surface_a_rows(cumulative=True)
            payload["surface_B"] = self.surface_b_rows(cumulative=True)
            payload["pairs"] = self.pair_rows(cumulative=True)
        return payload

    def to_dataframe(self, section: str, *, cumulative: bool = False):
        """Return one audit section as a pandas DataFrame."""

        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "to_dataframe() requires pandas. Use the row methods when "
                "pandas is unavailable."
            ) from exc

        normalized = str(section).strip().lower()
        readers = {
            "surface_a": self.surface_a_rows,
            "surface_b": self.surface_b_rows,
            "pairs": self.pair_rows,
        }
        try:
            rows = readers[normalized](cumulative=cumulative)
        except KeyError as exc:
            raise ValueError(
                "section must be one of 'surface_a', 'surface_b', or 'pairs'."
            ) from exc
        return pd.DataFrame.from_records(rows)

    def write_tables(
        self,
        directory: str | Path,
        *,
        cumulative: bool = False,
    ) -> tuple[Path, ...]:
        """Write the audit JSON and three CSV tables to ``directory``."""

        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        json_path = root / "enumeration_audit.json"
        json_path.write_text(
            json.dumps(self.to_dict(cumulative=cumulative), indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(json_path)

        sections = (
            ("surface_a", self.surface_a_rows(cumulative=cumulative)),
            ("surface_b", self.surface_b_rows(cumulative=cumulative)),
            ("pairs", self.pair_rows(cumulative=cumulative)),
        )
        for name, rows in sections:
            path = root / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                if rows:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            written.append(path)

        return tuple(written)
