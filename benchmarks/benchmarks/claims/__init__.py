"""Claim-oriented CALM qualification infrastructure.

The package is deliberately separate from the frozen ``legacy_v1`` benchmark
suite. Infrastructure records may be imported without importing CALM's
production matcher or pymatgen.
"""

from .claim_ids import (
    CLAIM_REGISTRY,
    ClaimDefinition,
    ClaimId,
    ClaimStatus,
    ordered_claim_ids,
    parse_claim_id,
)
from .schemas import (
    BENCHMARK_MANIFEST_SCHEMA,
    CLAIM_RESULT_SCHEMA,
    CLAIM_SUITE_VERSION,
    CLAIM_SUMMARY_SCHEMA,
    ArtifactRecord,
    BenchmarkManifest,
    ClaimResult,
)

__all__ = [
    "ArtifactRecord",
    "BENCHMARK_MANIFEST_SCHEMA",
    "BenchmarkManifest",
    "CLAIM_REGISTRY",
    "CLAIM_RESULT_SCHEMA",
    "CLAIM_SUITE_VERSION",
    "CLAIM_SUMMARY_SCHEMA",
    "ClaimDefinition",
    "ClaimId",
    "ClaimResult",
    "ClaimStatus",
    "ordered_claim_ids",
    "parse_claim_id",
]
