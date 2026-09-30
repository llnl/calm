"""Dependency-light structural characterization helpers.

The functions in this module derive deterministic, JSON-serializable metadata
from atom-like objects. They intentionally avoid bonding, charge, defect, and
other scientific-analysis concepts; the output is limited to composition,
cell geometry, symmetry labels already available from persistence, and slab
termination/stoichiometry bookkeeping.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from math import acos, degrees, gcd, isfinite, sqrt
from numbers import Integral, Real
from typing import Any, Mapping, Sequence

MATERIAL_CHARACTERIZATION_SCHEMA = "calm.material_characterization.v1"
SURFACE_CHARACTERIZATION_SCHEMA = "calm.surface_characterization.v1"
CHARACTERIZATION_POLICY_VERSION = 1
CHARACTERIZATION_ROUNDING_DIGITS = 8
CHARACTERIZATION_ROUNDING_MODE = "python_binary64_round_half_even"
MASS_DENSITY_CONVERSION_G_CM3_PER_AMU_A3 = 1.66053906660

MATERIAL_CELL_VOLUME_FORMULA = "abs(det(cell_rows_A))"
MATERIAL_VOLUME_PER_ATOM_FORMULA = "cell_volume_A3 / n_atoms"
MATERIAL_VOLUME_PER_FORMULA_UNIT_FORMULA = "cell_volume_A3 / gcd(composition_counts)"
MATERIAL_MASS_DENSITY_FORMULA = "total_mass_amu * 1.66053906660 / cell_volume_A3"
SURFACE_AREA_FORMULA = "norm(cross(cell_row_a_A, cell_row_b_A))"
SURFACE_NORMAL_FORMULA = "cross(cell_row_a_A, cell_row_b_A) / area_A2"
SURFACE_THICKNESS_FORMULA = (
    "max(dot(position_i_A, surface_normal)) - min(dot(position_i_A, surface_normal))"
)
SURFACE_CELL_HEIGHT_FORMULA = "abs(dot(cell_row_c_A, surface_normal))"
SURFACE_VACUUM_FORMULA = "max(cell_height_A - slab_thickness_A, 0)"
BULK_FORMULA_UNIT_COMPATIBILITY_RULE = (
    "surface_composition == n * parent_reduced_composition for one integer n >= 1"
)
MAX_COMPLETE_BULK_FORMULA_UNITS_FORMULA = (
    "min_s floor(surface_count_s / parent_coefficient_s)"
)
EXCESS_COMPOSITION_FORMULA = (
    "surface_composition - max_complete_bulk_formula_units * parent_reduced_composition"
)
CHEMICAL_POTENTIAL_RESERVOIR_RULE = (
    "required exactly when known surface composition is not an exact positive "
    "integer multiple of parent reduced composition"
)

MATERIAL_CHARACTERIZATION_CONTRACT: dict[str, Any] = {
    "policy": "material_structural_projection",
    "version": CHARACTERIZATION_POLICY_VERSION,
    "rounding_mode": CHARACTERIZATION_ROUNDING_MODE,
    "rounding_digits": CHARACTERIZATION_ROUNDING_DIGITS,
    "cell_vector_storage": "row_cartesian",
    "length_unit": "angstrom",
    "angle_unit": "degree",
    "volume_unit": "angstrom^3",
    "mass_unit": "unified_atomic_mass_unit",
    "density_unit": "gram/centimeter^3",
    "mass_density_conversion_factor": MASS_DENSITY_CONVERSION_G_CM3_PER_AMU_A3,
}

SURFACE_CHARACTERIZATION_CONTRACT: dict[str, Any] = {
    "policy": "oriented_surface_structural_projection",
    "version": CHARACTERIZATION_POLICY_VERSION,
    "rounding_mode": CHARACTERIZATION_ROUNDING_MODE,
    "rounding_digits": CHARACTERIZATION_ROUNDING_DIGITS,
    "cell_vector_storage": "row_cartesian",
    "in_plane_cell_rows": [0, 1],
    "surface_normal_orientation": "cross(cell_row_0,cell_row_1)",
    "position_projection": "unwrapped_cartesian",
    "length_unit": "angstrom",
    "area_unit": "angstrom^2",
    "reservoir_compatibility": "exact_parent_formula_unit_multiple",
}


def _contract_for_kind(kind: str) -> dict[str, Any]:
    if kind == "material":
        return MATERIAL_CHARACTERIZATION_CONTRACT
    if kind == "surface":
        return SURFACE_CHARACTERIZATION_CONTRACT
    raise ValueError("kind must be 'material' or 'surface'.")


def characterization_contract_status(value: Any, *, kind: str) -> str:
    """Classify characterization provenance without trusting stored status text."""

    expected = _contract_for_kind(kind)
    if isinstance(value, Mapping) and "contract" in value:
        contract = value.get("contract")
    else:
        contract = value
    if contract is None or contract == {}:
        return "legacy_unrecorded"
    if not isinstance(contract, Mapping):
        return "invalid"
    return "complete_v1" if dict(contract) == expected else "invalid"


def _contract_payload(kind: str) -> dict[str, Any]:
    return deepcopy(_contract_for_kind(kind))


def canonical_characterization_payload(
    value: Any,
    *,
    kind: str,
) -> dict[str, Any]:
    """Validate one persisted current characterization projection."""

    if not isinstance(value, Mapping):
        raise TypeError("Persisted characterization must be a mapping.")
    stored = dict(value)
    expected_schema = (
        MATERIAL_CHARACTERIZATION_SCHEMA
        if kind == "material"
        else SURFACE_CHARACTERIZATION_SCHEMA
        if kind == "surface"
        else None
    )
    if expected_schema is None:
        raise ValueError("kind must be 'material' or 'surface'.")
    if stored.get("schema") != expected_schema:
        raise ValueError(
            f"Current {kind} characterization requires schema {expected_schema!r}."
        )
    status = characterization_contract_status(stored, kind=kind)
    if status != "complete_v1":
        raise ValueError(
            f"Current {kind} characterization requires the complete v1 contract."
        )
    provenance = stored.get("provenance")
    if not isinstance(provenance, Mapping):
        raise TypeError(
            f"Current {kind} characterization provenance must be a mapping."
        )
    stored["contract"] = dict(stored["contract"])
    stored["provenance"] = dict(provenance)
    stored["contract_status"] = "complete_v1"
    return stored


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _finite_positive(value: Any) -> float | None:
    result = _finite_float(value)
    return result if result is not None and result > 0.0 else None


def round_characterization_value(
    value: Any,
    digits: int = CHARACTERIZATION_ROUNDING_DIGITS,
) -> float | None:
    """Round one binary64 value with Python's ties-to-even rule.

    The source floating-point value is part of the contract. Negative zero is
    normalized to positive zero so JSON projections have one representation.
    """

    if isinstance(digits, bool) or not isinstance(digits, Integral) or digits < 0:
        raise ValueError("digits must be a non-negative integer.")
    result = _finite_float(value)
    if result is None:
        return None
    rounded = round(result, int(digits))
    return 0.0 if rounded == 0.0 else rounded


def _rounded(
    value: Any, digits: int = CHARACTERIZATION_ROUNDING_DIGITS
) -> float | None:
    return round_characterization_value(value, digits)


def _cell_matrix(atoms: Any) -> list[list[float]]:
    getter = getattr(atoms, "get_cell", None)
    if callable(getter):
        cell = getter()
    elif hasattr(atoms, "cell"):
        cell = getattr(atoms, "cell")
    else:
        raise TypeError("Atom-like objects must provide a cell.")
    array = getattr(cell, "array", cell)
    try:
        rows = [[float(item) for item in row] for row in array]
    except (TypeError, ValueError) as exc:
        raise TypeError("Atom-like cell must be a finite 3x3 numeric matrix.") from exc
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError("Atom-like cell must have shape (3, 3).")
    if any(not isfinite(value) for row in rows for value in row):
        raise ValueError("Atom-like cell values must be finite.")
    return rows


def _det3(matrix: Sequence[Sequence[float]]) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return sqrt(_dot(a, a))


def _exact_positive_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        count = int(value)
    elif isinstance(value, Real):
        numeric = float(value)
        if not isfinite(numeric) or not numeric.is_integer():
            return None
        count = int(numeric)
    elif isinstance(value, str):
        text = value.strip()
        if (
            not text
            or (text[0] in "+-" and not text[1:].isdigit())
            or (text[0] not in "+-" and not text.isdigit())
        ):
            return None
        count = int(text, 10)
    else:
        return None
    return count if count > 0 else None


def normalize_composition_counts(composition: Mapping[Any, Any]) -> dict[str, int]:
    """Return sorted positive exact-integer counts.

    Invalid, zero, and negative entries are omitted. Labels that normalize to
    the same stripped string are accumulated rather than overwritten.
    """

    counts: dict[str, int] = {}
    for symbol, value in composition.items():
        label = str(symbol).strip()
        count = _exact_positive_count(value)
        if not label or count is None:
            continue
        counts[label] = counts.get(label, 0) + count
    return dict(sorted(counts.items()))


def composition_counts(atoms: Any) -> dict[str, int]:
    """Return sorted element counts from a valid atom-like object."""

    getter = getattr(atoms, "get_chemical_symbols", None)
    if not callable(getter):
        raise TypeError("Atom-like objects must provide get_chemical_symbols().")
    symbols = [str(value).strip() for value in getter()]
    if any(not symbol for symbol in symbols):
        raise ValueError("Atomic symbols must be non-empty strings.")
    return dict(sorted(Counter(symbols).items()))


def reduce_composition(
    composition: Mapping[Any, Any],
) -> tuple[dict[str, int], int | None]:
    """Return reduced integer composition and its formula-unit multiplier."""

    counts = normalize_composition_counts(composition)
    if not counts:
        return {}, None
    divisor = 0
    for value in counts.values():
        divisor = gcd(divisor, value)
    reduced = {symbol: value // divisor for symbol, value in counts.items()}
    return reduced, divisor


def _formula_from_atoms(atoms: Any, *, empirical: bool) -> str | None:
    getter = getattr(atoms, "get_chemical_formula", None)
    if not callable(getter):
        return None
    attempts = (
        {"mode": "metal", "empirical": empirical},
        {"mode": "hill", "empirical": empirical},
        {"empirical": empirical},
        {},
    )
    for kwargs in attempts:
        try:
            value = str(getter(**kwargs)).strip()
        except TypeError:
            continue
        if value:
            return value
    return None


def _spacegroup_parts(value: Any) -> tuple[str | None, int | None]:
    if isinstance(value, Mapping):
        symbol = value.get("international") or value.get("symbol")
        number = value.get("number")
        if isinstance(number, bool):
            number = None
        try:
            number = int(number) if number is not None else None
        except (TypeError, ValueError):
            number = None
        return (str(symbol).strip() if symbol else None, number)
    if isinstance(value, bool):
        return None, None
    if isinstance(value, int):
        return None, int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, None
        if text.isdigit():
            return None, int(text)
        if text.endswith(")") and "(" in text:
            symbol, _, suffix = text.rpartition("(")
            number_text = suffix[:-1].strip()
            return symbol.strip() or None, int(
                number_text
            ) if number_text.isdigit() else None
        return text, None
    return None, None


def crystal_system_from_spacegroup(number: int | None) -> str | None:
    """Map an international space-group number to its crystal system."""

    if number is None or not 1 <= number <= 230:
        return None
    if number <= 2:
        return "triclinic"
    if number <= 15:
        return "monoclinic"
    if number <= 74:
        return "orthorhombic"
    if number <= 142:
        return "tetragonal"
    if number <= 167:
        return "trigonal"
    if number <= 194:
        return "hexagonal"
    return "cubic"


def _lattice_parameters(
    atoms: Any | None,
    persisted: Mapping[str, Any] | None,
) -> tuple[dict[str, float | None], str]:
    if atoms is None:
        source_values = persisted or {}
        values = [
            source_values.get("a"),
            source_values.get("b"),
            source_values.get("c"),
            source_values.get("alpha"),
            source_values.get("beta"),
            source_values.get("gamma"),
        ]
        source = (
            "derived_mapping"
            if any(value is not None for value in values)
            else "unavailable"
        )
    else:
        matrix = _cell_matrix(atoms)
        lengths = [_norm(row) for row in matrix]
        if any(length <= 0.0 for length in lengths):
            raise ValueError("Atom-like cell vectors must have positive length.")

        def angle(left: Sequence[float], right: Sequence[float]) -> float:
            denominator = _norm(left) * _norm(right)
            cosine = max(-1.0, min(1.0, _dot(left, right) / denominator))
            return degrees(acos(cosine))

        values = [
            lengths[0],
            lengths[1],
            lengths[2],
            angle(matrix[1], matrix[2]),
            angle(matrix[0], matrix[2]),
            angle(matrix[0], matrix[1]),
        ]
        source = "atoms_cell"
    return (
        {
            "lattice_a_A": _rounded(values[0]),
            "lattice_b_A": _rounded(values[1]),
            "lattice_c_A": _rounded(values[2]),
            "alpha_deg": _rounded(values[3]),
            "beta_deg": _rounded(values[4]),
            "gamma_deg": _rounded(values[5]),
        },
        source,
    )


def material_characterization_data(
    atoms: Any | None,
    *,
    material: str | None = None,
    kind: str | None = None,
    derived: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive a versioned material-characterization projection."""

    derived = derived or {}
    composition = composition_counts(atoms) if atoms is not None else {}
    composition_source = "atoms" if composition else "unavailable"
    if not composition and isinstance(derived.get("composition"), Mapping):
        composition = normalize_composition_counts(derived["composition"])
        if composition:
            composition_source = "derived_mapping"
    reduced_composition, multiplier = reduce_composition(composition)

    formula = _formula_from_atoms(atoms, empirical=False) if atoms is not None else None
    reduced_formula = (
        _formula_from_atoms(atoms, empirical=True) if atoms is not None else None
    )
    formula_source = "atoms" if formula else "unavailable"
    reduced_formula_source = "atoms" if reduced_formula else "unavailable"
    if formula is None and derived.get("formula"):
        formula = str(derived["formula"])
        formula_source = "derived_mapping"
    if reduced_formula is None:
        if derived.get("reduced_formula"):
            reduced_formula = str(derived["reduced_formula"])
            reduced_formula_source = "derived_mapping"
        elif formula is not None:
            reduced_formula = formula
            reduced_formula_source = formula_source

    n_atoms = sum(composition.values()) if composition else None
    n_atoms_source = "composition" if n_atoms is not None else "unavailable"
    if n_atoms is None:
        for key in ("n_atoms", "natoms"):
            candidate = _exact_positive_count(derived.get(key))
            if candidate is not None:
                n_atoms = candidate
                n_atoms_source = f"derived_mapping:{key}"
                break

    lattice_value = derived.get("lattice")
    lattice, lattice_source = _lattice_parameters(
        atoms,
        lattice_value if isinstance(lattice_value, Mapping) else None,
    )
    matrix = _cell_matrix(atoms) if atoms is not None else None
    volume = _finite_positive(abs(_det3(matrix))) if matrix is not None else None
    if atoms is not None and volume is None:
        raise ValueError("Atom-like cell volume must be finite and positive.")
    volume_source = "atoms_cell" if volume is not None else "unavailable"
    if volume is None:
        for key in ("cell_volume_A3", "volume"):
            candidate = _finite_positive(derived.get(key))
            if candidate is not None:
                volume = candidate
                volume_source = f"derived_mapping:{key}"
                break
    volume = _rounded(volume)

    total_mass_amu = None
    if atoms is not None:
        mass_getter = getattr(atoms, "get_masses", None)
        if callable(mass_getter):
            candidate_mass = sum(float(value) for value in mass_getter())
            total_mass_amu = _finite_positive(candidate_mass)
            if total_mass_amu is None:
                raise ValueError(
                    "Atom-like masses must sum to a positive finite value."
                )
    mass_source = "atoms_masses" if total_mass_amu is not None else "unavailable"
    if total_mass_amu is None:
        total_mass_amu = _finite_positive(derived.get("total_mass_amu"))
        if total_mass_amu is not None:
            mass_source = "derived_mapping:total_mass_amu"

    sg_symbol, sg_number = _spacegroup_parts(derived.get("spacegroup"))
    spacegroup_source = (
        "derived_mapping:spacegroup" if sg_symbol or sg_number else "unavailable"
    )
    if sg_symbol is None:
        sg_symbol = str(derived.get("spacegroup_symbol") or "").strip() or None
        if sg_symbol is not None:
            spacegroup_source = "derived_mapping:spacegroup_symbol"
    if sg_number is None:
        candidate = derived.get("spacegroup_number")
        if not isinstance(candidate, bool):
            try:
                sg_number = int(candidate) if candidate is not None else None
            except (TypeError, ValueError):
                sg_number = None
        if sg_number is not None:
            spacegroup_source = "derived_mapping:spacegroup_number"

    volume_per_atom = volume / n_atoms if volume is not None and n_atoms else None
    volume_per_fu = volume / multiplier if volume is not None and multiplier else None
    density = (
        total_mass_amu * MASS_DENSITY_CONVERSION_G_CM3_PER_AMU_A3 / volume
        if total_mass_amu is not None and volume is not None
        else None
    )

    contract = _contract_payload("material")
    return {
        "schema": MATERIAL_CHARACTERIZATION_SCHEMA,
        "contract": contract,
        "contract_status": characterization_contract_status(contract, kind="material"),
        "provenance": {
            "composition_source": composition_source,
            "formula_source": formula_source,
            "reduced_formula_source": reduced_formula_source,
            "n_atoms_source": n_atoms_source,
            "lattice_source": lattice_source,
            "cell_volume_source": volume_source,
            "total_mass_source": mass_source,
            "spacegroup_source": spacegroup_source,
        },
        "material": material,
        "kind": kind,
        "formula": formula,
        "reduced_formula": reduced_formula,
        "composition": composition,
        "reduced_composition": reduced_composition,
        "n_atoms": n_atoms,
        "n_formula_units": multiplier,
        **lattice,
        "cell_volume_A3": volume,
        "volume_per_atom_A3": _rounded(volume_per_atom),
        "volume_per_formula_unit_A3": _rounded(volume_per_fu),
        "total_mass_amu": _rounded(total_mass_amu),
        "mass_density_g_cm3": _rounded(density),
        "spacegroup_symbol": sg_symbol,
        "spacegroup_number": sg_number,
        "crystal_system": crystal_system_from_spacegroup(sg_number),
    }


