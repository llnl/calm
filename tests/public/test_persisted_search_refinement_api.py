from types import SimpleNamespace

from calm.public.workflows.interface_refinement import (
    ProjectInterfaceRefinementService,
)
from calm.public.records.followups import InterfaceRefinementResult
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.inputs.settings import RegistrySettings, StrainPartitionSettings


class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def search(self, name=None):
        del name
        return self

    def select(self, **kwargs):
        del kwargs
        return self

    def select_top(self, n, by):
        del by
        return _Rows(self._rows[:n])

    def to_rows(self, view="all"):
        del view
        return list(self._rows)


class FakeProject:
    def __init__(self, candidates_rows=None, interface_rows=None):
        self._candidates = candidates_rows or []
        self._interfaces = interface_rows or []
        self.calls = []

    def search(self, search):
        return search

    def candidates(self):
        return _Rows(self._candidates)

    def interfaces(self):
        return _Rows(self._interfaces)

    def get_interface(self, identifier):
        return {
            "uid_full": str(identifier),
            "id_short": str(identifier),
            "label": str(identifier),
            "prototype_uid_full": "proto:1",
            "stage": "built",
            "search_name": "s1",
            "authority": "authoritative",
        }

    def start_strain_partition_scan(
        self,
        interfaces=None,
        prototypes=None,
        **kwargs,
    ):
        interfaces = prototypes if prototypes is not None else interfaces
        self.calls.append(("strain", list(interfaces), kwargs))
        return SimpleNamespace(id_short="r_strain", uid_full="run:strain")

    def derive_interfaces_from_strain_partition_scan(self, run_id, **kwargs):
        self.calls.append(("derive_strain", run_id, kwargs))
        return [SimpleNamespace(id_short="i_strain", uid_full="iface:strain")]

    def start_registry_search(
        self,
        interfaces=None,
        prototypes=None,
        **kwargs,
    ):
        interfaces = prototypes if prototypes is not None else interfaces
        self.calls.append(("registry", list(interfaces), kwargs))
        return SimpleNamespace(id_short="r_registry", uid_full="run:registry")

    def derive_interfaces_from_registry_search(self, run_id, **kwargs):
        self.calls.append(("derive_registry", run_id, kwargs))
        return [SimpleNamespace(id_short="i_registry", uid_full="iface:registry")]


def _service(project):
    return ProjectInterfaceRefinementService(
        project=project,
        workspace=project,
        repository=project,
    )


def _strain_settings():
    return StrainPartitionSettings(
        target_metric="potential_energy_density_eV_per_A2",
        alphas=(0.0, 0.5, 1.0),
    )


def test_refine_interfaces_no_prototypes_explain_mode():
    project = FakeProject(candidates_rows=[])
    search = PersistedInterfaceSearch(project=project, name="s1")

    result = _service(project).refine_interfaces(
        search,
        strain_settings=_strain_settings(),
        on_error="explain",
    )

    assert isinstance(result, InterfaceRefinementResult)
    assert not result.ok
    assert "no_built_interfaces_found_for_search" in result.issues


def test_refine_interfaces_requires_authoritative_built_interfaces():
    project = FakeProject(
        candidates_rows=[{"project_prototype_uid": "proto:1"}],
        interface_rows=[
            {
                "stage": "built",
                "authority": "projection",
                "prototype_uid": "proto:1",
                "interface_id": "projection-only",
            }
        ],
    )
    search = PersistedInterfaceSearch(project=project, name="s1")

    result = _service(project).refine_interfaces(
        search,
        strain_settings=_strain_settings(),
    )

    assert not result.ok
    assert "no_built_interfaces_found_for_search" in result.issues
    assert project.calls == []


def test_refine_interfaces_follows_built_strain_registry_lineage():
    project = FakeProject(
        candidates_rows=[{"project_prototype_uid": "proto:1"}],
        interface_rows=[
            {
                "stage": "built",
                "authority": "authoritative",
                "prototype_uid": "proto:1",
                "project_interface_uid": "iface:built",
                "search_name": "s1",
            }
        ],
    )
    strain = _strain_settings()
    registry = RegistrySettings(steps=9, translation_step=0.03, seed=11)
    search = PersistedInterfaceSearch(project=project, name="s1")

    result = _service(project).refine_interfaces(
        search,
        strain_settings=strain,
        registry_settings=registry,
        label_prefix="case",
        on_error="raise",
    )

    assert result.ok
    assert [x.uid_full for x in result.strain_interfaces] == ["iface:strain"]
    assert [x.uid_full for x in result.registry_interfaces] == ["iface:registry"]

    assert project.calls[0][0:2] == ("strain", ["iface:built"])
    assert project.calls[0][2]["alphas"] == [0.0, 0.5, 1.0]
    assert project.calls[0][2]["payload"]["target_metric"] == (
        "potential_energy_density_eV_per_A2"
    )
    assert project.calls[1][0:2] == ("derive_strain", "r_strain")
    assert project.calls[2][0:2] == ("registry", ["iface:strain"])
    assert project.calls[2][2]["n_steps"] == 9
    assert project.calls[2][2]["payload"]["registry_settings"] == (registry.to_dict())
    assert project.calls[3][0:2] == ("derive_registry", "r_registry")


def test_refine_interfaces_accepts_exact_built_interface_targets():
    project = FakeProject(candidates_rows=[])
    search = PersistedInterfaceSearch(project=project, name="s1")

    result = _service(project).refine_interfaces(
        search,
        strain_settings=_strain_settings(),
        interfaces=[SimpleNamespace(uid_full="iface:exact")],
        label_prefix="case",
        on_error="raise",
    )

    assert result.ok
    assert result.registry_run is None
    assert result.registry_interfaces == []
    assert [call[0] for call in project.calls] == ["strain", "derive_strain"]
    assert project.calls[0][0:2] == ("strain", ["iface:exact"])
