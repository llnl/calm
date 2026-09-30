"""benchmarks.pareto

Deterministic 2D Pareto-front extraction for minimization problems.

We use Pareto fronts in (d_size, d_cell), where *smaller is better* on both axes.

Implementation notes
--------------------
For 2D minimization, a point is Pareto-efficient iff it achieves a new running
minimum in y after sorting by x (then y). This is O(n log n).

We expose:
- pareto_mask_2d_minimize: boolean mask for efficient points
- pareto_front_df: convenience wrapper for pandas DataFrames

"""

from __future__ import annotations


import numpy as np
import pandas as pd


def pareto_mask_2d_minimize(
    x: np.ndarray,
    y: np.ndarray,
    *,
    y_atol: float = 1e-12,
    x_atol: float = 0.0,
) -> np.ndarray:
    """Return boolean mask for Pareto-efficient points (minimize x and y).

    Notes:
      - If x_atol > 0, x is quantized by rounding x/x_atol prior to sorting.
        This makes the front more stable when x contains near-duplicates due to
        floating point noise (e.g., identical integer sizes expressed as floats).
      - y_atol is a strict improvement tolerance in y when scanning in x-order.
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError("x and y must have the same shape")

    n = int(x.size)
    if n == 0:
        return np.zeros(0, dtype=bool)

    finite = np.isfinite(x) & np.isfinite(y)
    keep = np.zeros(n, dtype=bool)
    if not finite.any():
        return keep

    idx = np.where(finite)[0]
    # Stable lexicographic order: x increasing, then y increasing.
    if x_atol and x_atol > 0:
        xq = np.round(x[idx] / float(x_atol)).astype(np.int64)
        order = idx[np.lexsort((y[idx], xq))]
    else:
        order = idx[np.lexsort((y[idx], x[idx]))]

    best_y = float("inf")
    for j in order:
        # Strict improvement in y is required; points with equal y but larger x
        # are dominated by the earlier point.
        if float(y[j]) < best_y - float(y_atol):
            keep[j] = True
            best_y = float(y[j])

    return keep


def pareto_front_df(
    df: pd.DataFrame,
    *,
    x_col: str = "d_size",
    y_col: str = "d_cell",
    y_atol: float = 1e-12,
    x_atol: float = 0.0,
    sort: bool = True,
) -> pd.DataFrame:
    """Return a copy of df restricted to Pareto-efficient rows."""

    if df.empty:
        return df.copy()

    mask = pareto_mask_2d_minimize(
        df[x_col].to_numpy(),
        df[y_col].to_numpy(),
        y_atol=y_atol,
        x_atol=x_atol,
    )
    out = df.loc[mask].copy()
    if sort:
        out = out.sort_values([x_col, y_col], kind="mergesort").reset_index(drop=True)
    return out
