"""Run the complete CALM benchmark and qualification suite."""

from __future__ import annotations

if __package__ in {None, ""}:  # Direct execution from a repository checkout.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks.run_full_suite import main
else:  # Package execution: python -m benchmarks.run_full_suite
    from .benchmarks.run_full_suite import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
