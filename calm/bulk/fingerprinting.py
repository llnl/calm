"""Bulk structure fingerprinting utilities.

This module contains pure functions for:
- Canonical fingerprinting of atomic structures
- UID generation from structure fingerprints
- Metadata extraction from structures

These utilities are extracted from the BulksService to improve separation of
concerns and enable independent testing.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np

from calm.structure.standardization import (
    DEFAULT_SPGLIB_ANGLE_TOLERANCE,
    canonical_fractional_species_rows,
    exact_pbc3,
    finite_cell_rows,
    fingerprint_decimals,
    positive_finite_float,
    rounded_finite_array,
    validate_crystal_arrays,
)


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic JSON serialization for content-hash UIDs.

    Parameters
    ----------
    obj : Any
        Object to serialize (must be JSON-serializable).

    Returns
    -------
    bytes
        Canonical JSON representation as UTF-8 bytes.

    Notes
    -----
    - Keys are sorted alphabetically
    - No whitespace (compact separators)
    - Numpy arrays/scalars are converted to Python types
    - Path objects are converted to strings
    """

    def _default(o: Any) -> Any:
        # Numpy scalars / arrays
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        # Path
        if isinstance(o, Path):
            return str(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    s = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=_default,
    )
    return s.encode("utf-8")


def structure_to_spglib_cell(
    atoms: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return one validated spglib tuple from an Atoms-like structure."""

    lattice, positions, numbers, _pbc = validate_crystal_arrays(
        lattice=getattr(atoms, "cell"),
        scaled_positions=atoms.get_scaled_positions(wrap=False),
        numbers=atoms.get_atomic_numbers(),
        pbc=getattr(atoms, "pbc", (True, True, True)),
        require_3d_pbc=True,
        require_positive_numbers=True,
    )
    positions = np.mod(positions, 1.0)
    positions[positions == 0.0] = 0.0
    return lattice, positions, numbers


def _structure_formula(atoms: Any) -> str:
    method = getattr(atoms, "get_chemical_formula", None)
    if not callable(method):
        raise TypeError("Atoms-like structure must expose get_chemical_formula().")
    formula = str(method())
    if not formula:
        raise ValueError("Atoms-like structure returned an empty chemical formula.")
    return formula


def _lattice_metadata(atoms: Any) -> dict[str, float]:
    cellpar = np.asarray(atoms.get_cell().cellpar(), dtype=float)
    if cellpar.shape != (6,) or not np.isfinite(cellpar).all():
        raise ValueError("cell parameters must be six finite values.")

    a, b, c, alpha, beta, gamma = map(
        float,
        np.round(cellpar, decimals=6),
    )
    return {
        "a": a,
        "b": b,
        "c": c,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }


def _dataset_value(dataset: object, name: str) -> object:
    if isinstance(dataset, dict):
        return dataset.get(name)
    return getattr(dataset, name, None)


def _optional_spacegroup_metadata(
    atoms: Any,
    *,
    symprec: float,
) -> dict[str, object] | None:
    try:
        import spglib  # type: ignore
    except ImportError:
        return None

    cell_tuple = structure_to_spglib_cell(atoms)
    dataset = spglib.get_symmetry_dataset(
        cell_tuple,
        symprec=symprec,
        angle_tolerance=DEFAULT_SPGLIB_ANGLE_TOLERANCE,
    )
    if dataset is None:
        return None

    raw_number = _dataset_value(dataset, "number")
    number = int(raw_number) if isinstance(raw_number, (int, np.integer)) else None
    raw_symbol = _dataset_value(dataset, "international")
    symbol = raw_symbol if isinstance(raw_symbol, str) and raw_symbol else None
    if number is None and symbol is None:
        return None
    return {"number": number, "international": symbol}


def atoms_fingerprint_to_dict(
    atoms: Any,
    *,
    decimals: int = 12,
    symprec: float = 1e-5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a deterministic representation fingerprint and UX metadata.

    The fingerprint is invariant to atom ordering, periodic coordinate wrapping,
    and perturbations removed by the requested decimal rounding. It deliberately
    retains the submitted cell basis and origin; it is not a universal
    crystallographic equivalence key.
    """

    precision = fingerprint_decimals(decimals)
    tolerance = positive_finite_float("symprec", symprec)
    cell = finite_cell_rows(getattr(atoms, "cell"))
    scaled, numbers = canonical_fractional_species_rows(
        scaled_positions=atoms.get_scaled_positions(wrap=False),
        numbers=atoms.get_atomic_numbers(),
        decimals=precision,
    )
    pbc = exact_pbc3(
        getattr(atoms, "pbc", (True, True, True)),
        require_all=False,
    )
    cell_rounded = rounded_finite_array(cell, decimals=precision)

    fingerprint: dict[str, Any] = {
        "cell": cell_rounded.tolist(),
        "scaled_positions": scaled.tolist(),
        "numbers": numbers.tolist(),
        "pbc": pbc.tolist(),
    }
    derived: dict[str, Any] = {
        "formula": _structure_formula(atoms),
        "n_atoms": int(numbers.shape[0]),
        "lattice": _lattice_metadata(atoms),
        "spacegroup": _optional_spacegroup_metadata(
            atoms,
            symprec=tolerance,
        ),
    }
    return fingerprint, derived


def bulk_uid_full_from_payload(payload: dict[str, Any]) -> str:
    """Return the deterministic UID for a metadata-only bulk payload."""

    spec = {"payload": dict(payload)}
    return hashlib.sha256(canonical_json_bytes(spec)).hexdigest()


def bulk_uid_full_from_atoms_dict(atoms_dict: dict[str, Any]) -> str:
    """Compute a stable bulk uid_full from an atoms fingerprint dict.

    Parameters
    ----------
    atoms_dict : dict[str, Any]
        A minimal, JSON-serialisable representation of an ASE Atoms object.
        Expected keys: cell, scaled_positions, numbers, pbc.

    Returns
    -------
    str
        A deterministic uid_full in the form ``bulk:<sha256>``.

    Raises
    ------
    TypeError
        If atoms_dict is not a valid mapping.

    Notes
    -----
    We frequently want bulk identity to be deterministic with respect to the
    underlying structure (rather than a random UUID). The fingerprint dict is
    assumed to be:
      - JSON-serialisable
      - order-insensitive (we canonicalise keys)
      - rounded/normalised (handled by the caller, e.g. ``atoms_fingerprint_to_dict``)
    """
    try:
        structure_dict = dict(atoms_dict)
    except (TypeError, ValueError) as e:  # pragma: no cover
        # Defensive: helps surface programming errors (e.g. passing a tuple)
        # with a clear message rather than a confusing dict() ValueError.
        msg = (
            "bulk_uid_full_from_atoms_dict expects a mapping of "
            "str->JSON-serialisable values"
        )
        raise TypeError(msg) from e

    spec = {"structure": structure_dict}
    return f"bulk:{hashlib.sha256(canonical_json_bytes(spec)).hexdigest()}"


_CHEMICAL_SYMBOLS = (
    "",
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Y",
    "Zr",
    "Nb",
    "Mo",
    "Tc",
    "Ru",
    "Rh",
    "Pd",
    "Ag",
    "Cd",
    "In",
    "Sn",
    "Sb",
    "Te",
    "I",
    "Xe",
    "Cs",
    "Ba",
    "La",
    "Ce",
    "Pr",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
    "Hf",
    "Ta",
    "W",
    "Re",
    "Os",
    "Ir",
    "Pt",
    "Au",
    "Hg",
    "Tl",
    "Pb",
    "Bi",
    "Po",
    "At",
    "Rn",
    "Fr",
    "Ra",
    "Ac",
    "Th",
    "Pa",
    "U",
    "Np",
    "Pu",
    "Am",
    "Cm",
    "Bk",
    "Cf",
    "Es",
    "Fm",
    "Md",
    "No",
    "Lr",
    "Rf",
    "Db",
    "Sg",
    "Bh",
    "Hs",
    "Mt",
    "Ds",
    "Rg",
    "Cn",
    "Nh",
    "Fl",
    "Mc",
    "Lv",
    "Ts",
    "Og",
)


def _fingerprint_numbers(fingerprint: Mapping[str, Any]) -> list[int]:
    if not isinstance(fingerprint, Mapping):
        raise TypeError("Atoms fingerprint must be a mapping.")
    if "numbers" not in fingerprint:
        raise ValueError("Atoms fingerprint is missing required field 'numbers'.")
    raw = fingerprint["numbers"]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise TypeError("Atoms fingerprint 'numbers' must be a sequence.")
    numbers: list[int] = []
    for index, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise TypeError(f"Atoms fingerprint numbers[{index}] must be an integer.")
        number = int(value)
        if number <= 0 or number >= len(_CHEMICAL_SYMBOLS):
            raise ValueError(
                f"Atoms fingerprint numbers[{index}]={number} is not a supported "
                "atomic number."
            )
        numbers.append(number)
    if not numbers:
        raise ValueError("Atoms fingerprint must contain at least one atom.")
    return numbers


def atoms_formula(fingerprint: Mapping[str, Any]) -> str:
    """Return the deterministic species-count formula of a valid fingerprint."""

    counts = Counter(_fingerprint_numbers(fingerprint))
    return "".join(
        _CHEMICAL_SYMBOLS[number]
        if count == 1
        else f"{_CHEMICAL_SYMBOLS[number]}{count}"
        for number, count in sorted(counts.items())
    )


def atoms_natoms(fingerprint: Mapping[str, Any]) -> int:
    """Return the exact atom count of a valid fingerprint."""

    return len(_fingerprint_numbers(fingerprint))


def atoms_lattice(fingerprint: Mapping[str, Any]) -> dict[str, float]:
    """Return exact lattice lengths and angles from a valid fingerprint."""

    if not isinstance(fingerprint, Mapping):
        raise TypeError("Atoms fingerprint must be a mapping.")
    if "cell" not in fingerprint:
        raise ValueError("Atoms fingerprint is missing required field 'cell'.")
    cell = finite_cell_rows(fingerprint["cell"])
    lengths = np.linalg.norm(cell, axis=1)
    a, b, c = (float(value) for value in lengths)
    if min(a, b, c) <= 0.0:
        raise ValueError("Atoms fingerprint cell vectors must have positive length.")

    def angle(left: np.ndarray, right: np.ndarray, denominator: float) -> float:
        cosine = float(np.dot(left, right) / denominator)
        return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))

    return {
        "a": a,
        "b": b,
        "c": c,
        "alpha": angle(cell[1], cell[2], b * c),
        "beta": angle(cell[0], cell[2], a * c),
        "gamma": angle(cell[0], cell[1], a * b),
    }
