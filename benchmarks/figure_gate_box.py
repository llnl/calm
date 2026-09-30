"""Generate the two-dimensional gate box figure."""

from __future__ import annotations

from .benchmarks.figure_gate_box import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
