from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.errors import SearchEnumerationAuditUnavailableError
from calm.interface.matching.audit import (
    COUPLED_MATCH_AUDIT_SCHEMA_V1,
    CoupledIdentityReductionCounts,
    CoupledMatchEnumerationAudit,
    CoupledSearchSpaceCounts,
)
from calm.public.records.interfaces import InterfaceSearchResult
from calm.public.records.persistence import ProjectSearch
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.search_audit import InterfaceSearchEnumerationAudit


def _audit() -> CoupledMatchEnumerationAudit:
    audit = CoupledMatchEnumerationAudit.empty(2)

    audit.surface_A.hnf_generated[0] = 2
    audit.surface_A.admitted_members[0] = 2
    audit.surface_A.comparison_orbits[0] = 1
    audit.surface_A.hnf_generated[1] = 1
    audit.surface_A.condition_rejected[1] = 1

    audit.surface_B.hnf_generated[0] = 1
    audit.surface_B.admitted_members[0] = 1
    audit.surface_B.comparison_orbits[0] = 1

    pairs = audit.pairs
    pairs.index_pairs_scheduled[0] = 1
    pairs.orbit_pairs_considered[0] = 1
    pairs.orbit_prefilter_admitted[0] = 1
    pairs.member_pairs_expanded[0] = 2
    pairs.correspondence_domains[0] = 2
    pairs.correspondence_column_pairs_tested[0] = 3
    pairs.unimodular_correspondences_tested[0] = 3
    pairs.strain_admissible_correspondences[0] = 2
    pairs.unique_source_pairs_primitiveized[0] = 1
    pairs.primitiveization_cache_hits[0] = 1
    pairs.candidates_admitted[0] = 2
    pairs.primitive_classes_created[0] = 1
    pairs.sources_aggregated_by_pair_key[0] = 1

    audit.search_space = CoupledSearchSpaceCounts(
        raw_hnf_pairs=3,
        searchable_hnf_pairs=2,
        area_admissible_hnf_pairs=2,
        atom_lower_bound_admissible_hnf_pairs=2,
        orbit_prefilter_surviving_hnf_pairs=2,
    )
    audit.identity_reduction = CoupledIdentityReductionCounts(
        admitted_descriptions=2,
        unique_admitted_source_pairs=1,
        unique_admitted_primitive_pairs=1,
        unique_admitted_common_right_classes=1,
        unique_final_pair_classes=1,
    )

    audit.validate()
    return audit


def test_public_enumeration_audit_is_immutable_and_exportable(tmp_path) -> None:
    record = InterfaceSearchEnumerationAudit.from_value(_audit())

    assert record.k_max == 2
    assert record.surface_a_rows()[0]["comparison_symmetry_reduction"] == 1
    assert record.surface_a_rows(cumulative=True)[1]["hnf_generated"] == 3
    assert record.pair_rows()[0]["candidates_admitted"] == 2
    assert record.totals["pairs"]["primitive_classes_created"] == 1
    assert record.search_space == {
        "raw_hnf_pairs": 3,
        "searchable_hnf_pairs": 2,
        "area_admissible_hnf_pairs": 2,
        "atom_lower_bound_admissible_hnf_pairs": 2,
        "orbit_prefilter_surviving_hnf_pairs": 2,
    }
    assert record.identity_reduction == {
        "admitted_descriptions": 2,
        "unique_admitted_source_pairs": 1,
        "unique_admitted_primitive_pairs": 1,
        "unique_admitted_common_right_classes": 1,
        "unique_final_pair_classes": 1,
    }

    detached = record.to_dict()
    detached["surface_A"][0]["hnf_generated"] = 999
    detached["search_space"]["raw_hnf_pairs"] = 999
    assert record.surface_a_rows()[0]["hnf_generated"] == 2
    assert record.search_space["raw_hnf_pairs"] == 3

    written = record.write_tables(tmp_path / "audit")
    assert {path.name for path in written} == {
        "enumeration_audit.json",
        "surface_a.csv",
        "surface_b.csv",
        "pairs.csv",
    }
    assert all(path.is_file() for path in written)


def test_in_memory_and_persisted_searches_share_public_audit_view() -> None:
    audit = _audit()
    in_memory = InterfaceSearchResult(
        request=None,
        candidates=[],
        internal_result=SimpleNamespace(enumeration_audit=audit),
    )
    live = in_memory.enumeration_audit()
    assert live is not None

    persisted = PersistedInterfaceSearch(
        project=object(),
        name="screen",
        record=ProjectSearch(
            name="screen",
            progress={"enumeration_audit": live.to_dict()},
        ),
    )
    assert persisted.has_enumeration_audit
    assert persisted.enumeration_audit().to_dict() == live.to_dict()


def test_legacy_persisted_search_reports_missing_audit_clearly() -> None:
    persisted = PersistedInterfaceSearch(
        project=object(),
        name="legacy",
        record=ProjectSearch(name="legacy"),
    )

    assert not persisted.has_enumeration_audit
    with pytest.raises(
        SearchEnumerationAuditUnavailableError,
        match="resume=False",
    ):
        persisted.enumeration_audit()


def test_project_search_preserves_progress_roundtrip() -> None:
    record = ProjectSearch.from_item(
        {
            "name": "screen",
            "progress": {"enumeration_audit": _audit().to_dict()},
        }
    )

    assert record.progress is not None
    assert "enumeration_audit" in record.progress
    assert ProjectSearch.from_item(record.to_dict()).progress == record.progress


def test_public_enumeration_audit_rejects_corrupt_totals() -> None:
    payload = _audit().to_dict()
    payload["totals"]["pairs"]["candidates_admitted"] = 999

    with pytest.raises(ValueError, match="totals"):
        InterfaceSearchEnumerationAudit.from_value(payload)


def test_public_enumeration_audit_reads_v1_without_inventing_counts() -> None:
    payload = _audit().to_dict()
    payload["schema"] = COUPLED_MATCH_AUDIT_SCHEMA_V1
    payload.pop("search_space")
    payload.pop("identity_reduction")

    record = InterfaceSearchEnumerationAudit.from_value(payload)

    assert record.schema == COUPLED_MATCH_AUDIT_SCHEMA_V1
    assert record.search_space is None
    assert record.identity_reduction is None
    assert "search_space" not in record.to_dict()
    assert "identity_reduction" not in record.to_dict()


def test_public_enumeration_audit_rejects_corrupt_identity_funnel() -> None:
    payload = _audit().to_dict()
    payload["identity_reduction"]["unique_admitted_primitive_pairs"] = 3

    with pytest.raises(ValueError, match="nonincreasing"):
        InterfaceSearchEnumerationAudit.from_value(payload)


def test_public_enumeration_audit_rejects_corrupt_prefilter_population() -> None:
    payload = _audit().to_dict()
    payload["search_space"]["orbit_prefilter_surviving_hnf_pairs"] = 1

    with pytest.raises(ValueError, match="member_pairs_expanded"):
        InterfaceSearchEnumerationAudit.from_value(payload)
