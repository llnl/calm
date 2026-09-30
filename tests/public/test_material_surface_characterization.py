from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.project.application.bulk_fingerprinting import BulkFingerprintService
from calm.public.records.characterization import (
    MaterialCharacterization,
    SurfaceCharacterization,
)
from calm.public.records.generated_surface import GeneratedSurface
from calm.public.inputs.materials import Material
from calm.public.collections.structures import MaterialCollection, SurfaceCollection
from calm.structure.characterization import (
    material_characterization_data,
    surface_characterization_data,
)
from slab_record_fixtures import current_slab_payload


class _Cell:
    def __init__(self, matrix):
        self.array = np.asarray(matrix, dtype=float)

    def __array__(self, dtype=None):
        return np.asarray(self.array, dtype=dtype)

    def __iter__(self):
        return iter(self.array)

    def tolist(self):
        return self.array.tolist()

    def cellpar(self):
        lengths = self.lengths()
        return np.asarray([*lengths, 90.0, 90.0, 90.0])

    def lengths(self):
        return np.linalg.norm(self.array, axis=1)

    def angles(self):
        return np.asarray([90.0, 90.0, 90.0])


class _Atoms:
    _masses = {"Li": 6.94, "F": 18.998403163, "O": 15.999}
    _numbers = {"Li": 3, "F": 9, "O": 8}

    def __init__(self, symbols, scaled_positions, cell):
        self._symbols = list(symbols)
        self._scaled = np.asarray(scaled_positions, dtype=float)
        self.cell = _Cell(cell)
        self.numbers = np.asarray([self._numbers[s] for s in symbols], dtype=int)
        self.pbc = np.asarray([True, True, True])

    def __len__(self):
        return len(self._symbols)

    def get_cell(self):
        return self.cell

    def get_scaled_positions(self, wrap=False):
        return np.mod(self._scaled, 1.0) if wrap else self._scaled.copy()

    def get_positions(self):
        return self._scaled @ self.cell.array

    def get_atomic_numbers(self):
        return self.numbers.copy()

    def get_chemical_symbols(self):
        return list(self._symbols)

    def get_masses(self):
        return np.asarray([self._masses[s] for s in self._symbols])

    def get_chemical_formula(self, mode="metal", empirical=False):
        counts = {symbol: self._symbols.count(symbol) for symbol in dict.fromkeys(self._symbols)}
        if empirical:
            from math import gcd

            divisor = 0
            for value in counts.values():
                divisor = gcd(divisor, value)
            counts = {symbol: value // divisor for symbol, value in counts.items()}
        return "".join(
            symbol + (str(value) if value != 1 else "")
            for symbol, value in counts.items()
        )


def _lif_bulk_atoms():
    return _Atoms(
        ["Li", "F", "Li", "F"],
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.0],
        ],
        np.diag([4.0, 4.0, 4.0]),
    )


def _atoms_payload(atoms: _Atoms) -> dict[str, object]:
    return {
        "numbers": atoms.get_atomic_numbers().tolist(),
        "cell": atoms.get_cell().tolist(),
        "scaled_positions": atoms.get_scaled_positions(wrap=False).tolist(),
        "pbc": [bool(value) for value in atoms.pbc.tolist()],
    }


def test_material_characterization_derives_polymorph_metadata():
    data = material_characterization_data(
        _lif_bulk_atoms(),
        material="LiF_opt",
        kind="optimized",
        derived={"spacegroup": {"international": "Fm-3m", "number": 225}},
    )
    record = MaterialCharacterization.from_mapping(data)

    assert record.composition == {"F": 2, "Li": 2}
    assert record.reduced_composition == {"F": 1, "Li": 1}
    assert record.reduced_formula == "LiF"
    assert record.n_formula_units == 2
    assert record.cell_volume_A3 == 64.0
    assert record.volume_per_formula_unit_A3 == 32.0
    assert record.spacegroup_symbol == "Fm-3m"
    assert record.spacegroup_number == 225
    assert record.crystal_system == "cubic"
    assert record.mass_density_g_cm3 is not None
    assert record.contract_status == "complete_v1"
    assert record.contract["policy"] == "material_structural_projection"
    assert record.provenance["cell_volume_source"] == "atoms_cell"
    assert "density=" in record.summary()


