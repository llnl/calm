from __future__ import annotations

from types import SimpleNamespace

from calm.project.domain.models import InterfaceSearch
from calm.public.records.buildability import BuildabilityReport
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.project import Project
from calm.public.persistence.repository import PublicRepository
from calm.public.records.interfaces import InterfaceCandidate, InterfaceModel
from calm.public.inputs.settings import BuildSettings
from calm.public.persistence.adapter import WorkspaceAdapter


class _Workspace:
    def create_derived_interface(self, prototype, **kwargs):
        return {"prototype": prototype, **kwargs}

    def get_derived_interface(self, identifier):
        return {"identifier": identifier}

    def check_prototype_buildability(self, prototype):
        return SimpleNamespace(
            prototype_uid_full=prototype,
            reconstructable=True,
            buildable=True,
            reasons=["ok"],
        )

    def check_prototypes_buildability(self, prototypes):
        return {
            prototype: self.check_prototype_buildability(prototype)
            for prototype in prototypes
        }


def test_test_only_interface_creation_bridges_are_not_on_project(tmp_path) -> None:
    project = Project(_Workspace(), path=tmp_path / "project.calm")

    assert not hasattr(project, "_build_interface_from_prototype")
    assert not hasattr(project, "_create_derived_interface")
    assert not hasattr(project, "_start_strain_partition_scan")
    assert not hasattr(project, "_derive_interfaces_from_strain_partition_scan")
    assert not hasattr(project, "_start_registry_search")
    assert not hasattr(project, "_derive_interfaces_from_registry_search")
    assert not hasattr(project, "_get_derived_interface")

    assert not hasattr(project, "_check_prototype_buildability")
    assert not hasattr(project, "_check_prototypes_buildability")
    assert project._health.check_prototype_buildability("proto:x").buildable
    assert set(project._health.check_prototypes_buildability(["proto:x"])) == {
        "proto:x"
    }


class _CandidateCollection:
    def __init__(self, candidate):
        self._candidate = candidate

    def search(self, name):
        assert name == "screen"
        return self

    def select(self, **kwargs):
        del kwargs
        return self

    def select_top(self, n, *, by):
        assert n == 1
        assert by == "score"
        return self

    def validate_buildable(self):
        return BuildabilityReport(n_candidates=1, n_buildable=1, issues=[])

    def __iter__(self):
        return iter([self._candidate])

    def __len__(self):
        return 1


class _BuildProject:
    def __init__(self, candidate):
        self._collection = _CandidateCollection(candidate)
        self._repo = None
        self.saved_candidate = None
        self.saved_model = None
        self.persisted = SimpleNamespace(
            uid_full="iface:built",
            id_short="i_built",
            atoms=None,
        )
        self._saver = SimpleNamespace(
            record_interface_model=self._record_interface_model
        )
        from calm.public.workflows.interface_build import ProjectInterfaceBuildService

        self._interface_builds = ProjectInterfaceBuildService(
            project=self,
            workspace=SimpleNamespace(),
            repository=SimpleNamespace(),
            saver=self._saver,
        )

    def candidates(self):
        return self._collection

    def search(self, search):
        if isinstance(search, PersistedInterfaceSearch):
            return search
        return PersistedInterfaceSearch(project=self, name=search)

    def _record_interface_model(self, model, *, name=None, reporter=None):
        del name, reporter
        self.saved_model = model
        self.saved_candidate = model.candidate
        return self.persisted


def test_project_build_interfaces_preserves_search_provenance(
    monkeypatch,
) -> None:
    candidate = InterfaceCandidate(
        None,
        candidate_id="C0000",
        project_prototype_uid="proto:x",
        search_name="screen",
        score=0.1,
        is_pareto=True,
    )
    project = _BuildProject(candidate)

    atoms = [object()]

    def _build(*args, **kwargs):
        del args, kwargs
        return InterfaceModel(SimpleNamespace(atoms=atoms))

    monkeypatch.setattr(
        project._interface_builds,
        "_build_interface_model",
        _build,
    )

    search = project.search("screen")
    result = Project.build_interfaces(project, search, top=1)

    assert len(result) == 1
    assert result[0] is project.saved_model
    assert result[0].atoms is atoms
    assert result[0].project_interface_uid == "iface:built"
    assert result[0].project_interface_id == "i_built"
    assert result[0]._persisted_record is project.persisted
    assert project.saved_candidate["candidate_id"] == "C0000"
    assert project.saved_candidate["search_name"] == "screen"
    assert project.saved_candidate["project_prototype_uid"] == "proto:x"


