"""Repository-checkout wrapper for the C7 ZSL oracle comparison."""

from __future__ import annotations

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from benchmarks.run_zsl_oracle_comparison import main
else:  # pragma: no cover - module execution
    from .benchmarks.run_zsl_oracle_comparison import main


if __name__ == "__main__":
    raise SystemExit(main())
