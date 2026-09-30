"""End-to-end qualification of the current project-centered CALM public API.

Unlike the synthetic geometry runners, this command creates a fresh project,
generates atomistic surfaces, invokes ``Project.search_interfaces`` through the
supported top-level ``calm`` imports, and verifies that the persisted candidate
population carries complete, unique, versioned coupled-pair identities.

The command requires CALM's science and project-storage dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence


PUBLIC_API_QUALIFICATION_SCHEMA = "calm.public_api_match_qualification/v2"
PUBLIC_MATCH_IMPLEMENTATION = "primitive_coupled_pair_v2"
_REQUIRED_PAIR_IDENTITY_FIELDS = (
    "key_version",
    "primitive_pair_key",
    "pair_symmetry_policy",
    "correspondence_orientation",
    "material_exchange_identified",
)


def _candidate_row(candidate: Any, *, index: int) -> dict[str, Any]:
    to_dict = getattr(candidate, "to_dict", None)
    if not callable(to_dict):
        raise RuntimeError(
            f"public candidate at index {index} does not expose to_dict()"
        )
    row = to_dict()
    if not isinstance(row, dict):
        raise RuntimeError(
            f"public candidate at index {index} did not project to a dictionary"
        )
    return dict(row)


def _validate_candidate_population(
    candidate_records: Sequence[Any],
    *,
    run_uid: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Validate persisted candidate evidence from the supported public API."""

    rows = [
        _candidate_row(candidate, index=index)
        for index, candidate in enumerate(candidate_records)
    ]
    identities: list[dict[str, Any]] = []
    pareto_population_sizes: set[int] = set()
    for index, row in enumerate(rows):
        implementation = row.get("identity_algorithm")
        if implementation != PUBLIC_MATCH_IMPLEMENTATION:
            raise RuntimeError(
                "public candidate did not report the production coupled-v2 "
                f"identity algorithm at index {index}: {implementation!r}"
            )

        candidate_run_uid = row.get("run_uid") or row.get("run_uid_full")
        if str(candidate_run_uid or "") != str(run_uid):
            raise RuntimeError(
                "public candidate is not linked to the authoritative search run "
                f"at index {index}: {candidate_run_uid!r}"
            )

        identities.append(_validate_pair_identity(row.get("pair_identity")))

        population_size = row.get("pareto_population_size")
        if (
            isinstance(population_size, bool)
            or not isinstance(population_size, int)
            or population_size <= 0
        ):
            raise RuntimeError(
                "public candidate is missing authoritative Pareto population "
                f"provenance at index {index}: {population_size!r}"
            )
        pareto_population_sizes.add(int(population_size))

    identity_tokens = {
        json.dumps(identity, separators=(",", ":"), sort_keys=True)
        for identity in identities
    }
    if len(identity_tokens) != len(identities):
        raise RuntimeError(
            "public candidate population contains duplicate exact pair identities"
        )
    if len(pareto_population_sizes) != 1:
        raise RuntimeError(
            "public candidates disagree on the authoritative Pareto population "
            f"size: {sorted(pareto_population_sizes)}"
        )
    pareto_population_size = next(iter(pareto_population_sizes))
    if pareto_population_size < len(rows):
        raise RuntimeError(
            "authoritative Pareto population size is smaller than the retained "
            f"candidate count: {pareto_population_size} < {len(rows)}"
        )
    return rows, identities, pareto_population_size