def test_surface_characterization_tracks_termination_and_bulk_compatibility():
    parent = material_characterization_data(_lif_bulk_atoms())
    slab = _Atoms(
        ["Li", "F", "Li", "F"],
        [
            [0.0, 0.0, 0.40],
            [0.5, 0.5, 0.45],
            [0.0, 0.5, 0.50],
            [0.5, 0.0, 0.55],
        ],
        np.diag([4.0, 4.0, 20.0]),
    )
    record = SurfaceCharacterization.from_mapping(
        surface_characterization_data(
            slab,
            parent_characterization=parent,
            material="LiF_opt",
            miller=(1, 0, 0),
            termination="LiF",
            termination_top="LiF",
            termination_bottom="LiF",
            termination_shift=0,
            layers=4,
        )
    )

    assert record.miller == (1, 0, 0)
    assert record.symmetric_termination is True
    assert record.bulk_composition_compatible is True
    assert record.bulk_composition_relation == "exact_integer_multiple"
    assert record.bulk_formula_units == 2
    assert record.excess_composition == {}
    assert record.requires_chemical_potential_reservoir is False
    assert record.reservoir_status == "not_required"
    assert record.area_A2 == 16.0
    assert record.cell_height_A == 20.0
    assert record.slab_thickness_A == 3.0
    assert record.vacuum_A == 17.0


def test_surface_characterization_exposes_nonstoichiometric_excess():
    parent = material_characterization_data(_lif_bulk_atoms())
    slab = _Atoms(
        ["Li", "F", "Li"],
        [[0.0, 0.0, 0.4], [0.5, 0.5, 0.5], [0.0, 0.5, 0.6]],
        np.diag([4.0, 4.0, 20.0]),
    )
    record = SurfaceCharacterization.from_mapping(
        surface_characterization_data(
            slab,
            parent_characterization=parent,
            termination_top="Li",
            termination_bottom="F",
        )
    )

    assert record.symmetric_termination is False
    assert record.bulk_composition_compatible is False
    assert record.bulk_formula_units is None
    assert record.max_complete_bulk_formula_units == 1
    assert record.excess_composition == {"Li": 1}
    assert record.requires_chemical_potential_reservoir is True
    assert record.reservoir_status == "required"
    assert record.bulk_composition_relation == "nonstoichiometric"


def test_bulk_fingerprint_payload_persists_characterization():
    payload = BulkFingerprintService().assemble_structure_payload(_lif_bulk_atoms())

    assert payload["characterization"]["schema"] == "calm.material_characterization.v1"
    assert payload["characterization"]["reduced_formula"] == "LiF"
    assert payload["derived"]["cell_volume_A3"] == 64.0
    assert payload["derived"]["composition"] == {"F": 2, "Li": 2}


def test_public_material_and_surface_records_use_persisted_characterization():
    material_data = material_characterization_data(
        _lif_bulk_atoms(),
        material="LiF_opt",
        kind="optimized",
    )
    material = Material.from_workspace(
        {
            "id_short": "b_lif",
            "label": "LiF_opt",
            "kind": "optimized",
            "payload": {"characterization": material_data},
        }
    )
    assert material.characterize().reduced_formula == "LiF"

    surface_data = surface_characterization_data(
        _lif_bulk_atoms(),
        parent_characterization=material_data,
        material="LiF_opt",
        miller=(1, 0, 0),
        termination="LiF",
        termination_top="LiF",
        termination_bottom="LiF",
    )
    surface = GeneratedSurface.from_workspace(
        SimpleNamespace(
            uid_full="slab:lif",
            id_short="s_lif",
            bulk_uid_full="bulk:lif",
            bulk_id_short="b_lif",
            material="LiF_opt",
            miller=(1, 0, 0),
            payload=current_slab_payload(
                bulk_uid_full="bulk:lif",
                miller=(1, 0, 0),
                label="LiF",
                top="LiF",
                bottom="LiF",
                atoms=_atoms_payload(_lif_bulk_atoms()),
                characterization=surface_data,
            ),
        )
    )
    assert surface.characterize().bulk_composition_compatible is True


