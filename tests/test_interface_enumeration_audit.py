from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.interface.config import PrototypeSearchConfig
from calm.interface.results import PrototypeSearchResult


def test_coupled_enumeration_audit_serializes_through_search_result() -> None:
    audit = CoupledMatchEnumerationAudit.empty(k_max=2)
    result = PrototypeSearchResult(
        config=PrototypeSearchConfig(k_max=2),
        prototypes=[],
        slab_a_uid="A",
        slab_b_uid="B",
        enumeration_audit=audit,
    )

    payload = result.to_dict(include_enumeration_audit=True)
    serialized = payload["enumeration_audit"]
    assert serialized["schema"] == "calm.coupled_match_enumeration_audit/v2"
    assert serialized["implementation"] == "primitive_coupled_pair_v2"
    assert len(serialized["surface_A"]) == 2
    assert len(serialized["pairs"]) == 2
    assert serialized["search_space"]["raw_hnf_pairs"] == 0
    assert serialized["identity_reduction"]["admitted_descriptions"] == 0
