import numpy as np
from ase.build import bulk as ase_bulk


def test_bulk_standardizes_and_stamps_current_provenance() -> None:
    """Bulk construction produces conventional and primitive current records."""

    from calm.bulk.bulk import Bulk
    from calm.bulk.provenance import get_bulk_canonicalization_transforms

    atoms = ase_bulk("Al", "fcc", a=4.05, cubic=True).copy()

    # Swap lattice vectors and flip one to exercise a noncanonical input basis.
    cell = atoms.cell.array.copy()
    cell[[0, 1]] = cell[[1, 0]]
    cell[1] *= -1.0
    atoms.set_cell(cell, scale_atoms=True)

    bulk = Bulk(uid="mat:Al", atoms=atoms)

    assert bulk.atoms is bulk.conv
    assert bulk.conv.pbc.all()
    assert bulk.prim.pbc.all()
    assert np.linalg.det(bulk.conv.cell.array) > 0.0
    assert np.linalg.det(bulk.prim.cell.array) > 0.0

    record = get_bulk_canonicalization_transforms(bulk.atoms)
    assert record is not None
    assert record.schema_version == 3
    assert record.conventional_relation_verified is True
    assert record.primitive_relation_verified is True
    assert record.transformation_matrix_input_from_standardized is not None
    assert record.origin_shift_standardized_frac is not None
    assert record.rigid_rotation_standardized_cart is not None
    assert record.angle_tolerance == -1.0
    assert record.spglib_version.strip()
