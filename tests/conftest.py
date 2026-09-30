"""Pytest configuration, warning hygiene, and coarse test-tier markers.

This repository intentionally emits a small number of *user-facing* warnings in
edge/fallback paths (for example, reference-frame or surface-cell
canonicalization fallbacks). Those warnings are important for interactive use,
but they create noise in tests where we deliberately exercise those paths.

The warning policy is intentionally data-driven. Every accepted test warning
filter must be narrow, message-specific, tier-scoped, and carry its rationale in
``EXPECTED_TEST_WARNING_FILTERS``. Repository tests guard that contract so warning
filters do not become broad global ignores. Unasserted warnings are errors by
default; accepted filters are installed only while a test with a declared matching
tier is running.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import warnings

import pytest

from calm.project.domain.identity_v2 import (
    is_persisted_uid_v2,
    persisted_entity_uid_v2,
)


def _persisted_test_uid(entity_kind: str, token: str) -> str:
    """Return a deterministic current-format UID for non-identity tests."""

    return persisted_entity_uid_v2(
        entity_kind,
        {"test_token": str(token)},
    )


def _current_test_uid(entity_kind: str, value: str) -> str:
    if is_persisted_uid_v2(value, entity_kind=entity_kind):
        return value
    return _persisted_test_uid(entity_kind, value)


@pytest.fixture
def persisted_test_uid():
    """Build deterministic current-format persisted UIDs in tests."""

    return _persisted_test_uid


# Directory-based markers are used for the strongest test-suite tiers. They are
# intentionally coarse: individual tests may still add more specific markers.
TEST_PATH_MARKER_RULES: tuple[tuple[str, str], ...] = (
    ("tests/architecture/", "arch"),
    ("tests/repository/", "repository"),
    ("tests/public/", "public"),
    ("tests/examples/", "examples"),
    ("tests/slab/", "slab"),
    ("tests/integration/", "integration"),
    ("tests/integration/project/", "project"),
    ("tests/unit/", "unit"),
    ("tests/unit/interface/", "interface"),
    ("tests/unit/slab/", "slab"),
)

# Filename-based markers cover established root-level test families that have
# not yet been physically moved into tier directories.
TEST_FILENAME_MARKER_RULES: tuple[tuple[str, str], ...] = (
    ("test_examples_", "examples"),
    ("test_calculator", "calculators"),
    ("test_calculators", "calculators"),
    ("test_project_", "project"),
    ("test_schema_", "project"),
    ("test_tilt_metadata_", "project"),
    ("test_transaction_", "project"),
    ("test_workspace_", "project"),
    ("test_slab_", "slab"),
    ("test_oriented_slab_", "slab"),
    ("test_surface_", "slab"),
    ("test_interface_", "interface"),
    ("test_interfacial_", "interface"),
    ("test_registry_search_", "interface"),
    ("test_strain_", "interface"),
)


@dataclass(frozen=True)
class WarningFilterRule:
    """Documented warning filter installed for the test suite."""

    rule_id: str
    action: str
    message: str
    category: type[Warning]
    tiers: tuple[str, ...]
    reason: str


EXPECTED_TEST_WARNING_FILTERS: tuple[WarningFilterRule, ...] = (
    WarningFilterRule(
        rule_id="reference-frame-fallback",
        action="ignore",
        message=r"get_ortho_map: falling back to slab cell-vector basis .*",
        category=Warning,
        tiers=("slab", "interface"),
        reason=(
            "Reference-frame fallback warnings are intentionally exercised by "
            "selected guardrail tests. The fallback remains user-visible in "
            "normal use, but the repeated test warning is expected."
        ),
    ),
    WarningFilterRule(
        rule_id="surface-cell-handedness-auto-repair",
        action="ignore",
        message=r"canonical_gauss_reduce_2d: input 2D basis is left-handed.*",
        category=Warning,
        tiers=("slab", "interface", "examples"),
        reason=(
            "The 2D handedness warning documents deterministic auto-repair. "
            "Several smoke paths intentionally exercise this repair behavior."
        ),
    ),

    WarningFilterRule(
        rule_id="third-lattice-vector-xy-preservation",
        action="ignore",
        message=r"Third lattice vector has non-negligible xy components; not zeroing to preserve lattice geometry\.",
        category=UserWarning,
        tiers=("slab",),
        reason=(
            "Selected slab geometry tests intentionally exercise skew cells where "
            "the third lattice vector has in-plane components. The warning records "
            "that CALM preserves the geometry rather than silently zeroing it."
        ),
    ),

)


def _normalise_test_path(path: str | Path) -> str:
    """Return a slash-normalized path fragment for marker rules."""

    return Path(str(path)).as_posix()


def markers_for_test_path(path: str | Path) -> set[str]:
    """Return automatic coarse test-tier markers for a test path."""

    p = _normalise_test_path(path)
    marker_names: set[str] = set()

    for fragment, marker_name in TEST_PATH_MARKER_RULES:
        if f"/{fragment}" in f"/{p}":
            marker_names.add(marker_name)

    name = Path(p).name
    for prefix, marker_name in TEST_FILENAME_MARKER_RULES:
        if name.startswith(prefix):
            marker_names.add(marker_name)

    return marker_names


def _dependency_is_unavailable(module_name: str) -> bool:
    """Return whether an optional test dependency is unavailable."""

    return importlib.util.find_spec(module_name) is None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Attach coarse tier markers and optional-dependency skips."""

    sqlalchemy_missing = _dependency_is_unavailable("sqlalchemy")
    sqlalchemy_skip = pytest.mark.skip(reason="SQLAlchemy is required for project-persistence tests")

    for item in items:
        marker_names = markers_for_test_path(item.fspath)
        for marker_name in sorted(marker_names):
            item.add_marker(getattr(pytest.mark, marker_name))
        if sqlalchemy_missing and "project" in marker_names:
            item.add_marker(sqlalchemy_skip)


