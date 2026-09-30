"""Direct-script wrapper for public-API parity qualification."""

from __future__ import annotations

if __package__ in {None, ""}:  # pragma: no cover
    from benchmarks.run_public_api_parity_qualification import main
else:  # pragma: no cover
    from .benchmarks.run_public_api_parity_qualification import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
