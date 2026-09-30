from __future__ import annotations

from copy import deepcopy

import pytest

from benchmarks.benchmarks.claims.public_api_parity import (
    PUBLIC_API_PARITY_COMPARISON_SCHEMA,
    PUBLIC_API_PARITY_INVENTORY_SCHEMA,
    PublicApiParityConfig,
    build_inventory,
    compare_inventories,
    default_public_api_fixtures,
    normalize_scientific_record,
    select_public_api_fixtures,
)


def _pair_identity(key: list[int] | None = None) -> dict[str, object]:
    return {
        "key_version": 1,
        "primitive_pair_key": key or [1, 0, 0, 1, 1, 0, 0, 1],
        "pair_symmetry_policy": "full",
        "correspondence_orientation": "proper",
        "material_exchange_identified": False,
    }


def _supercell(*, k: int = 1) -> dict[str, object]:
    return {
        "k": k,
        "N_tot": [[1, 0], [0, 1]],
        "R_sup": [[1.0, 0.0], [0.0, 1.0]],
        "hnf_key_pg": [1, 0, 0, 1],
        "cond": 1.0,
        "S_red": [[1.0, 0.0], [0.0, 1.0]],
        "G_red": [[1.0, 0.0], [0.0, 1.0]],
        "gauge_orientation": "proper",
    }


def _source_provenance() -> dict[str, object]:
    return {
        "source_count": 1,
        "minimum_source_indices": [1, 1],
        "source_index_pairs": [[1, 1]],
        "repeat_indices": [1],
        "representative_source_H_A": [[1, 0], [0, 1]],
        "representative_source_H_B": [[1, 0], [0, 1]],
        "representative_source_N_A": [[1, 0], [0, 1]],
        "representative_source_N_B": [[1, 0], [0, 1]],
        "representative_correspondence_U_B": [[1, 0], [0, 1]],
        "representative_source_pair_matrix": [
            [1, 0],
            [0, 1],
            [1, 0],
            [0, 1],
        ],
        "representative_source_right_factor": [[1, 0], [0, 1]],
    }


def _row(
    *,
    key: list[int] | None = None,
    score: float = 0.1,
    prototype_uid: str = "proto:v3:test",
) -> dict[str, object]:
    return {
        "identity_algorithm": "primitive_coupled_pair_v2",
        "pair_identity": _pair_identity(key),
        "prototype_uid": prototype_uid,
        "slab_a_uid": "slab:v2:a",
        "slab_b_uid": "slab:v2:b",
        "supercell_a": _supercell(),
        "supercell_b": _supercell(),
        "source_provenance": _source_provenance(),
        "score": score,
        "d_cell": 0.02,
        "d_area": 0.01,
        "d_shape": 0.015,
        "d_size": 0.3,
        "rel_da": 0.001,
        "rel_db": 0.002,
        "d_gamma_deg": 0.1,
        "n_atoms_interface": 20,
        "is_pareto": True,
        "pareto_rank": 0,
        "pareto_policy": "strain_size_pareto",
        "pareto_policy_version": 1,
        "pareto_population_scope": "complete_admitted_population",
        "pareto_population_size": 1,
        "pareto_d_cell_key": 20000000,
    }