def warning_filters_for_markers(marker_names: set[str]) -> tuple[WarningFilterRule, ...]:
    """Return warning filters authorized for the supplied test-tier markers."""

    return tuple(
        rule
        for rule in EXPECTED_TEST_WARNING_FILTERS
        if marker_names.intersection(rule.tiers)
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    """Apply accepted warning filters only to tests in their declared tiers."""

    del nextitem
    marker_names = {marker.name for marker in item.iter_markers()}
    rules = warning_filters_for_markers(marker_names)

    with warnings.catch_warnings():
        for rule in rules:
            warnings.filterwarnings(
                rule.action,
                message=rule.message,
                category=rule.category,
            )
        yield


@pytest.fixture
def sqlite_uow_factory(tmp_path: Path):
    """Return a factory for fully initialized project SQLite UoWs.

    Each call opens the same temporary database path unless a different filename
    is supplied, matching the repeated helper pattern used by integration and
    public-workflow tests.
    """

    def factory(filename: str = "calm.sqlite"):
        from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork

        return SqlAlchemyUnitOfWork.from_sqlite_path(str(tmp_path / filename))

    return factory


@pytest.fixture
def schema_uow_factory(tmp_path: Path):
    """Return a factory for schema-only SQLite UoWs used by repository tests."""

    engines = []

    def factory(filename: str = "db.sqlite"):
        from sqlalchemy import create_engine

        from calm.project.infrastructure.db.tables import metadata
        from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork

        engine = create_engine(f"sqlite:///{tmp_path / filename}")
        engines.append(engine)
        metadata.create_all(engine)
        return SqlAlchemyUnitOfWork(engine)

    yield factory

    for engine in engines:
        engine.dispose()


@pytest.fixture
def current_atoms_payload_factory():
    """Build fresh exact-current serialized atom structures."""

    from current_structure_fixtures import current_atoms_payload

    return current_atoms_payload


@pytest.fixture
def hydrogen_atoms_payload_factory():
    """Return a factory for the canonical one-atom periodic test payload."""

    pytest.importorskip("ase")
    from ase import Atoms

    from calm.structure.payloads import atoms_to_dict

    def factory() -> dict[str, object]:
        atoms = Atoms(
            "H",
            positions=[[0, 0, 0]],
            cell=[[3, 0, 0], [0, 3, 0], [0, 0, 3]],
            pbc=True,
        )
        from calm.slab.oriented.tilt import compute_slab_tilt_metadata

        atoms.info["calm:tilt"] = compute_slab_tilt_metadata(
            atoms,
            transforms=None,
        )
        return {"atoms": atoms_to_dict(atoms)}

    return factory


@pytest.fixture
def prototype_payload_factory():
    """Return fresh current coupled-v2 prototype payloads for graph tests."""

    def factory(
        *,
        include_supercells: bool = False,
        include_pareto: bool = True,
        prototype_uid: str = "proto:x",
        slab_a_uid: str = "slab:a",
        slab_b_uid: str = "slab:b",
    ) -> dict[str, object]:
        if not include_supercells:
            return {}
        identity = [[1, 0], [0, 1]]
        supercell = {
            "k": 1,
            "N_tot": identity,
            "R_sup": [[1.0, 0.0], [0.0, 1.0]],
            "hnf_key_pg": [1, 0, 0, 1],
            "cond": 1.0,
            "S_red": [[1.0, 0.0], [0.0, 1.0]],
            "G_red": [[1.0, 0.0], [0.0, 1.0]],
            "gauge_orientation": "proper",
        }
        pareto = None
        if include_pareto:
            from calm.analysis.pareto import (
                authoritative_pareto_metadata,
                canonical_d_cell_key,
            )

            pareto = authoritative_pareto_metadata(
                is_member=True,
                rank=0,
                population_size=1,
                d_cell_key=canonical_d_cell_key(0.0),
            )

        return {
            "schema": "calm.interface_prototype_build_payload/v2",
            "identity_algorithm": "primitive_coupled_pair_v2",
            "interface_prototype_uid": prototype_uid,
            "slab_a_uid": slab_a_uid,
            "slab_b_uid": slab_b_uid,
            "miller_a": [0, 0, 1],
            "miller_b": [0, 0, 1],
            "supercell_a": dict(supercell),
            "supercell_b": dict(supercell),
            "pair_identity": {
                "key_version": 1,
                "primitive_pair_key": [1, 0, 0, 1, 1, 0, 0, 1],
                "pair_symmetry_policy": "full",
                "correspondence_orientation": "proper",
                "material_exchange_identified": False,
            },
            "source_provenance": {
                "source_count": 1,
                "minimum_source_indices": [1, 1],
                "source_index_pairs": [[1, 1]],
                "repeat_indices": [1],
                "representative_source_H_A": identity,
                "representative_source_H_B": identity,
                "representative_source_N_A": identity,
                "representative_source_N_B": identity,
                "representative_correspondence_U_B": identity,
                "representative_source_pair_matrix": [
                    [1, 0],
                    [0, 1],
                    [1, 0],
                    [0, 1],
                ],
                "representative_source_right_factor": identity,
            },
            "metrics": {
                "match_score": 0.0,
                "d_size": 0.0,
                "d_cell": 0.0,
                "d_area": 0.0,
                "d_shape": 0.0,
                "rel_da": 0.0,
                "rel_db": 0.0,
                "d_gamma_deg": 0.0,
                "n_atoms_interface": 2,
                "interface_area_A2": 1.0,
            },
            "pareto": pareto,
        }

    return factory


@pytest.fixture
def prototype_graph_factory(sqlite_uow_factory):
    """Seed a minimal bulk/slab/run/prototype persistence graph.

    This fixture performs only low-level repository setup. It deliberately does
    not invoke buildability, orchestration, public API, or workflow behavior.
    Callers retain control over deterministic identifier tokens, missing slab
    records, and every persisted payload so malformed and edge-case graphs
    remain explicit. Non-v2 tokens are converted to deterministic current-format
    UIDs before insertion.
    """

    def factory(
        *,
        filename: str = "calm.sqlite",
        bulk_uid_full: str = "bulk:1",
        bulk_id_short: str = "b1",
        bulk_payload: dict[str, object] | None = None,
        slab_a_uid_full: str = "slab:a",
        slab_a_id_short: str = "s_a",
        slab_a_payload: dict[str, object] | None = None,
        create_slab_a: bool = True,
        slab_b_uid_full: str = "slab:b",
        slab_b_id_short: str = "s_b",
        slab_b_payload: dict[str, object] | None = None,
        create_slab_b: bool = True,
        run_uid_full: str = "run:1",
        run_id_short: str = "r1",
        run_type: str = "prototype",
        run_status: str = "done",
        run_spec: dict[str, object] | None = None,
        search_name: str | None = None,
        search_identity: str | None = None,
        prototype_uid_full: str = "proto:x",
        prototype_id_short: str = "p_x",
        prototype_payload: dict[str, object] | None = None,
    ):
        from collections.abc import Mapping

        from calm.project.domain.contracts.slab_record import (
            SLAB_RECORD_SCHEMA,
            canonical_miller,
            canonical_slab_record_payload,
        )
        from calm.project.domain.models import Slab
        from calm.project.infrastructure.db.tables import (
            bulks,
            interface_searches,
            prototypes,
            runs,
        )
        from slab_record_fixtures import current_slab_payload, current_slab_uid

        slab_a_token = str(slab_a_uid_full)
        slab_b_token = str(slab_b_uid_full)
        bulk_uid_full = _current_test_uid("bulk", bulk_uid_full)
        run_uid_full = _current_test_uid("run", run_uid_full)
        prototype_uid_full = _current_test_uid(
            "prototype",
            prototype_uid_full,
        )
        run_spec_out = dict(run_spec or {})
        if search_name is not None:
            if run_type != "prototype_search":
                raise ValueError(
                    "Named interface-search fixtures require run_type="
                    "'prototype_search'."
                )
            if "name" in run_spec_out:
                raise ValueError(
                    "Current interface-search names are stored outside run specs."
                )
            search_identity = str(
                search_identity
                or run_spec_out.get("search_identity")
                or f"search:test:{search_name}"
            )
            run_spec_out["search_identity"] = search_identity

        def _surface_descriptor(name: str) -> dict[str, object]:
            raw = run_spec_out.get(name)
            return dict(raw) if isinstance(raw, Mapping) else {}

        def _current_slab(
            *,
            token: str,
            id_short: str,
            raw_payload: dict[str, object] | None,
            descriptor: dict[str, object],
        ) -> tuple[Slab, tuple[int, int, int]]:
            miller_raw = descriptor.get("miller", (0, 0, 1))
            miller = canonical_miller(miller_raw)
            source = dict(raw_payload or {})
            if source.get("schema") == SLAB_RECORD_SCHEMA:
                user_payload = dict(source.get("user_payload") or {})
                user_payload.setdefault("fixture_token", token)
                source["user_payload"] = user_payload
                payload_out = canonical_slab_record_payload(
                    source,
                    bulk_uid_full=bulk_uid_full,
                    miller=miller,
                )
            else:
                atoms_raw = source.get("atoms")
                if atoms_raw is not None and not isinstance(atoms_raw, Mapping):
                    raise TypeError("Fixture slab atoms must be a mapping.")
                termination = (
                    None
                    if descriptor.get("termination") is None
                    else str(descriptor["termination"])
                )
                payload_out = current_slab_payload(
                    bulk_uid_full=bulk_uid_full,
                    miller=miller,
                    label=termination,
                    shift=int(descriptor.get("termination_shift", 0)),
                    top=termination,
                    bottom=termination,
                    atoms=(
                        None
                        if atoms_raw is None
                        else dict(atoms_raw)
                    ),
                    user_payload={"fixture_token": token},
                )
            uid_full = current_slab_uid(
                bulk_uid_full=bulk_uid_full,
                miller=miller,
                payload=payload_out,
            )
            return (
                Slab(
                    uid_full=uid_full,
                    id_short=id_short,
                    bulk_uid_full=bulk_uid_full,
                    bulk_id_short=bulk_id_short,
                    miller=miller,
                    payload=payload_out,
                ),
                miller,
            )

        slab_a, miller_a = _current_slab(
            token=slab_a_token,
            id_short=slab_a_id_short,
            raw_payload=slab_a_payload,
            descriptor=_surface_descriptor("surface_a"),
        )
        slab_b, miller_b = _current_slab(
            token=slab_b_token,
            id_short=slab_b_id_short,
            raw_payload=slab_b_payload,
            descriptor=_surface_descriptor("surface_b"),
        )
        slab_a_uid_full = slab_a.uid_full
        slab_b_uid_full = slab_b.uid_full

        for name, slab, miller in (
            ("surface_a", slab_a, miller_a),
            ("surface_b", slab_b, miller_b),
        ):
            if name not in run_spec_out:
                continue
            descriptor = _surface_descriptor(name)
            descriptor["uid_full"] = slab.uid_full
            descriptor["id_short"] = slab.id_short
            descriptor["miller"] = list(miller)
            run_spec_out[name] = descriptor

        prototype_payload_out = dict(prototype_payload or {})
        for key, value in (
            ("interface_prototype_uid", prototype_uid_full),
            ("prototype_uid", prototype_uid_full),
            ("slab_a_uid", slab_a_uid_full),
            ("slab_b_uid", slab_b_uid_full),
        ):
            if key in prototype_payload_out:
                prototype_payload_out[key] = value

        metrics = prototype_payload_out.get("metrics")
        if not isinstance(metrics, Mapping):
            metrics = {}
        pareto = prototype_payload_out.get("pareto")
        if not isinstance(pareto, Mapping):
            pareto = {}
        d_cell = metrics.get("d_cell")

        uow = sqlite_uow_factory(filename)
        with uow as uw:
            uw.connection.execute(
                bulks.insert().values(
                    uid_full=bulk_uid_full,
                    id_short=bulk_id_short,
                    payload_json=json.dumps(bulk_payload or {}),
                )
            )
            if create_slab_a:
                uw.slabs.create_many([slab_a])
            if create_slab_b:
                uw.slabs.create_many([slab_b])
            uw.connection.execute(
                runs.insert().values(
                    uid_full=run_uid_full,
                    id_short=run_id_short,
                    run_type=run_type,
                    status=run_status,
                    spec_json=json.dumps(run_spec_out),
                )
            )
            if search_name is not None:
                uw.connection.execute(
                    interface_searches.insert().values(
                        name=search_name,
                        search_identity=search_identity,
                        run_uid_full=run_uid_full,
                    )
                )
            uw.connection.execute(
                prototypes.insert().values(
                    uid_full=prototype_uid_full,
                    id_short=prototype_id_short,
                    run_uid_full=run_uid_full,
                    slab_a_uid_full=slab_a_uid_full,
                    slab_b_uid_full=slab_b_uid_full,
                    match_score=metrics.get("match_score"),
                    hencky_norm=(
                        None if d_cell is None else 0.5 * float(d_cell)
                    ),
                    interface_area=metrics.get("interface_area_A2"),
                    n_atoms=metrics.get("n_atoms_interface"),
                    is_pareto=bool(pareto.get("is_member", False)),
                    pareto_rank=pareto.get("rank"),
                    payload_json=json.dumps(prototype_payload_out),
                )
            )
        return uow

    return factory


@pytest.fixture
def stub_authoritative_registry_evaluator(monkeypatch):
    """Replace atomistic registry evaluation in orchestration-only tests.

    These tests exercise persistence, resume, and provenance rather than an
    interatomic calculator.  The real workflow still requires calculator
    provenance; the fixture supplies a resolved token and a deterministic
    finite trajectory at the orchestration boundary.
    """

    from calm.interface.refinement.contract import stable_registry_seed
    from calm.calculators.spec import CalculatorSpec
    from calm.interface.refinement.registry import (
        PERSISTED_REGISTRY_SCORE_UNITS,
        monte_carlo_registry_search,
    )
    from calm.project.application.followups import registry_search as module

    calculator_spec = CalculatorSpec(
        family="test",
        model="orchestration-fixture",
        device="cpu",
    )
    monkeypatch.setattr(
        module,
        "require_calculator_from_prototype",
        lambda _uow, _prototype_uid: calculator_spec,
    )

    def fake_trace(
        _self,
        *,
        base,
        n_steps,
        prototype_uid_full,
        calc_spec,
        alpha=0.5,
        translation0=(0.0, 0.0),
        z_padding=1.5,
        vacuum_padding=None,
        step_scale=0.08,
        temperature=0.03,
        seed=None,
    ):
        del (
            prototype_uid_full,
            calc_spec,
            alpha,
            z_padding,
            vacuum_padding,
        )
        actual_seed = stable_registry_seed(base) if seed is None else int(seed)
        return monte_carlo_registry_search(
            lambda _translation: -2.5,
            x0=translation0,
            n_steps=int(n_steps),
            step_scale=float(step_scale),
            temperature=float(temperature),
            seed=actual_seed,
            keep_trace=True,
            score_units=PERSISTED_REGISTRY_SCORE_UNITS,
        )

    monkeypatch.setattr(
        module.RegistrySearchOrchestrator,
        "_compute_monte_carlo_trace",
        fake_trace,
    )