def test_characterization_collection_views_are_clean_and_typed():
    material_data = material_characterization_data(_lif_bulk_atoms(), material="LiF_opt")
    materials = MaterialCollection(
        items=[
            {
                "id_short": "b_lif",
                "label": "LiF_opt",
                "kind": "optimized",
                "payload": {"characterization": material_data},
            }
        ]
    )
    material_rows = materials.to_rows(view="characterization")
    material_full_rows = materials.to_rows(view="characterization_all")
    assert material_rows[0]["label"] == "LiF_opt"
    assert material_full_rows[0]["composition"] == '{"F":2,"Li":2}'
    assert isinstance(materials.characterizations()[0], MaterialCharacterization)

    surface_data = surface_characterization_data(
        _lif_bulk_atoms(),
        parent_characterization=material_data,
        material="LiF_opt",
        miller=(1, 0, 0),
        termination="LiF",
        termination_top="LiF",
        termination_bottom="LiF",
    )
    surfaces = SurfaceCollection(
        items=[
            SimpleNamespace(
                uid_full="slab:lif",
                id_short="s_lif",
                bulk_uid_full="bulk:lif",
                bulk_id_short="b_lif",
                material="LiF_opt",
                miller=(1, 0, 0),
                payload=current_slab_payload(
                    bulk_uid_full="bulk:lif",
                    miller=(1, 0, 0),
                    label="LiF",
                    top="LiF",
                    bottom="LiF",
                    atoms=_atoms_payload(_lif_bulk_atoms()),
                    characterization=surface_data,
                ),
            )
        ]
    )
    surface_rows = surfaces.to_rows(view="characterization")
    surface_full_rows = surfaces.to_rows(view="characterization_all")
    assert surface_rows[0]["id_short"] == "s_lif"
    assert surface_full_rows[0]["bulk_composition_compatible"] is True
    assert isinstance(surfaces.characterizations()[0], SurfaceCharacterization)


def test_material_characterization_survives_project_reopen(tmp_path):
    pytest.importorskip("ase")
    from calm.public.project import open_project

    project_path = tmp_path / "characterization.calm"
    project = open_project(project_path)
    project.add_material(
        Material(
            name="LiF",
            label="LiF",
            atoms=_lif_bulk_atoms(),
            formula="Li2F2",
        ),
        name="LiF",
    )

    reopened = open_project(project_path)
    characterization = reopened.material("LiF").characterize()

    assert characterization.schema == "calm.material_characterization.v1"
    assert characterization.contract_status == "complete_v1"
    assert characterization.reduced_formula == "LiF"
    assert characterization.cell_volume_A3 == 64.0
    assert reopened.materials().to_rows(view="characterization")[0][
        "mass_density_g_cm3"
    ] == characterization.mass_density_g_cm3

_MATERIAL_CHARACTERIZATION_COLUMNS = (
    "label",
    "reduced_formula",
    "spacegroup_symbol",
    "spacegroup_number",
    "lattice_a_A",
    "lattice_b_A",
    "lattice_c_A",
    "cell_volume_A3",
    "mass_density_g_cm3",
)
_SURFACE_CHARACTERIZATION_COLUMNS = (
    "id_short",
    "material",
    "miller",
    "termination",
    "termination_shift",
    "symmetric_termination",
    "reduced_formula",
    "bulk_formula_units",
    "area_A2",
    "slab_thickness_A",
    "layers",
    "n_atoms",
)