def bulk_composition_relation(
    composition: Mapping[Any, Any],
    parent_reduced_composition: Mapping[Any, Any],
) -> dict[str, Any]:
    """Project one slab composition onto complete parent formula units."""

    slab = normalize_composition_counts(composition)
    parent = reduce_composition(parent_reduced_composition)[0]
    if not slab or not parent:
        return {
            "bulk_composition_relation": "unknown_missing_composition",
            "bulk_composition_compatible": None,
            "bulk_formula_units": None,
            "max_complete_bulk_formula_units": None,
            "excess_composition": {},
            "requires_chemical_potential_reservoir": None,
            "reservoir_status": "unknown",
            "reservoir_reason": "surface_or_parent_composition_unavailable",
        }

    exact_formula_units: int | None = None
    if set(slab) == set(parent):
        ratios: set[int] = set()
        for symbol, coefficient in parent.items():
            if slab[symbol] % coefficient:
                ratios = set()
                break
            ratios.add(slab[symbol] // coefficient)
        if len(ratios) == 1:
            candidate = next(iter(ratios))
            if candidate >= 1:
                exact_formula_units = candidate

    complete = min(
        slab.get(symbol, 0) // coefficient for symbol, coefficient in parent.items()
    )
    excess: dict[str, int] = {}
    for symbol in sorted(set(slab) | set(parent)):
        value = slab.get(symbol, 0) - complete * parent.get(symbol, 0)
        if value:
            excess[symbol] = value

    compatible = exact_formula_units is not None
    return {
        "bulk_composition_relation": "exact_integer_multiple"
        if compatible
        else "nonstoichiometric",
        "bulk_composition_compatible": compatible,
        "bulk_formula_units": exact_formula_units,
        "max_complete_bulk_formula_units": complete,
        "excess_composition": excess,
        "requires_chemical_potential_reservoir": not compatible,
        "reservoir_status": "not_required" if compatible else "required",
        "reservoir_reason": (
            "exact_parent_formula_unit_multiple"
            if compatible
            else "nonzero_excess_or_missing_parent_species"
        ),
    }


def _canonical_termination(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                (str(key), _canonical_termination(item)) for key, item in value.items()
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_canonical_termination(item) for item in value)
    if value is None:
        return None
    return str(value).strip().casefold()


def surface_geometry_projection(atoms: Any) -> dict[str, float | None]:
    """Project a valid oriented slab onto area, normal span, and vacuum."""

    matrix = _cell_matrix(atoms)
    normal_vec = _cross(matrix[0], matrix[1])
    area = _finite_positive(_norm(normal_vec))
    if area is None:
        raise ValueError("Surface in-plane cell area must be finite and positive.")
    normal = tuple(value / area for value in normal_vec)
    cell_height = _finite_float(abs(_dot(matrix[2], normal)))
    if cell_height is None:
        raise ValueError("Surface cell height must be finite.")

    getter = getattr(atoms, "get_positions", None)
    if not callable(getter):
        raise TypeError("Atom-like surfaces must provide get_positions().")
    try:
        positions = [[float(item) for item in row] for row in getter()]
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Surface positions must be a finite Nx3 numeric matrix."
        ) from exc
    if not positions:
        raise ValueError("Surface characterization requires at least one atom.")
    if any(len(row) != 3 for row in positions):
        raise ValueError("Surface positions must have shape (N, 3).")
    if any(not isfinite(value) for row in positions for value in row):
        raise ValueError("Surface positions must be finite.")
    projections = [_dot(position, normal) for position in positions]
    thickness = max(projections) - min(projections)
    vacuum = max(cell_height - thickness, 0.0)
    return {
        "area_A2": _rounded(area),
        "cell_height_A": _rounded(cell_height),
        "slab_thickness_A": _rounded(thickness),
        "vacuum_A": _rounded(vacuum),
    }


