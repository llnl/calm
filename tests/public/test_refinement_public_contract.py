from types import SimpleNamespace

import pytest

from calm.interface.refinement.contract import select_strain_point, stable_registry_seed
from calm.public.workflows.interface_refinement import (
    ProjectInterfaceRefinementService,
)
from calm.public.projections.interface import normalize_interface_row
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.inputs.settings import RegistrySettings, StrainPartitionSettings


def test_selection_uses_exact_requested_strain_objective():
    points = [
        {
            "alpha": 0.0,
            "gamma_eV_per_A2": 1.0,
            "potential_energy_density_eV_per_A2": 0.1,
        },
        {
            "alpha": 1.0,
            "gamma_eV_per_A2": 0.2,
            "potential_energy_density_eV_per_A2": 0.9,
        },
    ]
    assert select_strain_point(points, "gamma_eV_per_A2")["alpha"] == 1.0
    assert (
        select_strain_point(points, "potential_energy_density_eV_per_A2")["alpha"]
        == 0.0
    )


def test_strain_point_ties_choose_the_smallest_finite_alpha():
    points = [
        {"alpha": 0.75, "gamma_eV_per_A2": 0.2},
        {"alpha": 0.25, "gamma_eV_per_A2": 0.2},
    ]
    assert select_strain_point(points, "gamma_eV_per_A2")["alpha"] == 0.25


def test_registry_seed_is_stable_target_specific_and_user_controlled():
    assert stable_registry_seed("run:1:iface:1", None) == stable_registry_seed(
        "run:1:iface:1", None
    )
    assert stable_registry_seed("run:1:iface:1", 7) != stable_registry_seed(
        "run:1:iface:2", 7
    )
    assert stable_registry_seed("run:1:iface:1", 7) != stable_registry_seed(
        "run:1:iface:1", 8
    )


def test_authoritative_interface_spec_exposes_stage_and_lineage():
    item = SimpleNamespace(
        uid_full="iface:1",
        id_short="i_1",
        label="refined",
        prototype_uid_full="proto:1",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:1",
            "stage": "registry_refined",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": None,
            "params": {
                "search_name": "search-1",
                "source_followup_uid": "followup:1",
                "source_run_uid": "run:1",
            },
        },
    )
    row = normalize_interface_row(item)
    assert row["stage"] == "registry_refined"
    assert row["search_name"] == "search-1"
    assert row["source_followup_uid"] == "followup:1"
    assert row["source_run_uid"] == "run:1"


def test_interface_collection_refined_filters_canonical_stages():
    collection = InterfaceCollection(
        interfaces=[
            {"interface_id": "built", "stage": "built"},
            {"interface_id": "strain", "stage": "strain_partitioned"},
            {"interface_id": "registry", "stage": "registry_refined"},
        ]
    )
    refined_rows = collection.refined().to_rows(view="all")
    assert [row["interface_id"] for row in refined_rows] == [
        "strain",
        "registry",
    ]
    assert [
        row["interface_id"]
        for row in collection.refined(stage="registry_refined").to_rows(view="all")
    ] == ["registry"]
    with pytest.raises(ValueError, match="stage must be"):
        collection.refined(stage="relaxed")


def test_interface_workflow_service_forwards_only_operational_settings():
    class Workspace:
        def __init__(self):
            self.calls = []

        def start_strain_partition_scan(self, **kwargs):
            self.calls.append(("strain", kwargs))
            return "strain-run"

        def start_registry_search(self, **kwargs):
            self.calls.append(("registry", kwargs))
            return "registry-run"

    workspace = Workspace()
    service = ProjectInterfaceRefinementService(
        project=SimpleNamespace(),
        workspace=workspace,
        repository=SimpleNamespace(),
    )

    strain = StrainPartitionSettings(
        target_metric="gamma_eV_per_A2",
        alphas=(1.0, 0.0, 0.5),
    )
    assert (
        service._start_strain_partition_scan(
            ["iface:built"],
            settings=strain,
            payload={"search_name": "s1"},
        )
        == "strain-run"
    )
    kind, kwargs = workspace.calls[0]
    assert kind == "strain"
    assert kwargs["prototypes"] == ["iface:built"]
    assert kwargs["alphas"] == [0.0, 0.5, 1.0]
    assert kwargs["payload"]["target_metric"] == "gamma_eV_per_A2"

    registry = RegistrySettings(steps=4, translation_step=0.02, seed=9)
    assert (
        service._start_registry_search(
            ["iface:strain"],
            settings=registry,
            payload={"search_name": "s1"},
        )
        == "registry-run"
    )
    kind, kwargs = workspace.calls[1]
    assert kind == "registry"
    assert kwargs["prototypes"] == ["iface:strain"]
    assert kwargs["n_steps"] == 4
    assert kwargs["payload"]["registry_settings"] == registry.to_dict()