def _validate_persisted_run(
    run: Any,
    *,
    expected_search_identity: str,
    expected_settings: dict[str, Any],
    expected_surface_uids: dict[str, str],
    candidate_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate identity-bearing run specification and lifecycle progress."""

    spec = dict(getattr(run, "spec", {}) or {})
    progress = dict(getattr(run, "progress", {}) or {})
    if getattr(run, "status", None) != "done":
        raise RuntimeError(
            f"public search run is not complete: {getattr(run, 'status', None)!r}"
        )

    implementation = spec.get("implementation")
    if implementation != PUBLIC_MATCH_IMPLEMENTATION:
        raise RuntimeError(
            "public search run specification did not report the production "
            f"coupled-v2 implementation: {implementation!r}"
        )
    schema_version = spec.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 2
    ):
        raise RuntimeError(
            "public search run specification has an invalid schema version: "
            f"{schema_version!r}"
        )
    if str(spec.get("search_identity") or "") != expected_search_identity:
        raise RuntimeError(
            "public search run specification does not match the persisted "
            "search identity"
        )
    run_settings = spec.get("settings")
    if not isinstance(run_settings, dict) or run_settings != expected_settings:
        raise RuntimeError(
            "public search run specification does not preserve the requested "
            "SearchSettings"
        )

    for field, expected_uid in expected_surface_uids.items():
        surface = spec.get(field)
        if not isinstance(surface, dict) or str(surface.get("uid_full") or "") != str(
            expected_uid
        ):
            raise RuntimeError(
                f"public search run specification has inconsistent {field} identity"
            )

    if progress.get("phase") != "complete":
        raise RuntimeError(
            "public search lifecycle progress is not complete: "
            f"{progress.get('phase')!r}"
        )
    progress_count = progress.get("n_candidates")
    if (
        isinstance(progress_count, bool)
        or not isinstance(progress_count, int)
        or progress_count != candidate_count
    ):
        raise RuntimeError(
            "public search lifecycle candidate count disagrees with persisted "
            f"candidates: {progress_count!r} != {candidate_count}"
        )
    return spec, progress


def _validate_pair_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("public candidate is missing pair_identity")
    missing = [name for name in _REQUIRED_PAIR_IDENTITY_FIELDS if name not in value]
    if missing:
        raise RuntimeError(f"public candidate pair_identity is incomplete: {missing}")

    version = value["key_version"]
    key = value["primitive_pair_key"]
    symmetry = value["pair_symmetry_policy"]
    orientation = value["correspondence_orientation"]
    exchange = value["material_exchange_identified"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise RuntimeError("pair_identity.key_version must be a positive integer")
    if (
        not isinstance(key, (list, tuple))
        or len(key) != 8
        or any(isinstance(entry, bool) or not isinstance(entry, int) for entry in key)
    ):
        raise RuntimeError(
            "pair_identity.primitive_pair_key must contain eight integers"
        )
    if symmetry not in {"proper", "full"}:
        raise RuntimeError("pair_identity.pair_symmetry_policy is invalid")
    if orientation not in {"proper", "all"}:
        raise RuntimeError("pair_identity.correspondence_orientation is invalid")
    if not isinstance(exchange, bool):
        raise RuntimeError(
            "pair_identity.material_exchange_identified must be a boolean"
        )
    return {
        "key_version": int(version),
        "primitive_pair_key": [int(entry) for entry in key],
        "pair_symmetry_policy": str(symmetry),
        "correspondence_orientation": str(orientation),
        "material_exchange_identified": bool(exchange),
    }


def pair_identity_digest(identities: Sequence[dict[str, Any]]) -> str:
    """Return a deterministic digest of complete public pair identities."""

    ordered = sorted(
        identities,
        key=lambda item: (
            item["key_version"],
            tuple(item["primitive_pair_key"]),
            item["pair_symmetry_policy"],
            item["correspondence_orientation"],
            item["material_exchange_identified"],
        ),
    )
    payload = json.dumps(ordered, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def run_public_api_qualification(
    *,
    project_path: str | Path,
    structure_a: str | Path,
    structure_b: str | Path,
    material_a: str = "benchmark_LiF",
    material_b: str = "benchmark_Li2O",
    termination_a: str = "LiF",
    termination_b: str = "O",
    termination_shift_a: int = 0,
    termination_shift_b: int = 1,
    max_principal_strain: float = 0.15,
    max_supercell_index: int = 5,
    max_atoms: int = 1000,
    max_candidates: int = 500,
    mismatch_weight: float = 0.5,
    reset: bool = False,
) -> dict[str, Any]:
    """Run a fresh public workflow and return its qualification summary."""

    # These are intentionally the only CALM imports in the benchmark workflow.
    import calm
    from calm import Material, SearchSettings, open_project

    for retired_name in ("Surface", "search_interfaces"):
        if hasattr(calm, retired_name):
            raise RuntimeError(
                f"retired top-level public entry point calm.{retired_name} is present"
            )

    project_dir = Path(project_path)
    if reset and project_dir.exists():
        shutil.rmtree(project_dir)
    if project_dir.exists():
        raise FileExistsError(
            f"qualification project already exists: {project_dir}; use --reset"
        )

    path_a = Path(structure_a)
    path_b = Path(structure_b)
    if not path_a.is_file() or not path_b.is_file():
        raise FileNotFoundError(
            f"qualification structures not found: {path_a}, {path_b}"
        )

    project = open_project(project_dir)
    project.add_material(
        Material.from_file(path_a, name=material_a),
        name=material_a,
    )
    project.add_material(
        Material.from_file(path_b, name=material_b),
        name=material_b,
    )
    project.generate_surfaces(
        [material_a, material_b],
        millers=[(1, 0, 0)],
        layers=4,
        vacuum=15.0,
    )

    surface_a = project.surface(
        material=material_a,
        miller=(1, 0, 0),
        termination=termination_a,
        termination_shift=int(termination_shift_a),
    )
    surface_b = project.surface(
        material=material_b,
        miller=(1, 0, 0),
        termination=termination_b,
        termination_shift=int(termination_shift_b),
    )
    settings = SearchSettings(
        max_principal_strain=float(max_principal_strain),
        max_supercell_index=int(max_supercell_index),
        max_atoms=int(max_atoms),
        max_candidates=int(max_candidates),
        mismatch_weight=float(mismatch_weight),
        surface_symmetry_mode="discover",
    )
    search = project.search_interfaces(
        surface_a,
        surface_b,
        settings=settings,
        name="public_api_lattice_match_qualification",
        resume=False,
    )
    if search.empty:
        raise RuntimeError(search.explain())

    run_uid = getattr(search.record, "run_uid_full", None)
    if not run_uid:
        raise RuntimeError("persisted search is missing its authoritative run UID")
    run = project.run(str(run_uid))
    candidate_records = search.candidates().records()
    _, identities, pareto_population_size = _validate_candidate_population(
        candidate_records,
        run_uid=str(run_uid),
    )
    search_identity = str(getattr(search.record, "search_identity", None) or "")
    if not search_identity:
        raise RuntimeError("persisted search is missing its scientific identity")
    expected_surface_uids = {
        "surface_a": str(getattr(surface_a, "project_slab_uid_full", None) or ""),
        "surface_b": str(getattr(surface_b, "project_slab_uid_full", None) or ""),
    }
    if not all(expected_surface_uids.values()):
        raise RuntimeError(
            "project-selected qualification surfaces are missing authoritative UIDs"
        )
    run_spec, progress = _validate_persisted_run(
        run,
        expected_search_identity=search_identity,
        expected_settings=settings.to_dict(),
        expected_surface_uids=expected_surface_uids,
        candidate_count=len(candidate_records),
    )
    implementation = str(run_spec["implementation"])

    key_versions = sorted({identity["key_version"] for identity in identities})
    policies = sorted(
        {
            (
                identity["pair_symmetry_policy"],
                identity["correspondence_orientation"],
                identity["material_exchange_identified"],
            )
            for identity in identities
        }
    )
    return {
        "schema": PUBLIC_API_QUALIFICATION_SCHEMA,
        "implementation": implementation,
        "project_path": str(project_dir),
        "public_entry_point": "Project.search_interfaces",
        "retired_top_level_entry_points_absent": True,
        "settings": settings.to_dict(),
        "search_name": search.name,
        "search_identity": search_identity,
        "search_run_uid": str(run_uid),
        "search_status": run.status,
        "run_spec_schema_version": int(run_spec["schema_version"]),
        "run_progress_phase": str(progress["phase"]),
        "run_progress_candidate_count": int(progress["n_candidates"]),
        "candidate_count": len(candidate_records),
        "candidate_identity_algorithm": PUBLIC_MATCH_IMPLEMENTATION,
        "pair_key_versions": key_versions,
        "pair_identity_policies": [list(policy) for policy in policies],
        "pair_identity_sha256": pair_identity_digest(identities),
        "surface_symmetry_mode": run_spec["settings"]["surface_symmetry_mode"],
        "resolved_surface_symmetry_status": (
            "qualified_by_coupled_kernel_not_duplicated_in_public_run_progress"
        ),
        "pareto_population_size": pareto_population_size,
        "retained_count": len(candidate_records),
    }


def _default_structure_path(name: str) -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    return repository_root / "examples" / "Structures" / name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify the current project-centered CALM public search API."
    )
    parser.add_argument("--project", default="public_api_qualification.calm")
    parser.add_argument("--out", default="public_api_qualification.json")
    parser.add_argument(
        "--structure-a",
        default=str(_default_structure_path("LiF.poscar")),
    )
    parser.add_argument(
        "--structure-b",
        default=str(_default_structure_path("Li2O.poscar")),
    )
    parser.add_argument("--max-principal-strain", type=float, default=0.15)
    parser.add_argument("--max-supercell-index", type=int, default=5)
    parser.add_argument("--max-atoms", type=int, default=1000)
    parser.add_argument("--max-candidates", type=int, default=500)
    parser.add_argument("--mismatch-weight", type=float, default=0.5)
    parser.add_argument("--reset", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_public_api_qualification(
        project_path=args.project,
        structure_a=args.structure_a,
        structure_b=args.structure_b,
        max_principal_strain=args.max_principal_strain,
        max_supercell_index=args.max_supercell_index,
        max_atoms=args.max_atoms,
        max_candidates=args.max_candidates,
        mismatch_weight=args.mismatch_weight,
        reset=args.reset,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote public API qualification summary to: {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
