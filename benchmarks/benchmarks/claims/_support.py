"""Shared mechanical support for claim-oriented benchmark evidence.

This module owns only artifact serialization, exact display helpers, and the
minimal slab-like fixture used to call CALM's basis-only matching kernels. It
must not own claim definitions, scientific policies, workload selection, or
correctness oracles.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .manifest import canonical_json_bytes


def key_text(key: Sequence[int]) -> str:
    """Return the stable compact JSON representation of an integer key."""

    return json.dumps([int(value) for value in key], separators=(",", ":"))


def matrix_payload(matrix: Any) -> list[list[int]]:
    """Return an exact rank-two integer matrix as nested native lists."""

    array = np.asarray(matrix)
    if array.shape == (4,):
        array = array.reshape(2, 2)
    if array.ndim != 2:
        raise ValueError("matrix must be rank two or contain four flat entries")
    return [
        [int(array[i, j]) for j in range(array.shape[1])]
        for i in range(array.shape[0])
    ]


@dataclass(frozen=True)
class _SyntheticCell:
    array: np.ndarray


@dataclass(frozen=True)
class _SyntheticAtoms:
    cell: _SyntheticCell


@dataclass(frozen=True)
class SyntheticSlab:
    """Minimal immutable slab-like object for basis-only matcher fixtures."""

    atoms: _SyntheticAtoms
    n_atoms: int = 1


def slab_from_basis(basis: Sequence[Sequence[float]]) -> SyntheticSlab:
    """Construct a minimal slab-like object from a 2x2 column basis."""

    matrix = np.asarray(basis, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError("basis must have shape (2, 2)")
    cell = np.eye(3, dtype=float)
    cell[:2, :2] = matrix.T
    cell[2, 2] = 10.0
    return SyntheticSlab(atoms=_SyntheticAtoms(cell=_SyntheticCell(cell)))


def _replace_atomic(temporary_name: str, path: Path) -> Path:
    try:
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return path


def write_jsonl_atomic(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    """Write compact sorted JSON objects atomically, one object per line."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(
                    json.dumps(dict(row), sort_keys=True, separators=(",", ":"))
                )
                handle.write("\n")
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return _replace_atomic(temporary_name, path)


def write_canonical_jsonl_atomic(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    """Write canonical claim JSON records atomically as ASCII JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            for row in rows:
                handle.write(canonical_json_bytes(dict(row)))
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return _replace_atomic(temporary_name, path)


def write_csv_atomic(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> Path:
    """Write mapping rows atomically with deterministic column ownership."""

    selected_fields: list[str]
    if fieldnames is None:
        if not rows:
            raise ValueError("cannot write an empty CSV")
        selected_fields = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    selected_fields.append(key)
                    seen.add(key)
    else:
        selected_fields = [str(name) for name in fieldnames]

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=selected_fields)
            writer.writeheader()
            if fieldnames is None:
                writer.writerows(rows)
            else:
                for row in rows:
                    writer.writerow({name: row.get(name) for name in selected_fields})
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return _replace_atomic(temporary_name, path)
