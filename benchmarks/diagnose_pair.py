"""Diagnose one CALM and pymatgen benchmark pair."""

from __future__ import annotations

from .benchmarks.diagnose_pair import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