def test_normalize_scientific_record_accepts_direct_and_persisted_payload_shapes(
) -> None:
    direct = _row()
    payload = {
        key: value
        for key, value in direct.items()
        if key
        not in {
            "score",
            "n_atoms_interface",
            "prototype_uid",
            "is_pareto",
            "pareto_rank",
            "pareto_policy",
            "pareto_policy_version",
            "pareto_population_scope",
            "pareto_population_size",
            "pareto_d_cell_key",
        }
    }
    payload["interface_prototype_uid"] = direct["prototype_uid"]
    payload["metrics"] = {
        "match_score": direct["score"],
        "d_cell": direct["d_cell"],
        "d_area": direct["d_area"],
        "d_shape": direct["d_shape"],
        "d_size": direct["d_size"],
        "rel_da": direct["rel_da"],
        "rel_db": direct["rel_db"],
        "d_gamma_deg": direct["d_gamma_deg"],
        "n_atoms_interface": direct["n_atoms_interface"],
    }
    payload["pareto"] = {
        "is_member": direct["is_pareto"],
        "rank": direct["pareto_rank"],
        "policy": direct["pareto_policy"],
        "version": direct["pareto_policy_version"],
        "population_scope": direct["pareto_population_scope"],
        "population_size": direct["pareto_population_size"],
        "d_cell_key": direct["pareto_d_cell_key"],
    }
    persisted = {
        "identity_algorithm": direct["identity_algorithm"],
        "payload": payload,
        "match_score": direct["score"],
        "n_atoms": direct["n_atoms_interface"],
        # The repository row has a distinct storage UID.  It must not replace
        # the scientific interface-prototype UID embedded in the payload.
        "prototype_uid": "proto:v2:storage-row",
        "uid_full": "proto:v2:storage-row",
    }

    direct_record = normalize_scientific_record(direct, rank=0)
    persisted_record = normalize_scientific_record(persisted, rank=0)

    assert direct_record == persisted_record
    assert direct_record["exact"]["pair_identity"] == _pair_identity()
    assert direct_record["exact"]["source_provenance"]["source_count"] == 1


def test_build_inventory_is_versioned_unique_and_order_sensitive() -> None:
    second = _row(
        key=[1, 0, 0, 1, 2, 1, 1, 1],
        score=0.2,
        prototype_uid="proto:v3:second",
    )
    first_inventory = build_inventory(
        [_row(), second],
        stage="direct_kernel",
        pareto_population_size=1,
    )
    second_inventory = build_inventory(
        [second, _row()],
        stage="project_search",
        pareto_population_size=1,
    )

    assert first_inventory["schema"] == PUBLIC_API_PARITY_INVENTORY_SCHEMA
    assert first_inventory["identity_set_sha256"] == second_inventory[
        "identity_set_sha256"
    ]
    assert first_inventory["ordered_identity_sha256"] != second_inventory[
        "ordered_identity_sha256"
    ]

    with pytest.raises(ValueError, match="duplicate pair identity"):
        build_inventory(
            [_row(), _row()],
            stage="invalid",
            pareto_population_size=1,
        )


def test_compare_inventories_separates_exact_metric_and_order_failures() -> None:
    baseline = build_inventory(
        [_row()],
        stage="direct_kernel",
        pareto_population_size=1,
    )
    same = build_inventory(
        [_row()],
        stage="project_search",
        pareto_population_size=1,
    )
    comparison = compare_inventories(baseline, same)
    assert comparison["schema"] == PUBLIC_API_PARITY_COMPARISON_SCHEMA
    assert comparison["passed"] is True

    metric_row = _row(score=0.10001)
    metric_inventory = build_inventory(
        [metric_row],
        stage="metric_drift",
        pareto_population_size=1,
    )
    metric_comparison = compare_inventories(baseline, metric_inventory)
    assert metric_comparison["passed"] is False
    assert metric_comparison["metric_mismatches"][0]["field"] == "score"

    exact_row = deepcopy(_row())
    exact_row["source_provenance"]["source_count"] = 2  # type: ignore[index]
    exact_inventory = build_inventory(
        [exact_row],
        stage="provenance_drift",
        pareto_population_size=1,
    )
    exact_comparison = compare_inventories(baseline, exact_inventory)
    assert exact_comparison["passed"] is False
    assert exact_comparison["exact_mismatches"]


