"""Pure presentation helpers for the internal project Workspace.

These functions transform current typed project records into display-oriented
rows or text. They do not resolve identifiers, open Units of Work, read the
retired reporting artifacts, or mutate persisted state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Real
from typing import Any

import numpy as np

from .notebook import _ascii_table_value
from ..domain.models import (
    Bulk,
    DerivedInterface,
    FollowupResult,
    PrototypeSummary,
    Slab,
    SlabSummary,
)


def material_name(bulk: Bulk) -> str:
    """Return the compact material token used by Workspace displays."""

    label = bulk.label.strip()
    return label.split()[0] if label else bulk.id_short


def enriched_slab_row(
    summary: SlabSummary,
    *,
    slab: Slab,
    bulk: Bulk,
) -> dict[str, Any]:
    """Project one current slab record into a JSON-friendly display row."""

    miller = tuple(int(value) for value in summary.miller)
    material = material_name(bulk)
    row: dict[str, Any] = {
        "id_short": summary.id_short,
        "bulk_id_short": summary.bulk_id_short,
        "bulk": summary.bulk_id_short,
        "miller": miller,
        "label": f"{material}-{''.join(str(value) for value in miller)}",
        "material": material,
        "calculator": bulk.calculator,
        "area": None,
        "natoms": None,
        "termination": None,
    }

    atoms = slab.atoms
    if atoms is not None:
        cell = atoms.get_cell()
        area = float(np.linalg.norm(np.cross(cell[0], cell[1])))
        row["area"] = round(area, 4)
        row["natoms"] = len(atoms)

    payload = slab.payload or {}
    termination = payload.get("termination")
    if isinstance(termination, Mapping):
        row["termination"] = termination.get("label")
    structure = payload.get("structure")
    if isinstance(structure, Mapping):
        row["area"] = structure.get("area_A2")
        row["natoms"] = structure.get("n_atoms")
    return row


def enriched_prototype_row(
    prototype: PrototypeSummary,
    *,
    slab_a: Slab,
    slab_b: Slab,
    bulk_a: Bulk,
    bulk_b: Bulk,
) -> dict[str, Any]:
    """Project one current prototype summary with exact parent context."""

    material_a = material_name(bulk_a)
    material_b = material_name(bulk_b)
    return {
        "id_short": prototype.id_short,
        "run_id_short": prototype.run_id_short,
        "slab_a_id_short": prototype.slab_a_id_short,
        "slab_b_id_short": prototype.slab_b_id_short,
        "match_score": prototype.match_score,
        "hencky_norm": prototype.hencky_norm,
        "d_cell": prototype.d_cell,
        "interface_area": prototype.interface_area,
        "natoms": prototype.natoms,
        "is_pareto": prototype.is_pareto,
        "pareto_rank": prototype.pareto_rank,
        "pareto_policy": prototype.pareto_policy,
        "pareto_policy_version": prototype.pareto_policy_version,
        "pareto_population_scope": prototype.pareto_population_scope,
        "pareto_population_size": prototype.pareto_population_size,
        "pareto_d_cell_key": prototype.pareto_d_cell_key,
        "pareto_status": prototype.pareto_status,
        "material_a": material_a,
        "material_b": material_b,
        "interface_label": f"{material_a}/{material_b}",
        "slab_a_uid_full": slab_a.uid_full,
        "slab_b_uid_full": slab_b.uid_full,
    }


def enriched_interface_row(interface: DerivedInterface) -> dict[str, Any]:
    """Project one current derived-interface specification for display."""

    shift = interface.registry_shift_frac_a
    shift_list = None if shift is None else [float(shift[0]), float(shift[1])]
    return {
        "id_short": interface.id_short,
        "prototype_uid_full": interface.prototype_uid_full,
        "label": interface.label,
        "stage": interface.stage,
        "strain_alpha": interface.strain_alpha,
        "registry_shift_frac_a": shift_list,
        "registry_shift_str": (
            "N/A" if shift is None else f"[{shift[0]:.4f}, {shift[1]:.4f}]"
        ),
        "z_padding": interface.z_padding,
        "vacuum": interface.vacuum,
        "spec": dict(interface.spec),
    }


def enriched_followup_row(result: FollowupResult) -> dict[str, Any]:
    """Project one current follow-up result into a stable display row."""

    row: dict[str, Any] = {
        "uid_full": result.uid_full,
        "id_short": result.id_short,
        "run_uid_full": result.run_uid_full,
        "run_id_short": result.run_id_short,
        "prototype_uid_full": result.prototype_uid_full,
        "prototype_id_short": result.prototype_id_short,
        "target_uid_full": result.target_uid_full,
        "target_id_short": result.target_id_short,
        "target_kind": result.target_kind,
        "kind": result.kind,
        "status": result.status,
        "best_energy": result.best_energy,
        "param1": result.param1,
        "param2": result.param2,
        "n_points": result.n_points,
        "payload": None if result.payload is None else dict(result.payload),
    }
    row["best_alpha"] = None
    if result.kind == "strain_partition_scan":
        from calm.project.domain.contracts.refinement_result import (
            strain_partition_selection,
        )

        _metric, alpha, _value = strain_partition_selection(result.payload or {})
        row["best_alpha"] = alpha
    return row


def format_mapping_table(
    data: Sequence[Mapping[str, Any]],
    headers: Sequence[str] | None = None,
    *,
    style: str = "grid",
) -> str:
    """Format current mapping rows as a deterministic plain-ASCII table."""

    rows_data = list(data)
    if not rows_data:
        return ""
    if any(not isinstance(row, Mapping) for row in rows_data):
        raise TypeError("Workspace table rows must be mappings.")

    selected_headers = (
        list(rows_data[0].keys())
        if headers is None
        else [str(item) for item in headers]
    )
    rows = [
        [_ascii_table_value(row.get(header, "")) for header in selected_headers]
        for row in rows_data
    ]

    try:
        from tabulate import tabulate
    except ImportError:
        widths = [
            max(
                len(str(header)),
                max(len(str(row[index])) for row in rows),
            )
            for index, header in enumerate(selected_headers)
        ]
        lines = [
            " | ".join(
                str(header).ljust(width)
                for header, width in zip(selected_headers, widths, strict=True)
            ),
            "-+-".join("-" * width for width in widths),
        ]
        lines.extend(
            " | ".join(
                str(value).ljust(width)
                for value, width in zip(row, widths, strict=True)
            )
            for row in rows
        )
        return "\n".join(lines)

    return str(tabulate(rows, headers=selected_headers, tablefmt=style))


def format_payload_mapping(
    payload: Mapping[str, Any] | None,
    *,
    max_list_items: int,
) -> str:
    """Format one current JSON payload mapping for notebook display."""

    if payload is None or not payload:
        return "No payload"
    if isinstance(max_list_items, bool) or not isinstance(max_list_items, int):
        raise TypeError("max_list_items must be a non-negative integer.")
    if max_list_items < 0:
        raise ValueError("max_list_items must be a non-negative integer.")

    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, Mapping):
            lines.append(f"- {key}:")
            for subkey, subvalue in value.items():
                if isinstance(subvalue, Mapping):
                    lines.append(
                        f"  - {subkey}: (mapping with {len(subvalue)} entries)"
                    )
                elif (
                    isinstance(subvalue, (list, tuple))
                    and len(subvalue) > max_list_items
                ):
                    lines.append(f"  - {subkey}: (sequence with {len(subvalue)} items)")
                else:
                    lines.append(f"  - {subkey}: {subvalue}")
        elif isinstance(value, (list, tuple)) and len(value) > max_list_items:
            lines.append(f"- {key}: (sequence with {len(value)} items)")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def strain_partition_plot_series(
    payload: Mapping[str, Any],
    *,
    metric: str | None,
) -> tuple[str, list[float], list[float]]:
    """Return exact-current strain-scan plot data.

    Persisted strain scans contain an exact ``selection`` and a non-empty list
    of mapping rows. Public callers and persisted selections use the same exact
    metric names; historical aliases and tuple rows are rejected.
    """

    from calm.interface.refinement.contract import canonical_strain_metric

    if not isinstance(payload, Mapping):
        raise TypeError("Strain-partition plot payload must be a mapping.")

    selection = payload.get("selection")
    if not isinstance(selection, Mapping):
        raise TypeError("Strain-partition plot payload requires selection mapping.")
    stored_metric = selection.get("metric")
    if not isinstance(stored_metric, str):
        raise TypeError("Strain-partition selection requires string metric.")
    canonical_stored = canonical_strain_metric(stored_metric)
    if stored_metric != canonical_stored:
        raise ValueError(
            "Persisted strain-partition target_metric must use its canonical name."
        )
    selected_metric = (
        canonical_stored if metric is None else canonical_strain_metric(metric)
    )

    points = payload.get("points")
    if not isinstance(points, list) or not points:
        raise ValueError(
            "Strain-partition plot payload requires a non-empty points list."
        )

    alphas: list[float] = []
    values: list[float] = []
    for index, point in enumerate(points):
        if not isinstance(point, Mapping):
            raise TypeError(f"Strain-partition point {index} must be a mapping row.")
        raw_alpha = point.get("alpha")
        raw_value = point.get(selected_metric)
        if isinstance(raw_alpha, bool) or not isinstance(raw_alpha, Real):
            raise TypeError(
                f"Strain-partition point {index} alpha must be a real number."
            )
        if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
            raise TypeError(
                f"Strain-partition point {index} metric {selected_metric!r} "
                "must be a real number."
            )
        alpha = float(raw_alpha)
        value = float(raw_value)
        if not isfinite(alpha) or not isfinite(value):
            raise ValueError(f"Strain-partition point {index} values must be finite.")
        alphas.append(alpha)
        values.append(value)

    return selected_metric, alphas, values


def registry_search_plot_series(
    payload: Mapping[str, Any],
) -> tuple[list[float], list[float]]:
    """Return the exact-current compact registry trace for plotting.

    Current registry writers persist each trace item as an exact mapping with
    ``step``, ``current_score``, and ``best_score``. Historical sequence and
    scalar variants are rejected rather than silently reinterpreted.
    """

    if not isinstance(payload, Mapping):
        raise TypeError("Registry-search plot payload must be a mapping.")
    trace = payload.get("trace")
    if not isinstance(trace, list) or not trace:
        raise ValueError(
            "Registry-search plot payload requires a non-empty trace list."
        )

    steps: list[float] = []
    best_scores: list[float] = []
    for index, item in enumerate(trace):
        if not isinstance(item, Mapping):
            raise TypeError(f"Registry-search trace item {index} must be a mapping.")
        if set(item) != {"step", "current_score", "best_score"}:
            raise ValueError(
                f"Registry-search trace item {index} must use exact current fields."
            )
        raw_step = item["step"]
        raw_best = item["best_score"]
        if (
            isinstance(raw_step, bool)
            or not isinstance(raw_step, Real)
            or isinstance(raw_best, bool)
            or not isinstance(raw_best, Real)
        ):
            raise TypeError(
                f"Registry-search trace item {index} step and best score "
                "must be real numbers."
            )
        step = float(raw_step)
        best = float(raw_best)
        if not isfinite(step) or not isfinite(best):
            raise ValueError(
                f"Registry-search trace item {index} values must be finite."
            )
        steps.append(step)
        best_scores.append(best)

    return steps, best_scores
