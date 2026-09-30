#!/usr/bin/env python3
"""Compare identity handling on one shared LiF/Li2O match ledger.

The script reads nine completed low-index searches from an existing CALM
project and reruns their exact scientific inputs under CALM's private admitted-
description observer.  Every comparator therefore receives the same population
that reached CALM's online identity aggregation.

The external-method adapters are fixed-surface, two-dimensional
operationalizations of selected paper- and source-described rules.  They do
not import or execute the external packages.  Their outputs are deliberately
typed as exact quotients, heuristic clusters, filters, or selectors; unlike
quantities are never presented as one funnel.

Run from the repository root::

    python examples/lif_li2o_low_index_dedup_comparison.py

An InterMatch-style selector requires per-description elastic energies.  Supply
them with ``--intermatch-elastic-energies`` as a CSV containing the columns
``entry_id`` and ``elastic_energy``.  The energy units, normalization, strained
side, and thickness convention must also be declared.  Without that input the
selector records an explicit not-applicable result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from itertools import product
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

WORK_DIR = SCRIPT_DIR / "work" / "lif-li2o-low-index-pareto"
DEFAULT_PROJECT_DIR = WORK_DIR / "lif-li2o-low-index-grace.calm"
DEFAULT_OUTPUT_DIR = WORK_DIR / "outputs-grace" / "dedup-comparison"
DEFAULT_SEARCH_PREFIX = "lif-li2o-low-index-v1"
MILLERS = ((1, 0, 0), (1, 1, 0), (1, 1, 1))

SUMMARY_SCHEMA = "calm.lif_li2o_low_index_dedup_comparison/v1"
LEDGER_SCHEMA = "calm.admitted_match_ledger_entry/v1"
METHOD_RUN_SCHEMA = "calm.dedup_method_run/v1"
ELASTIC_INPUT_SCHEMA = "calm.intermatch_elastic_energy_input/v1"

ZUR_REDUCTION_TOLERANCE = 1.0e-12
ZUR_SIGNATURE_SCALE = 1.0e10
INTEROPTIMUS_CROSS_TOLERANCE = 1.0e-2
INTEROPTIMUS_ANGLE_COSINE_TOLERANCE = 1.0e-1
JELVER_TOLERANCE = 1.0e-12
INTERMAT_LENGTH_NORM = "l2"
INTERMAT_REDUCTION_TOLERANCE = 1.0e-12
INTERMAT_MAX_LENGTH_MISMATCH = 0.08
INTERMAT_MAX_AREA_ANGSTROM2 = 300.0
INTERMAT_MAX_ANGLE_MISMATCH_DEGREES = 1.0
INTERMATCH_MAX_ABS_DEFORMATION = 0.10

CLASS_METHODS = (
    "calm_final",
    "zur_mcgill_descriptor",
    "interoptimus_greedy",
    "ogre_style",
)
CALM_STAGES = (
    ("source", "Unique exact source pairs"),
    ("primitive", "Shared-repeat saturation"),
    ("common_right", "Common interface-basis quotient"),
    ("final", "Terminated-surface symmetry quotient"),
)
USED_METHODS = (
    "zur_mcgill_descriptor",
    "calm",
    "interoptimus_greedy",
    "ogre_style",
    "jelver_style",
    "intermat_source",
    "intermat_paper_style",
    "intermatch_style",
)

ASSIGNMENT_FIELDS = (
    "search_name",
    "entry_id",
    "method_id",
    "result_kind",
    "class_id",
    "class_key",
)
SUMMARY_FIELDS = (
    "scope",
    "search_name",
    "method_id",
    "result_kind",
    "input_count",
    "output_count",
    "count_unit",
    "status",
)
DIAGNOSTIC_FIELDS = (
    "search_name",
    "comparison_method",
    "diagnostic",
    "reference_class_id",
    "comparison_class_id",
    "member_count",
    "reference_class_count",
    "comparison_class_count",
    "entry_ids",
)
FILTER_FIELDS = (
    "search_name",
    "entry_id",
    "method_id",
    "result_kind",
    "accepted",
    "reason",
    "outcome",
)
SELECTOR_FIELDS = (
    "search_name",
    "method_id",
    "result_kind",
    "status",
    "input_count",
    "selected_count",
    "selected_entry_ids",
    "outcome",
)


@dataclass(frozen=True)
class SearchLedger:
    """One rerun search and the exact context needed by comparator adapters."""

    name: str
    search_uid: str | None
    surface_a_uid: str
    surface_b_uid: str
    settings: Mapping[str, Any]
    point_group_a: tuple[Any, ...]
    point_group_b: tuple[Any, ...]
    surface_symmetry_a: Mapping[str, Any]
    surface_symmetry_b: Mapping[str, Any]
    trace_context: Mapping[str, Any]
    records: tuple[Mapping[str, Any], ...]
    entries: tuple[Any, ...]
    final_class_count: int
    persisted_candidate_count: int
    audit_admitted_count: int | None
    audit_identity_reduction: Mapping[str, int] | None
    persisted_pair_keys: tuple[tuple[int, ...], ...]
    rerun_pair_keys: tuple[tuple[int, ...], ...]


def compact_hkl(miller: tuple[int, int, int]) -> str:
    return "".join(str(value) for value in miller)


def default_search_names(prefix: str) -> list[str]:
    """Return the stable 3-by-3 low-index search matrix."""

    return [
        f"{prefix}-lif-{compact_hkl(a)}-li2o-{compact_hkl(b)}"
        for a, b in product(MILLERS, repeat=2)
    ]


def _json_native(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("benchmark output contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_native(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_native(to_dict())
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_native(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        return _json_native(item())
    raise TypeError(f"cannot serialize {type(value).__name__} as benchmark JSON")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_native(value),
        sort_keys=True,
        separators=(",", ":"),
    )


def _value_sha256(value: Any) -> str:
    """Hash one JSON-native value using the script's canonical encoding."""

    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _outcome_mapping(value: Any, *, owner: str) -> dict[str, Any]:
    payload = _json_native(value)
    if not isinstance(payload, Mapping):
        raise TypeError(f"{owner} must return a mapping-like outcome")
    return dict(payload)


