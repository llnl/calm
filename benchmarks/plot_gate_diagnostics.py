"""Generate the gate-diagnostic benchmark figure."""

from __future__ import annotations

from .benchmarks.plot_gate_diagnostics import main


if __name__ == "__main__":  # pragma: no cover
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