def test_public_api_fixture_profiles_cover_workflow_boundaries() -> None:
    standard = select_public_api_fixtures(PublicApiParityConfig(profile="standard"))
    smoke = select_public_api_fixtures(PublicApiParityConfig(profile="smoke"))

    assert len(default_public_api_fixtures()) == 7
    assert len(standard) == 7
    assert len(smoke) == 3
    assert any(fixture.expected_population == "empty" for fixture in standard)
    assert any("termination_pair" in fixture.tags for fixture in standard)
    assert any("output_limit" in fixture.tags for fixture in standard)
    assert {fixture.fixture_id for fixture in smoke} <= {
        fixture.fixture_id for fixture in standard
    }

    selected = select_public_api_fixtures(
        PublicApiParityConfig(
            fixture_ids=("lif_li2o_100_truncated", "lif_100_homointerface")
        )
    )
    assert [fixture.fixture_id for fixture in selected] == [
        "lif_li2o_100_truncated",
        "lif_100_homointerface",
    ]

    with pytest.raises(ValueError, match="unknown public API parity"):
        select_public_api_fixtures(
            PublicApiParityConfig(fixture_ids=("unknown",))
        )


def test_public_api_parity_orchestrates_direct_persisted_resume_and_reopen(
    tmp_path, monkeypatch
) -> None:
    import sys
    import types
    from types import SimpleNamespace

    from benchmarks.benchmarks.claims.claim_ids import ClaimStatus
    from benchmarks.benchmarks.claims.public_api_parity import (
        run_public_api_parity_qualification,
    )

    direct_row = _row()
    direct_row["slab_a_uid"] = "slab:v2:a"
    direct_row["slab_b_uid"] = "slab:v2:b"

    payload = {
        key: value
        for key, value in direct_row.items()
        if key
        not in {
            "score",
            "n_atoms_interface",
            "prototype_uid",
            "is_pareto",
            "pareto_rank",
            "pareto_policy",
            "pareto_policy_version",
            "pareto_population_scope",
            "pareto_population_size",
            "pareto_d_cell_key",
        }
    }
    payload["interface_prototype_uid"] = direct_row["prototype_uid"]
    payload["metrics"] = {
        "match_score": direct_row["score"],
        "d_cell": direct_row["d_cell"],
        "d_area": direct_row["d_area"],
        "d_shape": direct_row["d_shape"],
        "d_size": direct_row["d_size"],
        "rel_da": direct_row["rel_da"],
        "rel_db": direct_row["rel_db"],
        "d_gamma_deg": direct_row["d_gamma_deg"],
        "n_atoms_interface": direct_row["n_atoms_interface"],
    }
    payload["pareto"] = {
        "is_member": direct_row["is_pareto"],
        "rank": direct_row["pareto_rank"],
        "policy": direct_row["pareto_policy"],
        "version": direct_row["pareto_policy_version"],
        "population_scope": direct_row["pareto_population_scope"],
        "population_size": direct_row["pareto_population_size"],
        "d_cell_key": direct_row["pareto_d_cell_key"],
    }
    persisted_row = {
        "payload": payload,
        "uid_full": "proto:v2:storage-row",
        "prototype_uid": "proto:v2:storage-row",
        "match_score": direct_row["score"],
        "n_atoms": direct_row["n_atoms_interface"],
        "pareto_population_size": 1,
    }

    class FakeSearchSettings:
        def __init__(self, **values):
            self.values = dict(values)

        def validate(self) -> None:
            return None

        def to_dict(self):
            return dict(self.values)

        def to_internal_config(self):
            return dict(self.values)

    class FakeMaterial:
        @classmethod
        def from_file(cls, path, *, name):
            return SimpleNamespace(path=str(path), name=name)

    class FakeSurface:
        def __init__(self, uid):
            self.uid_full = uid

        def to_surface(self):
            return self

        def to_slab(self):
            return SimpleNamespace(uid=self.uid_full)

    class FakeCandidates:
        def __init__(self, rows):
            self._rows = list(rows)

        def records(self):
            return list(self._rows)

        def __len__(self):
            return len(self._rows)

    class FakeSearch:
        def __init__(self, state):
            self._state = state
            self.record = SimpleNamespace(
                run_uid_full=state["run_uid"],
                search_identity=state["search_identity"],
            )

        def candidates(self):
            return FakeCandidates(self._state["records"])

    stores = {}

    class FakeProject:
        def __init__(self, path):
            self.path = path
            self.state = stores.setdefault(str(path), {"searches": {}, "runs": {}})

        def add_material(self, material, *, name):
            return SimpleNamespace(material=material, name=name)

        def generate_surfaces(self, materials, *, millers, layers, vacuum):
            return None

        def surface(self, *, material, miller, termination_shift):
            uid = "slab:v2:a" if material == "benchmark_LiF" else "slab:v2:b"
            return FakeSurface(uid)

        def search_interfaces(
            self, surface_a, surface_b, *, settings, name, resume
        ):
            if name not in self.state["searches"]:
                run_uid = "run:v2:test"
                search_identity = "search:v2:test"
                state = {
                    "run_uid": run_uid,
                    "search_identity": search_identity,
                    "records": [persisted_row],
                }
                self.state["searches"][name] = state
                self.state["runs"][run_uid] = SimpleNamespace(
                    status="done",
                    spec={
                        "implementation": "primitive_coupled_pair_v2",
                        "settings": settings.to_dict(),
                        "search_identity": search_identity,
                        "surface_a": {"uid_full": surface_a.uid_full},
                        "surface_b": {"uid_full": surface_b.uid_full},
                    },
                    progress={"phase": "complete", "n_candidates": 1},
                )
            return FakeSearch(self.state["searches"][name])

        def run(self, uid):
            return self.state["runs"][uid]

        def search(self, name):
            return FakeSearch(self.state["searches"][name])

    def fake_open_project(path):
        # Retain the exact requested path so reopened calls share one in-memory
        # state and the expected database artifact location.
        requested = type(tmp_path)(path)
        requested.mkdir(parents=True, exist_ok=True)
        (requested / "calm.sqlite").write_bytes(b"sqlite-fixture")
        return FakeProject(requested)

    def fake_find_prototypes(slab_a, slab_b, *, config):
        assert slab_a.uid == "slab:v2:a"
        assert slab_b.uid == "slab:v2:b"
        return SimpleNamespace(prototypes=[direct_row], pareto_population_size=1)

    calm_module = types.ModuleType("calm")
    calm_module.__path__ = []  # type: ignore[attr-defined]
    calm_module.Material = FakeMaterial
    calm_module.SearchSettings = FakeSearchSettings
    calm_module.open_project = fake_open_project
    interface_module = types.ModuleType("calm.interface")
    interface_module.__path__ = []  # type: ignore[attr-defined]
    pipeline_module = types.ModuleType("calm.interface.pipeline")
    pipeline_module.find_prototypes = fake_find_prototypes
    monkeypatch.setitem(sys.modules, "calm", calm_module)
    monkeypatch.setitem(sys.modules, "calm.interface", interface_module)
    monkeypatch.setitem(sys.modules, "calm.interface.pipeline", pipeline_module)

    lif = tmp_path / "LiF.poscar"
    li2o = tmp_path / "Li2O.poscar"
    lif.write_text("LiF", encoding="utf-8")
    li2o.write_text("Li2O", encoding="utf-8")
    artifacts = run_public_api_parity_qualification(
        output_root=tmp_path / "out",
        repository_root=tmp_path,
        command=("python", "-m", "benchmarks.run_public_api_parity_qualification"),
        config=PublicApiParityConfig(
            fixture_ids=("lif_li2o_100_heterointerface",),
            structure_lif=lif,
            structure_li2o=li2o,
        ),
    )

    assert artifacts.result.status is ClaimStatus.PASS
    assert artifacts.project_database.is_file()
    assert artifacts.summary.is_file()
    assert artifacts.comparisons.is_file()