def _collections_with_characterization():
    material_data = material_characterization_data(
        _lif_bulk_atoms(),
        material="LiF_opt",
        kind="optimized",
        derived={"spacegroup": {"international": "Fm-3m", "number": 225}},
    )
    materials = MaterialCollection(
        items=[
            {
                "uid_full": "bulk:lif",
                "id_short": "b_lif",
                "label": "LiF_opt",
                "kind": "optimized",
                "payload": {
                    "atoms": _atoms_payload(_lif_bulk_atoms()),
                    "derived": {
                        "formula": "LiF",
                        "n_atoms": 4,
                        "spacegroup": {
                            "international": "Fm-3m",
                            "number": 225,
                        },
                    },
                    "characterization": material_data,
                },
            }
        ]
    )

    surface_data = surface_characterization_data(
        _lif_bulk_atoms(),
        parent_characterization=material_data,
        material="LiF_opt",
        miller=(1, 0, 0),
        termination="Li₂",
        termination_top="Li₂",
        termination_bottom="Li₂",
        termination_shift=0,
        layers=4,
    )
    surfaces = SurfaceCollection(
        items=[
            SimpleNamespace(
                uid_full="slab:lif",
                id_short="s_lif",
                bulk_uid_full="bulk:lif",
                bulk_id_short="b_lif",
                material="LiF_opt",
                miller=(1, 0, 0),
                payload=current_slab_payload(
                    bulk_uid_full="bulk:lif",
                    miller=(1, 0, 0),
                    label="Li₂",
                    top="Li₂",
                    bottom="Li₂",
                    atoms=_atoms_payload(_lif_bulk_atoms()),
                    formula=surface_data["formula"],
                    slab_thickness_A=surface_data["slab_thickness_A"],
                    vacuum_A=surface_data["vacuum_A"],
                    layers=4,
                    characterization=surface_data,
                ),
            )
        ]
    )
    return materials, surfaces


def test_material_views_own_stable_summary_and_characterization_schemas(
    tmp_path,
):
    materials, _ = _collections_with_characterization()

    assert materials.available_views() == (
        "summary",
        "characterization",
        "characterization_all",
        "all",
    )
    assert tuple(materials.to_rows()[0]) == (
        "id_short",
        "label",
        "kind",
        "formula",
        "natoms",
        "spacegroup",
    )

    rows = materials.to_rows(view="characterization")
    assert tuple(rows[0]) == _MATERIAL_CHARACTERIZATION_COLUMNS
    assert "crystal_system" not in rows[0]
    assert "volume_per_formula_unit_A3" not in rows[0]

    complete = materials.to_rows(view="characterization_all")
    assert complete[0]["crystal_system"] == "cubic"
    assert complete[0]["volume_per_formula_unit_A3"] == 32.0
    assert complete[0]["composition"] == '{"F":2,"Li":2}'

    table = materials.to_table(view="characterization")
    assert tuple(table.include or ()) == _MATERIAL_CHARACTERIZATION_COLUMNS
    assert tuple(materials.to_dataframe(view="characterization").columns) == (
        _MATERIAL_CHARACTERIZATION_COLUMNS
    )
    path = tmp_path / "materials.csv"
    materials.write_table(path, view="characterization")
    assert tuple(path.read_text(encoding="utf-8").splitlines()[0].split(",")) == (
        _MATERIAL_CHARACTERIZATION_COLUMNS
    )


def test_surface_views_own_stable_summary_and_characterization_schemas(
    tmp_path,
):
    _, surfaces = _collections_with_characterization()

    assert surfaces.available_views() == (
        "summary",
        "characterization",
        "characterization_all",
        "all",
    )
    assert tuple(surfaces.to_rows()[0]) == (
        "id_short",
        "label",
        "bulk",
        "miller",
        "termination",
        "area",
        "natoms",
    )

    rows = surfaces.to_rows(view="characterization")
    assert tuple(rows[0]) == _SURFACE_CHARACTERIZATION_COLUMNS
    assert "bulk_composition_compatible" not in rows[0]
    assert "excess_composition" not in rows[0]
    assert "vacuum_A" not in rows[0]

    complete = surfaces.to_rows(view="characterization_all")
    assert complete[0]["bulk_composition_compatible"] is True
    assert complete[0]["excess_composition"] == "{}"
    assert complete[0]["vacuum_A"] is not None

    table = surfaces.to_table(view="characterization")
    assert tuple(table.include or ()) == _SURFACE_CHARACTERIZATION_COLUMNS
    assert tuple(surfaces.to_dataframe(view="characterization").columns) == (
        _SURFACE_CHARACTERIZATION_COLUMNS
    )
    path = tmp_path / "surfaces.csv"
    surfaces.write_table(path, view="characterization")
    assert tuple(path.read_text(encoding="utf-8").splitlines()[0].split(",")) == (
        _SURFACE_CHARACTERIZATION_COLUMNS
    )


