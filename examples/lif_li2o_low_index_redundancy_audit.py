#!/usr/bin/env python3
"""Audit redundancy removal in completed low-index LiF/Li2O searches.

This read-only companion expects the nine named searches produced by the
low-index LiF/Li2O workflow. It does not rerun matching. New searches must use
the v2 enumeration-audit schema, which records the global HNF-pair populations
and exact coupled-identity quotient introduced for this analysis.

Run from the repository root::

    python examples/lif_li2o_low_index_redundancy_audit.py

Use ``--project-dir``, ``--output-dir``, or repeated ``--search-name`` options
when the generating workflow used different locations or names.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any

from calm import open_project


SCRIPT_DIR = Path(__file__).resolve().parent
WORK_DIR = SCRIPT_DIR / "work" / "lif-li2o-low-index-pareto"
DEFAULT_PROJECT_DIR = WORK_DIR / "lif-li2o-low-index-grace.calm"
DEFAULT_OUTPUT_DIR = WORK_DIR / "outputs-grace" / "redundancy-audit"
DEFAULT_SEARCH_PREFIX = "lif-li2o-low-index-v1"
MILLERS = ((1, 0, 0), (1, 1, 0), (1, 1, 1))

SUMMARY_SCHEMA = "calm.lif_li2o_low_index_redundancy_audit/v1"
REQUIRED_AUDIT_SCHEMA = "calm.coupled_match_enumeration_audit/v2"

SEARCH_SPACE_STAGES = (
    (
        "raw_hnf_pairs",
        "Raw HNF pairs",
        "Cross-product of all A- and B-side HNFs within the index bound.",
    ),
    (
        "searchable_hnf_pairs",
        "Reduction- and condition-admitted HNF pairs",
        "HNF pairs remaining after one-sided reduction and condition filters.",
    ),
    (
        "area_admissible_hnf_pairs",
        "Area-admissible HNF pairs",
        "Remaining HNF pairs after the necessary logarithmic-area bound.",
    ),
    (
        "atom_lower_bound_admissible_hnf_pairs",
        "Atom-lower-bound-admissible HNF pairs",
        "Remaining HNF pairs after the necessary pre-enumeration atom bound.",
    ),
    (
        "orbit_prefilter_surviving_hnf_pairs",
        "Orbit-prefilter-surviving HNF pairs",
        "HNF pairs expanded after symmetry-compressed orbit screening; "
        "admitted and inconclusive orbit pairs are retained.",
    ),
)

IDENTITY_STAGES = (
    (
        "admitted_descriptions",
        "Admitted descriptions",
        "All strain- and atom-admissible correspondence occurrences.",
    ),
    (
        "unique_admitted_source_pairs",
        "Unique exact source pairs",
        "Distinct coupled integer source matrices before saturation.",
    ),
    (
        "unique_admitted_primitive_pairs",
        "Unique saturated pairs",
        "Distinct coupled matrices after shared repetition is removed.",
    ),
    (
        "unique_admitted_common_right_classes",
        "Common-basis classes",
        "Saturated pairs modulo one common interface-basis change.",
    ),
    (
        "unique_final_pair_classes",
        "Final pair-identity classes",
        "Common-basis classes modulo the configured surface symmetries and "
        "material-exchange policy.",
    ),
)


def compact_hkl(miller: tuple[int, int, int]) -> str:
    """Return a compact Miller label such as ``100`` or ``111``."""

    return "".join(str(value) for value in miller)


def default_search_names(prefix: str) -> list[str]:
    """Return the nine stable low-index search names."""

    return [
        f"{prefix}-lif-{compact_hkl(miller_a)}-li2o-{compact_hkl(miller_b)}"
        for miller_a, miller_b in product(MILLERS, repeat=2)
    ]


def _mapping(value: Any, *, name: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name} is not valid JSON.") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{name} must be a mapping.")
    return dict(value)


def _sequence(value: Any, *, name: str) -> list[Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name} is not valid JSON.") from exc
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeError(f"{name} must be a sequence.")
    return list(value)


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{name} must be a nonnegative integer.")
    return int(value)


def _positive_int(value: Any, *, name: str) -> int:
    parsed = _nonnegative_int(value, name=name)
    if parsed == 0:
        raise RuntimeError(f"{name} must be a positive integer.")
    return parsed


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sum_fields(
    rows: list[dict[str, object]],
    names: Sequence[str],
) -> dict[str, int]:
    return {
        name: sum(_nonnegative_int(row[name], name=f"row.{name}") for row in rows)
        for name in names
    }


def _candidate_multiplicity_rows(
    search_name: str,
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for index, row in enumerate(candidate_rows, start=1):
        candidate_id = row.get("candidate_id") or row.get("candidate_uid")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise RuntimeError(
                f"{search_name} candidate {index} has no persistent candidate ID."
            )
        provenance = _mapping(
            row.get("source_provenance"),
            name=f"{search_name} candidate {index} source_provenance",
        )
        pair_identity = _mapping(
            row.get("pair_identity"),
            name=f"{search_name} candidate {index} pair_identity",
        )
        source_index_pairs = _sequence(
            provenance.get("source_index_pairs"),
            name=f"{search_name} candidate {index} source_index_pairs",
        )
        repeat_indices = _sequence(
            provenance.get("repeat_indices"),
            name=f"{search_name} candidate {index} repeat_indices",
        )
        source_count = _positive_int(
            provenance.get("source_count"),
            name=f"{search_name} candidate {index} source_count",
        )
        primitive_pair_key = _sequence(
            pair_identity.get("primitive_pair_key"),
            name=f"{search_name} candidate {index} primitive_pair_key",
        )
        if len(primitive_pair_key) != 8 or any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in primitive_pair_key
        ):
            raise RuntimeError(
                f"{search_name} candidate {index} primitive_pair_key must "
                "contain eight exact integers."
            )
        if not source_index_pairs:
            raise RuntimeError(
                f"{search_name} candidate {index} has no source-index provenance."
            )
        for pair_number, source_pair in enumerate(source_index_pairs, start=1):
            values = _sequence(
                source_pair,
                name=(
                    f"{search_name} candidate {index} source index pair "
                    f"{pair_number}"
                ),
            )
            if len(values) != 2:
                raise RuntimeError(
                    f"{search_name} candidate {index} source index pair "
                    f"{pair_number} must contain two indices."
                )
            for value in values:
                _positive_int(value, name="source index")
        if not repeat_indices:
            raise RuntimeError(
                f"{search_name} candidate {index} has no repeat-index provenance."
            )
        repeat_indices = [
            _positive_int(value, name="repeat index") for value in repeat_indices
        ]
        output.append(
            {
                "search_name": search_name,
                "candidate_id": candidate_id,
                "source_count": source_count,
                "distinct_source_index_pairs": len(source_index_pairs),
                "distinct_repeat_indices": len(repeat_indices),
                "repeat_indices": json.dumps(repeat_indices, separators=(",", ":")),
                "primitive_pair_key": json.dumps(
                    primitive_pair_key,
                    separators=(",", ":"),
                ),
            }
        )
    return output


def collect_search(
    project: Any,
    search_name: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Collect and validate one completed search through CALM's public API."""

    try:
        search = project.search(search_name)
    except KeyError as exc:
        raise RuntimeError(
            f"Search {search_name!r} is missing. Run the low-index search workflow "
            "before this read-only audit."
        ) from exc

    if not search.has_enumeration_audit:
        raise RuntimeError(
            f"Search {search_name!r} has no enumeration audit. Rerun it with "
            "resume=False using the current CALM version."
        )

    audit = search.enumeration_audit()
    search_space = audit.search_space
    identity = audit.identity_reduction
    if (
        audit.schema != REQUIRED_AUDIT_SCHEMA
        or search_space is None
        or identity is None
    ):
        raise RuntimeError(
            f"Search {search_name!r} uses {audit.schema!r}; the exact reduction "
            f"funnel requires {REQUIRED_AUDIT_SCHEMA!r}. Rerun the search with "
            "resume=False using the current CALM version."
        )

    totals = audit.totals
    surface_a_totals = totals["surface_A"]
    surface_b_totals = totals["surface_B"]
    pair_totals = totals["pairs"]
    reduction_failures = (
        surface_a_totals["reduction_failed"]
        + surface_b_totals["reduction_failed"]
    )
    if reduction_failures:
        raise RuntimeError(
            f"Search {search_name!r} recorded {reduction_failures} one-sided "
            "cell-reduction failures and is not a complete finite-space audit."
        )
    if pair_totals["correspondence_limit_failures"]:
        raise RuntimeError(
            f"Search {search_name!r} encountered a correspondence enumeration "
            "limit and is not a complete audit."
        )

    candidate_rows = search.candidates().to_rows(view="all")
    final_count = identity["unique_final_pair_classes"]
    if len(candidate_rows) != final_count:
        raise RuntimeError(
            f"Search {search_name!r} persisted {len(candidate_rows)} of "
            f"{final_count} final classes. Increase max_candidates and rerun "
            "with a new search name."
        )

    multiplicities = _candidate_multiplicity_rows(search_name, candidate_rows)
    candidate_ids = [str(row["candidate_id"]) for row in multiplicities]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RuntimeError(f"Search {search_name!r} contains duplicate candidate IDs.")
    source_count_total = sum(int(row["source_count"]) for row in multiplicities)
    if source_count_total != identity["admitted_descriptions"]:
        raise RuntimeError(
            f"Search {search_name!r} candidate provenance accounts for "
            f"{source_count_total} admitted descriptions, but its enumeration "
            f"audit records {identity['admitted_descriptions']}."
        )

    record = getattr(search, "record", None)
    settings = dict(getattr(record, "settings", {}) or {})
    row: dict[str, object] = {
        "search_name": search_name,
        "search_uid": getattr(search, "uid_full", None),
        "search_identity": getattr(record, "search_identity", None),
        "search_settings": json.dumps(
            settings,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "audit_schema": audit.schema,
        "audit_implementation": audit.implementation,
        "k_max": audit.k_max,
        "surface_a_hnfs_generated": surface_a_totals["hnf_generated"],
        "surface_b_hnfs_generated": surface_b_totals["hnf_generated"],
        "surface_a_reduction_failed": surface_a_totals["reduction_failed"],
        "surface_b_reduction_failed": surface_b_totals["reduction_failed"],
        "surface_a_condition_rejected": surface_a_totals["condition_rejected"],
        "surface_b_condition_rejected": surface_b_totals["condition_rejected"],
        "surface_a_hnfs_searchable": surface_a_totals["admitted_members"],
        "surface_b_hnfs_searchable": surface_b_totals["admitted_members"],
        "surface_a_comparison_orbits": surface_a_totals["comparison_orbits"],
        "surface_b_comparison_orbits": surface_b_totals["comparison_orbits"],
        **{
            key: search_space[key]
            for key, _label, _definition in SEARCH_SPACE_STAGES
        },
        "index_pairs_scheduled": pair_totals["index_pairs_scheduled"],
        "orbit_pairs_considered": pair_totals["orbit_pairs_considered"],
        "orbit_prefilter_rejected": pair_totals["orbit_prefilter_rejected"],
        "orbit_prefilter_inconclusive": pair_totals[
            "orbit_prefilter_inconclusive"
        ],
        "orbit_prefilter_admitted": pair_totals["orbit_prefilter_admitted"],
        "member_pairs_expanded": pair_totals["member_pairs_expanded"],
        "correspondence_column_pairs_tested": pair_totals[
            "correspondence_column_pairs_tested"
        ],
        "unimodular_correspondences_tested": pair_totals[
            "unimodular_correspondences_tested"
        ],
        "strain_admissible_correspondences": pair_totals[
            "strain_admissible_correspondences"
        ],
        "nonprimitive_repetition_incidence": pair_totals[
            "nonprimitive_repetitions"
        ],
        "primitive_atom_rejected": pair_totals["primitive_atom_rejected"],
        "strict_strain_rejected": pair_totals["strict_strain_rejected"],
        **{
            key: identity[key]
            for key, _label, _definition in IDENTITY_STAGES
        },
        "persisted_candidates": len(candidate_rows),
        "candidate_source_count_total": source_count_total,
    }
    return row, multiplicities


def _stage_rows(
    counts: Mapping[str, int],
    stages: Sequence[tuple[str, str, str]],
    *,
    group: str,
    unit: str,
    quotient: bool,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    previous: int | None = None
    for order, (key, label, definition) in enumerate(stages, start=1):
        count = int(counts[key])
        if previous is not None and count > previous:
            raise RuntimeError(f"{group} counts increase from {previous} to {count}.")
        removed = "" if previous is None else previous - count
        retained = "" if previous in (None, 0) else count / previous
        output.append(
            {
                "stage_group": group,
                "stage_order": order,
                "stage_key": key,
                "stage": label,
                "count": count,
                "removed_from_previous": removed,
                "retained_fraction_of_previous": retained,
                "unit": unit,
                "operation": (
                    "baseline"
                    if previous is None
                    else ("exact quotient" if quotient else "configured filter")
                ),
                "definition": definition,
            }
        )
        previous = count
    return output


def build_outputs(
    per_search_rows: list[dict[str, object]],
    multiplicity_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Build aggregate tables and machine-checkable summary data."""

    search_names = [str(row["search_name"]) for row in per_search_rows]
    if not search_names:
        raise RuntimeError("At least one completed search is required.")
    if len(set(search_names)) != len(search_names):
        raise RuntimeError(
            "Search names must be unique; duplicate aggregation is invalid."
        )

    search_space_keys = [key for key, _label, _definition in SEARCH_SPACE_STAGES]
    identity_keys = [key for key, _label, _definition in IDENTITY_STAGES]
    search_space = _sum_fields(per_search_rows, search_space_keys)
    identity = _sum_fields(per_search_rows, identity_keys)

    search_space_rows = _stage_rows(
        search_space,
        SEARCH_SPACE_STAGES,
        group="finite_hnf_pair_space",
        unit="HNF-pair descriptions",
        quotient=False,
    )
    identity_rows = _stage_rows(
        identity,
        IDENTITY_STAGES,
        group="coupled_identity_reduction",
        unit="coupled-pair descriptions or exact classes",
        quotient=True,
    )

    work_fields = (
        (
            "orbit_pairs_considered",
            "Surface-orbit pair comparisons",
            "comparison tasks",
        ),
        (
            "correspondence_column_pairs_tested",
            "Correspondence column pairs tested",
            "column-pair tests",
        ),
        (
            "unimodular_correspondences_tested",
            "Unimodular correspondences tested",
            "correspondence tests",
        ),
        (
            "strain_admissible_correspondences",
            "Strain-admissible correspondence occurrences",
            "correspondence occurrences",
        ),
    )
    work_counts = _sum_fields(
        per_search_rows,
        [key for key, _label, _unit in work_fields],
    )
    work_rows = [
        {
            "stage_group": "enumeration_work",
            "stage_order": order,
            "stage_key": key,
            "stage": label,
            "count": work_counts[key],
            "removed_from_previous": "",
            "retained_fraction_of_previous": "",
            "unit": unit,
            "operation": "work counter",
            "definition": "A workload counter; not part of either monotonic funnel.",
        }
        for order, (key, label, unit) in enumerate(work_fields, start=1)
    ]

    disposition_keys = (
        "strain_admissible_correspondences",
        "primitive_atom_rejected",
        "strict_strain_rejected",
        "admitted_descriptions",
    )
    disposition = _sum_fields(per_search_rows, disposition_keys)
    if disposition["strain_admissible_correspondences"] != (
        disposition["primitive_atom_rejected"]
        + disposition["strict_strain_rejected"]
        + disposition["admitted_descriptions"]
    ):
        raise RuntimeError(
            "Strain-admissible correspondence dispositions do not partition "
            "their input population."
        )
    disposition_rows = [
        {
            "stage_group": "correspondence_disposition",
            "stage_order": order,
            "stage_key": key,
            "stage": label,
            "count": disposition[key],
            "removed_from_previous": "",
            "retained_fraction_of_previous": "",
            "unit": "correspondence occurrences",
            "operation": operation,
            "definition": definition,
        }
        for order, (key, label, operation, definition) in enumerate(
            (
                (
                    "strain_admissible_correspondences",
                    "Strain-admissible correspondences",
                    "partition input",
                    "Correspondence occurrences admitted by enumeration.",
                ),
                (
                    "primitive_atom_rejected",
                    "Rejected by primitive atom cap",
                    "rejected branch",
                    "Occurrences whose saturated pair exceeds the atom cap.",
                ),
                (
                    "strict_strain_rejected",
                    "Rejected by strict strain check",
                    "rejected branch",
                    "Tolerance-only occurrences outside the declared strain bound.",
                ),
                (
                    "admitted_descriptions",
                    "Admitted descriptions",
                    "accepted branch",
                    "Occurrences entering the exact identity quotient.",
                ),
            ),
            start=1,
        )
    ]

    source_count_total = sum(int(row["source_count"]) for row in multiplicity_rows)
    final_count = identity["unique_final_pair_classes"]
    if len(multiplicity_rows) != final_count:
        raise RuntimeError(
            "Class-multiplicity rows do not equal the aggregate final-class count."
        )
    if source_count_total != identity["admitted_descriptions"]:
        raise RuntimeError(
            "Class multiplicities do not sum to aggregate admitted descriptions."
        )

    summary: dict[str, object] = {
        "schema": SUMMARY_SCHEMA,
        "audit_schema": REQUIRED_AUDIT_SCHEMA,
        "aggregation_scope": "independent low-index surface-pair searches",
        "search_count": len(per_search_rows),
        "search_names": search_names,
        "searches": [
            {
                "search_name": row["search_name"],
                "search_uid": row["search_uid"],
                "search_identity": row["search_identity"],
                "settings": json.loads(str(row["search_settings"])),
                "audit_implementation": row["audit_implementation"],
                "k_max": row["k_max"],
            }
            for row in per_search_rows
        ],
        "search_space": search_space,
        "correspondence_disposition": disposition,
        "identity_reduction": identity,
        "persisted_candidate_count": len(multiplicity_rows),
        "candidate_source_count_total": source_count_total,
        "checks": {
            "search_space_nonincreasing": True,
            "identity_reduction_nonincreasing": True,
            "correspondence_dispositions_partition_input": True,
            "surface_reduction_failures": 0,
            "final_classes_equal_persisted_candidates": True,
            "admitted_descriptions_equal_candidate_source_count": True,
            "correspondence_limit_failures": 0,
        },
        "interpretation": {
            "search_space": (
                "A monotonic HNF-pair filtering sequence within the configured "
                "finite determinant domain."
            ),
            "enumeration_work": (
                "Work counters have different units and must not be read as one "
                "monotonic reduction sequence."
            ),
            "correspondence_disposition": (
                "Rejected and admitted branches partition the strain-admissible "
                "correspondence occurrences."
            ),
            "identity_reduction": (
                "Exact cardinalities under successive coupled-pair equivalence "
                "relations."
            ),
        },
    }
    rows = search_space_rows + work_rows + disposition_rows + identity_rows
    return rows, identity_rows, summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=DEFAULT_PROJECT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--search-prefix", default=DEFAULT_SEARCH_PREFIX)
    parser.add_argument(
        "--search-name",
        dest="search_names",
        action="append",
        help="Audit this search; repeat to override the default nine-search set.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    project_dir = args.project_dir.resolve()
    output_dir = args.output_dir.resolve()
    names = args.search_names or default_search_names(args.search_prefix)

    if any(not str(name).strip() for name in names):
        raise ValueError("Search names must be nonempty.")
    if len(set(names)) != len(names):
        raise ValueError(
            "Search names must be unique; duplicate searches would be counted twice."
        )

    if not project_dir.is_dir():
        raise FileNotFoundError(
            f"CALM project not found at {project_dir}. Run the low-index "
            "LiF/Li2O workflow first or pass --project-dir."
        )

    project = open_project(project_dir)
    per_search_rows: list[dict[str, object]] = []
    multiplicity_rows: list[dict[str, object]] = []
    for name in names:
        row, class_rows = collect_search(project, name)
        per_search_rows.append(row)
        multiplicity_rows.extend(class_rows)

    stage_rows, funnel_rows, summary = build_outputs(
        per_search_rows,
        multiplicity_rows,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "per-search-accounting.csv", per_search_rows)
    _write_csv(output_dir / "aggregate-stage-accounting.csv", stage_rows)
    _write_csv(output_dir / "deduplication-funnel.csv", funnel_rows)
    _write_csv(output_dir / "class-multiplicity.csv", multiplicity_rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Audited {len(per_search_rows)} completed searches.")
    print(
        "Identity reduction: "
        + " -> ".join(str(row["count"]) for row in funnel_rows)
    )
    print(f"Outputs: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