def _first_present(
    payload: Mapping[str, Any],
    names: Sequence[str],
    *,
    owner: str,
) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    raise RuntimeError(f"{owner} outcome is missing one of {tuple(names)!r}")


def _class_key(value: Any, *, owner: str) -> Any:
    payload = _outcome_mapping(value, owner=owner)
    return _first_present(
        payload,
        ("key", "class_key", "signature"),
        owner=owner,
    )


def _class_id(search_name: str, method_id: str, key: Any) -> str:
    digest = hashlib.sha256(
        f"{search_name}\0{method_id}\0{_canonical_json(key)}".encode("utf-8")
    ).hexdigest()
    return f"{method_id}:{digest[:20]}"


def _search_surface_uid(record: Any, role: str) -> str:
    spec = dict(getattr(record, "spec", {}) or {})
    value = spec.get(role)
    if isinstance(value, Mapping):
        uid = value.get("uid_full") or value.get("slab_uid_full")
        if uid:
            return str(uid)
    legacy_key = "slab_a_uid_full" if role == "surface_a" else "slab_b_uid_full"
    uid = spec.get(legacy_key)
    if uid:
        return str(uid)
    raise RuntimeError(f"persisted search spec has no exact {role} UID")


def _search_settings(record: Any) -> dict[str, Any]:
    settings = dict(getattr(record, "settings", {}) or {})
    if settings:
        return settings
    spec = dict(getattr(record, "spec", {}) or {})
    value = spec.get("settings")
    if not isinstance(value, Mapping):
        raise RuntimeError("persisted search spec has no settings mapping")
    return dict(value)


def _audit_counts(
    search: Any,
) -> tuple[int | None, dict[str, int] | None]:
    if not bool(getattr(search, "has_enumeration_audit", False)):
        return None, None
    audit = search.enumeration_audit()
    totals = audit.totals
    pairs = totals.get("pairs", {})
    value = pairs.get("candidates_admitted")
    identity = getattr(audit, "identity_reduction", None)
    normalized_identity = (
        None
        if identity is None
        else {str(key): int(count) for key, count in identity.items()}
    )
    return (int(value) if value is not None else None), normalized_identity


def _surface_provenance(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return _outcome_mapping(value, owner="surface-symmetry provenance")


def _persisted_pair_keys(
    search: Any,
    *,
    expected_policy: Mapping[str, Any],
) -> tuple[tuple[int, ...], ...]:
    """Read and validate exact identities through the public project query API."""

    from calm.interface.model import PairIdentity2D

    keys: list[tuple[int, ...]] = []
    for index, row in enumerate(search.candidates().to_rows(view="all"), start=1):
        identity = row.get("pair_identity")
        if not isinstance(identity, Mapping):
            raise RuntimeError(
                f"{search.name}: persisted candidate {index} has no pair_identity."
            )
        try:
            typed_identity = PairIdentity2D.from_dict(identity)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"{search.name}: persisted candidate {index} has an invalid "
                "exact pair identity."
            ) from exc
        actual_policy = {
            "pair_key_version": typed_identity.key_version,
            "pair_symmetry": typed_identity.pair_symmetry_policy,
            "correspondence_orientation": (
                typed_identity.correspondence_orientation
            ),
            "identify_material_exchange": (
                typed_identity.material_exchange_identified
            ),
        }
        if actual_policy != dict(expected_policy):
            raise RuntimeError(
                f"{search.name}: persisted candidate {index} uses pair-identity "
                "policy metadata different from the exact rerun."
            )
        keys.append(tuple(typed_identity.primitive_pair_key))
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{search.name}: persisted exact pair keys are not unique.")
    return tuple(keys)


