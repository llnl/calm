"""Generate the three-panel Hencky benchmark figure."""

from __future__ import annotations

from .benchmarks.figure_hencky_triptych import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
