"""Read-only project health, buildability, and opening-summary presentation."""

from __future__ import annotations

from typing import Any


class ProjectHealthService:
    """Diagnose authoritative project state without repairing or mutating it."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: Any,
        repository: Any,
        queries: Any,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository
        self._queries = queries

    def check_prototype_buildability(self, prototype: str) -> Any:
        """Return the authoritative buildability result for one prototype."""
        return self._workspace.check_prototype_buildability(prototype)

    def check_prototypes_buildability(
        self,
        prototypes: list[str],
    ) -> dict[str, Any]:
        """Return authoritative buildability results for a prototype batch."""
        return self._workspace.check_prototypes_buildability(prototypes)

    def search_buildability(self, name: str):
        """Return the public buildability report for one named search."""
        return self._queries.candidates().search(name).validate_buildable()

    def search_status(self, name: str) -> dict[str, Any]:
        """Return authoritative workflow-readiness counters for one search."""
        search = self._repo.get_search(name)
        canonical_name = str(getattr(search, "name", name))
        rows = self._repo.list_candidates(search_name=canonical_name)
        n_authoritative = sum(
            1
            for row in rows
            if bool(row.get("project_prototype_uid") or row.get("project_prototype_id"))
        )
        report = self.search_buildability(canonical_name)
        failure = getattr(search, "failure", None)
        if failure is not None and hasattr(failure, "to_dict"):
            failure = failure.to_dict()
        return {
            "name": canonical_name,
            "status": getattr(search, "status", None),
            "search_identity": getattr(search, "search_identity", None),
            "run_uid_full": getattr(search, "run_uid_full", None),
            "run_id_short": getattr(search, "run_id_short", None),
            "failure": failure,
            "n_candidates": len(rows),
            "n_authoritative_prototypes": n_authoritative,
            "n_buildable": int(report.n_buildable),
            "n_built_interfaces": len(
                self._repo.list_interfaces(search_name=canonical_name)
            ),
        }

    def search_summary(self, name: str):
        """Return a stable readiness summary for one named search."""
        from calm.public.records.buildability import PersistedSearchBuildabilitySummary

        status = self.search_status(name)
        report = self.search_buildability(name)
        return PersistedSearchBuildabilitySummary(
            name=str(status["name"]),
            n_candidates=int(status["n_candidates"]),
            n_authoritative_prototypes=int(status["n_authoritative_prototypes"]),
            n_buildable=int(status["n_buildable"]),
            n_built_interfaces=int(status["n_built_interfaces"]),
            report=report,
        )

    def project_counts(self) -> dict[str, int]:
        """Return authoritative stored-object counts for opening summaries."""
        return {
            "materials": len(self._repo.list_bulks()),
            "surfaces": len(self._repo.list_slabs()),
            "searches": len(self._repo.list_searches(limit=None)),
            "candidates": len(self._repo.list_candidates()),
            "interfaces": len(self._repo.list_interfaces()),
            "datasets": len(self._repo.list_datasets(limit=None)),
            "energies": len(
                self._repo.list_followup_results(
                    kind="energy_stage",
                    limit=100000,
                )
            ),
        }

    def _calculator_label(self) -> str:
        configuration = dict(getattr(self._project, "_configuration", {}) or {})
        uid = configuration.get("default_calculator_uid_full")
        if not uid:
            return "none"
        calculator = self._workspace.get_calculator(str(uid))
        if calculator is None:
            return str(uid)
        family = getattr(calculator, "family", None)
        model = getattr(calculator, "model", None)
        if family and model:
            return f"{family}:{model}"
        return str(uid)

    def project_info(self) -> dict[str, str]:
        """Return persisted configuration fields used in opening summaries."""
        configuration = dict(getattr(self._project, "_configuration", {}) or {})
        workflow_defaults = configuration.get("workflow_defaults")
        path = getattr(self._project, "path", None)
        return {
            "path": str(path) if path is not None else "<unknown>",
            "mlip": str(configuration.get("default_mlip") or "none"),
            "calculator": self._calculator_label(),
            "workflow defaults": ("present" if workflow_defaults else "none"),
        }

    def workflow_warnings(self) -> list[str]:
        """Return actionable warnings for current persisted searches."""
        warnings: list[str] = []
        seen: set[str] = set()
        for search in self._repo.list_searches(limit=None):
            name = str(getattr(search, "name", "") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                status = self.search_status(name)
            except KeyError:
                # A search may disappear between collection construction and
                # exact lookup. It is no longer a current workflow to diagnose.
                continue
            n_candidates = int(status.get("n_candidates", 0) or 0)
            n_authoritative = int(status.get("n_authoritative_prototypes", 0) or 0)
            n_buildable = int(status.get("n_buildable", 0) or 0)

            if n_candidates > 0 and n_authoritative == 0:
                warnings.append(
                    f"Search {name} is reporting-only: candidates exist, but "
                    "authoritative prototypes are missing."
                )
                warnings.append(
                    "Re-run the interface search with a persistent Project "
                    "backend to make this search buildable."
                )
                continue

            if n_candidates > 0 and n_buildable == 0:
                warnings.append(f"Search {name} has no buildable candidates.")
                warnings.append(
                    f"Inspect project.search({name!r})."
                    "buildability_summary().explain() for details."
                )
        return warnings

    def report_open_project(self, reporter: Any) -> None:
        """Emit the optional project-open summary through ``reporter``."""
        with reporter.section("Opened CALM project"):
            reporter.mapping(self.project_info(), title="Project")
            reporter.mapping(self.project_counts(), title="Stored objects")

            warnings = self.workflow_warnings()
            for message in warnings:
                reporter.warn(message)

            if warnings:
                reporter.summary("Project opened with workflow warnings")
            else:
                reporter.summary("Project ready for scientific workflows")
