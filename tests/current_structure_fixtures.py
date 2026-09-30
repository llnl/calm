"""Exact-current atom-structure fixtures shared by successful tests.

Successful persistence and public-read tests should construct atom payloads
through this module. Tests of malformed or historical state should keep their
invalid mappings local so the failure being exercised remains explicit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def current_atoms_payload(
    *,
    numbers: Sequence[int] = (1,),
    cell: Sequence[Sequence[float]] | None = None,
    scaled_positions: Sequence[Sequence[float]] | None = None,
    pbc: Sequence[bool] = (True, True, True),
    info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one fresh exact-current serialized atom structure.

    This builder deliberately spells out the persisted representation rather
    than calling a production canonicalizer. It is for valid successful-test
    setup only; malformed-state tests should define invalid payloads locally.
    """

    atomic_numbers = [int(value) for value in numbers]
    if not atomic_numbers:
        raise ValueError("Current atom fixtures require at least one atom.")

    cell_rows = (
        [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]]
        if cell is None
        else [[float(value) for value in row] for row in cell]
    )
    if len(cell_rows) != 3 or any(len(row) != 3 for row in cell_rows):
        raise ValueError("Current atom fixtures require one 3x3 cell.")

    positions = (
        [[0.0, 0.0, 0.0] for _ in atomic_numbers]
        if scaled_positions is None
        else [[float(value) for value in row] for row in scaled_positions]
    )
    if len(positions) != len(atomic_numbers):
        raise ValueError(
            "Current atom fixtures require one scaled position per atom."
        )
    if any(len(row) != 3 for row in positions):
        raise ValueError("Current scaled positions must have length three.")

    periodicity = [bool(value) for value in pbc]
    if len(periodicity) != 3:
        raise ValueError("Current atom fixtures require exactly three PBC flags.")

    payload: dict[str, Any] = {
        "numbers": atomic_numbers,
        "cell": cell_rows,
        "scaled_positions": positions,
        "pbc": periodicity,
    }
    if info is not None:
        payload["info"] = dict(info)
    return payload
