from __future__ import annotations

import pytest

from calm.public.queries.structures import ProjectStructureQueryService


class _Repository:
    def __init__(self, row=None) -> None:
        self.row = row or {
            "uid_full": "iface:1",
            "id_short": "i_1",
        }
        self.calls = []

    def get_interface(self, identifier):
        self.calls.append(identifier)
        return dict(self.row)


class _Workspace:
    def __init__(self) -> None:
        self.calls = []
        self.atoms = object()
        self.error = None

    def materialize_derived_interface_atoms(
        self,
        identifier,
        *,
        registry_shift_frac_a=None,
    ):
        self.calls.append((identifier, registry_shift_frac_a))
        if self.error is not None:
            raise self.error
        return self.atoms


def test_structure_service_resolves_durable_interface_identity() -> None:
    repository = _Repository()
    workspace = _Workspace()
    service = ProjectStructureQueryService(
        workspace=workspace,
        repository=repository,
    )

    assert service.get_interface_atoms(" i_1 ") is workspace.atoms
    assert repository.calls == ["i_1"]
    assert workspace.calls == [("iface:1", None)]


def test_structure_service_forwards_registry_shift_to_authoritative_loader() -> None:
    repository = _Repository()
    workspace = _Workspace()
    service = ProjectStructureQueryService(
        workspace=workspace,
        repository=repository,
    )

    assert (
        service.get_interface_atoms(
            "i_1",
            registry_shift=(1.25, -0.25),
        )
        is workspace.atoms
    )
    assert workspace.calls == [("iface:1", (1.25, -0.25))]


def test_structure_service_materializes_through_workspace_adapter() -> None:
    from calm.public.persistence.adapter import WorkspaceAdapter

    backend = _Workspace()
    service = ProjectStructureQueryService(
        workspace=WorkspaceAdapter(backend),
        repository=_Repository(),
    )

    assert (
        service.get_interface_atoms(
            "i_1",
            registry_shift=(0.25, 0.75),
        )
        is backend.atoms
    )
    assert backend.calls == [("iface:1", (0.25, 0.75))]


def test_structure_service_propagates_materialization_errors() -> None:
    workspace = _Workspace()
    workspace.error = KeyError("stage cannot be reconstructed")
    service = ProjectStructureQueryService(
        workspace=workspace,
        repository=_Repository(),
    )

    with pytest.raises(KeyError, match="cannot be reconstructed"):
        service.get_interface_atoms("i_1")


def test_structure_service_rejects_invalid_or_identityless_records() -> None:
    service = ProjectStructureQueryService(
        workspace=_Workspace(),
        repository=_Repository(row={"label": "projection"}),
    )
    with pytest.raises(RuntimeError, match="durable identity"):
        service.get_interface_atoms("projection")

    with pytest.raises(TypeError, match="non-empty identifier"):
        service.get_interface_atoms("")


def test_project_interface_atoms_delegates_to_structure_query_service() -> None:
    from calm.public.project import Project

    calls = []

    class StructureQueries:
        def get_interface_atoms(self, identifier, *, registry_shift=None):
            calls.append((identifier, registry_shift))
            return "atoms"

    project = object.__new__(Project)
    project._structure_queries = StructureQueries()

    assert project.interface_atoms("i_1") == "atoms"
    assert (
        project.interface_atoms(
            "iface:1",
            registry_shift=(0.25, 0.75),
        )
        == "atoms"
    )
    assert calls == [
        ("i_1", None),
        ("iface:1", (0.25, 0.75)),
    ]
