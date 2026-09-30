"""Validation helpers for current synchronous campaign specifications."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from calm.serialization.json import canonical_json as _canonical_json
from calm.serialization.json import json_native


CAMPAIGN_SPEC_VERSION = 3
CAMPAIGN_STAGE_POLICY = "strict_ordered_subsequence"
CAMPAIGN_STAGE_POLICY_VERSION = 1
CAMPAIGN_CANONICAL_JSON_POLICY = "sorted_ascii_compact_json_native"
CAMPAIGN_STAGE_ORDER = (
    "search",
    "build",
    "refine",
    "relax",
    "energy",
    "dataset",
)


class CampaignIdentityConflictError(ValueError):
    """A campaign name conflicts with an existing persisted specification."""


def canonical_campaign_name(value: object) -> str:
    """Return one exact campaign name suitable for identity construction."""

    if not isinstance(value, str):
        raise TypeError("Campaign name must be a string.")
    if not value:
        raise ValueError("Campaign name must be non-empty.")
    if value != value.strip():
        raise ValueError("Campaign name must not have surrounding whitespace.")
    return value


def canonical_campaign_stages(values: Sequence[str]) -> tuple[str, ...]:
    """Validate and normalize one ordered subsequence of campaign stages."""

    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("Campaign stages must be a sequence of strings.")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("Campaign stage names must be strings.")
        stage = value.strip().lower()
        if not stage:
            raise ValueError("Campaign stage names must be non-empty.")
        normalized.append(stage)
    stages = tuple(normalized)
    if not stages:
        raise ValueError("Campaign stages must be non-empty.")
    if len(stages) != len(set(stages)):
        raise ValueError("Campaign stages must not contain duplicates.")
    unknown = [stage for stage in stages if stage not in CAMPAIGN_STAGE_ORDER]
    if unknown:
        raise ValueError("Unsupported campaign stage(s): " + ", ".join(sorted(unknown)))
    positions = [CAMPAIGN_STAGE_ORDER.index(stage) for stage in stages]
    if positions != sorted(positions):
        raise ValueError(
            "Campaign stages must follow the canonical order: "
            + " -> ".join(CAMPAIGN_STAGE_ORDER)
        )
    return stages


def _typed_campaign_stages(spec: Mapping[str, Any]) -> tuple[str, ...]:
    settings = spec.get("settings")
    if not isinstance(settings, Mapping):
        raise TypeError("Typed campaign spec settings must be a mapping.")
    stages = settings.get("stages")
    if not isinstance(stages, Sequence) or isinstance(stages, (str, bytes, bytearray)):
        raise TypeError("Typed campaign spec settings.stages must be a sequence.")
    return canonical_campaign_stages(stages)


def validate_typed_campaign_spec(spec: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate the current version-3 typed campaign specification."""

    version = spec.get("identity_version")
    if isinstance(version, bool) or version != CAMPAIGN_SPEC_VERSION:
        raise ValueError(
            f"Typed campaign spec identity_version must equal {CAMPAIGN_SPEC_VERSION}."
        )
    cases = spec.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes, bytearray)):
        raise TypeError("Typed campaign spec cases must be a sequence.")
    if not cases:
        raise ValueError("Typed campaign spec cases must be non-empty.")
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise TypeError(
                f"Typed campaign spec case at index {index} must be a mapping."
            )
    stages = _typed_campaign_stages(spec)
    stored_stages = list(spec["settings"]["stages"])
    if stored_stages != list(stages):
        raise ValueError(
            "Typed campaign spec settings.stages must already use canonical "
            "lower-case names without surrounding whitespace."
        )
    json_native(spec)
    return stages


def campaign_spec_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Compare campaign specifications under the current JSON contract."""

    return _canonical_json(left) == _canonical_json(right)


__all__ = [
    "CAMPAIGN_CANONICAL_JSON_POLICY",
    "CAMPAIGN_SPEC_VERSION",
    "CAMPAIGN_STAGE_ORDER",
    "CAMPAIGN_STAGE_POLICY",
    "CAMPAIGN_STAGE_POLICY_VERSION",
    "CampaignIdentityConflictError",
    "campaign_spec_equal",
    "canonical_campaign_name",
    "canonical_campaign_stages",
    "validate_typed_campaign_spec",
]
