"""Run the detailed CALM and pymatgen benchmark workflow."""

from __future__ import annotations

if __package__ in {None, ""}:  # Direct execution from a repository checkout.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks.run_all import main
else:  # Package execution: python -m benchmarks.run_all
    from .benchmarks.run_all import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
