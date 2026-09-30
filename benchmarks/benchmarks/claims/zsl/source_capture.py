"""Execute pymatgen ZSL while retaining raw source evidence."""

from __future__ import annotations

import importlib.metadata
import inspect
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...benchmark_pairs import LatticePair2D, basis_to_3d_vectors
from .._support import write_canonical_jsonl_atomic
from ..claim_ids import ClaimId
from ..fixtures import FixtureDescriptor, fixture_descriptor
from ..manifest import (
    artifact_record,
    build_manifest,
    write_json_atomic,
)
from ..schemas import ProjectedMatch, RawExternalMatch
from .raw_adapter import ZSL_CAPTURE_SUMMARY_SCHEMA, capture_raw_zsl_match
from .transformation_reconstruction import reconstruct_zsl_source_pair


GeneratorFactory = Callable[..., Any]


@dataclass(frozen=True)
class ZSLCaptureArtifacts:
    """Paths produced by one source-preserving capture invocation."""

    manifest: Path
    raw_matches: Path
    reconstructions: Path
    summary: Path


def pymatgen_version() -> str:
    try:
        return importlib.metadata.version("pymatgen")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def default_generator_factory(**settings: Any) -> Any:
    """Construct pymatgen's generator without importing it at module import."""

    try:
        from pymatgen.analysis.interfaces.zsl import ZSLGenerator  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "pymatgen is required for ZSL source capture; install pymatgen "
            "and rerun this command"
        ) from exc
    return ZSLGenerator(**settings)


def call_zsl_generator(generator: Any, film_vectors: Any, substrate_vectors: Any) -> list[Any]:
    """Call ZSL across supported vector keyword and positional APIs."""

    try:
        names = list(inspect.signature(generator.__call__).parameters)
        if names and names[0] == "self":
            names = names[1:]
    except (TypeError, ValueError):
        names = []

    if {"film_vectors", "substrate_vectors"}.issubset(names):
        try:
            return list(
                generator(
                    film_vectors=film_vectors,
                    substrate_vectors=substrate_vectors,
                )
            )
        except TypeError:
            pass
    return list(generator(film_vectors, substrate_vectors))


def _format_area(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def _fixture(pair: LatticePair2D) -> FixtureDescriptor:
    family = {
        "rect_small_mismatch": "rectangular",
        "hex_near_degenerate": "near_hexagonal",
        "oblique_tradeoff": "oblique",
    }.get(pair.name, "custom")
    return fixture_descriptor(
        fixture_id=pair.name,
        family=family,
        description=pair.comment or f"ZSL source-capture fixture {pair.name}.",
        basis_A=pair.A,
        basis_B=pair.B,
        claims=(ClaimId.C7_ZSL_COMPARISON,),
        tags=("zsl", "source_capture", "basis_only"),
    )


def _failure_label(projected: ProjectedMatch) -> str:
    reasons = projected.diagnostics.get("failure_reasons", [])
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(reason) for reason in reasons)
    return "unspecified reconstruction failure"