def capture_search_ledger(project: Any, search_name: str) -> SearchLedger:
    """Rerun one persisted search and capture all pre-aggregation descriptions."""

    from benchmarks.benchmarks.claims.dedup_comparison import LedgerEntry
    from calm.interface.matching._audit_trace import (
        _capture_coupled_match_trace,
    )
    from calm.interface.matching.search import search_primitive_match_classes
    from calm.public.inputs.settings import SearchSettings

    try:
        search = project.search(search_name)
    except KeyError as exc:
        raise RuntimeError(
            f"Search {search_name!r} is missing. Complete the low-index search "
            "workflow or pass explicit --search-name values."
        ) from exc
    status = str(getattr(search, "run_status", "") or "").lower()
    if status and status not in {"done", "completed", "succeeded", "success"}:
        raise RuntimeError(f"Search {search_name!r} is not complete: {status!r}.")

    record = search.record
    surface_a_uid = _search_surface_uid(record, "surface_a")
    surface_b_uid = _search_surface_uid(record, "surface_b")
    surface_a = project.surface(surface_a_uid).to_surface()
    surface_b = project.surface(surface_b_uid).to_surface()
    settings_payload = _search_settings(record)
    settings = SearchSettings.from_dict(settings_payload)
    config = settings.to_internal_config()
    slab_a = surface_a.to_slab()
    slab_b = surface_b.to_slab()

    with _capture_coupled_match_trace() as trace:
        result = search_primitive_match_classes(slab_a, slab_b, config)
    if len(trace.search_contexts) != 1:
        raise RuntimeError(
            f"{search_name}: expected one private search context, captured "
            f"{len(trace.search_contexts)}."
        )
    context = trace.search_contexts[0]
    context_payload = context.to_dict()

    rows: list[dict[str, Any]] = []
    entries: list[Any] = []
    for trace_record in trace.records:
        row = trace_record.to_dict()
        audit_index = int(row["audit_index"])
        row.update(
            {
                "schema": LEDGER_SCHEMA,
                "search_name": search_name,
                "search_uid": getattr(search, "uid_full", None),
                "entry_id": f"{search_name}:{audit_index:08d}",
                "record_id": f"{search_name}:{audit_index:08d}",
                "surface_a_uid": surface_a_uid,
                "surface_b_uid": surface_b_uid,
            }
        )
        rows.append(row)
        entries.append(LedgerEntry.from_record(row))

    result_source_count = sum(
        int(match_class.source_count) for match_class in result.match_classes
    )
    if len(rows) != result_source_count:
        raise RuntimeError(
            f"{search_name}: trace contains {len(rows)} descriptions but final "
            f"classes account for {result_source_count}."
        )
    observed_final = {
        tuple(int(item) for item in row["final_pair_key"]) for row in rows
    }
    expected_final = {
        tuple(int(item) for item in match_class.pair_key)
        for match_class in result.match_classes
    }
    if len(expected_final) != len(result.match_classes):
        raise RuntimeError(f"{search_name}: rerun returned duplicate final pair keys.")
    if observed_final != expected_final:
        raise RuntimeError(f"{search_name}: trace and final CALM class keys disagree.")

    admitted, audit_identity = _audit_counts(search)
    if admitted is not None and admitted != len(rows):
        raise RuntimeError(
            f"{search_name}: persisted audit reports {admitted} admitted "
            f"descriptions, but the exact rerun captured {len(rows)}."
        )
    expected_policy = {
        "pair_key_version": int(context_payload["pair_key_version"]),
        "pair_symmetry": str(context_payload["pair_symmetry"]),
        "correspondence_orientation": str(
            context_payload["correspondence_orientation"]
        ),
        "identify_material_exchange": bool(
            context_payload["identify_material_exchange"]
        ),
    }
    persisted_keys = _persisted_pair_keys(
        search,
        expected_policy=expected_policy,
    )
    persisted_count = len(persisted_keys)
    final_count = len(result.match_classes)
    if persisted_count != final_count:
        raise RuntimeError(
            f"{search_name}: persisted candidates ({persisted_count}) do not "
            f"cover the complete rerun population ({final_count}). Increase "
            "max_candidates and rerun the source search before comparison."
        )
    if set(persisted_keys) != expected_final:
        missing = sorted(expected_final - set(persisted_keys))
        extra = sorted(set(persisted_keys) - expected_final)
        raise RuntimeError(
            f"{search_name}: persisted and rerun exact pair-key sets differ "
            f"(missing={len(missing)}, extra={len(extra)})."
        )

    return SearchLedger(
        name=search_name,
        search_uid=getattr(search, "uid_full", None),
        surface_a_uid=surface_a_uid,
        surface_b_uid=surface_b_uid,
        settings=settings_payload,
        point_group_a=tuple(context.surface_point_group_A),
        point_group_b=tuple(context.surface_point_group_B),
        surface_symmetry_a=_surface_provenance(result.surface_symmetry_a),
        surface_symmetry_b=_surface_provenance(result.surface_symmetry_b),
        trace_context=context_payload,
        records=tuple(rows),
        entries=tuple(entries),
        final_class_count=final_count,
        persisted_candidate_count=persisted_count,
        audit_admitted_count=admitted,
        audit_identity_reduction=audit_identity,
        persisted_pair_keys=persisted_keys,
        rerun_pair_keys=tuple(sorted(expected_final)),
    )


def _stage_keys(value: Any) -> dict[str, Any]:
    payload = _outcome_mapping(value, owner="CALM stage-key adapter")
    if payload.get("status") != "classified":
        raise RuntimeError(
            "CALM rejected a record from its own admitted-description trace"
        )
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise RuntimeError("CALM stage-key outcome has no diagnostics mapping")
    aliases = {
        "source": ("source_key", "source_pair_key"),
        "primitive": ("saturated_key", "primitive_key", "primitive_pair_key"),
        "common_right": (
            "common_right_key",
            "common_right_class_key",
        ),
        "final": ("surface_symmetry_key", "final_key", "final_pair_key"),
    }
    output = {
        stage: _first_present(
            diagnostics,
            names,
            owner="CALM stage-key adapter diagnostics",
        )
        for stage, names in aliases.items()
    }
    if payload.get("class_key") != output["final"]:
        raise RuntimeError("CALM class key disagrees with its stage diagnostics")
    return output


def _accepted(value: Any) -> tuple[bool, str, dict[str, Any]]:
    payload = _outcome_mapping(value, owner="Jelver-style filter")
    accepted = _first_present(
        payload,
        ("retained", "accepted", "survives", "keep"),
        owner="Jelver-style filter",
    )
    if not isinstance(accepted, bool):
        raise TypeError("Jelver-style acceptance outcome must be boolean")
    diagnostics = payload.get("diagnostics")
    reason_value = None
    if isinstance(diagnostics, Mapping):
        reason_value = diagnostics.get("reason")
    reason = str(
        reason_value
        or payload.get("reason")
        or payload.get("disposition")
        or payload.get("status")
        or ""
    )
    return accepted, reason, payload


def _selected_entry_ids(value: Any, *, owner: str) -> tuple[str, ...]:
    payload = _outcome_mapping(value, owner=owner)
    for name in (
        "selected_entry_ids",
        "selected_record_ids",
        "entry_ids",
        "selected_ids",
        "pareto_entry_ids",
    ):
        if name in payload:
            values = payload[name]
            if values is None:
                return ()
            if isinstance(values, str):
                return (values,)
            if isinstance(values, Sequence):
                return tuple(str(item) for item in values)
            raise TypeError(f"{owner}.{name} must be a sequence")
    entry_id = (
        payload.get("selected_entry_id")
        or payload.get("selected_record_id")
        or payload.get("entry_id")
        or payload.get("record_id")
    )
    return () if entry_id is None else (str(entry_id),)


def _status(value: Any) -> str:
    payload = _outcome_mapping(value, owner="selector")
    return str(
        payload.get("status")
        or (
            "selected"
            if _selected_entry_ids(value, owner="selector")
            else "not_applicable"
        )
    )