def test_empty_characterization_views_preserve_declared_headers(tmp_path):
    cases = (
        (
            MaterialCollection(items=[]),
            _MATERIAL_CHARACTERIZATION_COLUMNS,
            tmp_path / "empty-materials.csv",
        ),
        (
            SurfaceCollection(items=[]),
            _SURFACE_CHARACTERIZATION_COLUMNS,
            tmp_path / "empty-surfaces.csv",
        ),
    )

    for collection, columns, path in cases:
        assert collection.to_rows(view="characterization") == []
        dataframe_columns = tuple(
            collection.to_dataframe(view="characterization").columns
        )
        assert dataframe_columns == columns
        collection.write_table(path, view="characterization")
        assert tuple(path.read_text(encoding="utf-8").strip().split(",")) == columns


def test_surface_table_rendering_uses_ascii_without_mutating_canonical_rows(
    tmp_path,
):
    from io import StringIO

    _, surfaces = _collections_with_characterization()

    rows = surfaces.to_rows(view="characterization")
    assert rows[0]["termination"] == "Li₂"
    dataframe = surfaces.to_dataframe(view="characterization")
    assert dataframe.iloc[0]["termination"] == "Li₂"

    stream = StringIO()
    surfaces.to_table(
        view="characterization",
        file=stream,
    ).display()
    rendered = stream.getvalue()
    assert "Li2" in rendered
    assert "Li₂" not in rendered

    path = tmp_path / "ascii-surfaces.csv"
    surfaces.write_table(path, view="characterization")
    csv_text = path.read_text(encoding="utf-8")
    assert "Li2" in csv_text
    assert "Li₂" not in csv_text


def test_characterization_display_labels_fit_default_terminal_width() -> None:
    import io

    from calm.project.presentation.notebook import TableView
    from calm.public.collections.structures import MaterialCollection, SurfaceCollection
    from calm.public.collections.views import resolve_table_projection

    material_spec = next(
        spec
        for spec in MaterialCollection._view_specs
        if spec.name == "characterization"
    )
    material_projection = resolve_table_projection(
        material_spec,
        [
            {
                "label": "LiF_opt",
                "reduced_formula": "LiF",
                "spacegroup_symbol": "Fm-3m",
                "spacegroup_number": 225,
                "lattice_a_A": 4.0058,
                "lattice_b_A": 4.0058,
                "lattice_c_A": 4.0058,
                "cell_volume_A3": 64.2769,
                "mass_density_g_cm3": 2.6804,
            }
        ],
    )
    material_stream = io.StringIO()
    TableView(
        rows=material_projection.to_rows(),
        include=material_projection.columns,
        column_labels=dict(material_projection.display_labels),
        title="",
        file=material_stream,
    ).display()
    material_text = material_stream.getvalue()
    assert "…" not in material_text
    assert max(map(len, material_text.splitlines())) <= 120
    assert "spacegroup" in material_text.splitlines()[0]
    assert "density_g_cm3" in material_text.splitlines()[0]

    surface_spec = next(
        spec
        for spec in SurfaceCollection._view_specs
        if spec.name == "characterization"
    )
    surface_projection = resolve_table_projection(
        surface_spec,
        [
            {
                "id_short": "s_9a3196f1",
                "material": "Li2O_opt",
                "miller": [1, 0, 0],
                "termination": "Li2O",
                "termination_shift": 0,
                "symmetric_termination": False,
                "reduced_formula": "Li2O",
                "bulk_formula_units": 4,
                "area_A2": 10.5710,
                "slab_thickness_A": 8.0466,
                "layers": 4,
                "n_atoms": 12,
            }
        ],
    )
    surface_stream = io.StringIO()
    TableView(
        rows=surface_projection.to_rows(),
        include=surface_projection.columns,
        column_labels=dict(surface_projection.display_labels),
        title="",
        file=surface_stream,
    ).display()
    surface_text = surface_stream.getvalue()
    assert "…" not in surface_text
    assert max(map(len, surface_text.splitlines())) <= 120
    header = surface_text.splitlines()[0]
    assert "shift" in header
    assert "sym" in header
    assert "thick_A" in header