def _integer_triplet(value: Sequence[Any] | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    try:
        items = list(value)
    except (TypeError, ValueError):
        return None
    if len(items) != 3:
        return None
    out: list[int] = []
    for item in items:
        if isinstance(item, bool):
            return None
        if isinstance(item, Integral):
            out.append(int(item))
            continue
        if (
            isinstance(item, Real)
            and isfinite(float(item))
            and float(item).is_integer()
        ):
            out.append(int(item))
            continue
        return None
    result = tuple(out)
    return result if result != (0, 0, 0) else None


def surface_characterization_data(
    atoms: Any | None,
    *,
    parent_characterization: Mapping[str, Any] | None = None,
    material: str | None = None,
    miller: Sequence[int] | None = None,
    termination: Any = None,
    termination_top: Any = None,
    termination_bottom: Any = None,
    termination_shift: int | None = None,
    layers: int | None = None,
    area_A2: float | None = None,
    thickness_A: float | None = None,
    vacuum_A: float | None = None,
    formula: str | None = None,
) -> dict[str, Any]:
    """Derive a versioned surface-characterization projection."""

    parent = parent_characterization or {}
    composition = composition_counts(atoms) if atoms is not None else {}
    reduced_composition, multiplier = reduce_composition(composition)
    derived_formula = (
        _formula_from_atoms(atoms, empirical=False) if atoms is not None else None
    )
    formula = derived_formula or formula
    reduced_formula = (
        _formula_from_atoms(atoms, empirical=True) if atoms is not None else None
    )
    reduced_formula = reduced_formula or formula

    parent_composition_value = parent.get("reduced_composition") or parent.get(
        "composition"
    )
    parent_composition = (
        reduce_composition(parent_composition_value)[0]
        if isinstance(parent_composition_value, Mapping)
        else {}
    )
    relation = bulk_composition_relation(composition, parent_composition)

    computed = (
        surface_geometry_projection(atoms)
        if atoms is not None
        else {
            "area_A2": None,
            "cell_height_A": None,
            "slab_thickness_A": None,
            "vacuum_A": None,
        }
    )
    provided = {
        "area_A2": _rounded(area_A2),
        "slab_thickness_A": _rounded(thickness_A),
        "vacuum_A": _rounded(vacuum_A),
    }
    area = (
        computed["area_A2"] if computed["area_A2"] is not None else provided["area_A2"]
    )
    thickness = (
        computed["slab_thickness_A"]
        if computed["slab_thickness_A"] is not None
        else provided["slab_thickness_A"]
    )
    vacuum = (
        computed["vacuum_A"]
        if computed["vacuum_A"] is not None
        else provided["vacuum_A"]
    )
    geometry_sources = {
        "area_A2": "atoms"
        if computed["area_A2"] is not None
        else ("provided" if provided["area_A2"] is not None else "unavailable"),
        "cell_height_A": "atoms"
        if computed["cell_height_A"] is not None
        else "unavailable",
        "slab_thickness_A": "atoms"
        if computed["slab_thickness_A"] is not None
        else (
            "provided" if provided["slab_thickness_A"] is not None else "unavailable"
        ),
        "vacuum_A": "atoms"
        if computed["vacuum_A"] is not None
        else ("provided" if provided["vacuum_A"] is not None else "unavailable"),
    }

    top_key = _canonical_termination(termination_top)
    bottom_key = _canonical_termination(termination_bottom)
    symmetric = (
        top_key == bottom_key
        if top_key is not None and bottom_key is not None
        else None
    )
    miller_value = _integer_triplet(miller)
    layer_count = _exact_positive_count(layers)

    contract = _contract_payload("surface")
    return {
        "schema": SURFACE_CHARACTERIZATION_SCHEMA,
        "contract": contract,
        "contract_status": characterization_contract_status(contract, kind="surface"),
        "provenance": {
            "composition_source": "atoms" if composition else "unavailable",
            "parent_composition_source": (
                "parent_reduced_composition" if parent_composition else "unavailable"
            ),
            "formula_source": "atoms"
            if derived_formula
            else ("provided" if formula else "unavailable"),
            "geometry_sources": geometry_sources,
            "termination_comparison": "canonical_casefolded_recursive_value",
        },
        "material": material,
        "miller": list(miller_value) if miller_value is not None else None,
        "termination": termination,
        "termination_top": termination_top,
        "termination_bottom": termination_bottom,
        "termination_shift": termination_shift,
        "symmetric_termination": symmetric,
        "formula": formula,
        "reduced_formula": reduced_formula,
        "composition": composition,
        "reduced_composition": reduced_composition,
        "n_atoms": sum(composition.values()) if composition else None,
        "n_formula_units": multiplier,
        "parent_reduced_formula": parent.get("reduced_formula")
        or parent.get("formula"),
        "parent_reduced_composition": parent_composition,
        **relation,
        "area_A2": area,
        "cell_height_A": computed["cell_height_A"],
        "slab_thickness_A": thickness,
        "vacuum_A": vacuum,
        "layers": layer_count,
    }
