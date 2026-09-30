from __future__ import annotations

import math

import pytest

from calm.project.domain.contracts.campaign import (
    CAMPAIGN_CANONICAL_JSON_POLICY,
    CAMPAIGN_SPEC_VERSION,
    CAMPAIGN_STAGE_ORDER,
    CAMPAIGN_STAGE_POLICY,
    CAMPAIGN_STAGE_POLICY_VERSION,
    campaign_spec_equal,
    canonical_campaign_name,
    canonical_campaign_stages,
    validate_typed_campaign_spec,
)
from calm.serialization.json import canonical_json
from calm.project.domain.identity_v2 import (
    campaign_identity_payload,
    persisted_entity_uid_v2,
)
from calm.public.inputs.campaigns import CampaignCase, CampaignSettings


def _typed_spec(
    *,
    stages: tuple[str, ...] = ("search",),
    cases: tuple[CampaignCase, ...] | None = None,
) -> dict:
    selected_cases = cases or (
        CampaignCase(name="case", search_name="existing"),
    )
    return {
        "identity_version": CAMPAIGN_SPEC_VERSION,
        "cases": [case.to_dict() for case in selected_cases],
        "settings": CampaignSettings(stages=stages, on_error="record").to_dict(),
    }


def _campaign_uid(*, name: str, spec: dict) -> str:
    return persisted_entity_uid_v2(
        "campaign",
        campaign_identity_payload(name=name, spec=spec),
    )


def test_campaign_stage_contract_is_a_strict_ordered_subsequence() -> None:
    assert CAMPAIGN_STAGE_ORDER == (
        "search",
        "build",
        "refine",
        "relax",
        "energy",
        "dataset",
    )
    assert CAMPAIGN_STAGE_POLICY == "strict_ordered_subsequence"
    assert CAMPAIGN_STAGE_POLICY_VERSION == 1
    assert canonical_campaign_stages((" SEARCH ", "Refine", "dataset")) == (
        "search",
        "refine",
        "dataset",
    )

    with pytest.raises(TypeError, match="sequence of strings"):
        canonical_campaign_stages("search")
    with pytest.raises(TypeError, match="stage names must be strings"):
        canonical_campaign_stages(("search", 1))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty"):
        canonical_campaign_stages(("search", "  "))
    with pytest.raises(ValueError, match="duplicates"):
        canonical_campaign_stages(("search", " SEARCH "))
    with pytest.raises(ValueError, match="Unsupported"):
        canonical_campaign_stages(("search", "publish"))
    with pytest.raises(ValueError, match="canonical order"):
        canonical_campaign_stages(("energy", "search"))


def test_campaign_name_is_exact_and_identity_bearing() -> None:
    assert canonical_campaign_name("demo") == "demo"
    with pytest.raises(TypeError, match="must be a string"):
        canonical_campaign_name(1)
    with pytest.raises(ValueError, match="non-empty"):
        canonical_campaign_name("")
    with pytest.raises(ValueError, match="surrounding whitespace"):
        canonical_campaign_name(" demo ")


def test_campaign_identity_is_current_domain_separated_v2() -> None:
    spec = _typed_spec()
    uid = _campaign_uid(name="demo", spec=spec)

    assert spec["identity_version"] == CAMPAIGN_SPEC_VERSION == 3
    assert CAMPAIGN_CANONICAL_JSON_POLICY == "sorted_ascii_compact_json_native"
    assert uid.startswith("campaign:v2:")
    assert len(uid.removeprefix("campaign:v2:")) == 64


def test_campaign_rejects_retired_search_deduplication_value() -> None:
    row = CampaignCase(name="case", search_name="existing").to_dict()
    row["search_settings"]["deduplicate"] = False

    with pytest.raises(TypeError, match="deduplicate"):
        CampaignCase.from_dict(row)


def test_campaign_spec_equality_ignores_mapping_insertion_order_only() -> None:
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}
    assert campaign_spec_equal(left, right)
    assert _campaign_uid(name="raw", spec=left) == _campaign_uid(
        name="raw", spec=right
    )

    assert not campaign_spec_equal(
        {"cases": [{"name": "a"}, {"name": "b"}]},
        {"cases": [{"name": "b"}, {"name": "a"}]},
    )


def test_campaign_name_stage_selection_and_case_order_change_uid() -> None:
    base = _typed_spec(stages=("search", "energy"))
    other_stage = _typed_spec(stages=("search",))
    assert _campaign_uid(name="demo", spec=base) != _campaign_uid(
        name="demo", spec=other_stage
    )
    assert _campaign_uid(name="demo", spec=base) != _campaign_uid(
        name="other", spec=base
    )

    case_a = CampaignCase(name="a", search_name="search-a")
    case_b = CampaignCase(name="b", search_name="search-b")
    first = _typed_spec(cases=(case_a, case_b))
    second = _typed_spec(cases=(case_b, case_a))
    assert _campaign_uid(name="demo", spec=first) != _campaign_uid(
        name="demo", spec=second
    )


def test_typed_campaign_specs_store_the_normalized_stage_sequence() -> None:
    spec = _typed_spec()
    spec["settings"] = dict(spec["settings"])
    spec["settings"]["stages"] = [" SEARCH "]
    with pytest.raises(ValueError, match="already use canonical"):
        validate_typed_campaign_spec(spec)


def test_campaign_spec_rejects_non_json_and_nonfinite_values() -> None:
    class Unsupported:
        pass

    with pytest.raises(TypeError, match="JSON-native"):
        canonical_json({"value": Unsupported()})
    with pytest.raises(TypeError, match="mapping key"):
        canonical_json({1: "value"})  # type: ignore[dict-item]
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            canonical_json({"value": value})

    assert canonical_json({"value": True}) != canonical_json({"value": 1})
    assert canonical_json({"value": [1, 2]}) == canonical_json(
        {"value": (1, 2)}
    )