class _CanonicalDerivedInterfaceWorkspace:
    def __init__(self) -> None:
        self.calls = []

    def create_derived_interface(self, prototype, **kwargs):
        self.calls.append((prototype, kwargs))
        stage = kwargs.get("stage") or "built"
        alpha = kwargs.get("strain_alpha")
        if alpha is None:
            alpha = 0.5
        shift = kwargs.get("registry_shift_frac_a") or (0.0, 0.0)
        shift = tuple(float(value) % 1.0 for value in shift)
        z_padding = kwargs.get("z_padding")
        if z_padding is None:
            z_padding = 1.5
        vacuum = kwargs.get("vacuum")
        persisted = SimpleNamespace(
            uid_full="iface:abc123",
            id_short="i_abc123",
            prototype_uid_full=prototype,
            label=kwargs.get("label"),
            spec={
                "schema": "calm.derived_interface",
                "version": 1,
                "prototype": prototype,
                "stage": stage,
                "strain_alpha": float(alpha),
                "registry_shift_frac_a": list(shift),
                "z_padding": float(z_padding),
                "vacuum": vacuum,
                "params": kwargs.get("params") or {},
            },
            stage=stage,
            strain_alpha=float(alpha),
            registry_shift_frac_a=shift,
            z_padding=float(z_padding),
            vacuum=vacuum,
        )
        self.persisted = persisted
        return persisted

    def list_derived_interfaces(self, *, limit=None):
        del limit
        persisted = getattr(self, "persisted", None)
        return [] if persisted is None else [persisted]

    def get_derived_interface(self, identifier):
        persisted = getattr(self, "persisted", None)
        if persisted is None or identifier not in {
            persisted.uid_full,
            persisted.id_short,
        }:
            raise KeyError(identifier)
        return persisted

    def get_interface_search(self, identifier):
        if identifier not in {
            "screen",
            "search:screen",
            "run:screen",
            "r_screen",
        }:
            raise KeyError(identifier)
        return InterfaceSearch(
            name="screen",
            search_identity="search:screen",
            run_uid_full="run:screen",
            run_id_short="r_screen",
            status="done",
            spec={"search_identity": "search:screen"},
        )

    def list_interface_searches(self, *, limit=None):
        del limit
        return [self.get_interface_search("screen")]

    def list_prototypes(self, *, run=None, limit=None):
        del limit
        if run not in {None, "run:screen"}:
            return []
        return [
            SimpleNamespace(
                uid_full="proto:authoritative",
                id_short="p_authoritative",
                run_uid_full="run:screen",
                run_id_short="r_screen",
                slab_a_uid_full="slab:a",
                slab_a_id_short="s_a",
                slab_b_uid_full="slab:b",
                slab_b_id_short="s_b",
                match_score=0.1,
                hencky_norm=0.01,
                interface_area=4.0,
                natoms=2,
                d_cell=0.01,
                is_pareto=True,
                pareto_rank=0,
                payload={"metrics": {"d_cell": 0.01}},
            )
        ]


def test_interface_model_is_converted_to_canonical_derived_interface_call() -> None:
    workspace = _CanonicalDerivedInterfaceWorkspace()
    adapter = WorkspaceAdapter(workspace)
    atoms = object()
    model = InterfaceModel(
        SimpleNamespace(
            atoms=atoms,
            prototype_uid="proto:fallback",
            strain_state={"source": "authoritative-build"},
        ),
        candidate={
            "candidate_id": "C0000",
            "project_prototype_uid": "proto:authoritative",
            "search_name": "screen",
        },
        build_settings=BuildSettings(
            alpha=0.25,
            gap=2.0,
            vacuum=12.0,
            translation=(0.125, 0.375),
        ),
    )

    persisted = adapter.persist_derived_interface(model, name="screen_C0000")

    assert persisted.uid_full == "iface:abc123"
    assert workspace.calls == [
        (
            "proto:authoritative",
            {
                "label": "screen_C0000",
                "strain_alpha": 0.25,
                "registry_shift_frac_a": (0.125, 0.375),
                "z_padding": 2.0,
                "vacuum": 12.0,
                "params": None,
                "atoms": atoms,
                "strain_state": {"source": "authoritative-build"},
            },
        )
    ]


def test_persisted_interface_query_keeps_search_and_durable_identity() -> None:
    workspace = _CanonicalDerivedInterfaceWorkspace()
    repository = PublicRepository(WorkspaceAdapter(workspace))
    model = InterfaceModel(
        SimpleNamespace(atoms=[], prototype_uid="proto:authoritative"),
        candidate={
            "candidate_id": "C0000",
            "project_prototype_uid": "proto:authoritative",
            "search_name": "screen",
        },
        build_settings=BuildSettings(),
    )

    repository.save_interface(model, name="screen_C0000")
    rows = repository.list_interfaces(search_name="screen")

    assert len(rows) == 1
    row = rows[0]
    assert row["interface_id"] == "i_abc123"
    assert row["id"] == "i_abc123"
    assert row["label"] == "screen_C0000"
    assert row["id_short"] == "i_abc123"
    assert row["search_name"] == "screen"
    assert row["prototype_uid"] == "proto:authoritative"
    assert row["project_interface_uid"] == "iface:abc123"
    assert row["project_interface_id"] == "i_abc123"
    assert row["_authority"] == "authoritative"

    resolved = repository.get_interface("screen_C0000")
    assert resolved["interface_id"] == "i_abc123"
    assert resolved["label"] == "screen_C0000"
    assert resolved["id_short"] == "i_abc123"
    assert resolved["project_interface_uid"] == "iface:abc123"
    assert resolved["_object"] is workspace.persisted