def _method_metadata() -> dict[str, Any]:
    from benchmarks.benchmarks.claims.dedup_comparison import METHOD_METADATA

    return {
        method_id: _json_native(METHOD_METADATA[method_id])
        for method_id in USED_METHODS
    }


def _method_run(
    ledger: SearchLedger,
    method_id: str,
    result_kind: str,
    *,
    parameters: Mapping[str, Any],
    outcome: Mapping[str, Any],
) -> dict[str, Any]:
    from benchmarks.benchmarks.claims.dedup_comparison import METHOD_METADATA

    outcome_payload = dict(_json_native(outcome))
    # Adapter outcomes repeat their static MethodMetadata.  The run owns that
    # metadata once at the top level, while retaining all scientific results.
    outcome_payload.pop("method", None)
    return {
        "schema": METHOD_RUN_SCHEMA,
        "search_name": ledger.name,
        "search_uid": ledger.search_uid,
        "method_id": method_id,
        "result_kind": result_kind,
        "method": _json_native(METHOD_METADATA[method_id]),
        "parameters": _json_native(parameters),
        "outcome": outcome_payload,
    }


def classify_ledger(
    ledger: SearchLedger,
    *,
    elastic_energy_by_id: Mapping[str, float] | None,
    elastic_energy_provenance: Mapping[str, Any] | None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Apply class, filter, and selector adapters to one shared ledger."""

    from benchmarks.benchmarks.claims.dedup_comparison import (
        calm_stage_keys,
        cluster_interoptimus_style,
        jelver_style_filter,
        ogre_style_key,
        select_intermat_paper_style,
        select_intermat_source,
        select_intermatch_style,
        zur_mcgill_descriptor_key,
    )
    from calm.interface.matching._types import PairIdentityPolicy2D

    assignments: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    class_ids: dict[str, list[str]] = defaultdict(list)
    record_outcomes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    context = ledger.trace_context
    policy = PairIdentityPolicy2D(
        pair_symmetry=str(context["pair_symmetry"]),
        correspondence_orientation=str(context["correspondence_orientation"]),
        identify_material_exchange=bool(context["identify_material_exchange"]),
        key_version=int(context["pair_key_version"]),
    )

    for record, entry in zip(ledger.records, ledger.entries):
        entry_id = str(record["entry_id"])
        outcomes = {
            "calm": calm_stage_keys(
                entry,
                point_group_A=ledger.point_group_a,
                point_group_B=ledger.point_group_b,
                policy=policy,
            ),
            "zur_mcgill_descriptor": zur_mcgill_descriptor_key(
                entry,
                reduction_tolerance=ZUR_REDUCTION_TOLERANCE,
                signature_scale=ZUR_SIGNATURE_SCALE,
            ),
            "ogre_style": ogre_style_key(
                entry,
                point_group_A=ledger.point_group_a,
                point_group_B=ledger.point_group_b,
            ),
            "jelver_style": jelver_style_filter(
                entry,
                point_group_A=ledger.point_group_a,
                point_group_B=ledger.point_group_b,
                tolerance=JELVER_TOLERANCE,
            ),
        }
        stage_outcome = outcomes["calm"]
        stages = _stage_keys(stage_outcome)
        for stage, _label in CALM_STAGES:
            method_id = f"calm_{stage}"
            key = stages[stage]
            cid = _class_id(ledger.name, method_id, key)
            class_ids[method_id].append(cid)
            assignments.append(
                {
                    "search_name": ledger.name,
                    "entry_id": entry_id,
                    "method_id": method_id,
                    "result_kind": "exact_equivalence_class",
                    "class_id": cid,
                    "class_key": _canonical_json(key),
                }
            )

        comparator_values = {
            "zur_mcgill_descriptor": outcomes["zur_mcgill_descriptor"],
            "ogre_style": outcomes["ogre_style"],
        }
        for method_id, outcome in comparator_values.items():
            outcome_payload = _outcome_mapping(outcome, owner=method_id)
            outcome_payload.pop("method", None)
            record_outcomes[method_id].append(outcome_payload)
            key = _class_key(outcome, owner=method_id)
            cid = _class_id(ledger.name, method_id, key)
            class_ids[method_id].append(cid)
            assignments.append(
                {
                    "search_name": ledger.name,
                    "entry_id": entry_id,
                    "method_id": method_id,
                    "result_kind": "heuristic_cluster",
                    "class_id": cid,
                    "class_key": _canonical_json(key),
                }
            )

        accepted, reason, outcome = _accepted(outcomes["jelver_style"])
        compact_outcome = dict(outcome)
        compact_outcome.pop("method", None)
        record_outcomes["jelver_style"].append(compact_outcome)
        filters.append(
            {
                "search_name": ledger.name,
                "entry_id": entry_id,
                "method_id": "jelver_style",
                "result_kind": "generation_filter",
                "accepted": accepted,
                "reason": reason,
                "outcome": _canonical_json(outcome),
            }
        )

    interoptimus = cluster_interoptimus_style(
        ledger.entries,
        point_group_A=ledger.point_group_a,
        point_group_B=ledger.point_group_b,
        cross_tolerance=INTEROPTIMUS_CROSS_TOLERANCE,
        angle_cosine_tolerance=INTEROPTIMUS_ANGLE_COSINE_TOLERANCE,
    )
    if interoptimus.status != "classified":
        raise RuntimeError(
            f"{ledger.name}: InterOptimus-style clustering is "
            f"{interoptimus.status}: {interoptimus.reason}"
        )
    expected_ids = {str(record["entry_id"]) for record in ledger.records}
    assigned_ids = set(interoptimus.class_by_record_id)
    if assigned_ids != expected_ids:
        raise RuntimeError(
            f"{ledger.name}: InterOptimus-style clustering did not assign "
            "every ledger record exactly once."
        )
    for entry_id, local_class_id in sorted(interoptimus.class_by_record_id.items()):
        method_id = "interoptimus_greedy"
        cid = _class_id(ledger.name, method_id, local_class_id)
        class_ids[method_id].append(cid)
        assignments.append(
            {
                "search_name": ledger.name,
                "entry_id": entry_id,
                "method_id": method_id,
                "result_kind": "heuristic_cluster",
                "class_id": cid,
                "class_key": _canonical_json(local_class_id),
            }
        )

    for stage, _label in CALM_STAGES:
        method_id = f"calm_{stage}"
        summaries.append(
            {
                "scope": "search",
                "search_name": ledger.name,
                "method_id": method_id,
                "result_kind": "exact_equivalence_class",
                "input_count": len(ledger.entries),
                "output_count": len(set(class_ids[method_id])),
                "count_unit": "classes",
                "status": "completed",
            }
        )
    for method_id in (
        "zur_mcgill_descriptor",
        "interoptimus_greedy",
        "ogre_style",
    ):
        summaries.append(
            {
                "scope": "search",
                "search_name": ledger.name,
                "method_id": method_id,
                "result_kind": "heuristic_cluster",
                "input_count": len(ledger.entries),
                "output_count": len(set(class_ids[method_id])),
                "count_unit": "clusters",
                "status": "completed",
            }
        )
    summaries.append(
        {
            "scope": "search",
            "search_name": ledger.name,
            "method_id": "jelver_style",
            "result_kind": "generation_filter",
            "input_count": len(ledger.entries),
            "output_count": sum(bool(row["accepted"]) for row in filters),
            "count_unit": "surviving_descriptions",
            "status": "completed",
        }
    )

    selectors: list[dict[str, Any]] = []
    intermatch_strained_side = (
        "A"
        if elastic_energy_provenance is None
        else str(elastic_energy_provenance["strained_side"])
    )
    if intermatch_strained_side not in {"A", "B"}:
        raise ValueError("InterMatch strained side must be 'A' or 'B'")
    selector_values = {
        # Native JARVIS traversal ranks are not contained in a CALM ledger.
        # Preserve that missing-input result alongside the paper-text proxy.
        "intermat_source": select_intermat_source(ledger.entries),
        "intermat_paper_style": select_intermat_paper_style(
            ledger.entries,
            length_norm=INTERMAT_LENGTH_NORM,
            reduction_tolerance=INTERMAT_REDUCTION_TOLERANCE,
            max_length_mismatch=INTERMAT_MAX_LENGTH_MISMATCH,
            max_area=INTERMAT_MAX_AREA_ANGSTROM2,
            max_angle_mismatch_degrees=INTERMAT_MAX_ANGLE_MISMATCH_DEGREES,
        ),
        "intermatch_style": select_intermatch_style(
            ledger.entries,
            elastic_energy_by_id=elastic_energy_by_id,
            max_abs_deformation=INTERMATCH_MAX_ABS_DEFORMATION,
            strained_side=intermatch_strained_side,
        ),
    }
    for method_id, outcome in selector_values.items():
        payload = _outcome_mapping(outcome, owner=method_id)
        selected = _selected_entry_ids(outcome, owner=method_id)
        status = _status(outcome)
        selectors.append(
            {
                "search_name": ledger.name,
                "method_id": method_id,
                "result_kind": "selection_policy",
                "status": status,
                "input_count": len(ledger.entries),
                "selected_count": len(selected),
                "selected_entry_ids": _canonical_json(selected),
                "outcome": _canonical_json(payload),
            }
        )
        summaries.append(
            {
                "scope": "search",
                "search_name": ledger.name,
                "method_id": method_id,
                "result_kind": "selection_policy",
                "input_count": len(ledger.entries),
                "output_count": len(selected),
                "count_unit": "selected_descriptions",
                "status": status,
            }
        )

    if len(set(class_ids["calm_final"])) != ledger.final_class_count:
        raise RuntimeError(
            f"{ledger.name}: comparator projection does not reproduce CALM's "
            "final class count."
        )
    if ledger.audit_identity_reduction is not None:
        observed = {
            "admitted_descriptions": len(ledger.entries),
            "unique_admitted_source_pairs": len(set(class_ids["calm_source"])),
            "unique_admitted_primitive_pairs": len(
                set(class_ids["calm_primitive"])
            ),
            "unique_admitted_common_right_classes": len(
                set(class_ids["calm_common_right"])
            ),
            "unique_final_pair_classes": len(set(class_ids["calm_final"])),
        }
        expected = {
            key: ledger.audit_identity_reduction[key]
            for key in observed
            if key in ledger.audit_identity_reduction
        }
        if expected != {key: observed[key] for key in expected}:
            raise RuntimeError(
                f"{ledger.name}: rerun CALM stage counts disagree with the "
                "persisted exact identity-reduction audit."
            )
    stage_counts = {
        stage: len(set(class_ids[f"calm_{stage}"]))
        for stage, _label in CALM_STAGES
    }
    common_parameters = {
        "candidate_universe": "CALM-admitted fixed-surface source ledger",
        "record_count": len(ledger.entries),
        "input_ledger_artifact": "raw-match-ledger.jsonl",
        "input_entry_id_sha256": _value_sha256(
            sorted(str(record["entry_id"]) for record in ledger.records)
        ),
        "search_settings": ledger.settings,
        "point_group_A": ledger.point_group_a,
        "point_group_B": ledger.point_group_b,
    }
    method_runs = [
        _method_run(
            ledger,
            "calm",
            "exact_equivalence_class",
            parameters={
                **common_parameters,
                "pair_identity_policy": {
                    "pair_symmetry": policy.pair_symmetry,
                    "correspondence_orientation": policy.correspondence_orientation,
                    "identify_material_exchange": policy.identify_material_exchange,
                    "key_version": policy.key_version,
                },
            },
            outcome={
                "status": "completed",
                "stage_counts": stage_counts,
                "persisted_pair_key_set_equals_rerun": True,
                "persisted_pair_key_sha256": _value_sha256(
                    sorted(ledger.persisted_pair_keys)
                ),
                "rerun_final_pair_key_sha256": _value_sha256(
                    sorted(ledger.rerun_pair_keys)
                ),
                "assignment_artifact": "classifier-assignments.csv",
            },
        ),
        _method_run(
            ledger,
            "zur_mcgill_descriptor",
            "heuristic_cluster",
            parameters={
                **common_parameters,
                "reduction_tolerance": ZUR_REDUCTION_TOLERANCE,
                "signature_scale": ZUR_SIGNATURE_SCALE,
            },
            outcome={
                "status": "completed",
                "cluster_count": len(set(class_ids["zur_mcgill_descriptor"])),
                "record_outcomes": record_outcomes["zur_mcgill_descriptor"],
                "assignment_artifact": "classifier-assignments.csv",
            },
        ),
        _method_run(
            ledger,
            "interoptimus_greedy",
            "heuristic_cluster",
            parameters={
                **common_parameters,
                "cross_tolerance": INTEROPTIMUS_CROSS_TOLERANCE,
                "angle_cosine_tolerance": (
                    INTEROPTIMUS_ANGLE_COSINE_TOLERANCE
                ),
            },
            outcome=_outcome_mapping(interoptimus, owner="interoptimus_greedy"),
        ),
        _method_run(
            ledger,
            "ogre_style",
            "heuristic_cluster",
            parameters=common_parameters,
            outcome={
                "status": "completed",
                "cluster_count": len(set(class_ids["ogre_style"])),
                "record_outcomes": record_outcomes["ogre_style"],
                "assignment_artifact": "classifier-assignments.csv",
            },
        ),
        _method_run(
            ledger,
            "jelver_style",
            "generation_filter",
            parameters={**common_parameters, "tolerance": JELVER_TOLERANCE},
            outcome={
                "status": "completed",
                "retained_count": sum(bool(row["accepted"]) for row in filters),
                "rejected_count": sum(not bool(row["accepted"]) for row in filters),
                "record_outcomes": record_outcomes["jelver_style"],
                "filter_artifact": "filter-survivors.csv",
            },
        ),
    ]
    selector_parameters = {
        "intermat_source": {
            **common_parameters,
            "native_zsl_rank_by_id": None,
        },
        "intermat_paper_style": {
            **common_parameters,
            "length_norm": INTERMAT_LENGTH_NORM,
            "reduction_tolerance": INTERMAT_REDUCTION_TOLERANCE,
            "max_length_mismatch": INTERMAT_MAX_LENGTH_MISMATCH,
            "max_area_angstrom2": INTERMAT_MAX_AREA_ANGSTROM2,
            "max_angle_mismatch_degrees": (
                INTERMAT_MAX_ANGLE_MISMATCH_DEGREES
            ),
        },
        "intermatch_style": {
            **common_parameters,
            "max_abs_deformation": INTERMATCH_MAX_ABS_DEFORMATION,
            "strained_side": intermatch_strained_side,
            "elastic_energy_input": elastic_energy_provenance,
        },
    }
    method_runs.extend(
        _method_run(
            ledger,
            method_id,
            "selection_policy",
            parameters=selector_parameters[method_id],
            outcome=_outcome_mapping(outcome, owner=method_id),
        )
        for method_id, outcome in selector_values.items()
    )
    return assignments, filters, selectors, summaries, method_runs


def build_relative_split_merge_diagnostics(
    assignments: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Report analogue over-merges and over-splits relative to CALM classes."""

    by_search_entry: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in assignments:
        method = str(row["method_id"])
        if method not in CLASS_METHODS:
            continue
        key = (str(row["search_name"]), str(row["entry_id"]))
        by_search_entry[key][method] = str(row["class_id"])

    over_merges: list[dict[str, Any]] = []
    over_splits: list[dict[str, Any]] = []
    search_names = sorted({name for name, _entry_id in by_search_entry})
    for search_name in search_names:
        rows = [
            (entry_id, values)
            for (name, entry_id), values in by_search_entry.items()
            if name == search_name
        ]
        for method in (
            "zur_mcgill_descriptor",
            "interoptimus_greedy",
            "ogre_style",
        ):
            by_comparison: dict[str, list[tuple[str, str]]] = defaultdict(list)
            by_reference: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for entry_id, values in rows:
                if "calm_final" not in values or method not in values:
                    raise RuntimeError(
                        f"incomplete class assignments for {search_name}:{entry_id}"
                    )
                reference = values["calm_final"]
                comparison = values[method]
                by_comparison[comparison].append((entry_id, reference))
                by_reference[reference].append((entry_id, comparison))

            for comparison, members in sorted(by_comparison.items()):
                references = sorted({reference for _entry, reference in members})
                if len(references) <= 1:
                    continue
                over_merges.append(
                    {
                        "search_name": search_name,
                        "comparison_method": method,
                        "diagnostic": "heuristic_cluster_spans_calm_classes",
                        "reference_class_id": _canonical_json(references),
                        "comparison_class_id": comparison,
                        "member_count": len(members),
                        "reference_class_count": len(references),
                        "comparison_class_count": 1,
                        "entry_ids": _canonical_json(
                            sorted(entry for entry, _reference in members)[:10]
                        ),
                    }
                )
            for reference, members in sorted(by_reference.items()):
                comparisons = sorted(
                    {comparison for _entry, comparison in members}
                )
                if len(comparisons) <= 1:
                    continue
                over_splits.append(
                    {
                        "search_name": search_name,
                        "comparison_method": method,
                        "diagnostic": "calm_class_spans_heuristic_clusters",
                        "reference_class_id": reference,
                        "comparison_class_id": _canonical_json(comparisons),
                        "member_count": len(members),
                        "reference_class_count": 1,
                        "comparison_class_count": len(comparisons),
                        "entry_ids": _canonical_json(
                            sorted(entry for entry, _comparison in members)[:10]
                        ),
                    }
                )
    return over_merges, over_splits


def aggregate_summaries(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Sum independent search counts without identifying across searches."""

    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["method_id"]),
            str(row["result_kind"]),
            str(row["count_unit"]),
        )
        grouped[key].append(row)
    output = [dict(row) for row in rows]
    for (method_id, result_kind, count_unit), members in sorted(grouped.items()):
        statuses = {str(row["status"]) for row in members}
        output.append(
            {
                "scope": "independent_search_sum",
                "search_name": "ALL",
                "method_id": method_id,
                "result_kind": result_kind,
                "input_count": sum(int(row["input_count"]) for row in members),
                "output_count": sum(int(row["output_count"]) for row in members),
                "count_unit": count_unit,
                "status": statuses.pop() if len(statuses) == 1 else "mixed",
            }
        )
    return output


def _read_elastic_energies(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    values: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"entry_id", "elastic_energy"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise RuntimeError(
                "elastic-energy CSV must contain entry_id and elastic_energy"
            )
        for line, row in enumerate(reader, start=2):
            entry_id = str(row["entry_id"] or "").strip()
            if not entry_id or entry_id in values:
                raise RuntimeError(
                    f"invalid or duplicate entry_id on elastic-energy line {line}"
                )
            energy = float(row["elastic_energy"])
            if not math.isfinite(energy) or energy < 0.0:
                raise RuntimeError(
                    f"elastic_energy must be finite and nonnegative on line {line}"
                )
            values[entry_id] = energy
    return values


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_elastic_energy_input(
    path: Path | None,
    *,
    units: str | None,
    normalization: str | None,
    strained_side: str | None,
    thickness_convention: str | None,
) -> tuple[dict[str, float] | None, dict[str, Any] | None]:
    """Load comparable energies and record their uninterpreted semantics."""

    declarations = {
        "units": units,
        "normalization": normalization,
        "strained_side": strained_side,
        "thickness_convention": thickness_convention,
    }
    supplied = {
        name: str(value).strip()
        for name, value in declarations.items()
        if value is not None and str(value).strip()
    }
    if path is None:
        if supplied:
            raise ValueError(
                "InterMatch energy semantics require "
                "--intermatch-elastic-energies."
            )
        return None, None
    missing = [name for name in declarations if name not in supplied]
    if missing:
        raise ValueError(
            "elastic-energy input requires explicit declarations for: "
            + ", ".join(missing)
        )
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"elastic-energy CSV not found: {resolved}")
    energies = _read_elastic_energies(resolved)
    assert energies is not None
    provenance = {
        "schema": ELASTIC_INPUT_SCHEMA,
        "path": str(resolved),
        "sha256": _file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
        "record_count": len(energies),
        "columns": {
            "identifier": "entry_id",
            "elastic_energy": "elastic_energy",
        },
        **supplied,
        "strained_side_reference": (
            "A and B denote the persisted search's surface_a and surface_b"
        ),
        "values_rescaled_by_driver": False,
    }
    return energies, provenance


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str | None:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPOSITORY_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {
        "root": str(REPOSITORY_ROOT),
        "commit": commit,
        "dirty": None if status is None else bool(status),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=DEFAULT_PROJECT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--search-prefix", default=DEFAULT_SEARCH_PREFIX)
    parser.add_argument(
        "--search-name",
        dest="search_names",
        action="append",
        help="Compare one completed search; repeat to replace the default matrix.",
    )
    parser.add_argument(
        "--intermatch-elastic-energies",
        type=Path,
        help="CSV with entry_id and elastic_energy for InterMatch-style selection.",
    )
    parser.add_argument(
        "--intermatch-energy-units",
        help="Units of elastic_energy (recorded verbatim; no conversion is applied).",
    )
    parser.add_argument(
        "--intermatch-energy-normalization",
        help="Energy normalization, for example per source cell or per area.",
    )
    parser.add_argument(
        "--intermatch-strained-side",
        choices=("A", "B"),
        help="Material side strained to the other endpoint in the proxy.",
    )
    parser.add_argument(
        "--intermatch-thickness-convention",
        help="Thickness convention used to convert elasticity to energy.",
    )
    args = parser.parse_args(argv)
    semantic_values = {
        "--intermatch-energy-units": args.intermatch_energy_units,
        "--intermatch-energy-normalization": (
            args.intermatch_energy_normalization
        ),
        "--intermatch-strained-side": args.intermatch_strained_side,
        "--intermatch-thickness-convention": (
            args.intermatch_thickness_convention
        ),
    }
    if args.intermatch_elastic_energies is None:
        unexpected = [name for name, value in semantic_values.items() if value]
        if unexpected:
            parser.error(
                f"{', '.join(unexpected)} require "
                "--intermatch-elastic-energies"
            )
    else:
        missing = [
            name
            for name, value in semantic_values.items()
            if value is None or not str(value).strip()
        ]
        if missing:
            parser.error(
                "--intermatch-elastic-energies also requires "
                + ", ".join(missing)
            )
    return args


def main(argv: Sequence[str] | None = None) -> int:
    from benchmarks.benchmarks.claims._support import (
        write_csv_atomic,
        write_jsonl_atomic,
    )
    from calm import open_project

    args = _parse_args(argv)
    project_dir = args.project_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    names = list(args.search_names or default_search_names(args.search_prefix))
    if len(names) != len(set(names)) or any(not str(name).strip() for name in names):
        raise ValueError("search names must be nonempty and unique")
    if not project_dir.is_dir():
        raise FileNotFoundError(
            f"CALM project not found at {project_dir}. Complete the low-index "
            "workflow first or pass --project-dir."
        )

    energies, elastic_energy_provenance = _load_elastic_energy_input(
        args.intermatch_elastic_energies,
        units=args.intermatch_energy_units,
        normalization=args.intermatch_energy_normalization,
        strained_side=args.intermatch_strained_side,
        thickness_convention=args.intermatch_thickness_convention,
    )
    project = open_project(project_dir, summarize=False)
    ledgers: list[SearchLedger] = []
    assignments: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    selectors: list[dict[str, Any]] = []
    per_search_summaries: list[dict[str, Any]] = []
    method_runs: list[dict[str, Any]] = []
    for name in names:
        print(f"Capturing admitted descriptions: {name}")
        ledger = capture_search_ledger(project, name)
        ledgers.append(ledger)
        local_energies = None
        if energies is not None:
            local_ids = {str(row["entry_id"]) for row in ledger.records}
            missing = sorted(local_ids - energies.keys())
            if missing:
                raise RuntimeError(
                    f"elastic-energy input is missing {len(missing)} entries for "
                    f"{name}; first missing ID: {missing[0]}"
                )
            local_energies = {entry_id: energies[entry_id] for entry_id in local_ids}
        local = classify_ledger(
            ledger,
            elastic_energy_by_id=local_energies,
            elastic_energy_provenance=elastic_energy_provenance,
        )
        assignments.extend(local[0])
        filters.extend(local[1])
        selectors.extend(local[2])
        per_search_summaries.extend(local[3])
        method_runs.extend(local[4])

    if energies is not None:
        ledger_ids = {
            str(record["entry_id"])
            for ledger in ledgers
            for record in ledger.records
        }
        extra = sorted(energies.keys() - ledger_ids)
        if extra:
            raise RuntimeError(
                f"elastic-energy input contains {len(extra)} unknown entry IDs; "
                f"first unknown ID: {extra[0]}"
            )

    over_merges, over_splits = build_relative_split_merge_diagnostics(assignments)
    summaries = aggregate_summaries(per_search_summaries)
    ledger_rows = [dict(record) for ledger in ledgers for record in ledger.records]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl_atomic(output_dir / "raw-match-ledger.jsonl", ledger_rows)
    write_csv_atomic(
        output_dir / "classifier-assignments.csv",
        assignments,
        fieldnames=ASSIGNMENT_FIELDS,
    )
    write_csv_atomic(
        output_dir / "classifier-summary.csv",
        summaries,
        fieldnames=SUMMARY_FIELDS,
    )
    write_csv_atomic(
        output_dir / "over-merges-relative-to-calm.csv",
        over_merges,
        fieldnames=DIAGNOSTIC_FIELDS,
    )
    write_csv_atomic(
        output_dir / "over-splits-relative-to-calm.csv",
        over_splits,
        fieldnames=DIAGNOSTIC_FIELDS,
    )
    write_csv_atomic(
        output_dir / "filter-survivors.csv",
        filters,
        fieldnames=FILTER_FIELDS,
    )
    write_csv_atomic(
        output_dir / "selector-results.csv",
        selectors,
        fieldnames=SELECTOR_FIELDS,
    )
    write_jsonl_atomic(
        output_dir / "method-run-diagnostics.jsonl",
        method_runs,
    )

    metadata = {
        "schema": SUMMARY_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(project_dir),
        "output_dir": str(output_dir),
        "python": platform.python_version(),
        "calm_version": _package_version("calm"),
        "command": list(sys.argv),
        "repository": _git_state(),
        "environment": {
            package: _package_version(package)
            for package in ("numpy", "scipy", "ase", "spglib")
        },
        "search_count": len(ledgers),
        "shared_ledger": "CALM strain- and atom-admitted source descriptions",
        "aggregation_scope": "sum of independent fixed-surface searches",
        "method_metadata": _method_metadata(),
        "intermatch_elastic_energy_input": elastic_energy_provenance,
        "interpretation": {
            "calm": "exact successive equivalence quotients",
            "interoptimus_greedy": (
                "greedy, order-defined fixed-surface 2D analogue clusters"
            ),
            "ogre_style": "heuristic fixed-surface 2D signature clusters",
            "jelver_style": "generation-filter survivors",
            "intermat_source": (
                "current-source selector; not applicable without native ZSL ranks"
            ),
            "intermat_paper_style": "paper-text proxy selection, not classes",
            "intermatch_style": "selected descriptions, not classes",
            "relative_diagnostics": (
                "over-merge and over-split labels are relative to CALM's exact "
                "identity on this shared ledger; they do not establish errors "
                "in native external software"
            ),
            "native_parity": False,
        },
        "searches": [
            {
                "search_name": ledger.name,
                "search_uid": ledger.search_uid,
                "surface_a_uid": ledger.surface_a_uid,
                "surface_b_uid": ledger.surface_b_uid,
                "settings": dict(ledger.settings),
                "point_group_a": _json_native(ledger.point_group_a),
                "point_group_b": _json_native(ledger.point_group_b),
                "surface_symmetry_a": dict(ledger.surface_symmetry_a),
                "surface_symmetry_b": dict(ledger.surface_symmetry_b),
                "trace_context": dict(ledger.trace_context),
                "admitted_descriptions": len(ledger.records),
                "final_calm_classes": ledger.final_class_count,
                "persisted_candidates": ledger.persisted_candidate_count,
                "exact_pair_key_count": len(ledger.rerun_pair_keys),
                "persisted_pair_key_sha256": _value_sha256(
                    sorted(ledger.persisted_pair_keys)
                ),
                "rerun_final_pair_key_sha256": _value_sha256(
                    sorted(ledger.rerun_pair_keys)
                ),
                "persisted_pair_key_set_equals_rerun": True,
                "persisted_audit_admitted": ledger.audit_admitted_count,
                "persisted_identity_reduction": (
                    None
                    if ledger.audit_identity_reduction is None
                    else dict(ledger.audit_identity_reduction)
                ),
            }
            for ledger in ledgers
        ],
        "artifacts": [
            "raw-match-ledger.jsonl",
            "classifier-assignments.csv",
            "classifier-summary.csv",
            "over-merges-relative-to-calm.csv",
            "over-splits-relative-to-calm.csv",
            "filter-survivors.csv",
            "selector-results.csv",
            "method-run-diagnostics.jsonl",
        ],
    }
    (output_dir / "run-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    total_raw = sum(len(ledger.records) for ledger in ledgers)
    total_final = sum(ledger.final_class_count for ledger in ledgers)
    print(f"Captured {total_raw} admitted descriptions across {len(ledgers)} searches.")
    print(f"CALM exact final classes (independent-search sum): {total_final}")
    print(f"Outputs: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
