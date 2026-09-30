"""Plot CALM and pymatgen benchmark CSVs."""

from __future__ import annotations

from .benchmarks.plot_benchmarks import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
