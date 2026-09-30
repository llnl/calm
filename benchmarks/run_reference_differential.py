"""Direct-script and module wrapper for the C2 reference differential runner."""

from __future__ import annotations

if __package__ in {None, ""}:  # pragma: no cover - direct script path
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from benchmarks.run_reference_differential import main
else:  # pragma: no cover - module path
    from .benchmarks.run_reference_differential import main


if __name__ == "__main__":
    raise SystemExit(main())
