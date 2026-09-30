"""Workspace consistency validation.

This module provides utilities for validating workspace database integrity,
checking for broken references, orphaned records, and other consistency issues.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from calm.project.domain.contracts.bulk_record import (
    CurrentBulkPayloadError,
    InvalidBulkCanonicalizationProvenanceError,
    MissingBulkCanonicalizationProvenanceError,
)

from ._uow import fresh_uow, require_uow_factory


@dataclass
class ValidationIssue:
    """A single validation issue found during workspace consistency check.

    Attributes
    ----------
    severity : str
        Issue severity: "error", "warning", or "info"
    category : str
        Issue category (e.g., "broken_reference", "orphaned_record", "missing_data")
    entity_type : str
        Type of entity affected (e.g., "slab", "prototype", "artifact")
    entity_id : str
        Short ID of affected entity
    message : str
        Human-readable description of the issue
    details : dict
        Additional context about the issue
    """

    severity: str  # "error", "warning", "info"
    category: str
    entity_type: str
    entity_id: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Report of workspace consistency validation.

    Attributes
    ----------
    issues : list[ValidationIssue]
        List of all issues found
    summary : dict[str, int]
        Summary statistics (counts by severity and category)
    """

    issues: list[ValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Number of errors found."""
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Number of warnings found."""
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def info_count(self) -> int:
        """Number of info messages."""
        return sum(1 for issue in self.issues if issue.severity == "info")

    @property
    def is_valid(self) -> bool:
        """True if no errors or warnings found."""
        return self.error_count == 0 and self.warning_count == 0

    def add_issue(
        self,
        severity: str,
        category: str,
        entity_type: str,
        entity_id: str,
        message: str,
        **details: Any,
    ) -> None:
        """Add an issue to the report."""
        self.issues.append(
            ValidationIssue(
                severity=severity,
                category=category,
                entity_type=entity_type,
                entity_id=entity_id,
                message=message,
                details=dict(details),
            )
        )

    def compute_summary(self) -> None:
        """Compute summary statistics."""
        self.summary = {
            "total_issues": len(self.issues),
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "by_severity": self._count_by("severity"),
            "by_category": self._count_by("category"),
            "by_entity_type": self._count_by("entity_type"),
        }

    def _count_by(self, field: str) -> dict[str, int]:
        """Count issues by a given field."""
        counts = defaultdict(int)
        for issue in self.issues:
            value = getattr(issue, field)
            counts[value] += 1
        return dict(counts)


class WorkspaceValidator:
    """Workspace consistency validator.

    This validator checks for:
    - Broken references (entities referencing non-existent entities)
    - Orphaned records (entities not referenced by anything)
    - Missing data (required fields that are null or empty)
    - Duplicate entities (same UID appearing multiple times)
    """

    def __init__(self, *, uow_factory: Callable[[], Any]):
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="WorkspaceValidator",
        )

    def validate(
        self,
        *,
        check_references: bool = True,
        check_orphans: bool = False,
        check_duplicates: bool = True,
        check_provenance: bool = False,
    ) -> ValidationReport:
        """Validate workspace consistency.

        Parameters
        ----------
        check_references : bool
            If True, check for broken references (default True)
        check_orphans : bool
            If True, check for orphaned records (default False)
        check_duplicates : bool
            If True, check for duplicate UIDs (default True)
        check_provenance : bool
            If True, validate provenance payloads stored in ``Atoms.info``
            (default False).

        Returns
        -------
        ValidationReport
            Report containing all issues found
        """
        report = ValidationReport()

        with fresh_uow(self._uow_factory, owner="WorkspaceValidator") as uow:
            # Build UID registries for reference checking
            bulk_uids = set()
            slab_uids = set()
            prototype_uids = set()
            run_uids = set()

            # Load all entity identities without hydrating malformed bulk rows.
            bulk_references = list(uow.bulks.list_reference_records(limit=100000))
            slab_references = list(uow.slabs.list_reference_records(limit=100000))
            current_slabs = self._hydrate_current_slabs(
                report,
                uow,
                slab_references,
            )
            # Prototype repositories expose ``query`` rather than ``list``.
            prototypes = list(uow.prototypes.query(limit=100000))
            runs = list(uow.runs.list(limit=100000))

            # Build UID sets
            for bulk in bulk_references:
                bulk_uids.add(bulk.uid_full)

            for slab in slab_references:
                slab_uids.add(slab.uid_full)

            for proto in prototypes:
                prototype_uids.add(proto.uid_full)

            for run in runs:
                run_uids.add(run.uid_full)

            # Check for duplicate UIDs
            if check_duplicates:
                self._check_duplicates(report, "bulk", bulk_references)
                self._check_duplicates(report, "slab", slab_references)
                self._check_duplicates(report, "prototype", prototypes)
                self._check_duplicates(report, "run", runs)

            # Check references
            if check_references:
                self._check_slab_references(
                    report,
                    slab_references,
                    bulk_uids,
                )
                self._check_prototype_references(
                    report,
                    prototypes,
                    slab_uids,
                    run_uids,
                )
                self._check_derived_interface_references(report, uow, prototype_uids)
                self._check_artifact_references(report, uow, run_uids)
                self._check_followup_references(report, uow, run_uids, prototype_uids)

            # Hydrate exact-current scientific state when provenance checks
            # are requested. Repository hydration owns bulk validation.
            if check_provenance:
                self._hydrate_current_bulks(
                    report,
                    uow,
                    bulk_references,
                )
                self._check_slab_provenance(report, current_slabs)

            # Check for orphans (optional, can be slow)
            if check_orphans:
                self._check_orphaned_bulks(
                    report,
                    bulk_references,
                    slab_references,
                )
                self._check_orphaned_runs(report, runs, prototypes)

        # Compute summary
        report.compute_summary()

        return report

    def _check_duplicates(
        self, report: ValidationReport, entity_type: str, entities: list[Any]
    ) -> None:
        """Check for duplicate UIDs."""
        uid_counts = defaultdict(int)
        for entity in entities:
            uid_counts[entity.uid_full] += 1

        for uid, count in uid_counts.items():
            if count > 1:
                report.add_issue(
                    severity="error",
                    category="duplicate_uid",
                    entity_type=entity_type,
                    entity_id=uid[:16],
                    message=f"Duplicate {entity_type} UID found {count} times",
                    uid_full=uid,
                    count=count,
                )

    def _hydrate_current_bulks(
        self,
        report: ValidationReport,
        uow: Any,
        references: list[Any],
    ) -> None:
        """Hydrate current bulk rows and report exact-schema violations."""

        for reference in references:
            try:
                bulk = uow.bulks.get_by_uid_full(reference.uid_full)
            except MissingBulkCanonicalizationProvenanceError as exc:
                report.add_issue(
                    severity="error",
                    category="missing_provenance",
                    entity_type="bulk",
                    entity_id=reference.id_short,
                    message=(
                        "Current structure-backed bulk row is missing required "
                        "canonicalization state."
                    ),
                    bulk_uid=reference.uid_full,
                    error=repr(exc),
                )
                continue
            except InvalidBulkCanonicalizationProvenanceError as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_provenance",
                    entity_type="bulk",
                    entity_id=reference.id_short,
                    message=(
                        "Current bulk canonicalization state is malformed or "
                        "does not verify its persisted structures."
                    ),
                    bulk_uid=reference.uid_full,
                    error=repr(exc),
                )
                continue
            except CurrentBulkPayloadError as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_persisted_state",
                    entity_type="bulk",
                    entity_id=reference.id_short,
                    message="Current bulk row failed exact-schema hydration.",
                    bulk_uid=reference.uid_full,
                    error=repr(exc),
                )
                continue
            except (KeyError, TypeError, ValueError) as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_persisted_state",
                    entity_type="bulk",
                    entity_id=reference.id_short,
                    message="Current bulk row failed exact-schema hydration.",
                    bulk_uid=reference.uid_full,
                    error=repr(exc),
                )
                continue
            if bulk is None:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="bulk",
                    entity_id=reference.id_short,
                    message="Bulk row disappeared during validation.",
                    bulk_uid=reference.uid_full,
                )

    def _hydrate_current_slabs(
        self,
        report: ValidationReport,
        uow: Any,
        references: list[Any],
    ) -> list[Any]:
        """Hydrate valid slab rows while reporting malformed current state."""

        slabs: list[Any] = []
        for reference in references:
            if reference.bulk_uid_full is None:
                continue
            try:
                slab = uow.slabs.get_by_uid_full(reference.uid_full)
            except (KeyError, TypeError, ValueError) as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_persisted_state",
                    entity_type="slab",
                    entity_id=reference.id_short,
                    message="Current slab row failed exact-schema hydration.",
                    slab_uid=reference.uid_full,
                    error=repr(exc),
                )
                continue
            if slab is None:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="slab",
                    entity_id=reference.id_short,
                    message="Slab row disappeared during validation.",
                    slab_uid=reference.uid_full,
                )
                continue
            slabs.append(slab)
        return slabs

    def _check_slab_references(
        self,
        report: ValidationReport,
        slabs: list[Any],
        bulk_uids: set[str],
    ) -> None:
        """Check raw slab-parent relationships without hydrating slab rows."""

        for slab in slabs:
            if slab.bulk_uid_full in bulk_uids:
                continue
            parent = slab.bulk_uid_full or f"bulk_pk={slab.bulk_pk}"
            report.add_issue(
                severity="error",
                category="broken_reference",
                entity_type="slab",
                entity_id=slab.id_short,
                message=f"Slab references non-existent bulk {parent}",
                slab_uid=slab.uid_full,
                bulk_pk=slab.bulk_pk,
                bulk_uid=slab.bulk_uid_full,
                bulk_id_short=slab.bulk_id_short,
            )

    def _check_prototype_references(
        self,
        report: ValidationReport,
        prototypes: list[Any],
        slab_uids: set[str],
        run_uids: set[str],
    ) -> None:
        """Check that all prototypes reference existing slabs and runs."""
        for proto in prototypes:
            # Check slab A
            if proto.slab_a_uid_full not in slab_uids:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="prototype",
                    entity_id=proto.id_short,
                    message="Prototype references non-existent slab A",
                    prototype_uid=proto.uid_full,
                    slab_a_uid=proto.slab_a_uid_full,
                )

            # Check slab B
            if proto.slab_b_uid_full not in slab_uids:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="prototype",
                    entity_id=proto.id_short,
                    message="Prototype references non-existent slab B",
                    prototype_uid=proto.uid_full,
                    slab_b_uid=proto.slab_b_uid_full,
                )

            # Check run
            if proto.run_uid_full not in run_uids:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="prototype",
                    entity_id=proto.id_short,
                    message=(
                        f"Prototype references non-existent run {proto.run_id_short}"
                    ),
                    prototype_uid=proto.uid_full,
                    run_uid=proto.run_uid_full,
                    run_id_short=proto.run_id_short,
                )

    def _check_derived_interface_references(
        self, report: ValidationReport, uow: Any, prototype_uids: set[str]
    ) -> None:
        """Check that all derived interfaces reference existing prototypes."""
        derived_interfaces = list(uow.derived_interfaces.list(limit=100000))

        for di in derived_interfaces:
            if di.prototype_uid_full not in prototype_uids:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="derived_interface",
                    entity_id=di.id_short,
                    message="Derived interface references non-existent prototype",
                    derived_interface_uid=di.uid_full,
                    prototype_uid=di.prototype_uid_full,
                )

    def _check_artifact_references(
        self, report: ValidationReport, uow: Any, run_uids: set[str]
    ) -> None:
        """Check that all artifacts reference existing runs."""
        # Get all artifacts (need to query by run, so get from all runs)
        all_artifacts = []
        for run_uid in run_uids:
            try:
                # Artifact repositories are queried one run at a time.
                artifacts = uow.artifacts.list_for_run(run_uid)
                all_artifacts.extend(artifacts)
            except Exception as exc:
                report.add_issue(
                    severity="error",
                    category="validation_failed",
                    entity_type="artifact",
                    entity_id=run_uid,
                    message=(
                        "Could not query artifacts for an authoritative run; "
                        "artifact-reference validation is incomplete."
                    ),
                    run_uid=run_uid,
                    error=repr(exc),
                )

        for artifact in all_artifacts:
            if artifact.run_uid_full not in run_uids:
                report.add_issue(
                    severity="error",
                    category="broken_reference",
                    entity_type="artifact",
                    entity_id=artifact.id_short,
                    message="Artifact references non-existent run",
                    artifact_uid=artifact.uid_full,
                    run_uid=artifact.run_uid_full,
                )

    def _check_followup_references(
        self,
        report: ValidationReport,
        uow: Any,
        run_uids: set[str],
        prototype_uids: set[str],
    ) -> None:
        """Check that all followup results reference existing runs/prototypes."""
        followups = list(uow.followups.list(limit=100000))

        for followup in followups:
            # Check run reference (if present)
            if followup.run_uid_full and followup.run_uid_full not in run_uids:
                report.add_issue(
                    severity="warning",
                    category="broken_reference",
                    entity_type="followup",
                    entity_id=followup.id_short,
                    message=(
                        f"Followup references non-existent run {followup.run_id_short}"
                    ),
                    followup_uid=followup.uid_full,
                    run_uid=followup.run_uid_full,
                )

            # Check prototype reference (if present)
            if (
                followup.prototype_uid_full
                and followup.prototype_uid_full not in prototype_uids
            ):
                report.add_issue(
                    severity="warning",
                    category="broken_reference",
                    entity_type="followup",
                    entity_id=followup.id_short,
                    message=(
                        "Followup references non-existent prototype "
                        f"{followup.prototype_id_short}"
                    ),
                    followup_uid=followup.uid_full,
                    prototype_uid=followup.prototype_uid_full,
                )

    def _check_slab_provenance(
        self,
        report: ValidationReport,
        slabs: list[Any],
    ) -> None:
        """Validate exact-current oriented-slab provenance.

        Current slab writers store one mapping payload under the canonical
        ``Atoms.info`` key. Missing, malformed, historical, or unsupported
        payloads are errors under the exact-current project schema.
        """

        if not slabs:
            return

        from calm.slab.slab import (
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
            get_oriented_slab_transforms_payload,
        )

        for slab in slabs:
            try:
                atoms = slab.atoms
            except Exception as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_provenance",
                    entity_type="slab",
                    entity_id=slab.id_short,
                    message=(
                        "Could not materialize slab ASE Atoms for current "
                        "provenance validation."
                    ),
                    slab_uid=slab.uid_full,
                    error=repr(exc),
                )
                continue
            if atoms is None:
                continue

            try:
                payload = get_oriented_slab_transforms_payload(atoms)
            except (TypeError, ValueError) as exc:
                report.add_issue(
                    severity="error",
                    category="invalid_provenance",
                    entity_type="slab",
                    entity_id=slab.id_short,
                    message=(
                        "Slab oriented-slab provenance is malformed, "
                        "historical, or uses an unsupported schema."
                    ),
                    slab_uid=slab.uid_full,
                    error=repr(exc),
                )
                continue

            if payload is None:
                report.add_issue(
                    severity="error",
                    category="missing_provenance",
                    entity_type="slab",
                    entity_id=slab.id_short,
                    message=(
                        "Current slab is missing required oriented-slab "
                        "transform provenance in Atoms.info "
                        f"({ORIENTED_SLAB_TRANSFORMS_INFO_KEY})."
                    ),
                    slab_uid=slab.uid_full,
                )

    def _check_orphaned_bulks(
        self, report: ValidationReport, bulks: list[Any], slabs: list[Any]
    ) -> None:
        """Check for bulks not referenced by any slabs."""
        # Build set of bulk UIDs referenced by slabs
        referenced_bulk_uids = {slab.bulk_uid_full for slab in slabs}

        for bulk in bulks:
            if bulk.uid_full not in referenced_bulk_uids:
                report.add_issue(
                    severity="info",
                    category="orphaned_record",
                    entity_type="bulk",
                    entity_id=bulk.id_short,
                    message=f"Bulk '{bulk.label}' not referenced by any slabs",
                    bulk_uid=bulk.uid_full,
                )

    def _check_orphaned_runs(
        self, report: ValidationReport, runs: list[Any], prototypes: list[Any]
    ) -> None:
        """Check for runs not referenced by any prototypes."""
        # Build set of run UIDs referenced by prototypes
        referenced_run_uids = {proto.run_uid_full for proto in prototypes}

        for run in runs:
            if run.uid_full not in referenced_run_uids:
                report.add_issue(
                    severity="info",
                    category="orphaned_record",
                    entity_type="run",
                    entity_id=run.id_short,
                    message=f"Run '{run.run_type}' not referenced by any prototypes",
                    run_uid=run.uid_full,
                    run_type=run.run_type,
                )
