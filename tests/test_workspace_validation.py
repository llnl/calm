"""Tests for workspace consistency validation."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from calm.bulk.provenance import (
    CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
)
from calm.project.application.workspace_validation import (
    ValidationIssue,
    ValidationReport,
    WorkspaceValidator,
)
from calm.project.domain.contracts.bulk_record import (
    MissingBulkCanonicalizationProvenanceError,
)
from calm.project.domain.identity_v2 import (
    bulk_metadata_identity_payload,
    bulk_structure_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import Bulk, Slab
from bulk_record_fixtures import current_bulk_payload
from slab_record_fixtures import current_slab_payload, current_slab_uid


def _persist_bulk(workspace, *, token: str, label: str) -> Bulk:
    payload = {"fixture_token": token}
    bulk = Bulk(
        uid_full=persisted_entity_uid_v2(
            "bulk",
            bulk_metadata_identity_payload(payload=payload),
        ),
        id_short=f"b_{token}",
        label=label,
        payload=payload,
    )
    with workspace._uow_factory() as uow:
        stored = uow.bulks.upsert(bulk)
        uow.commit()
    return stored


def _persist_structure_bulk(
    workspace,
    *,
    token: str,
    label: str,
) -> tuple[Bulk, dict[str, object]]:
    payload = current_bulk_payload()
    payload["fingerprint"] = {"fixture": f"fcc-al-{token}"}
    bulk = Bulk(
        uid_full=persisted_entity_uid_v2(
            "bulk",
            bulk_structure_identity_payload(
                fingerprint=payload["fingerprint"],
            ),
        ),
        id_short=f"b_{token}",
        label=label,
        payload=payload,
    )
    with workspace._uow_factory() as uow:
        stored = uow.bulks.upsert(bulk)
        uow.commit()
    return stored, deepcopy(payload)


def _persist_spec_only_slab(
    workspace,
    *,
    bulk: Bulk,
    token: str,
    miller: tuple[int, int, int] = (1, 1, 1),
) -> Slab:
    payload = current_slab_payload(
        bulk_uid_full=bulk.uid_full,
        miller=miller,
    )
    slab = Slab(
        uid_full=current_slab_uid(
            bulk_uid_full=bulk.uid_full,
            miller=miller,
            payload=payload,
        ),
        id_short=f"s_{token}",
        bulk_uid_full=bulk.uid_full,
        bulk_id_short=bulk.id_short,
        miller=miller,
        payload=payload,
    )
    with workspace._uow_factory() as uow:
        stored = uow.slabs.create_many([slab])[0]
        uow.commit()
    return stored


class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_create_issue(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            severity="error",
            category="broken_reference",
            entity_type="slab",
            entity_id="s_001",
            message="Slab references non-existent bulk",
            details={"bulk_id": "b_missing"},
        )

        assert issue.severity == "error"
        assert issue.category == "broken_reference"
        assert issue.entity_type == "slab"
        assert issue.entity_id == "s_001"
        assert issue.message == "Slab references non-existent bulk"
        assert issue.details["bulk_id"] == "b_missing"


class TestValidationReport:
    """Test ValidationReport."""

    def test_empty_report(self):
        """Test empty report."""
        report = ValidationReport()

        assert len(report.issues) == 0
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.info_count == 0
        assert report.is_valid

    def test_add_issue(self):
        """Test adding issues."""
        report = ValidationReport()

        report.add_issue(
            severity="error",
            category="broken_reference",
            entity_type="slab",
            entity_id="s_001",
            message="Test error",
            extra_field="extra_value",
        )

        assert len(report.issues) == 1
        assert report.error_count == 1
        assert report.warning_count == 0
        assert not report.is_valid

        issue = report.issues[0]
        assert issue.severity == "error"
        assert issue.details["extra_field"] == "extra_value"

    def test_multiple_severities(self):
        """Test report with multiple severity levels."""
        report = ValidationReport()

        report.add_issue("error", "cat1", "type1", "id1", "Error 1")
        report.add_issue("error", "cat1", "type1", "id2", "Error 2")
        report.add_issue("warning", "cat2", "type2", "id3", "Warning 1")
        report.add_issue("info", "cat3", "type3", "id4", "Info 1")

        assert report.error_count == 2
        assert report.warning_count == 1
        assert report.info_count == 1
        assert not report.is_valid

    def test_compute_summary(self):
        """Test summary computation."""
        report = ValidationReport()

        report.add_issue("error", "broken_reference", "slab", "s_001", "Error 1")
        report.add_issue("error", "broken_reference", "prototype", "p_001", "Error 2")
        report.add_issue("warning", "orphaned_record", "bulk", "b_001", "Warning 1")
        report.add_issue("info", "orphaned_record", "bulk", "b_002", "Info 1")

        report.compute_summary()

        assert report.summary["total_issues"] == 4
        assert report.summary["errors"] == 2
        assert report.summary["warnings"] == 1
        assert report.summary["info"] == 1

        assert report.summary["by_severity"]["error"] == 2
        assert report.summary["by_severity"]["warning"] == 1
        assert report.summary["by_severity"]["info"] == 1

        assert report.summary["by_category"]["broken_reference"] == 2
        assert report.summary["by_category"]["orphaned_record"] == 2

        assert report.summary["by_entity_type"]["slab"] == 1
        assert report.summary["by_entity_type"]["prototype"] == 1
        assert report.summary["by_entity_type"]["bulk"] == 2

    def test_is_valid_only_info(self):
        """Test that report with only info messages is considered valid."""
        report = ValidationReport()

        report.add_issue("info", "orphaned_record", "bulk", "b_001", "Info message")

        assert report.info_count == 1
        assert report.error_count == 0
        assert report.warning_count == 0
        # Info messages don't make the report invalid
        assert report.is_valid  # Only errors and warnings affect validity


class TestWorkspaceValidatorIntegration:
    """Integration tests for WorkspaceValidator.

    These tests use a real (test) workspace to verify validation behavior.
    """

    def test_validates_empty_workspace(self, test_workspace):
        """Test validation of empty workspace."""

        validator = WorkspaceValidator(uow_factory=test_workspace._uow_factory)
        report = validator.validate()

        # Empty workspace should have no issues
        assert len(report.issues) == 0
        assert report.is_valid

    def test_validates_consistent_workspace(self, workspace_with_data):
        """Test validation of consistent exact-current rows."""

        ws = workspace_with_data
        bulk = _persist_bulk(ws, token="al", label="Al FCC")
        _persist_spec_only_slab(ws, bulk=bulk, token="al111")

        validator = WorkspaceValidator(uow_factory=ws._uow_factory)
        report = validator.validate()

        assert report.error_count == 0
        assert report.warning_count == 0

    def test_detects_broken_slab_reference(self, test_workspace):
        """Validation reports a broken relation without hydrating the slab."""
        from sqlalchemy import text

        ws = test_workspace
        bulk = _persist_bulk(ws, token="temporary", label="Temp Bulk")
        slab = _persist_spec_only_slab(
            ws,
            bulk=bulk,
            token="temporary111",
        )

        validator = WorkspaceValidator(uow_factory=ws._uow_factory)
        report_before = validator.validate()
        assert report_before.error_count == 0

        with ws._uow_factory() as uow:
            uow.connection.execute(
                text("DELETE FROM bulks WHERE uid_full = :uid"),
                {"uid": bulk.uid_full},
            )
            uow.commit()

        report_after = validator.validate()

        broken_refs = [
            issue
            for issue in report_after.issues
            if issue.category == "broken_reference"
        ]
        assert report_after.error_count == 1
        assert len(broken_refs) == 1
        assert broken_refs[0].entity_type == "slab"
        assert broken_refs[0].entity_id == slab.id_short
        assert broken_refs[0].details["slab_uid"] == slab.uid_full
        assert broken_refs[0].details["bulk_uid"] is None

    def test_reports_malformed_current_slab_without_crashing(
        self,
        test_workspace,
    ):
        """Malformed present state is reported through the validator."""
        from sqlalchemy import text

        ws = test_workspace
        bulk = _persist_bulk(ws, token="malformed", label="Malformed Bulk")
        slab = _persist_spec_only_slab(
            ws,
            bulk=bulk,
            token="malformed111",
        )

        with ws._uow_factory() as uow:
            uow.connection.execute(
                text(
                    "UPDATE slabs SET payload_json = :payload "
                    "WHERE uid_full = :uid"
                ),
                {"payload": "{}", "uid": slab.uid_full},
            )
            uow.commit()

        report = WorkspaceValidator(uow_factory=ws._uow_factory).validate()

        issues = [
            issue
            for issue in report.issues
            if issue.category == "invalid_persisted_state"
        ]
        assert len(issues) == 1
        assert issues[0].entity_id == slab.id_short
        assert issues[0].details["slab_uid"] == slab.uid_full

    def test_provenance_check_accepts_metadata_only_and_current_structure_bulks(
        self,
        test_workspace,
    ):
        ws = test_workspace
        _persist_bulk(ws, token="metadata", label="Metadata Bulk")
        _persist_structure_bulk(
            ws,
            token="structure",
            label="Structure Bulk",
        )

        report = WorkspaceValidator(uow_factory=ws._uow_factory).validate(
            check_provenance=True,
        )

        assert report.error_count == 0
        assert report.warning_count == 0

    def test_missing_current_bulk_provenance_is_an_error_not_a_legacy_warning(
        self,
        test_workspace,
    ):
        from sqlalchemy import text

        ws = test_workspace
        bulk, payload = _persist_structure_bulk(
            ws,
            token="missing-provenance",
            label="Missing Provenance",
        )
        del payload["atoms_conventional"]["info"]

        with ws._uow_factory() as uow:
            uow.connection.execute(
                text(
                    "UPDATE bulks SET payload_json = :payload "
                    "WHERE uid_full = :uid"
                ),
                {"payload": json.dumps(payload), "uid": bulk.uid_full},
            )
            uow.commit()

        unchecked = WorkspaceValidator(uow_factory=ws._uow_factory).validate(
            check_provenance=False,
        )
        assert unchecked.error_count == 0

        report = WorkspaceValidator(uow_factory=ws._uow_factory).validate(
            check_provenance=True,
        )
        issues = [
            issue
            for issue in report.issues
            if issue.entity_type == "bulk"
        ]
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].category == "missing_provenance"
        assert issues[0].entity_id == bulk.id_short
        assert report.warning_count == 0

    def test_malformed_present_bulk_provenance_is_reported_as_invalid(
        self,
        test_workspace,
    ):
        from sqlalchemy import text

        ws = test_workspace
        bulk, payload = _persist_structure_bulk(
            ws,
            token="invalid-provenance",
            label="Invalid Provenance",
        )
        key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
        payload["atoms_conventional"]["info"][key] = "not-json"

        with ws._uow_factory() as uow:
            uow.connection.execute(
                text(
                    "UPDATE bulks SET payload_json = :payload "
                    "WHERE uid_full = :uid"
                ),
                {"payload": json.dumps(payload), "uid": bulk.uid_full},
            )
            uow.commit()

        report = WorkspaceValidator(uow_factory=ws._uow_factory).validate(
            check_provenance=True,
        )
        issues = [
            issue
            for issue in report.issues
            if issue.entity_type == "bulk"
        ]
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].category == "invalid_provenance"
        assert issues[0].entity_id == bulk.id_short

    def test_bulk_upsert_cannot_repair_malformed_current_state(
        self,
        test_workspace,
    ):
        from sqlalchemy import text

        ws = test_workspace
        stored, payload = _persist_structure_bulk(
            ws,
            token="repair",
            label="Repair Guard",
        )
        malformed = deepcopy(payload)
        del malformed["atoms_primitive"]

        with ws._uow_factory() as uow:
            uow.connection.execute(
                text(
                    "UPDATE bulks SET payload_json = :payload "
                    "WHERE uid_full = :uid"
                ),
                {"payload": json.dumps(malformed), "uid": stored.uid_full},
            )
            uow.commit()

        replacement = Bulk(
            uid_full=stored.uid_full,
            id_short=stored.id_short,
            label=stored.label,
            payload=payload,
        )
        with ws._uow_factory() as uow:
            with pytest.raises(MissingBulkCanonicalizationProvenanceError):
                uow.bulks.upsert(replacement)

    def test_check_orphans_flag(self, workspace_with_data):
        """Test that orphan checking is controlled by flag."""

        ws = workspace_with_data
        _persist_bulk(ws, token="orphan", label="Orphaned Bulk")

        validator = WorkspaceValidator(uow_factory=ws._uow_factory)

        report1 = validator.validate(check_orphans=False)
        orphan_issues1 = [
            issue
            for issue in report1.issues
            if issue.category == "orphaned_record"
        ]
        assert orphan_issues1 == []

        report2 = validator.validate(check_orphans=True)
        orphan_issues2 = [
            issue
            for issue in report2.issues
            if issue.category == "orphaned_record"
        ]
        assert len(orphan_issues2) == 1
        assert orphan_issues2[0].entity_type == "bulk"


class TestWorkspaceValidateMethod:
    """Test the Workspace.validate_workspace() method."""

    def test_validate_workspace_method_exists(self, test_workspace):
        """Test that validate_workspace method exists."""
        ws = test_workspace
        assert hasattr(ws, "validate_workspace")
        assert callable(ws.validate_workspace)

    def test_validate_workspace_returns_report(self, test_workspace):
        """Test that validate_workspace returns ValidationReport."""
        ws = test_workspace
        report = ws.validate_workspace()

        assert hasattr(report, "issues")
        assert hasattr(report, "error_count")
        assert hasattr(report, "warning_count")
        assert hasattr(report, "is_valid")

    def test_validate_workspace_with_options(self, test_workspace):
        """Test validate_workspace with different options."""
        ws = test_workspace

        # Test with all checks
        report1 = ws.validate_workspace(
            check_references=True,
            check_orphans=True,
            check_duplicates=True,
        )
        assert isinstance(report1.issues, list)

        # Test with minimal checks
        report2 = ws.validate_workspace(
            check_references=False,
            check_orphans=False,
            check_duplicates=False,
        )
        assert isinstance(report2.issues, list)


# Fixtures


@pytest.fixture
def test_workspace(tmp_path):
    """Create a test workspace."""
    from calm.project.bootstrap import open_workspace

    ws_path = tmp_path / "test_workspace.calm"
    ws = open_workspace(str(ws_path))
    return ws


@pytest.fixture
def workspace_with_data(tmp_path):
    """Create a test workspace with some data."""
    from calm.project.bootstrap import open_workspace

    ws_path = tmp_path / "test_workspace.calm"
    ws = open_workspace(str(ws_path))

    # Could add some test data here if fixtures are available
    # For now, return empty workspace

    return ws
