"""Repository-root entry point for correspondence performance qualification."""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks.run_correspondence_performance_qualification import main
else:
    from .benchmarks.run_correspondence_performance_qualification import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
