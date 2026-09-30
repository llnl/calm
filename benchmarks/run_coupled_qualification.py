"""Repository-root entry point for coupled-v2 qualification benchmarks."""

from __future__ import annotations

if __package__ in {None, ""}:  # Direct execution from a repository checkout.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks.run_coupled_qualification import main
else:  # Package execution: python -m benchmarks.run_coupled_qualification
    from .benchmarks.run_coupled_qualification import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
