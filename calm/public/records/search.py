"""Durable query and navigation view for one persisted interface search.

Workflow execution remains on ``Project``. This object exposes status,
candidates, buildability, and interfaces without becoming a second workflow
entry point.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from calm.public.records.buildability import BuildabilityReport
from calm.public.collections.candidates import CandidateCollection

if TYPE_CHECKING:
    from calm.public.records.buildability import PersistedSearchBuildabilitySummary
    from calm.public.records.search_audit import InterfaceSearchEnumerationAudit


@dataclass
class PersistedInterfaceSearch:
    """Bind one persisted search to its originating Project.

    Users inspect the durable search through this view and pass it back to
    ``Project.build_interfaces`` or ``Project.refine_interfaces`` when starting
    another workflow stage.
    """

    project: Any
    name: str
    record: Any | None = None

    @property
    def uid_full(self) -> str | None:
        return getattr(self.record, "uid_full", None)

    @property
    def id_short(self) -> str | None:
        return getattr(self.record, "id_short", None)

    @property
    def authority(self):
        return getattr(self.record, "authority", None)

    @property
    def run_status(self) -> str | None:
        """Return the persisted workflow status for this search."""
        value = getattr(self.record, "status", None)
        return str(value) if value is not None else None

    @property
    def failure(self) -> Any | None:
        """Return the structured persisted failure, when present."""
        return getattr(self.record, "failure", None)

    @property
    def empty(self) -> bool:
        """Return whether this search currently has no persisted candidates."""
        return len(self.candidates()) == 0

    def _enumeration_audit_payload(self) -> Any | None:
        progress = getattr(self.record, "progress", None)
        if progress is None:
            metadata = getattr(self.record, "metadata", None)
            if isinstance(metadata, Mapping):
                progress = metadata.get("progress")
        if not isinstance(progress, Mapping):
            return None
        return progress.get("enumeration_audit")

    @property
    def has_enumeration_audit(self) -> bool:
        """Return whether this completed search persisted enumeration accounting."""

        return self._enumeration_audit_payload() is not None

    def enumeration_audit(self) -> "InterfaceSearchEnumerationAudit":
        """Return immutable enumeration accounting for this persisted search.

        Searches completed before enumeration accounting was persisted cannot be
        reconstructed from the final candidate population. Rerun the same named
        search with ``resume=False`` to populate the audit.
        """

        payload = self._enumeration_audit_payload()
        if payload is None:
            from calm.public.errors import SearchEnumerationAuditUnavailableError

            raise SearchEnumerationAuditUnavailableError(
                f"Persisted search {self.name!r} has no enumeration audit. "
                "Rerun the same named search with resume=False to recompute and "
                "persist complete enumeration accounting."
            )
        from calm.public.records.search_audit import InterfaceSearchEnumerationAudit

        return InterfaceSearchEnumerationAudit.from_value(payload)

    def candidates(self) -> CandidateCollection:
        return self.project.candidates().search(self.name)

    def validate_buildable(self) -> BuildabilityReport:
        return self.project._health.search_buildability(self.name)

    def status(self) -> dict:
        """Return authoritative workflow status and readiness counters."""
        return self.project._health.search_status(self.name)

    def buildability_summary(self) -> "PersistedSearchBuildabilitySummary":
        """Return a stable readiness summary for this named search."""
        return self.project._health.search_summary(self.name)

    def summary(self) -> str:
        """Return a concise human-readable summary of the persisted search."""
        st = self.status()
        lines = [f"Persisted interface search: {st['name']}"]
        if st.get("status"):
            lines.append(f"  status: {st['status']}")
        lines.extend(
            (
                f"  candidates: {st['n_candidates']}",
                f"  authoritative prototypes: {st['n_authoritative_prototypes']}",
                f"  buildable candidates: {st['n_buildable']}",
                f"  built interfaces: {st['n_built_interfaces']}",
            )
        )
        return "\n".join(lines)

    def explain(self) -> str:
        """Return a human-readable explanation of the persisted search state.

        This summarizes status and, when problems exist, provides actionable
        suggestions for the user.
        """
        st = self.status()
        lines = self.summary().splitlines()
        if st.get("search_identity"):
            lines.append(f"  search identity: {st['search_identity']}")

        if st.get("failure"):
            failure = st["failure"]
            message = (
                failure.get("message") if isinstance(failure, dict) else str(failure)
            )
            lines.append("")
            lines.append(f"The persisted search failed: {message}")
            lines.append(
                "Rerun the same named search with resume=True to restart it on the same deterministic run identity."
            )

        if st["n_authoritative_prototypes"] == 0:
            lines.append("")
            lines.append(
                "This search appears to be reporting-only: candidate rows exist but authoritative prototype records are missing."
            )
            lines.append(
                "To make this search buildable, rerun the search with a Project backend that persists prototypes:"
            )
            lines.append(
                '  project.search_interfaces(surface_a, surface_b, settings=..., name="{name}")'
            )

        report = self.validate_buildable()
        if not report.ok:
            lines.append("")
            lines.append("Buildability issues summary:")
            lines.append(report.summary())
            lines.append("")
            lines.append(
                "Inspect individual candidate issues via search.candidates().to_table(...).display() or use the candidate.validate_buildable() API for details."
            )

        return "\n".join(lines)

    def interfaces(self):
        # Membership is derived from the authoritative search run, its
        # prototypes, and the interfaces derived from those prototypes.
        return self.project.interfaces().search(name=self.name)

    def prototype_ids(
        self, *, top: int | None = None, pareto: bool = True
    ) -> list[str]:
        """Return durable prototype identifiers for this persisted search.

        Scans candidate rows for authoritative prototype identifiers and returns
        a de-duplicated list. By default selects only Pareto candidates; set
        pareto=False to consider all candidates. Optionally limit to the top N
        candidates (by score) when ``top`` is provided.
        """
        coll = self.candidates()
        if pareto:
            coll = coll.select(pareto=True)
        if top is not None:
            coll = coll.select_top(int(top), by="score")
        rows = coll.to_rows(view="all")
        ids: list[str] = []
        seen = set()
        for r in rows:
            # Only accept authoritative persisted prototype identifiers.
            # Do not accept internal candidate_uid descriptors as they may
            # reference non-persisted internal objects that the workspace
            # cannot resolve. Prefer explicit project-level persisted ids.
            v = r.get("project_prototype_uid") or r.get("project_prototype_id")
            if v:
                s = str(v)
                if s not in seen:
                    ids.append(s)
                    seen.add(s)
        return ids

    def _authoritative_interface_uids(self) -> tuple[str, ...]:
        """Return authoritative interface identities associated with this search."""
        values: list[str] = []
        seen: set[str] = set()
        for interface in self.interfaces().records():
            authority = getattr(interface, "authority", None)
            authority_value = getattr(authority, "value", authority)
            if authority_value not in {None, "authoritative"}:
                continue
            uid = getattr(interface, "uid_full", None)
            if uid and str(uid) not in seen:
                values.append(str(uid))
                seen.add(str(uid))
        return tuple(values)

    def _lineage_followups(self, *, kind: str):
        """Return follow-ups descended from this search's persisted interfaces."""
        from calm.public.records.persistence import ProjectEdge, ProjectFollowupResult

        repo = getattr(self.project, "_repo", None)
        if repo is None:
            return []

        results: dict[str, ProjectFollowupResult] = {}
        for interface_uid in self._authoritative_interface_uids():
            for raw_edge in repo.list_edges(
                src=interface_uid,
                kind="interface_to_followup",
                limit=100000,
            ):
                edge = ProjectEdge.from_item(raw_edge)
                try:
                    raw_result = repo.get_followup_result(edge.dst_uid_full)
                except (KeyError, ValueError, RuntimeError):
                    continue
                result = ProjectFollowupResult.from_item(raw_result)
                if result.kind == kind:
                    results[result.uid_full] = result

        return sorted(
            results.values(),
            key=lambda item: (str(item.created_at or ""), item.uid_full),
        )

    @staticmethod
    def _matches_result_status(record: Any, status: str | None) -> bool:
        if status is None:
            return True
        normalized = str(status).strip().lower()
        if normalized in {"completed", "done", "succeeded", "success"}:
            return bool(getattr(record, "succeeded", False))
        if normalized in {"failed", "failure"}:
            return (
                bool(getattr(record, "failure", None))
                or str(getattr(record, "status", "")).lower() == "failed"
            )
        return str(getattr(record, "status", "")).lower() == normalized

    def _select_result_run(
        self,
        results: list[Any],
        *,
        run: Any | None,
        latest_run: bool,
        run_type: str,
        result_label: str,
    ) -> list[Any]:
        from calm.public.errors import AmbiguousProjectQueryError

        if run is not None and latest_run:
            raise ValueError("run and latest_run=True are mutually exclusive.")

        if run is not None:
            identifier = (
                getattr(run, "uid_full", None)
                or getattr(run, "id_short", None)
                or str(run)
            )
            selected_run = self.project.run(str(identifier))
            if selected_run.run_type != run_type:
                raise ValueError(
                    f"Run {identifier!r} has type {selected_run.run_type!r}; "
                    f"expected {run_type!r}."
                )
            return [
                result
                for result in results
                if result.run_uid_full == selected_run.uid_full
            ]

        run_uids = sorted(
            {
                str(result.run_uid_full)
                for result in results
                if result.run_uid_full is not None
            }
        )
        if len(run_uids) <= 1:
            return results
        if not latest_run:
            raise AmbiguousProjectQueryError(
                f"Persisted search {self.name!r} has {result_label} from "
                f"multiple {run_type!r} runs. Pass run=... or "
                "latest_run=True to select one run explicitly."
            )

        runs = [self.project.run(uid) for uid in run_uids]
        selected_run = max(
            runs,
            key=lambda item: (str(item.created_at or ""), item.uid_full),
        )
        return [
            result for result in results if result.run_uid_full == selected_run.uid_full
        ]

    def _runs_for_results(
        self,
        results: list[Any],
        *,
        run_type: str,
        status: str | None,
    ):
        from calm.public.collections.persistence import RunCollection

        run_uids = sorted(
            {
                str(result.run_uid_full)
                for result in results
                if result.run_uid_full is not None
            }
        )
        runs = [self.project.run(uid) for uid in run_uids]
        if status is not None:
            normalized = str(status).strip().lower()
            runs = [
                run for run in runs if str(run.status).strip().lower() == normalized
            ]
        return RunCollection(run for run in runs if run.run_type == run_type)

    def reference_energy_runs(self, *, status: str | None = None):
        """Return reference-energy runs linked to interfaces from this search."""
        results = self._lineage_followups(kind="reference_energy")
        return self._runs_for_results(
            results,
            run_type="reference_energy",
            status=status,
        )

    def reference_energy_results(
        self,
        *,
        run: Any | None = None,
        status: str | None = None,
        latest_run: bool = False,
        formula: str | None = None,
        reference_kind: str | None = None,
    ):
        """Return one run's reference energies for this persisted search."""
        from calm.public.collections.persistence import ReferenceEnergyResultCollection
        from calm.public.records.persistence import ProjectReferenceEnergyResult

        results = [
            ProjectReferenceEnergyResult.from_item(item)
            for item in self._lineage_followups(kind="reference_energy")
        ]
        results = [
            result for result in results if self._matches_result_status(result, status)
        ]
        selected = self._select_result_run(
            results,
            run=run,
            latest_run=latest_run,
            run_type="reference_energy",
            result_label="reference-energy results",
        )
        collection = ReferenceEnergyResultCollection(selected)
        if formula is not None:
            collection = collection.where(formula_id=str(formula))
        if reference_kind is not None:
            collection = collection.reference_kind(str(reference_kind))
        return collection

    def energy_runs(self, *, status: str | None = None):
        """Return raw-energy runs linked to interfaces from this search."""
        raw_results = self._lineage_followups(kind="energy_stage")
        return self._runs_for_results(
            raw_results,
            run_type="energy_stage",
            status=status,
        )

    def energy_results(
        self,
        *,
        run: Any | None = None,
        status: str | None = None,
        latest_run: bool = False,
    ):
        """Return one run's raw-energy results for interfaces from this search.

        Results are scoped through authoritative ``interface_to_followup``
        lineage edges. If more than one matching energy run exists, callers
        must pass ``run=...`` or opt into deterministic ``latest_run=True``
        selection; results from separate runs are never combined silently.
        """
        from calm.public.collections.persistence import EnergyResultCollection
        from calm.public.records.persistence import ProjectEnergyResult

        results = [
            ProjectEnergyResult.from_item(item)
            for item in self._lineage_followups(kind="energy_stage")
        ]
        results = [
            result for result in results if self._matches_result_status(result, status)
        ]
        selected = self._select_result_run(
            results,
            run=run,
            latest_run=latest_run,
            run_type="energy_stage",
            result_label="raw-energy results",
        )
        return EnergyResultCollection(selected)

    def thermodynamic_runs(self, *, status: str | None = None):
        """Return thermodynamic-derivation runs linked to this search."""
        results = self._lineage_followups(kind="thermodynamic_quantity")
        return self._runs_for_results(
            results,
            run_type="thermodynamic_derivation",
            status=status,
        )

    def thermodynamic_results(
        self,
        *,
        run: Any | None = None,
        status: str | None = None,
        latest_run: bool = False,
    ):
        """Return one run's derived thermodynamic results for this search."""
        from calm.public.collections.persistence import ThermodynamicResultCollection
        from calm.public.records.persistence import ProjectThermodynamicResult

        results = [
            ProjectThermodynamicResult.from_item(item)
            for item in self._lineage_followups(kind="thermodynamic_quantity")
        ]
        results = [
            result for result in results if self._matches_result_status(result, status)
        ]
        selected = self._select_result_run(
            results,
            run=run,
            latest_run=latest_run,
            run_type="thermodynamic_derivation",
            result_label="thermodynamic results",
        )
        return ThermodynamicResultCollection(selected)
