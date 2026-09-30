from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.benchmarks.claims._support import (
    key_text,
    matrix_payload,
    slab_from_basis,
    write_canonical_jsonl_atomic,
    write_csv_atomic,
    write_jsonl_atomic,
)


def test_key_and_matrix_payloads_preserve_claim_evidence_shapes() -> None:
    assert key_text((1, -2, 3)) == "[1,-2,3]"
    assert matrix_payload(np.array([[1, 2], [3, 4]], dtype=object)) == [
        [1, 2],
        [3, 4],
    ]
    assert matrix_payload((1, 2, 3, 4)) == [[1, 2], [3, 4]]
    assert matrix_payload(np.arange(8).reshape(4, 2)) == [
        [0, 1],
        [2, 3],
        [4, 5],
        [6, 7],
    ]
    with pytest.raises(ValueError, match="rank two"):
        matrix_payload((1, 2, 3))


def test_slab_fixture_uses_column_basis_and_is_fresh() -> None:
    basis = np.array([[2.0, 0.5], [0.0, 1.5]])
    first = slab_from_basis(basis)
    second = slab_from_basis(basis)

    expected = np.eye(3)
    expected[:2, :2] = basis.T
    expected[2, 2] = 10.0
    assert np.array_equal(first.atoms.cell.array, expected)
    assert first.n_atoms == 1
    assert first is not second
    assert first.atoms.cell.array is not second.atoms.cell.array


def test_jsonl_writers_preserve_compact_and_canonical_encodings(
    tmp_path: Path,
) -> None:
    rows = ({"z": 1, "a": "value"}, {"nested": {"b": 2, "a": 1}})

    compact = write_jsonl_atomic(tmp_path / "compact.jsonl", rows)
    canonical = write_canonical_jsonl_atomic(tmp_path / "canonical.jsonl", rows)

    expected = (
        b'{"a":"value","z":1}\n'
        b'{"nested":{"a":1,"b":2}}\n'
    )
    assert compact.read_bytes() == expected
    assert canonical.read_bytes() == expected


def test_csv_writer_preserves_discovered_and_explicit_columns(
    tmp_path: Path,
) -> None:
    rows = ({"b": 2, "a": 1}, {"c": 3, "a": 4})

    inferred = write_csv_atomic(tmp_path / "inferred.csv", rows)
    with inferred.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["b", "a", "c"]
        assert list(reader) == [
            {"b": "2", "a": "1", "c": ""},
            {"b": "", "a": "4", "c": "3"},
        ]

    explicit = write_csv_atomic(
        tmp_path / "explicit.csv",
        rows,
        fieldnames=("a", "c"),
    )
    assert explicit.read_text(encoding="utf-8").splitlines() == [
        "a,c",
        "1,",
        "4,3",
    ]

    with pytest.raises(ValueError, match="empty CSV"):
        write_csv_atomic(tmp_path / "empty.csv", ())


def test_atomic_writers_replace_existing_artifacts(tmp_path: Path) -> None:
    destination = tmp_path / "records.jsonl"
    destination.write_text("obsolete\n", encoding="utf-8")

    write_jsonl_atomic(destination, ({"current": True},))

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "current": True
    }
    assert not tuple(tmp_path.glob(f".{destination.name}.*"))
