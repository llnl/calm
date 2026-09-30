"""Source-preserving pymatgen ZSL capture and reconstruction utilities.

The adapter imports pymatgen only when a capture is executed. Raw ZSL output is
retained separately from every CALM-specific projection so later roadmap phases
can reanalyze the same external-tool evidence without rerunning pymatgen.
Projection modules are intentionally not imported here, keeping source capture
independent from CALM's coupled-identity implementation.
"""

from .raw_adapter import (
    ZSL_CAPTURE_SUMMARY_SCHEMA,
    capture_raw_zsl_match,
    json_compatible,
    raw_match_id,
)
from .transformation_reconstruction import reconstruct_zsl_source_pair

__all__ = [
    "ZSL_CAPTURE_SUMMARY_SCHEMA",
    "capture_raw_zsl_match",
    "json_compatible",
    "raw_match_id",
    "reconstruct_zsl_source_pair",
]
