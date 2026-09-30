"""Internal orchestration owner for public interface construction.

The :class:`~calm.public.project.Project` facade delegates persisted-search
candidate selection and interface construction to this service. Scientific
construction and persistence remain owned by the current Workspace and public
repository boundaries; this module owns public workflow validation, sequencing,
reporting, and typed result assembly.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, Protocol

from calm.public.presentation.reporting import ensure_console_reporter

from calm.public.projections.buildability import prototype_identifier_from_candidate_row
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.records.interfaces import InterfaceModel
from calm.public.inputs.settings import BuildSettings


class _BuildWorkspace(Protocol):
    def build_interface_from_prototype(
        self,
        prototype: str,
        **kwargs: Any,
    ) -> Any: ...


class _BuildSaver(Protocol):
    def record_interface_model(
        self,
        interface: Any,
        *,
        name: str | None = None,
        reporter: Any | None = None,
    ) -> Any: ...


class ProjectInterfaceBuildService:
    """Coordinate public interface construction over authoritative candidates."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: _BuildWorkspace,
        repository: Any,
        saver: _BuildSaver,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository
        self._saver = saver

    @staticmethod
    def _candidate_row(candidate: Any) -> dict[str, Any]:
        if isinstance(candidate, Mapping):
            return dict(candidate)
        to_dict = getattr(candidate, "to_dict", None)
        if not callable(to_dict):
            raise TypeError("Selected candidates must expose a to_dict() mapping.")
        row = to_dict()
        if not isinstance(row, Mapping):
            raise TypeError("Candidate.to_dict() must return a mapping.")
        return dict(row)

    def _build_interface_model(
        self,
        row: dict[str, Any],
        *,
        settings: BuildSettings,
    ) -> InterfaceModel:
        prototype = prototype_identifier_from_candidate_row(row)
        if prototype is None:
            raise RuntimeError(
                "Candidate rows must carry an authoritative prototype identifier."
            )
        built = self._workspace.build_interface_from_prototype(
            prototype,
            alpha=settings.alpha,
            translation_frac=settings.translation,
            z_padding=settings.gap,
            vacuum=settings.vacuum,
        )
        internal = SimpleNamespace(
            atoms=built.atoms,
            prototype_uid=(
                getattr(built, "prototype_uid_full", None)
                or getattr(built, "prototype_uid", None)
            ),
            build_uid=None,
            area_A2=None,
        )
        return InterfaceModel(internal, build_settings=settings)

    def build_interfaces(
        self,
        search: Any,
        *,
        top: int = 1,
        settings: BuildSettings | None = None,
        name_prefix: str | None = None,
        reporter: Any | None = None,
    ) -> InterfaceCollection:
        """Build and persist the top authoritative candidates from one search."""

        if isinstance(top, bool) or not isinstance(top, int) or top <= 0:
            raise ValueError("top must be a positive integer.")
        if settings is not None and not isinstance(settings, BuildSettings):
            raise TypeError("settings must be a BuildSettings instance or None.")

        search = self._project.search(search)
        selected = search.candidates().select(pareto=True).select_top(top, by="score")
        rows = [self._candidate_row(candidate) for candidate in selected]
        missing = [
            row.get("candidate_id") or row.get("candidate_uid") or "<unknown>"
            for row in rows
            if not (row.get("project_prototype_uid") or row.get("project_prototype_id"))
        ]
        if missing:
            raise RuntimeError(
                "Build aborted because selected candidates lack authoritative "
                "persisted prototype identifiers: " + ", ".join(map(str, missing))
            )

        report = selected.validate_buildable()
        if not report.ok:
            raise RuntimeError(
                f"Build aborted: {len(report.issues)} buildability issues detected.\n"
                f"{report.summary()}"
            )

        resolved_settings = settings or BuildSettings()
        rep = ensure_console_reporter(reporter)
        built: list[Any] = []
        with rep.stage("build_interfaces", search=search.name, n=top):
            for index, row in enumerate(rows):
                model = self._build_interface_model(
                    row,
                    settings=resolved_settings,
                )
                if getattr(model, "candidate", None) is None:
                    model.candidate = dict(row)
                name = f"{name_prefix}_{index:04d}" if name_prefix else None
                persisted = self._saver.record_interface_model(
                    model,
                    name=name,
                    reporter=rep,
                )
                if isinstance(persisted, Mapping):
                    project_uid = persisted.get("uid_full")
                    project_id = persisted.get("id_short")
                else:
                    project_uid = getattr(persisted, "uid_full", None)
                    project_id = getattr(persisted, "id_short", None)
                if not project_uid or not project_id:
                    raise RuntimeError(
                        "Authoritative interface persistence did not return uid_full "
                        "and id_short."
                    )
                model.project_interface_uid = str(project_uid)
                model.project_interface_id = str(project_id)
                model._persisted_record = persisted
                built.append(model)

        rep.mapping(
            {"n_selected": len(rows), "n_built": len(built)},
            title="Build interfaces summary",
        )
        return InterfaceCollection(
            workspace=self._project,
            interfaces=built,
            repo=self._repo,
            project=self._project,
        )
