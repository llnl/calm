"""Import-lightness guardrail.

`import calm` should be lightweight and must not eagerly import the heavy
atomistic stack (ASE, spglib).

This test uses a subprocess so it is isolated from the state of the current
pytest process (which may have already imported ASE/spglib for other tests).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_import_calm_does_not_eagerly_import_ase_or_spglib() -> None:
    code = textwrap.dedent(
        """
        import sys

        import calm  # noqa: F401

        assert "ase" not in sys.modules
        assert "spglib" not in sys.modules
        """
    ).strip()

    subprocess.run([sys.executable, "-c", code], check=True)
