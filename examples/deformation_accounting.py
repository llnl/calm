"""Work through CALM's deformation-accounting conventions numerically.

Run from the repository root:

    python examples/deformation_accounting.py

The example uses only NumPy. It distinguishes a rigid gauge rotation, a
physical construction shear, an incremental interface-matching deformation,
and a later cell-relaxation deformation. It also verifies the transpose needed
when the same maps are applied to ASE row-oriented cell arrays.
"""

from __future__ import annotations

from typing import Final

import numpy as np


PRINT_PRECISION: Final = 6


def rotation_about_z(angle_degrees: float) -> np.ndarray:
    """Return a proper Cartesian rotation about global z."""

    angle = np.deg2rad(float(angle_degrees))
    cosine = float(np.cos(angle))
    sine = float(np.sin(angle))
    return np.array(
        [
            [cosine, -sine, 0.0],
            [sine, cosine, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def principal_hencky_percent(deformation: np.ndarray) -> np.ndarray:
    """Return ordered principal logarithmic strains in percent."""

    matrix = np.asarray(deformation, dtype=float)
    right_cauchy_green = matrix.T @ matrix
    squared_stretches = np.linalg.eigvalsh(right_cauchy_green)
    return 0.5 * np.log(squared_stretches) * 100.0


def deformation_example() -> dict[str, np.ndarray | float]:
    """Construct and verify one complete deformation-accounting chain."""

    # --8<-- [start:deformation-accounting-inputs]
    # Mathematical convention: lattice vectors are columns.
    pristine_cell = np.array(
        [
            [3.00, 0.00, 0.60],
            [0.00, 3.00, -0.36],
            [0.00, 0.00, 12.00],
        ],
        dtype=float,
    )

    # Physical shear that removes the lateral component of c by deforming the
    # complete material, not merely by changing the boundary vector.
    construction_source = np.array(
        [
            [1.00, 0.00, -0.05],
            [0.00, 1.00, 0.03],
            [0.00, 0.00, 1.00],
        ],
        dtype=float,
    )

    gauge = rotation_about_z(30.0)

    # Incremental deformation needed to place this side in the common
    # interface cell after the gauge has been selected.
    interface_increment = np.array(
        [
            [1.030, 0.008, 0.0],
            [0.005, 0.975, 0.0],
            [0.000, 0.000, 1.0],
        ],
        dtype=float,
    )

    # Cell change measured after variable-cell relaxation.
    relaxation = np.array(
        [
            [0.996, -0.004, 0.0],
            [0.003, 1.006, 0.0],
            [0.000, 0.000, 1.0],
        ],
        dtype=float,
    )
    # --8<-- [end:deformation-accounting-inputs]

    # --8<-- [start:deformation-accounting-composition]
    construction_gauge = gauge @ construction_source @ gauge.T
    total_pre_relaxation = interface_increment @ construction_gauge
    total_post_relaxation = relaxation @ total_pre_relaxation

    gauged_pristine_cell = gauge @ pristine_cell
    final_cell = total_post_relaxation @ gauged_pristine_cell

    # ASE stores the same cell vectors as rows. The corresponding row-array
    # update is therefore C_final = C_initial @ F.T.
    ase_gauged_pristine_cell = gauged_pristine_cell.T
    ase_final_cell = ase_gauged_pristine_cell @ total_post_relaxation.T
    # --8<-- [end:deformation-accounting-composition]

    orthogonalized_source = construction_source @ pristine_cell
    expected_orthogonal = np.diag([3.0, 3.0, 12.0])

    if not np.allclose(orthogonalized_source, expected_orthogonal, atol=1e-12):
        raise RuntimeError("The construction shear did not remove the c tilt.")
    if not np.allclose(
        construction_gauge @ gauged_pristine_cell,
        gauge @ orthogonalized_source,
        atol=1e-12,
    ):
        raise RuntimeError("Gauge conjugation changed the physical construction map.")
    if not np.allclose(ase_final_cell, final_cell.T, atol=1e-12):
        raise RuntimeError("Column and ASE row cell conventions disagree.")

    reversed_order = construction_gauge @ interface_increment

    return {
        "pristine_cell": pristine_cell,
        "gauge": gauge,
        "construction_source": construction_source,
        "construction_gauge": construction_gauge,
        "interface_increment": interface_increment,
        "total_pre_relaxation": total_pre_relaxation,
        "relaxation": relaxation,
        "total_post_relaxation": total_post_relaxation,
        "final_cell": final_cell,
        "composition_order_difference": float(
            np.linalg.norm(total_pre_relaxation - reversed_order)
        ),
    }


def _format_matrix(value: np.ndarray) -> str:
    return np.array2string(
        np.asarray(value, dtype=float),
        precision=PRINT_PRECISION,
        suppress_small=True,
    )


def main() -> None:
    """Print the example matrices and their principal strain diagnostics."""

    result = deformation_example()
    ordered = (
        ("construction in matching gauge", "construction_gauge"),
        ("incremental interface matching", "interface_increment"),
        ("total before relaxation", "total_pre_relaxation"),
        ("relaxation cell change", "relaxation"),
        ("total after relaxation", "total_post_relaxation"),
    )

    print("CALM deformation-accounting example")
    for label, key in ordered:
        matrix = np.asarray(result[key], dtype=float)
        strains = principal_hencky_percent(matrix)
        print(f"\n{label}")
        print(_format_matrix(matrix))
        print(f"determinant: {np.linalg.det(matrix):.9f}")
        print(
            "principal Hencky strain (%): "
            + np.array2string(strains, precision=4, suppress_small=True)
        )

    print("\nfinal column-oriented cell")
    print(_format_matrix(np.asarray(result["final_cell"], dtype=float)))
    print(
        "composition-order difference: "
        f"{result['composition_order_difference']:.9e}"
    )
    print("ASE row-cell transpose check: passed")


if __name__ == "__main__":
    main()
