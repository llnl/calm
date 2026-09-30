"""Core 2D math utilities used by CALM.

This module implements a small set of low-level linear-algebra helpers used by
the higher-level math2d package. The functions here favor clarity and exact
integer semantics where applicable.
"""

from __future__ import annotations

from typing import Literal, overload

import numpy as np

_DetMode = Literal["auto", "exact", "float"]


def _as_2x2(A: np.ndarray, *, dtype=None, name: str = "A") -> np.ndarray:
    """Validate that *A* is a 2×2 array and (optionally) cast dtype."""
    A = np.asarray(A) if dtype is None else np.asarray(A, dtype=dtype)
    if A.shape != (2, 2):
        raise ValueError(f"{name}: expected shape (2, 2), got {A.shape}")
    return A


def _cast_object_2x2(A: np.ndarray, *, name: str) -> np.ndarray:
    return _as_2x2(A, dtype=object, name=name)


def _safe_object_to_int(Aobj: np.ndarray, *, name: str) -> np.ndarray:
    """
    Convert an object array of Python ints to ``np.int_`` with overflow checking.

    Raises
    ------
    OverflowError
        If any values are outside the range representable by ``np.int_``.
    """
    Aobj = np.asarray(Aobj, dtype=object)
    info = np.iinfo(np.int_)
    for v in Aobj.ravel():
        iv = int(v)
        if iv < info.min or iv > info.max:
            raise OverflowError(
                f"{name}: value {iv} out of range for np.int_ [{info.min}, {info.max}]"
            )
    return np.asarray(Aobj, dtype=np.int_)


@overload
def det2(A: np.ndarray, *, mode: Literal["exact"]) -> int: ...
@overload
def det2(A: np.ndarray, *, mode: Literal["float"]) -> float: ...
@overload
def det2(A: np.ndarray, *, mode: Literal["auto"] = "auto") -> int | float: ...


def det2(A: np.ndarray, *, mode: _DetMode = "auto") -> int | float:
    """
    Determinant of a 2×2 matrix with dtype-aware behavior.

    Parameters
    ----------
    A
        2×2 matrix.
    mode
        - ``"auto"``: exact for int/bool/object dtypes, float otherwise
        - ``"exact"``: Python-int exact arithmetic
        - ``"float"``: float arithmetic

    Returns
    -------
    int | float
        Determinant in the requested arithmetic mode.
    """
    A = _as_2x2(A, name="det2")

    if mode == "auto":
        mode = "exact" if A.dtype.kind in ("i", "u", "b", "O") else "float"
    if mode not in ("exact", "float"):
        raise ValueError(f"det2: invalid mode={mode!r}")

    if mode == "exact":
        a11 = int(A[0, 0])
        a12 = int(A[0, 1])
        a21 = int(A[1, 0])
        a22 = int(A[1, 1])
        return a11 * a22 - a12 * a21

    a11 = float(A[0, 0])
    a12 = float(A[0, 1])
    a21 = float(A[1, 0])
    a22 = float(A[1, 1])
    return a11 * a22 - a12 * a21


def sym2(A: np.ndarray) -> np.ndarray:
    """Return ``(A + Aᵀ)/2`` cast to ``float``."""
    A = np.asarray(A, dtype=float)
    return 0.5 * (A + A.T)


def inv2(A: np.ndarray, *, det_tol: float = 1e-15) -> np.ndarray:
    """Explicit 2×2 inverse in float arithmetic."""
    A = _as_2x2(A, dtype=float, name="inv2")
    d = float(det2(A, mode="float"))
    if abs(d) < det_tol:
        raise ValueError("inv2: singular 2x2 matrix")
    return np.array([[A[1, 1], -A[0, 1]], [-A[1, 0], A[0, 0]]], dtype=float) / d


__all__ = [
    "_DetMode",
    "_as_2x2",
    "_cast_object_2x2",
    "_safe_object_to_int",
    "det2",
    "sym2",
    "inv2",
]
