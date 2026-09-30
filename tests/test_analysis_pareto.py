from __future__ import annotations

import numpy as np
import pytest

from calm.analysis.pareto import pareto_front_2d_numpy, strain_size_pareto


def test_pareto_front_2d_numpy_basic_minimization() -> None:
    x = np.array([0.0, 1.0, 0.5, 2.0])
    y = np.array([2.0, 1.0, 0.5, 2.0])

    mask, idx, ids, px, py = pareto_front_2d_numpy(x, y)

    assert mask.tolist() == [True, False, True, False]
    assert idx.tolist() == [0, 2]
    assert ids.tolist() == [0, 2]
    assert px.tolist() == [0.0, 0.5]
    assert py.tolist() == [2.0, 0.5]


def test_pareto_front_2d_numpy_filters_nonfinite_values() -> None:
    x = np.array([np.inf, 1.0, 0.0, np.nan])
    y = np.array([0.0, 1.0, 2.0, 0.0])

    mask, idx, ids, px, py = pareto_front_2d_numpy(x, y)

    assert mask.tolist() == [False, True, True, False]
    assert idx.tolist() == [2, 1]
    assert ids.tolist() == [2, 1]
    assert px.tolist() == [0.0, 1.0]
    assert py.tolist() == [2.0, 1.0]


def test_pareto_front_2d_numpy_validates_shapes() -> None:
    with pytest.raises(ValueError, match="x and y must have same shape"):
        pareto_front_2d_numpy(np.array([1.0]), np.array([1.0, 2.0]))

    with pytest.raises(ValueError, match="x and y must be 1D"):
        pareto_front_2d_numpy(np.array([[1.0]]), np.array([[1.0]]))

    with pytest.raises(ValueError, match="ids must have same length"):
        pareto_front_2d_numpy(np.array([1.0]), np.array([1.0]), ids=["a", "b"])



def test_authoritative_pareto_callable_failure_propagates() -> None:
    def broken_feature(_point):
        raise RuntimeError("feature extraction failed")

    with pytest.raises(RuntimeError, match="feature extraction failed"):
        strain_size_pareto(
            [{"uid": "p", "d_cell": 0.01}],
            atom_count=broken_feature,
        )