def test_refined_collection_search_reads_authoritative_spec_params():
    item = SimpleNamespace(
        uid_full="iface:registry",
        id_short="i_registry",
        label="registry",
        prototype_uid_full="proto:1",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:1",
            "stage": "registry_refined",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": None,
            "params": {
                "search_name": "search-1",
            },
        },
    )
    rows = (
        InterfaceCollection(interfaces=[item])
        .refined(stage="registry_refined")
        .search(name="search-1")
        .to_rows(view="all")
    )
    assert len(rows) == 1
    assert rows[0]["stage"] == "registry_refined"


def test_registry_seed_rejects_inexact_or_negative_values():
    with pytest.raises(TypeError, match="requested_seed must be an integer"):
        stable_registry_seed("run:1:iface:1", 1.5)
    with pytest.raises(ValueError, match="requested_seed must be non-negative"):
        stable_registry_seed("run:1:iface:1", -1)


def test_refinement_contract_rejects_coercive_scientific_values() -> None:
    from calm.interface.refinement.contract import (
        canonical_alpha_grid,
        canonical_strain_metric,
    )

    with pytest.raises(TypeError, match="target_metric"):
        canonical_strain_metric(1)  # type: ignore[arg-type]
    for value in (True, "0.5"):
        with pytest.raises(TypeError, match="alpha values must be real numbers"):
            canonical_alpha_grid((value,))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="metric .* must be a real number"):
        select_strain_point(
            [{"alpha": 0.5, "gamma_eV_per_A2": "0.1"}],
            "gamma_eV_per_A2",
        )
    with pytest.raises(TypeError, match="alpha must be a real number"):
        select_strain_point(
            [{"alpha": "0.5", "gamma_eV_per_A2": 0.1}],
            "gamma_eV_per_A2",
        )
    with pytest.raises(TypeError, match="seed base"):
        stable_registry_seed(1, None)  # type: ignore[arg-type]


def test_spec_only_refined_collection_exports_reconstructed_structure(
    tmp_path,
    monkeypatch,
):
    from pathlib import Path

    from calm.public.queries.structures import ProjectStructureQueryService

    atoms = object()
    source = SimpleNamespace(
        uid_full="iface:strain",
        id_short="i_strain",
        label="selected strain interface",
        prototype_uid_full="proto:1",
        stage="strain_partitioned",
        strain_alpha=0.25,
        registry_shift_frac_a=(0.0, 0.0),
        z_padding=1.5,
        vacuum=15.0,
        atoms_artifact_uid=None,
    )
    row = {
        "uid_full": source.uid_full,
        "id_short": source.id_short,
        "label": source.label,
        "prototype_uid_full": source.prototype_uid_full,
        "stage": source.stage,
        "_object": source,
    }

    class Repository:
        def get_interface(self, identifier):
            assert identifier == "iface:strain"
            return dict(row)

    class Workspace:
        def __init__(self):
            self.calls = []

        def materialize_derived_interface_atoms(
            self,
            identifier,
            *,
            registry_shift_frac_a=None,
        ):
            self.calls.append((identifier, registry_shift_frac_a))
            return atoms

    workspace = Workspace()
    structure_queries = ProjectStructureQueryService(
        workspace=workspace,
        repository=Repository(),
    )
    project = SimpleNamespace(_structure_queries=structure_queries)

    writes = []

    def fake_write(path, value, *, format=None):
        output = Path(path)
        output.write_text("reconstructed", encoding="utf-8")
        writes.append((output, value, format))

    monkeypatch.setattr(
        "calm.structure.io.safe_write_structure",
        fake_write,
    )

    written = InterfaceCollection(
        interfaces=[row],
        project=project,
    ).write_structures(tmp_path, format="vasp")

    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == "reconstructed"
    assert writes == [(written[0], atoms, "vasp")]
    assert workspace.calls == [("iface:strain", None)]
