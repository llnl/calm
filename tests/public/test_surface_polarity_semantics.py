from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.projections.slab import normalize_slab_row
from calm.public.records.surfaces import Surface
from calm.slab.oriented import terminations as termination_enumeration


class _FakeSlab:
    def __init__(self, formula: str, n_atoms: int = 2) -> None:
        self._formula = formula
        self._n_atoms = n_atoms

    def get_chemical_formula(self) -> str:
        return self._formula

    def __len__(self) -> int:
        return self._n_atoms


def _surface(monkeypatch: pytest.MonkeyPatch) -> Surface:
    monkeypatch.setattr(Surface, "to_bulk", lambda self: object())
    return Surface(structure=object(), miller=(1, 0, 0), layers=4)


def test_termination_rows_report_multiplicity_without_polarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface = _surface(monkeypatch)
    enumerated = [
        (_FakeSlab("AB"), "A", 0),
        (_FakeSlab("AB"), "B", 1),
    ]
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        lambda *args, **kwargs: enumerated,
    )
    monkeypatch.setattr(
        termination_enumeration,
        "_cluster_atoms_by_z",
        lambda atoms, tolerance: [
            SimpleNamespace(composition="A"),
            SimpleNamespace(composition="B"),
        ],
    )

    rows = surface.terminations().to_rows()

    assert len(rows) == 2
    for row in rows:
        assert "polar" not in row
        assert row["enumeration_count"] == 2
        assert row["has_multiple_enumerated_terminations"] is True
        assert row["polarity_status"] == "not_evaluated"


def test_single_termination_is_reported_as_enumeration_cardinality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface = _surface(monkeypatch)
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        lambda *args, **kwargs: [(_FakeSlab("A", 1), "A", 0)],
    )
    monkeypatch.setattr(
        termination_enumeration,
        "_cluster_atoms_by_z",
        lambda atoms, tolerance: [SimpleNamespace(composition="A")],
    )

    row = surface.terminations()[0]

    assert row["enumeration_count"] == 1
    assert row["has_multiple_enumerated_terminations"] is False
    assert row["polarity_status"] == "not_evaluated"


def test_enumeration_failure_is_not_converted_to_nonpolar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = RuntimeError("termination enumeration failed")

    def _raise(*args, **kwargs):
        raise expected

    monkeypatch.setattr(
        termination_enumeration,
        "identify_unique_terminations",
        _raise,
    )

    with pytest.raises(RuntimeError, match="termination enumeration failed"):
        termination_enumeration.has_multiple_enumerated_terminations(
            object(),
            (1, 0, 0),
        )



@pytest.mark.parametrize("legacy_value", [True, False, None])
def test_legacy_persisted_polar_flag_is_rejected(legacy_value: object) -> None:
    with pytest.raises(ValueError, match="missing required current field"):
        normalize_slab_row(
            {
                "uid_full": "slab:legacy",
                "id_short": "s_legacy",
                "bulk_uid_full": "bulk:m",
                "bulk_id_short": "b_m",
                "miller": (1, 0, 0),
                "payload": {"termination": "A", "polar": legacy_value},
            }
        )


def test_root_level_legacy_polar_flag_is_rejected() -> None:
    with pytest.raises(ValueError, match="slab-record payload"):
        normalize_slab_row(
            {
                "uid_full": "slab:legacy-root",
                "id_short": "s_legacy_root",
                "bulk_uid_full": "bulk:m",
                "bulk_id_short": "b_m",
                "miller": (1, 0, 0),
                "termination": "A",
                "polar": True,
            }
        )
