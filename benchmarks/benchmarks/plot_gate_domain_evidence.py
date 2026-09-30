"""Validate and plot gate-domain principal-strain histogram evidence.

The qualification run owns the seeded candidate generation and fixed-bin count
artifacts.  This module consumes only those persisted CSV/JSON files.  It does
not regenerate candidates and is intentionally independent of manuscript figure
numbering or layout.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .claims._support import write_csv_atomic
from .claims.gate_domain import (
    CALM_GATE_ID,
    TARGET_POPULATION_ID,
    histogram_population_filename,
    manuscript_gate_id,
    GateDomainConfig,
)
from .claims.manifest import sha256_file, write_json_atomic


PLOT_VALIDATION_SCHEMA = "calm.gate_domain_plot_validation/v1"
ACCEPTANCE_SUMMARY_SCHEMA = "calm.gate_acceptance_summary/v1"


@dataclass(frozen=True)
class GateDomainHistogramEvidence:
    """Validated fixed-bin evidence required for gate-domain heat maps."""

    input_root: Path
    config: GateDomainConfig
    edges: np.ndarray
    histograms: Mapping[str, np.ndarray]
    histogram_summary: Mapping[str, Mapping[str, str]]
    confusion_rows: Mapping[str, Mapping[str, str]]
    manifest: Mapping[str, Any]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _config_from_summary(summary: Mapping[str, Any]) -> GateDomainConfig:
    config = summary["config"]
    reference = config["reference_cell"]
    trial = config["trial_domain"]
    calm = config["calm_gate"]
    manuscript = config["manuscript_reduced_parameter_gates"]
    pymatgen = config["pymatgen_native_vector_gate"]
    boundary = config["boundary_suite"]
    histogram = config["principal_strain_histogram"]
    return GateDomainConfig(
        sample_count=int(config["sample_count"]),
        seed=int(config["seed"]),
        chunk_size=int(config["chunk_size"]),
        checkpoints=tuple(int(value) for value in config["checkpoints"]),
        retained_sample_count=int(config["retained_sample_count"]),
        disagreement_examples_per_category=int(
            config["disagreement_examples_per_category"]
        ),
        reference_a=float(reference["a"]),
        reference_b=float(reference["b"]),
        reference_gamma_deg=float(reference["gamma_deg"]),
        maximum_length_perturbation=max(
            abs(float(value)) for value in trial["relative_length_perturbation"]
        ),
        maximum_angle_perturbation_deg=max(
            abs(float(value)) for value in trial["absolute_angle_perturbation_deg"]
        ),
        max_principal_strain=float(calm["max_abs_principal_strain"]),
        calm_gate_tolerance=float(calm["roundoff_tolerance"]),
        manuscript_length_tolerance=float(manuscript["relative_length_tolerance"]),
        manuscript_angle_tolerances_deg=tuple(
            float(value) for value in manuscript["absolute_angle_tolerances_deg"]
        ),
        pymatgen_max_length_tol=float(pymatgen["max_length_tol"]),
        pymatgen_max_angle_tol=float(pymatgen["max_angle_tol"]),
        boundary_inside_offset=float(boundary["inside_offset"]),
        boundary_outside_offset=float(boundary["outside_offset"]),
        boundary_measurement_tolerance=float(boundary["measurement_tolerance"]),
        histogram_bin_count=int(histogram["bin_count_per_axis"]),
        histogram_min_strain=float(histogram["epsilon_1_range"][0]),
        histogram_max_strain=float(histogram["epsilon_1_range"][1]),
    )


def validate_manifest_artifacts(input_root: str | Path) -> dict[str, str]:
    """Verify every artifact recorded by the benchmark manifest."""

    root = Path(input_root).expanduser().resolve()
    manifest_path = root / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validated: dict[str, str] = {}
    for record in manifest["artifacts"]:
        relative = str(record["path"])
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"Manifest artifact is missing: {relative}")
        digest = sha256_file(path)
        if digest != record["sha256"]:
            raise RuntimeError(
                f"Manifest checksum mismatch for {relative}: "
                f"expected {record['sha256']}, observed {digest}"
            )
        validated[relative] = digest
    return validated


def _load_edges(path: Path, bin_count: int) -> np.ndarray:
    rows = _read_csv(path)
    by_axis: dict[str, list[tuple[int, float]]] = {"epsilon_1": [], "epsilon_2": []}
    for row in rows:
        axis = row["axis"]
        if axis not in by_axis:
            raise RuntimeError(f"Unexpected histogram axis: {axis!r}")
        by_axis[axis].append((int(row["edge_index"]), float(row["edge_value"])))
    arrays: dict[str, np.ndarray] = {}
    for axis, values in by_axis.items():
        ordered = sorted(values)
        if [index for index, _ in ordered] != list(range(bin_count + 1)):
            raise RuntimeError(f"Histogram edge indices are incomplete for {axis}")
        arrays[axis] = np.asarray([value for _, value in ordered], dtype=float)
    if not np.array_equal(arrays["epsilon_1"], arrays["epsilon_2"]):
        raise RuntimeError("epsilon_1 and epsilon_2 histogram edges differ")
    if not np.all(np.diff(arrays["epsilon_1"]) > 0.0):
        raise RuntimeError("Histogram edges must be strictly increasing")
    return arrays["epsilon_1"]


def _load_histogram(
    path: Path,
    *,
    population_id: str,
    bin_count: int,
) -> np.ndarray:
    rows = _read_csv(path)
    if len(rows) != bin_count * bin_count:
        raise RuntimeError(
            f"Histogram {path.name} contains {len(rows)} rows; "
            f"expected {bin_count * bin_count}"
        )
    counts = np.zeros((bin_count, bin_count), dtype=np.int64)
    seen: set[tuple[int, int]] = set()
    for row in rows:
        if row["population_id"] != population_id:
            raise RuntimeError(
                f"Histogram {path.name} contains population "
                f"{row['population_id']!r}, expected {population_id!r}"
            )
        bin_i = int(row["bin_i"])
        bin_j = int(row["bin_j"])
        key = (bin_i, bin_j)
        if key in seen:
            raise RuntimeError(f"Duplicate histogram bin in {path.name}: {key}")
        if not (0 <= bin_i < bin_count and 0 <= bin_j < bin_count):
            raise RuntimeError(f"Out-of-range histogram bin in {path.name}: {key}")
        count = int(row["count"])
        if count < 0:
            raise RuntimeError(f"Negative histogram count in {path.name}: {key}")
        counts[key] = count
        seen.add(key)
    return counts


def load_gate_domain_histogram_evidence(
    input_root: str | Path,
) -> GateDomainHistogramEvidence:
    """Load and cross-check one complete gate-domain benchmark output."""

    root = Path(input_root).expanduser().resolve()
    validate_manifest_artifacts(root)
    manifest = json.loads(
        (root / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    domain_summary = json.loads(
        (root / "gate_domain_summary.json").read_text(encoding="utf-8")
    )
    config = _config_from_summary(domain_summary)
    edges = _load_edges(
        root / "principal_strain_histogram_bin_edges.csv",
        config.histogram_bin_count,
    )
    expected_edges = np.linspace(
        config.histogram_min_strain,
        config.histogram_max_strain,
        config.histogram_bin_count + 1,
        dtype=float,
    )
    if not np.array_equal(edges, expected_edges):
        raise RuntimeError("Persisted histogram edges do not match the recorded config")

    summary_rows = _read_csv(root / "principal_strain_histogram_summary.csv")
    summary_by_population = {row["population_id"]: row for row in summary_rows}
    expected_population_ids = (
        TARGET_POPULATION_ID,
        CALM_GATE_ID,
        *(
            manuscript_gate_id(value)
            for value in config.manuscript_angle_tolerances_deg
        ),
    )
    if set(summary_by_population) != set(expected_population_ids):
        raise RuntimeError("Histogram summary populations do not match the config")

    histograms: dict[str, np.ndarray] = {}
    for population_id in expected_population_ids:
        expected_name = histogram_population_filename(config, population_id)
        summary_row = summary_by_population[population_id]
        if summary_row["histogram_file"] != expected_name:
            raise RuntimeError(
                f"Histogram filename mismatch for {population_id!r}: "
                f"{summary_row['histogram_file']!r} != {expected_name!r}"
            )
        counts = _load_histogram(
            root / expected_name,
            population_id=population_id,
            bin_count=config.histogram_bin_count,
        )
        observed = int(np.sum(counts, dtype=np.int64))
        expected = int(summary_row["in_range_count"])
        outside = int(summary_row["out_of_range_count"])
        total = int(summary_row["total_count"])
        if outside != 0 or observed != expected or observed + outside != total:
            raise RuntimeError(f"Histogram accounting mismatch for {population_id!r}")
        histograms[population_id] = counts

    confusion_rows = {
        row["gate_id"]: row for row in _read_csv(root / "gate_confusion_matrix.csv")
    }
    calm_row = confusion_rows[CALM_GATE_ID]
    target_count = int(calm_row["true_positive"]) + int(calm_row["false_negative"])
    if int(np.sum(histograms[TARGET_POPULATION_ID], dtype=np.int64)) != target_count:
        raise RuntimeError(
            "Target histogram does not match the confusion-matrix target"
        )
    for gate_id, counts in histograms.items():
        if gate_id == TARGET_POPULATION_ID:
            continue
        row = confusion_rows[gate_id]
        accepted = int(row["true_positive"]) + int(row["false_positive"])
        if int(np.sum(counts, dtype=np.int64)) != accepted:
            raise RuntimeError(
                f"Histogram accepted count does not match confusion row {gate_id!r}"
            )

    return GateDomainHistogramEvidence(
        input_root=root,
        config=config,
        edges=edges,
        histograms=histograms,
        histogram_summary=summary_by_population,
        confusion_rows=confusion_rows,
        manifest=manifest,
    )


def acceptance_summary_rows(
    evidence: GateDomainHistogramEvidence,
) -> list[dict[str, Any]]:
    """Return the controlled four-row reduced-parameter/CALM comparison."""

    gate_ids = [
        *(
            manuscript_gate_id(value)
            for value in evidence.config.manuscript_angle_tolerances_deg
        ),
        CALM_GATE_ID,
    ]
    rows: list[dict[str, Any]] = []
    for gate_id in gate_ids:
        source = evidence.confusion_rows[gate_id]
        rows.append(
            {
                "schema": ACCEPTANCE_SUMMARY_SCHEMA,
                "gate_id": gate_id,
                "gate_label": source["gate_label"],
                "sample_count": int(source["total"]),
                "accepted_count": int(source["true_positive"])
                + int(source["false_positive"]),
                "accepted_fraction": float(source["accepted_fraction"]),
                "target_retained_count": int(source["true_positive"]),
                "target_retained_fraction": float(source["recall"]),
                "outside_target_accepted_count": int(source["false_positive"]),
                "outside_target_accepted_fraction": float(
                    source["false_positive_rate"]
                ),
            }
        )
    return rows


def render_gate_domain_evidence(
    evidence: GateDomainHistogramEvidence,
    *,
    output_root: str | Path,
    dpi: int = 300,
) -> dict[str, Path]:
    """Render generic heat maps and write their quantitative summary."""

    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import LogNorm
        from matplotlib.patches import Rectangle
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "Plotting requires the CALM plot extra: pip install -e '.[plot]'"
        ) from exc

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = evidence.config
    panel_ids = [
        *(
            manuscript_gate_id(value)
            for value in config.manuscript_angle_tolerances_deg
        ),
        CALM_GATE_ID,
    ]
    panel_titles = [
        *(
            "Reduced-parameter accepted\n"
            rf"$|\Delta\gamma|\leq {value:g}^\circ$"
            for value in config.manuscript_angle_tolerances_deg
        ),
        "CALM accepted",
    ]
    maximum = max(int(np.max(evidence.histograms[gate_id])) for gate_id in panel_ids)
    if maximum <= 0:
        raise RuntimeError("Cannot plot empty gate-domain histograms")

    fig, axes = plt.subplots(
        1,
        len(panel_ids),
        figsize=(15.5, 3.8),
        sharex=True,
        sharey=True,
    )
    image = None
    for axis, gate_id, title in zip(axes, panel_ids, panel_titles, strict=True):
        counts = evidence.histograms[gate_id].T.astype(float)
        counts[counts == 0.0] = np.nan
        image = axis.pcolormesh(
            evidence.edges,
            evidence.edges,
            counts,
            shading="flat",
            norm=LogNorm(vmin=1.0, vmax=float(maximum)),
        )
        threshold = config.max_principal_strain
        axis.add_patch(
            Rectangle(
                (-threshold, -threshold),
                2.0 * threshold,
                2.0 * threshold,
                fill=False,
                linewidth=1.5,
            )
        )
        axis.axhline(0.0, linewidth=0.5)
        axis.axvline(0.0, linewidth=0.5)
        axis.set_title(title, fontsize=10)
        axis.set_xlabel(r"$\varepsilon_1$")
        axis.set_aspect("equal", adjustable="box")
    axes[0].set_ylabel(r"$\varepsilon_2$")
    if image is None:  # pragma: no cover - panel_ids is nonempty by contract
        raise RuntimeError("No heat-map panels were rendered")
    colorbar = fig.colorbar(image, ax=axes, pad=0.02)
    colorbar.set_label("Candidate count")

    png_path = root / "gate_domain_principal_strain_histograms.png"
    pdf_path = root / "gate_domain_principal_strain_histograms.pdf"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    summary_path = write_csv_atomic(
        root / "gate_domain_acceptance_summary.csv",
        acceptance_summary_rows(evidence),
        fieldnames=(
            "schema",
            "gate_id",
            "gate_label",
            "sample_count",
            "accepted_count",
            "accepted_fraction",
            "target_retained_count",
            "target_retained_fraction",
            "outside_target_accepted_count",
            "outside_target_accepted_fraction",
        ),
    )
    validation_path = write_json_atomic(
        root / "gate_domain_plot_validation.json",
        {
            "schema": PLOT_VALIDATION_SCHEMA,
            "status": "passed",
            "input_root": str(evidence.input_root),
            "benchmark_commit": evidence.manifest["repository"]["commit"],
            "benchmark_repository_dirty": evidence.manifest["repository"]["dirty"],
            "histogram_bin_count": config.histogram_bin_count,
            "histogram_range": [
                config.histogram_min_strain,
                config.histogram_max_strain,
            ],
            "panel_gate_ids": panel_ids,
            "outputs": {
                path.name: {
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in (png_path, pdf_path, summary_path)
            },
        },
    )
    return {
        "png": png_path,
        "pdf": pdf_path,
        "acceptance_summary": summary_path,
        "validation": validation_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--dpi", type=int, default=300)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dpi <= 0 or not math.isfinite(float(args.dpi)):
        raise ValueError("dpi must be positive")
    evidence = load_gate_domain_histogram_evidence(args.input_dir)
    outputs = render_gate_domain_evidence(
        evidence,
        output_root=args.outdir,
        dpi=args.dpi,
    )
    print(f"Validated benchmark: {evidence.input_root}")
    for label, path in outputs.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
