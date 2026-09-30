"""Internal persistence dispatch for the public Project workflow.

User-authored materials enter through ``Project.add_material``. Search, build,
and energy workflows persist their internal result objects through this module
without exposing a generic public ``save`` operation.
"""

from __future__ import annotations

from typing import Any


class PublicProjectSaver:
    """Persist workflow objects through authoritative project owners."""

    def __init__(self, *, workspace: Any, repo: Any | None = None):
        from calm.public.persistence.adapter import WorkspaceAdapter

        if not isinstance(workspace, WorkspaceAdapter):
            raise TypeError(
                "PublicProjectSaver requires the Project-owned WorkspaceAdapter."
            )
        self._workspace = workspace
        self._repo = repo

    def record_search_result(
        self,
        result: Any,
        *,
        name: str | None = None,
        tags=None,
        reporter: Any | None = None,
    ) -> None:
        """Persist the authoritative prototypes produced by one search.

        Search and candidate reporting projections are retired. ``name`` is
        used only for reporting this persistence step, while ``tags`` is
        rejected until CALM has an explicit durable annotation owner.
        """
        from calm.public.presentation.reporting import ensure_console_reporter

        rep = ensure_console_reporter(reporter)

        if tags:
            raise ValueError(
                "Persisted search candidates do not support implicit tags; "
                "store durable annotations through an explicit annotation owner."
            )

        n_candidates = len(result.candidates)

        with rep.stage("record_search_result", name=name, n_candidates=n_candidates):
            internal = getattr(result, "_internal_result", None)
            protos = getattr(internal, "prototypes", None)
            proto_map = None
            if protos:
                metadata = dict(getattr(result, "metadata", {}) or {})
                proto_map = self._workspace.persist_interface_prototypes(
                    protos,
                    run_uid_full=metadata.get("run_uid_full"),
                )
                result._persisted_prototype_map = proto_map

            rep.mapping(
                {
                    "n_candidates": n_candidates,
                    "n_prototypes_persisted": len(proto_map) if proto_map else 0,
                },
                title="Search persistence summary",
            )

    def record_interface_model(
        self,
        interface: Any,
        *,
        name: str | None = None,
        reporter: Any | None = None,
    ) -> Any:
        """Persist one interface exactly once through the authoritative repository."""
        if self._repo is None:
            from calm.public.errors import ProjectPersistenceError

            raise ProjectPersistenceError(
                "Interface persistence requires the Project repository boundary."
            )

        from calm.public.presentation.reporting import ensure_console_reporter

        rep = ensure_console_reporter(reporter)
        with rep.stage("record_interface_model", name=name):
            persisted = self._repo.save_interface(
                interface,
                name=name,
            )
            rep.mapping(
                {
                    "written": True,
                    "name": name,
                    "uid_full": getattr(persisted, "uid_full", None),
                    "id_short": getattr(persisted, "id_short", None),
                },
                title="Interface persistence summary",
            )
            return persisted

    def persist_material(
        self,
        obj: Any,
        *,
        name: str | None = None,
        reporter: Any | None = None,
    ):
        """Persist one supported material through the exact current contract."""
        from calm.public.workflows.materials import persist_material

        return persist_material(
            workspace=self._workspace,
            obj=obj,
            name=name,
            reporter=reporter,
        )
