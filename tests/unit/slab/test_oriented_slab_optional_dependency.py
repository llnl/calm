from __future__ import annotations

import pytest

from calm.exceptions import OptionalDependencyError
from calm.slab.oriented import builder as oriented_slab


def test_oriented_slab_reports_standardized_missing_ase_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oriented_slab, "make_supercell", None)

    with pytest.raises(OptionalDependencyError, match=r"calm\[science\]"):
        oriented_slab.build_oriented_slab(
            object(),
            hkl=(1, 0, 0),
            layers=1,
        )
