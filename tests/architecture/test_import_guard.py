"""Import guard tests.

Stage A contract: core imports must not import matplotlib.

This test passes whether or not matplotlib is installed; it only asserts that
calm core import does not eagerly load it.
"""

from __future__ import annotations

import sys


def test_import_calm_does_not_import_matplotlib() -> None:
    # Ensure clean state for the check (best-effort).
    sys.modules.pop("matplotlib", None)
    sys.modules.pop("matplotlib.pyplot", None)

    import calm  # noqa: F401

    assert "matplotlib" not in sys.modules
    assert "matplotlib.pyplot" not in sys.modules
