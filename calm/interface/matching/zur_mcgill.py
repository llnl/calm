"""Dependency-light contract for Zur-McGill mismatch diagnostics."""

from __future__ import annotations

ZUR_MCGILL_DIAGNOSTIC_POLICY = "zur_mcgill_length_angle_diagnostic"
ZUR_MCGILL_DIAGNOSTIC_VERSION = 1
ZUR_MCGILL_DIAGNOSTIC_ONLY = True


def zur_mcgill_diagnostic_metadata() -> dict[str, object]:
    """Return the self-describing, non-authoritative diagnostic contract."""

    return {
        "policy": ZUR_MCGILL_DIAGNOSTIC_POLICY,
        "policy_version": ZUR_MCGILL_DIAGNOSTIC_VERSION,
        "diagnostic_only": ZUR_MCGILL_DIAGNOSTIC_ONLY,
        "authoritative_uses": (),
    }


__all__ = [
    "ZUR_MCGILL_DIAGNOSTIC_ONLY",
    "ZUR_MCGILL_DIAGNOSTIC_POLICY",
    "ZUR_MCGILL_DIAGNOSTIC_VERSION",
    "zur_mcgill_diagnostic_metadata",
]
