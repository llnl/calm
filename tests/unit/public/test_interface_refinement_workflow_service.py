from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from calm.public.workflows.interface_refinement import (
    ProjectInterfaceRefinementService,
)
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


class _Owner:
    def __init__(self, *, candidates=None, interfaces=None):
        self._candidates = list(candidates or [])
        self._interfaces = list(interfaces or [])

    def search(self, search):
        return search

    def candidates(self):
        return _Rows(self._candidates)

    def interfaces(self):
        return _Rows(self._interfaces)


class _Repository:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    def get_interface(self, identifier: str):
        return self.rows[str(identifier)]


class _Workspace:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    def start_strain_partition_scan(self, **kwargs):
        self.calls.append(("strain", kwargs["prototypes"], kwargs))
        return SimpleNamespace(id_short="r_strain", uid_full="run:strain")

    def derive_interfaces_from_strain_partition_scan(self, run, **kwargs):
        self.calls.append(("derive_strain", run, kwargs))
        return [SimpleNamespace(uid_full="iface:strain", id_short="i_strain")]

    def start_registry_search(self, **kwargs):
        self.calls.append(("registry", kwargs["prototypes"], kwargs))
        return SimpleNamespace(id_short="r_registry", uid_full="run:registry")

    def derive_interfaces_from_registry_search(self, run, **kwargs):
        self.calls.append(("derive_registry", run, kwargs))
        return [SimpleNamespace(uid_full="iface:registry", id_short="i_registry")]

    def run_registry_stage(self, prototypes, **kwargs):
        self.calls.append(("registry_stage", list(prototypes), kwargs))
        return [
            {"prototype_uid": prototype, "status": "completed"}
            for prototype in prototypes
        ]


def _settings() -> StrainPartitionSettings:
    return StrainPartitionSettings(
        target_metric="potential_energy_density_eV_per_A2",
        alphas=(0.0, 0.5, 1.0),
    )


def _service(owner, workspace=None, repository=None):
    workspace = workspace or _Workspace()
    repository = repository or _Repository()
    return (
        ProjectInterfaceRefinementService(
            project=owner,
            workspace=workspace,
            repository=repository,
        ),
        workspace,
    )


def test_refinement_service_composes_strain_and_registry_lineage() -> None:
    owner = _Owner(
        candidates=[{"project_prototype_uid": "proto:1"}],
        interfaces=[
            {
                "stage": "built",
                "authority": "authoritative",
                "prototype_uid_full": "proto:1",
                "project_interface_uid": "iface:built",
            }
        ],
    )
    service, workspace = _service(owner)
    search = PersistedInterfaceSearch(project=owner, name="search-a")
    registry = RegistrySettings(steps=5, translation_step=0.02, seed=7)

    result = service.refine_interfaces(
        search,
        strain_settings=_settings(),
        registry_settings=registry,
        label_prefix="case",
        on_error="raise",
    )

    assert result.ok
    assert [row.uid_full for row in result.strain_interfaces] == ["iface:strain"]
    assert [row.uid_full for row in result.registry_interfaces] == ["iface:registry"]
    assert workspace.calls[0][0:2] == ("strain", ["iface:built"])
    assert workspace.calls[0][2]["alphas"] == [0.0, 0.5, 1.0]
    assert workspace.calls[1][0:2] == ("derive_strain", "r_strain")
    assert workspace.calls[2][0:2] == ("registry", ["iface:strain"])
    assert workspace.calls[2][2]["n_steps"] == 5
    assert workspace.calls[3][0:2] == ("derive_registry", "r_registry")


def test_explicit_refinement_targets_are_resolved_authoritatively_and_deduped() -> None:
    owner = _Owner()
    repository = _Repository(
        {
            "iface:built": {
                "uid_full": "iface:built",
                "id_short": "i_built",
                "label": "built",
                "prototype_uid_full": "proto:1",
                "stage": "built",
                "search_name": "search-a",
                "authority": "authoritative",
            }
        }
    )
    service, workspace = _service(owner, repository=repository)
    search = PersistedInterfaceSearch(project=owner, name="search-a")

    result = service.refine_interfaces(
        search,
        strain_settings=_settings(),
        interfaces=["iface:built", "iface:built"],
        on_error="raise",
    )

    assert result.ok
    assert result.registry_run is None
    assert result.registry_interfaces == []
    assert [call[0] for call in workspace.calls] == ["strain", "derive_strain"]
    assert workspace.calls[0][0:2] == ("strain", ["iface:built"])


def test_explicit_refinement_target_from_another_search_is_rejected() -> None:
    owner = _Owner()
    repository = _Repository(
        {
            "iface:foreign": {
                "uid_full": "iface:foreign",
                "id_short": "i_foreign",
                "label": "foreign",
                "prototype_uid_full": "proto:1",
                "stage": "built",
                "search_name": "search-b",
                "authority": "authoritative",
            }
        }
    )
    service, workspace = _service(owner, repository=repository)
    search = PersistedInterfaceSearch(project=owner, name="search-a")

    with pytest.raises(ValueError, match="belongs to search"):
        service.refine_interfaces(
            search,
            strain_settings=_settings(),
            interfaces=["iface:foreign"],
            on_error="raise",
        )

    assert workspace.calls == []


def test_registry_only_refinement_uses_existing_strain_interface() -> None:
    owner = _Owner()
    repository = _Repository(
        {
            "iface:strain": {
                "uid_full": "iface:strain",
                "id_short": "i_strain",
                "label": "selected-strain",
                "prototype_uid_full": "proto:1",
                "stage": "strain_partitioned",
                "search_name": "search-a",
                "authority": "authoritative",
                "strain_alpha": 0.45,
                "registry_shift_frac_a": [0.0, 0.0],
                "z_padding": 1.5,
                "vacuum": 15.0,
            }
        }
    )
    service, workspace = _service(owner, repository=repository)
    settings = RegistrySettings(steps=500, translation_step=0.08, seed=17)

    result = service.refine_registry(
        ["iface:strain", "iface:strain"],
        settings=settings,
        label_prefix="compact_seed_17",
        on_error="raise",
    )

    assert result.ok
    assert result.strain_scan is None
    assert [row.uid_full for row in result.strain_interfaces] == ["iface:strain"]
    assert [row.uid_full for row in result.registry_interfaces] == ["iface:registry"]
    assert [call[0] for call in workspace.calls] == ["registry", "derive_registry"]
    assert workspace.calls[0][0:2] == ("registry", ["iface:strain"])
    assert workspace.calls[0][2]["n_steps"] == 500
    assert workspace.calls[0][2]["payload"]["registry_settings"] == (settings.to_dict())
    assert workspace.calls[0][2]["payload"]["public_api"] == ("Project.refine_registry")


def test_registry_only_refinement_rejects_non_strain_interface() -> None:
    owner = _Owner()
    repository = _Repository(
        {
            "iface:built": {
                "uid_full": "iface:built",
                "id_short": "i_built",
                "label": "built",
                "prototype_uid_full": "proto:1",
                "stage": "built",
                "search_name": "search-a",
                "authority": "authoritative",
                "strain_alpha": 0.5,
                "registry_shift_frac_a": [0.0, 0.0],
                "z_padding": 1.5,
                "vacuum": 15.0,
            }
        }
    )
    service, workspace = _service(owner, repository=repository)

    with pytest.raises(ValueError, match="stage='strain_partitioned'"):
        service.refine_registry(
            ["iface:built"],
            settings=RegistrySettings(steps=10, seed=3),
            on_error="raise",
        )

    assert workspace.calls == []
