"""Candidate-to-prototype identity helpers for public buildability checks."""

from __future__ import annotations


def prototype_identifier_from_candidate_row(row: dict) -> str | None:
    return (
        row.get("project_prototype_uid")
        or row.get("project_prototype_id")
        or row.get("prototype_uid")
    )
