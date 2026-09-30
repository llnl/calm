"""Built-interface public query collection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable

from calm.public.collections.base import _BaseCollection, _row
from calm.public.records.interface_views import (
    INTERFACE_VIEW_SPECS,
    attach_interface_deformation_diagnostics,
    attach_interface_realized_geometry,
    normalize_interface_public_row,
)


class InterfaceCollection(_BaseCollection):
    """Provide a chainable view of constructed and persisted interfaces.

    The collection can hold in-memory interface models or authoritative project
    records. Filtering, export, and tabulation are read-only; workflow execution
    remains owned by ``Project``.
    """

    _view_specs = INTERFACE_VIEW_SPECS

    _items_attr = "_ifaces"

    def __init__(
        self,
        workspace: Any | None = None,
        interfaces: Iterable[Any] | None = None,
        items: Iterable[Any] | None = None,
        repo: Any | None = None,
        project: Any | None = None,
    ):
        self._ws = workspace
        self._repo = repo
        self._project = project
        source = interfaces if interfaces is not None else items
        self._ifaces = list(source) if source is not None else []
        self._loaded = source is not None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError(
                "InterfaceCollection requires an authoritative project repository."
            )
        self._ifaces = list(self._repo.list_interfaces())
        self._loaded = True

    def _clone(self, items):
        return InterfaceCollection(
            workspace=self._ws,
            interfaces=items,
            repo=self._repo,
            project=self._project,
        )

    def _public_item(self, item: Any):
        from calm.public.records.persistence import ProjectInterface

        if isinstance(item, ProjectInterface):
            return item
        # Persisted database records and authoritative row mappings receive the
        # typed persistence facade. In-memory build results retain their
        # scientific object type until they are saved to the project.
        if isinstance(item, dict) or getattr(item, "uid_full", None):
            return ProjectInterface.from_item(item)
        return item

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if view == "construction":
            return [self._construction_row(item) for item in self._ifaces]
        if view == "strain":
            return [self._strain_row(item) for item in self._ifaces]
        return [self._normalize_item(item) for item in self._ifaces]

    @staticmethod
    def _in_memory_atoms(item: Any) -> Any | None:
        atoms = getattr(item, "atoms", None)
        if atoms is not None:
            return atoms
        internal = getattr(item, "_internal", None)
        return getattr(internal, "atoms", None)

    @staticmethod
    def _strain_state(item: Any, row: dict[str, Any]) -> Any | None:
        value = getattr(item, "strain_state", None)
        if value is not None:
            return value
        internal = getattr(item, "_internal", None)
        value = getattr(internal, "strain_state", None)
        if value is not None:
            return value
        spec = row.get("spec")
        if isinstance(spec, Mapping):
            return spec.get("strain_state")
        return None

    def _materialize_atoms(
        self,
        item: Any,
        row: dict[str, Any],
        *,
        purpose: str,
    ) -> Any:
        atoms = self._in_memory_atoms(item)
        if atoms is not None:
            return atoms

        identifier = row.get("uid_full") or row.get("id_short")
        if not identifier:
            raise RuntimeError(
                f"Interface {purpose} requires atomistic structure identity."
            )
        owner = self._project or self._ws
        if owner is None:
            raise RuntimeError(
                f"Persisted interface {purpose} requires the owning Project or "
                "Workspace."
            )
        materialize = getattr(owner, "materialize_derived_interface_atoms", None)
        if callable(materialize):
            return materialize(str(identifier))
        structure_queries = getattr(owner, "_structure_queries", None)
        getter = getattr(structure_queries, "get_interface_atoms", None)
        if callable(getter):
            return getter(str(identifier))
        raise RuntimeError(
            "The owning Project or Workspace cannot materialize interface atoms "
            f"for {purpose}."
        )

    def _construction_row(self, item: Any) -> dict[str, Any]:
        public_item = self._public_item(item)
        row = normalize_interface_public_row(public_item)
        atoms = self._materialize_atoms(
            item,
            row,
            purpose="construction geometry reporting",
        )
        return attach_interface_realized_geometry(row, atoms)

    def _strain_row(self, item: Any) -> dict[str, Any]:
        public_item = self._public_item(item)
        row = normalize_interface_public_row(public_item)
        atoms = self._materialize_atoms(
            item,
            row,
            purpose="strain reporting",
        )

        from calm.slab.oriented.cell_contract import (
            interface_deformation_diagnostics,
        )

        cell = getattr(atoms, "cell", None)
        if hasattr(cell, "array"):
            cell = cell.array
        diagnostics = interface_deformation_diagnostics(
            getattr(atoms, "info", None),
            current_cell=cell,
            strain_state=self._strain_state(item, row),
        )
        return attach_interface_deformation_diagnostics(row, diagnostics)

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_interface_public_row(self._public_item(item))

    def materials(self, *names: str):
        if not names:
            return self
        names_l = {n.lower() for n in names}
        self._ensure_loaded()
        out = []
        for item in self._ifaces:
            r = _row(item) if not isinstance(item, dict) else dict(item)
            vals = {
                str(r.get("material_a") or "").lower(),
                str(r.get("material_b") or "").lower(),
            }
            vals.update(
                {
                    str(r.get("surface_a") or "").lower(),
                    str(r.get("surface_b") or "").lower(),
                }
            )
            if vals & names_l:
                out.append(item)
        return self._clone(out)

    def stage(self, stage: str):
        return self.where(stage=stage)

    def refined(self, *, stage: str | None = None):
        """Return persisted strain-partitioned and/or registry-refined interfaces."""
        if stage is not None and stage not in {
            "strain_partitioned",
            "registry_refined",
        }:
            raise ValueError(
                "stage must be 'strain_partitioned', 'registry_refined', or None"
            )
        self._ensure_loaded()
        allowed = (
            {stage}
            if stage is not None
            else {
                "strain_partitioned",
                "registry_refined",
            }
        )
        out = []
        for item in self._ifaces:
            row = self._normalize_item(item)
            if row.get("stage") in allowed:
                out.append(item)
        return self._clone(out)

    def relaxed(self):
        """Return authoritative structurally relaxed interfaces."""
        self._ensure_loaded()
        return self._clone(
            [
                item
                for item in self._ifaces
                if self._normalize_item(item).get("stage") == "relaxed"
            ]
        )

    def candidate(
        self, candidate_id: str | None = None, *, candidate_uid: str | None = None
    ):
        if candidate_id is None and candidate_uid is None:
            return self
        self._ensure_loaded()
        out = []
        for item in self._ifaces:
            r = self._normalize_item(item)
            if candidate_id is not None and str(r.get("candidate_id")) == str(
                candidate_id
            ):
                out.append(item)
                continue
            if candidate_uid is not None and str(
                r.get("candidate_uid") or r.get("prototype_uid")
            ) == str(candidate_uid):
                out.append(item)
        return self._clone(out)

    def search(self, name: str | None = None, *, id: str | None = None):
        if name is None and id is None:
            return self
        self._ensure_loaded()
        out = []
        for item in self._ifaces:
            r = self._normalize_item(item)
            if name is not None and r.get("search_name") == name:
                out.append(item)
                continue
            if id is not None and r.get("search_id") == id:
                out.append(item)
        return self._clone(out)

    def write_structures(
        self,
        directory: str | Path,
        *,
        format: str | None = None,
    ) -> list[Path]:
        """Write each selected interface through its authoritative atom source."""
        from calm.structure.io import safe_write_structure

        from calm.public.records.persistence import ProjectInterface
        from calm.public.records.interfaces import InterfaceModel

        self._ensure_loaded()
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        for index, item in enumerate(self._ifaces):
            if isinstance(item, InterfaceModel):
                atoms = item.atoms
                row = self._normalize_item(item)
            else:
                record = self._public_item(item)
                if not isinstance(record, ProjectInterface):
                    raise TypeError(
                        "Interface structure export requires InterfaceModel or "
                        "authoritative ProjectInterface records."
                    )
                identifier = record.uid_full or record.id_short
                if identifier is None:
                    raise RuntimeError(
                        "Authoritative interface records must expose durable identity."
                    )
                if self._project is None:
                    raise RuntimeError(
                        "Persisted interface export requires the owning Project."
                    )
                atoms = self._project._structure_queries.get_interface_atoms(identifier)
                row = record.to_dict()

            if atoms is None:
                raise ValueError("Interface has no atomistic structure to export.")
            name = str(
                row.get("label")
                or row.get("id_short")
                or row.get("uid_full")
                or f"interface_{index:04d}"
            )
            safe_name = name.replace("/", "_").replace(" ", "_")
            path = output / f"{safe_name}.vasp"
            safe_write_structure(path, atoms, format=format)
            written.append(path)
        return written

    def plot_build_summary(
        self,
        *,
        x: str = "interface_id",
        y: str = "n_atoms",
        save: str | None = None,
        **kwargs,
    ):
        rows = self.to_rows(view="all")
        try:
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise ImportError("plot_build_summary() requires matplotlib.") from error
        fig, ax = plt.subplots()
        labels = [
            str(r.get(x) or r.get("interface_id") or i) for i, r in enumerate(rows)
        ]
        values = []
        for r in rows:
            try:
                values.append(float(r.get(y)))
            except (TypeError, ValueError):
                values.append(0.0)
        ax.bar(labels, values)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if labels:
            ax.tick_params(axis="x", labelrotation=45)
        fig.tight_layout()
        if save is not None:
            path = Path(save)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, **kwargs)
        return fig, ax
