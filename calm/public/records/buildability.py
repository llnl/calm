"""Buildability reporting primitives for public facade workflows.

Provides simple data classes used by candidate/collection validation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BuildabilityIssue:
    candidate_id: str | None
    candidate_uid: str | None
    code: str
    message: str


@dataclass
class BuildabilityReport:
    n_candidates: int
    n_buildable: int
    issues: list[BuildabilityIssue]

    @property
    def ok(self) -> bool:
        return self.n_buildable == self.n_candidates

    def summary(self) -> str:
        lines = [f"Buildability: {self.n_buildable}/{self.n_candidates} buildable"]
        if self.issues:
            lines.append("Issues:")
            for it in self.issues:
                lines.append(
                    f"  {it.candidate_id or it.candidate_uid}: {it.code} - {it.message}"
                )
        return "\n".join(lines)


@dataclass
class PersistedSearchBuildabilitySummary:
    """Convenience summary object describing buildability/readiness of a
    persisted named search. This composes an existing BuildabilityReport and
    small status counters to present a stable public-facing contract for
    examples and scripts.

    Fields:
    - name: search name
    - n_candidates: total candidate rows
    - n_authoritative_prototypes: count of rows referencing authoritative prototypes
    - n_buildable: number of buildable candidates (from BuildabilityReport)
    - n_built_interfaces: number of existing persisted derived interfaces
    - report: BuildabilityReport instance
    - has_buildable_candidates: True when at least one buildable candidate exists
    - all_candidates_buildable: True when every candidate is buildable (report.ok)
    """

    name: str
    n_candidates: int
    n_authoritative_prototypes: int
    n_buildable: int
    n_built_interfaces: int
    report: BuildabilityReport

    @property
    def has_buildable_candidates(self) -> bool:
        return int(self.n_buildable) > 0

    @property
    def all_candidates_buildable(self) -> bool:
        return bool(self.report and self.report.ok)

    @property
    def ok(self) -> bool:
        """Workflow-oriented ok: at least one authoritative, buildable candidate.

        This definition aligns with the common Level-4 user flow: a search is
        usable for building when it can produce at least one buildable
        interface, even if some candidates are problematic.
        """
        return self.has_buildable_candidates

    def summary(self) -> str:
        lines = [
            f"Search: {self.name}",
            f"Candidates: {self.n_candidates}",
            f"Authoritative prototypes: {self.n_authoritative_prototypes}",
            f"Buildable candidates: {self.n_buildable}",
            f"Built interfaces: {self.n_built_interfaces}",
        ]
        if self.report:
            lines.append("")
            lines.append(self.report.summary())
        return "\n".join(lines)

    def explain(self) -> str:
        # More actionable explanation for non-ok states
        lines = [self.summary()]
        if not self.has_buildable_candidates:
            lines.append("")
            lines.append("No buildable candidates were detected for this search.")
            lines.append(
                "To make this search buildable, ensure authoritative prototypes were persisted when running the search."
            )
            lines.append(
                "Re-run the matching search with a Project backend that persists prototypes or inspect candidate rows for missing prototype references."
            )
        if not self.all_candidates_buildable:
            lines.append("")
            lines.append(
                "Some candidates are not buildable; inspect individual candidate issues via search.candidates().to_table(...).display() or use the candidate.validate_buildable() API for details."
            )
        return "\n".join(lines)