def capture_zsl_sources(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    pairs: Sequence[LatticePair2D],
    max_areas: Sequence[float],
    max_area_ratio_tol: float = 0.09,
    max_length_tol: float = 0.03,
    max_angle_tol: float = 0.01,
    bidirectional: bool = False,
    reconstruction_atol: float = 1.0e-8,
    reconstruction_rtol: float = 1.0e-8,
    generator_factory: GeneratorFactory | None = None,
    tool_version: str | None = None,
) -> ZSLCaptureArtifacts:
    """Capture raw ZSL records and source-transform reconstructions."""

    if not pairs:
        raise ValueError("at least one lattice pair is required")
    if not max_areas or any(float(area) <= 0 for area in max_areas):
        raise ValueError("max_areas must contain positive values")
    if reconstruction_atol < 0 or reconstruction_rtol < 0:
        raise ValueError("reconstruction tolerances must be nonnegative")

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    factory = generator_factory or default_generator_factory
    version = tool_version or pymatgen_version()
    generator_base_settings = {
        "max_area_ratio_tol": float(max_area_ratio_tol),
        "max_length_tol": float(max_length_tol),
        "max_angle_tol": float(max_angle_tol),
        "bidirectional": bool(bidirectional),
    }

    raw_records: list[RawExternalMatch] = []
    reconstruction_records: list[ProjectedMatch] = []
    run_summaries: list[dict[str, Any]] = []
    fixtures = tuple(_fixture(pair) for pair in pairs)

    for pair, descriptor in zip(pairs, fixtures, strict=True):
        film_vectors = basis_to_3d_vectors(pair.A)
        substrate_vectors = basis_to_3d_vectors(pair.B)
        for max_area in max_areas:
            settings = {
                **generator_base_settings,
                "max_area": float(max_area),
            }
            run_id = f"max_area_{_format_area(max_area)}"
            generator = factory(**settings)
            started = time.perf_counter()
            matches = call_zsl_generator(generator, film_vectors, substrate_vectors)
            elapsed = time.perf_counter() - started
            invocation = {
                "run_id": run_id,
                "film_role": "A",
                "substrate_role": "B",
                "basis_vector_storage": "external_rows",
                "input_film_vectors": film_vectors,
                "input_substrate_vectors": substrate_vectors,
            }
            run_raw: list[RawExternalMatch] = []
            run_reconstructions: list[ProjectedMatch] = []
            for raw_index, match in enumerate(matches):
                raw = capture_raw_zsl_match(
                    match,
                    tool_version=version,
                    fixture_id=descriptor.fixture_id,
                    run_id=run_id,
                    raw_index=raw_index,
                    generator_settings=settings,
                    invocation=invocation,
                )
                projected = reconstruct_zsl_source_pair(
                    raw,
                    atol=reconstruction_atol,
                    rtol=reconstruction_rtol,
                )
                raw_records.append(raw)
                reconstruction_records.append(projected)
                run_raw.append(raw)
                run_reconstructions.append(projected)

            failed = [
                projected
                for projected in run_reconstructions
                if projected.status != "reconstructed"
            ]
            run_summaries.append(
                {
                    "fixture_id": descriptor.fixture_id,
                    "run_id": run_id,
                    "max_area": float(max_area),
                    "elapsed_seconds": float(elapsed),
                    "raw_match_count": len(run_raw),
                    "reconstructed_count": len(run_reconstructions) - len(failed),
                    "failed_count": len(failed),
                    "failure_reasons": sorted(
                        {_failure_label(projected) for projected in failed}
                    ),
                }
            )

    raw_path = write_canonical_jsonl_atomic(
        root / "raw_zsl_matches.jsonl",
        (record.to_dict() for record in raw_records),
    )
    reconstruction_path = write_canonical_jsonl_atomic(
        root / "zsl_source_reconstruction.jsonl",
        (record.to_dict() for record in reconstruction_records),
    )
    failed_records = [
        record for record in reconstruction_records if record.status != "reconstructed"
    ]
    summary_payload = {
        "schema": ZSL_CAPTURE_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "claim_id": ClaimId.C7_ZSL_COMPARISON.value,
        "scientific_claim_evaluated": False,
        "tool": "pymatgen_zsl",
        "tool_version": version,
        "generator_base_settings": generator_base_settings,
        "reconstruction_tolerances": {
            "atol": float(reconstruction_atol),
            "rtol": float(reconstruction_rtol),
        },
        "fixture_count": len(fixtures),
        "run_count": len(run_summaries),
        "raw_match_count": len(raw_records),
        "reconstructed_count": len(reconstruction_records) - len(failed_records),
        "failed_count": len(failed_records),
        "all_matches_retained": len(raw_records) == len(reconstruction_records),
        "runs": run_summaries,
        "note": (
            "Source capture and integer reconstruction only; this artifact does "
            "not evaluate the controlled CALM-versus-ZSL manuscript claim."
        ),
    }
    summary_path = write_json_atomic(root / "source_capture_summary.json", summary_payload)

    artifacts = (
        artifact_record(raw_path, relative_to=root, media_type="application/x-ndjson"),
        artifact_record(
            reconstruction_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(summary_path, relative_to=root, media_type="application/json"),
    )
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C7_ZSL_COMPARISON,),
        artifacts=artifacts,
        fixture_hashes={fixture.fixture_id: fixture.sha256() for fixture in fixtures},
        policy_settings={
            "stage": "zsl_source_capture",
            "generator": generator_base_settings,
            "max_areas": [float(area) for area in max_areas],
            "reconstruction": {
                "atol": float(reconstruction_atol),
                "rtol": float(reconstruction_rtol),
            },
        },
    )
    manifest_path = write_json_atomic(root / "benchmark_manifest.json", manifest.to_dict())
    return ZSLCaptureArtifacts(
        manifest=manifest_path,
        raw_matches=raw_path,
        reconstructions=reconstruction_path,
        summary=summary_path,
    )
