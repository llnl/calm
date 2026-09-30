"""Versioned basis-only fixture descriptors for claim-oriented qualification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .claim_ids import ClaimId
from .matrix_conventions import column_basis


FIXTURE_SCHEMA = "calm.claim_fixture/v1"


@dataclass(frozen=True)
class FixtureDescriptor:
    """Self-describing pair of primitive 2D column bases."""

    fixture_id: str
    family: str
    description: str
    basis_A: tuple[tuple[float, float], tuple[float, float]]
    basis_B: tuple[tuple[float, float], tuple[float, float]]
    claims: tuple[ClaimId, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)
    schema: str = FIXTURE_SCHEMA

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id must be nonempty")
        if not self.family.strip():
            raise ValueError("family must be nonempty")
        if not self.description.strip():
            raise ValueError("description must be nonempty")
        column_basis(self.basis_A, name="basis_A")
        column_basis(self.basis_B, name="basis_B")
        if not self.claims:
            raise ValueError("fixture must be associated with at least one claim")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "fixture_id": self.fixture_id,
            "family": self.family,
            "description": self.description,
            "basis_vector_storage": "columns",
            "basis_A": [list(row) for row in self.basis_A],
            "basis_B": [list(row) for row in self.basis_B],
            "claims": [claim.value for claim in self.claims],
            "tags": list(self.tags),
        }

    def sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()


def fixture_descriptor(
    *,
    fixture_id: str,
    family: str,
    description: str,
    basis_A: Any,
    basis_B: Any,
    claims: tuple[ClaimId, ...],
    tags: tuple[str, ...] = (),
) -> FixtureDescriptor:
    """Construct an immutable descriptor from arbitrary 2x2 array-like inputs."""

    A = column_basis(basis_A, name="basis_A")
    B = column_basis(basis_B, name="basis_B")
    return FixtureDescriptor(
        fixture_id=fixture_id,
        family=family,
        description=description,
        basis_A=(
            (float(A[0, 0]), float(A[0, 1])),
            (float(A[1, 0]), float(A[1, 1])),
        ),
        basis_B=(
            (float(B[0, 0]), float(B[0, 1])),
            (float(B[1, 0]), float(B[1, 1])),
        ),
        claims=claims,
        tags=tags,
    )
