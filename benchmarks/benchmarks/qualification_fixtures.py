"""Frozen exact fixtures for coupled-matcher qualification.

These values are benchmark evidence, not production matching logic.  They are
kept outside ``tests`` so command-line qualification does not depend on the test
package or import a second algorithmic implementation.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from calm.symmetry.surface_group import validate_surface_symmetry_group_2d

PairKey = tuple[int, int, int, int, int, int, int, int]

PAIR_KEY_VERSION: Final[int] = 1
IDENTITY_PAIR_KEY_FULL: Final[PairKey] = (-1, 0, 0, -1, 1, 0, 0, 1)
SIGMA5_PAIR_KEY_FULL: Final[PairKey] = (-4, -3, -3, -1, 5, 3, 0, 1)

# Frozen cumulative first-discovery oracle for equal unit-square lattices under
# independent full D4 surface symmetry, a shared right-unimodular gauge,
# proper correspondences, ordered A/B materials, and an effectively exact
# principal-strain tolerance.
FULL_D4_DISCOVERY_BY_INDEX: Final[tuple[tuple[int, PairKey], ...]] = (
    (1, IDENTITY_PAIR_KEY_FULL),
    (5, SIGMA5_PAIR_KEY_FULL),
    (13, (-12, -7, -5, -4, 13, 8, 0, 1)),
    (17, (-15, -11, -8, -7, 17, 13, 0, 1)),
    (25, (-24, -17, -7, -6, 25, 18, 0, 1)),
    (29, (-21, -13, -20, -11, 29, 17, 0, 1)),
)

# Exact non-cumulative index-five funnel reported in the manuscript/SI.
INDEX5_SURFACE_ORACLE: Final[dict[str, int]] = {
    "k": 5,
    "hnf_generated": 6,
    "reduction_failed": 0,
    "condition_rejected": 0,
    "admitted_members": 6,
    "comparison_orbits": 3,
    "comparison_symmetry_reduction": 3,
}
INDEX5_PAIR_ORACLE: Final[dict[str, int]] = {
    "orbit_pairs_considered": 9,
    "orbit_prefilter_rejected": 6,
    "orbit_prefilter_inconclusive": 0,
    "orbit_prefilter_admitted": 3,
    "member_pairs_expanded": 12,
    "correspondence_domains": 12,
    "strain_admissible_correspondences": 32,
    "candidates_admitted": 32,
    "primitive_classes_created": 1,
    "sources_aggregated_by_pair_key": 31,
}


def full_square_point_group() -> tuple[np.ndarray, ...]:
    """Return the validated eight-operation D4 group for a unit square."""

    operations = tuple(
        np.asarray(values, dtype=int).reshape(2, 2)
        for values in (
            (-1, 0, 0, -1),
            (-1, 0, 0, 1),
            (0, -1, -1, 0),
            (0, -1, 1, 0),
            (0, 1, -1, 0),
            (0, 1, 1, 0),
            (1, 0, 0, -1),
            (1, 0, 0, 1),
        )
    )
    return validate_surface_symmetry_group_2d(
        operations,
        metric=np.eye(2, dtype=float),
        metric_tolerance=1.0e-12,
    )


def expected_full_d4_keys(k_max: int) -> tuple[PairKey, ...]:
    """Return the frozen exact square-class inventory through ``k_max <= 30``."""

    limit = int(k_max)
    if limit < 1 or limit > 30:
        raise ValueError("the frozen full-D4 inventory is defined for 1 <= k_max <= 30")
    return tuple(key for first_index, key in FULL_D4_DISCOVERY_BY_INDEX if first_index <= limit)
