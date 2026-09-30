"""Direct-script wrapper for :mod:`benchmarks.run_extension_stability_qualification`."""

from __future__ import annotations

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    from benchmarks.run_extension_stability_qualification import main
else:  # pragma: no cover - module execution
    from .benchmarks.run_extension_stability_qualification import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
