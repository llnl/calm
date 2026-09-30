"""Repository-root wrapper for the C3/C4 identity-policy qualification."""

from __future__ import annotations

if __package__ in {None, ""}:  # pragma: no cover - direct-script compatibility
    from benchmarks.run_identity_policy_qualification import main
else:
    from .benchmarks.run_identity_policy_qualification import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
