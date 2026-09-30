"""Version helpers for CALM.

This module is intentionally lightweight and avoids importing any heavy optional
dependencies. It is safe to import at module import time.

Notes
-----
- In an installed environment, ``__version__`` is read from package metadata.
- When running from a source tree without an installed distribution (e.g. some
  CI/test configurations), metadata may be unavailable; in that case we fall
  back to a sentinel value.
"""

from __future__ import annotations

from importlib import metadata


def get_version(package: str = "calm") -> str:
    """Return the installed version for *package*.

    If package metadata is unavailable (e.g. running from a source checkout that
    has not been installed), returns a best-effort sentinel string.

    Parameters
    ----------
    package:
        Distribution name to query via ``importlib.metadata``.
    """

    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        # Common in editable-less source tree test runs.
        return "0.0.0+unknown"


__version__: str = get_version()
