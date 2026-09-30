"""Shared visualization I/O helpers.

This module centralizes save-path normalization and consistent
``Figure.savefig`` behavior across plotting helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

PathLike = Union[str, Path]


def coerce_savepath(*, savepath: Optional[PathLike] = None) -> Optional[Path]:
    """Return ``savepath`` as a :class:`pathlib.Path`, or ``None``."""

    return None if savepath is None else Path(savepath)


def save_figure(
    fig: Any,
    savepath: Path,
    *,
    dpi: Optional[int] = None,
    bbox_inches: str = "tight",
) -> None:
    """Save a matplotlib figure robustly.

    - Creates parent directories (if any).
    - Applies consistent save options.

    Parameters
    ----------
    fig
        A matplotlib Figure-like object.

    savepath
        Destination path.

    dpi
        Optional DPI for raster formats.

    bbox_inches
        Passed through to ``Figure.savefig``.
    """

    try:
        savepath.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If the parent is not settable or path is unusual, proceed and let
        # matplotlib handle the failure.
        pass

    if dpi is None:
        fig.savefig(savepath, bbox_inches=bbox_inches)
    else:
        fig.savefig(savepath, dpi=int(dpi), bbox_inches=bbox_inches)
