#!/usr/bin/env python3
"""Interfacial energy computations and helpers.

This module implements interface excess-energy computations and helpers. The
strained-bulk subtraction implemented here is an **interface excess energy**,
not a work of adhesion. Its normalization is

    gamma_sb = (E_interface - n_A * mu_A - n_B * mu_B)
               / (N_interfaces * Area)

where ``N_interfaces`` is an explicit positive periodic-interface multiplicity.
"""

import itertools
import math
from dataclasses import dataclass
from numbers import Integral

import numpy as np
import scipy.spatial as spatial

from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2 as _EV_PER_A2_TO_J_PER_M2,
    INTERFACE_EXCESS_ENERGY_QUANTITY,
    INTERFACE_EXCESS_REFERENCE_CONVENTION,
    INTERFACE_EXCESS_STRAINED_BULK_FORMULA,
    positive_interface_multiplicity,
)
from calm.interface.results import InterfaceEnergyScalarResult


def compute_interface_energy_from_scalars(  # noqa: C901
    *,
    interface_energy_eV: float,
    n_formula_units_A: float,
    n_formula_units_B: float,
    mu_A_eV_per_formula_unit: float,
    mu_B_eV_per_formula_unit: float,
    interface_area_A2: float,
    n_interfaces: int,
    strained_bulk_reference_mode: str = "unrelaxed_scaled_positions",
    bulk_reference_relaxed: bool = False,
    gamma_reference_convention: str = INTERFACE_EXCESS_REFERENCE_CONVENTION,
) -> InterfaceEnergyScalarResult:
    r"""Compute strained-bulk interface excess from known scalar quantities.

    This helper evaluates the arithmetic relation

    .. math::

        \gamma = \frac{E_{A|B} - N_A \mu_A - N_B \mu_B}{n_{\mathrm{interfaces}} A}

    where:

    - ``E_{A|B}`` is the total interface-cell energy in eV,
    - ``N_A`` and ``N_B`` are formula-unit counts for the two materials,
    - ``mu_A`` and ``mu_B`` are strained-bulk reference energies per formula unit in eV,
    - ``A`` is the single-interface area in Å²,
    - ``n_interfaces`` is the number of equivalent interfaces contributing to the denominator.

    Parameters
    ----------
    interface_energy_eV
        Total interface-cell energy in eV.
    n_formula_units_A, n_formula_units_B
        Formula-unit counts for materials A and B. These must be non-negative.
    mu_A_eV_per_formula_unit, mu_B_eV_per_formula_unit
        Strained-bulk reference energies per formula unit in eV.
    interface_area_A2
        Single-interface area in Å². Must be strictly positive.
    n_interfaces
        Exact positive number of interfaces represented in the denominator.
        This argument is required because periodic-interface multiplicity is a
        property of the modeled cell, not an inference made by the helper.
    strained_bulk_reference_mode
        Descriptive provenance string for the strained-bulk reference convention.
        The current default convention is ``"unrelaxed_scaled_positions"``.
    bulk_reference_relaxed
        Whether the strained-bulk references were relaxed. The current default is ``False``.
    gamma_reference_convention
        Descriptive provenance string for the subtraction convention. The
        current default is ``"strained_unrelaxed_bulk_subtraction"``.

    Returns
    -------
    InterfaceEnergyScalarResult
        Result containing numerator, denominator, gamma in eV/Å² and J/m²,
        plus the original scalar inputs and convention metadata.

    Notes
    -----
    This helper performs **arithmetic only**. It does not generate strained bulk
    references, build an interface structure, attach a calculator, or relax any
    atomic positions. Use :func:`calm.interface.compute_interfacial_energy` for
    the current geometry + calculator-backed workflow.
    """

    finite_inputs = {
        "interface_energy_eV": interface_energy_eV,
        "mu_A_eV_per_formula_unit": mu_A_eV_per_formula_unit,
        "mu_B_eV_per_formula_unit": mu_B_eV_per_formula_unit,
        "interface_area_A2": interface_area_A2,
    }
    normalized: dict[str, float] = {}
    for name, value in finite_inputs.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite; got {value!r}") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite; got {value!r}")
        normalized[name] = number

    if normalized["interface_area_A2"] <= 0:
        raise ValueError(f"interface_area_A2 must be > 0; got {interface_area_A2!r}")
    try:
        interface_multiplicity = positive_interface_multiplicity(n_interfaces)
    except ValueError as exc:
        raise ValueError(f"n_interfaces must be > 0; got {n_interfaces!r}") from exc

    formula_counts: dict[str, int] = {}
    for name, value in (
        ("n_formula_units_A", n_formula_units_A),
        ("n_formula_units_B", n_formula_units_B),
    ):
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be a non-negative integer; got {value!r}")
        count = int(value)
        if count < 0:
            raise ValueError(f"{name} must be >= 0; got {value!r}")
        formula_counts[name] = count

    denominator_A2 = normalized["interface_area_A2"] * interface_multiplicity
    if not math.isfinite(denominator_A2):
        raise ValueError("The interface normalization denominator must be finite.")
    numerator_eV = (
        normalized["interface_energy_eV"]
        - formula_counts["n_formula_units_A"] * normalized["mu_A_eV_per_formula_unit"]
        - formula_counts["n_formula_units_B"] * normalized["mu_B_eV_per_formula_unit"]
    )
    if not math.isfinite(numerator_eV):
        raise ValueError("The interface-energy numerator must be finite.")
    gamma_eV_per_A2 = numerator_eV / denominator_A2
    gamma_J_per_m2 = gamma_eV_per_A2 * _EV_PER_A2_TO_J_PER_M2
    if not math.isfinite(gamma_eV_per_A2) or not math.isfinite(gamma_J_per_m2):
        raise ValueError("The derived interface-energy density must be finite.")

    return InterfaceEnergyScalarResult(
        numerator_eV=float(numerator_eV),
        denominator_A2=float(denominator_A2),
        gamma_eV_per_A2=float(gamma_eV_per_A2),
        gamma_J_per_m2=float(gamma_J_per_m2),
        interface_energy_eV=normalized["interface_energy_eV"],
        n_formula_units_A=float(formula_counts["n_formula_units_A"]),
        n_formula_units_B=float(formula_counts["n_formula_units_B"]),
        mu_A_eV_per_formula_unit=normalized["mu_A_eV_per_formula_unit"],
        mu_B_eV_per_formula_unit=normalized["mu_B_eV_per_formula_unit"],
        interface_area_A2=normalized["interface_area_A2"],
        n_interfaces=interface_multiplicity,
        thermodynamic_formula=INTERFACE_EXCESS_STRAINED_BULK_FORMULA,
        thermodynamic_quantity=INTERFACE_EXCESS_ENERGY_QUANTITY,
        strained_bulk_reference_mode=str(strained_bulk_reference_mode),
        bulk_reference_relaxed=bool(bulk_reference_relaxed),
        gamma_reference_convention=str(gamma_reference_convention),
    )


@dataclass(frozen=True)
class StrainedBulkDeformation:
    """Composed deformation used to construct one bulk reference."""

    F_construction_slab: np.ndarray
    F_interface_slab: np.ndarray
    F_total_slab: np.ndarray
    F_construction_conv: np.ndarray
    F_interface_conv: np.ndarray
    F_total_conv: np.ndarray
    slab_to_conv_map: np.ndarray


def _strained_bulk_deformation(
    unstrained_slab,
    super_slab_atoms,
    F,
    *,
    gauge_rotation=None,
    config=None,
) -> StrainedBulkDeformation:
    """Resolve construction, interface, and total deformation consistently."""

    from calm.slab.oriented.cell_contract import (
        compose_slab_deformations,
        require_interface_stackable_slab,
        slab_to_conventional_map,
    )

    source_atoms = getattr(unstrained_slab, "atoms", None)
    if source_atoms is not None:
        require_interface_stackable_slab(
            source_atoms,
            name="Strained-bulk source slab",
        )
        composition = compose_slab_deformations(
            source_atoms,
            F,
            gauge_rotation=gauge_rotation,
            name="Strained-bulk source slab",
        )
        Q = slab_to_conventional_map(
            source_atoms,
            gauge_rotation=gauge_rotation,
            name="Strained-bulk source slab",
        )
    else:
        composition = compose_slab_deformations(
            None,
            F,
            gauge_rotation=gauge_rotation,
            name="Strained-bulk source slab",
        )
        Q = None

    strict = True
    warn = True
    check = True
    tol = 1e-8
    if config is not None:
        strict = bool(getattr(config, "strict_reference_frame", True))
        warn = bool(getattr(config, "warn_on_reference_frame_fallback", True))
        check = bool(getattr(config, "reference_frame_check", True))
        tol = float(getattr(config, "reference_frame_tol", 1e-8))

    if Q is None:
        frame_atoms = super_slab_atoms
        if gauge_rotation is not None:
            from calm.interface.building._geometry import _rotate_atoms_cartesian

            frame_atoms = super_slab_atoms.copy()
            _rotate_atoms_cartesian(
                frame_atoms,
                np.asarray(gauge_rotation, dtype=float),
            )
        Q = get_ortho_map(
            unstrained_slab,
            frame_atoms,
            strict=strict,
            warn=warn,
            check=check,
            tol=tol,
        )
    Q = np.asarray(Q, dtype=float)
    F_construction_conv = Q @ composition.F_construction @ Q.T
    F_interface_conv = Q @ composition.F_interface @ Q.T
    F_total_conv = Q @ composition.F_total @ Q.T
    return StrainedBulkDeformation(
        F_construction_slab=composition.F_construction,
        F_interface_slab=composition.F_interface,
        F_total_slab=composition.F_total,
        F_construction_conv=F_construction_conv,
        F_interface_conv=F_interface_conv,
        F_total_conv=F_total_conv,
        slab_to_conv_map=Q,
    )


def get_strained_bulk(
    unstrained_slab,
    super_slab_atoms,
    F,
    *,
    gauge_rotation=None,
    config=None,
):
    """Return a conventional bulk cell carrying the total source deformation.

    ``F`` is the interface-matching deformation in the post-gauge slab frame.
    Any physical construction shear recorded on the source slab is rotated into
    that frame and composed before the total deformation is mapped back to the
    conventional-cell frame.
    """

    deformation = _strained_bulk_deformation(
        unstrained_slab,
        super_slab_atoms,
        F,
        gauge_rotation=gauge_rotation,
        config=config,
    )

    conv = unstrained_slab.bulk.conv
    A = unstrained_slab.bulk.conv_cell
    A_strained = deformation.F_total_conv @ A
    strained_bulk = conv.copy()
    strained_bulk.set_cell(A_strained.T, scale_atoms=True)
    return strained_bulk


def in_plane_uvw(hkl, max_index=6, prefer_nonzero_w=True):  # noqa: C901
    """
    Return an acceptable in-plane crystallographic direction [u v w] for a plane (h k l),
    i.e. an integer triplet (u,v,w) != (0,0,0) satisfying the zone law:
        h*u + k*v + l*w = 0.

    The function searches small integers and returns a "simple" (small-norm) solution.

    Parameters
    ----------
    hkl : iterable of 3 ints
        Miller index (h,k,l).
    max_index : int
        Search range for u,v,w in [-max_index, ..., max_index].
    prefer_nonzero_w : bool
        If True, slightly prefer solutions with w != 0 when norms tie (helps avoid
        returning trivial in-plane directions in some settings).

    Returns
    -------
    uvw : tuple[int,int,int]
        A reduced integer direction (u,v,w) with gcd(|u|,|v|,|w|)=1.
    """
    # Normalize Miller indices to an integer triple for clarity and consistency.
    hkl = tuple(int(x) for x in hkl)
    h, k, l = hkl  # noqa: E741 - canonical Miller index triple (h,k,l)
    if (h, k, l) == (0, 0, 0):
        raise ValueError("hkl cannot be (0,0,0).")

    best = None
    best_key = None

    rng = range(-max_index, max_index + 1)
    for u, v, w in itertools.product(rng, rng, rng):
        if (u, v, w) == (0, 0, 0):
            continue
        if h * u + k * v + l * w != 0:
            continue

        # Reduce by gcd so [2, -2, 0] -> [1, -1, 0]
        g = math.gcd(abs(u), math.gcd(abs(v), abs(w)))
        uu, vv, ww = u // g, v // g, w // g

        # Deterministic sign convention: make first nonzero positive
        for t in (uu, vv, ww):
            if t != 0:
                if t < 0:
                    uu, vv, ww = -uu, -vv, -ww
                break

        # Rank candidates by small Euclidean norm in index space, then lexicographically
        norm2 = uu * uu + vv * vv + ww * ww
        tie_w = 0 if (prefer_nonzero_w and ww != 0) else 1
        key = (norm2, tie_w, abs(uu) + abs(vv) + abs(ww), uu, vv, ww)

        if best_key is None or key < best_key:
            best_key = key
            best = (uu, vv, ww)

    if best is None:
        raise RuntimeError(
            f"No in-plane [uvw] found for (hkl)={hkl} within |u,v,w|<= {max_index}. "
            "Increase max_index."
        )

    return best


def get_prim_in_slab(  # noqa: C901
    slab,
    P_C: np.ndarray,
    n_hat_c: np.ndarray,
    *,
    rtol: float = 1e-8,
    atol: float = 1e-12,
    max_origins: int = 20,
    dist_tol: float = 1e-7,
    det_tol: float | None = None,
) -> np.ndarray | None:
    """Recover a right-handed primitive basis embedded in a pristine slab.

    Finds a 3x3 basis T = [t0 t1 t2] (columns) made of actual displacement vectors
    from a single origin atom such that:

      (1) T^T T ≈ G, where G = P_C^T P_C
      (2) T @ n_c ≈ [0,0,1]^T, where n_c solves P_C @ n_c = n_hat_c
      (3) det(T) > 0 (right-handed), and det(T) is not near-zero (conditioning guard)

    Parameters
    ----------
    slab
        ASE Atoms-like object providing get_positions().
    P_C
        (3,3) primitive basis in Cartesian coordinates (columns are vectors).
    n_hat_c
        (3,) unit surface normal in the same Cartesian frame as P_C.
    rtol, atol
        Relative/absolute tolerances for dot products and squared norms (units Å²).
        Defaults are set for pristine, lattice-derived structures.
    max_origins
        Number of origin atoms to try.
    dist_tol
        KD-tree distance tolerance (units Å) for snapping the solved vector to an
        actual displacement. Defaults for pristine structures.
    det_tol
        Minimum determinant threshold (units Å³). If None, a scale-aware default is used.

    Returns
    -------
    np.ndarray | None
        (3,3) basis T with columns [t0, t1, t2], or None if not found.
    """
    pos = np.asarray(slab.get_positions(), dtype=float)
    if pos.ndim != 2 or pos.shape[1] != 3:
        raise ValueError(
            "get_prim_in_slab: slab.get_positions() must return an (N,3) array"
        )
    N = pos.shape[0]
    if N < 4:
        return None

    P_C = np.asarray(P_C, dtype=float)
    if P_C.shape != (3, 3):
        raise ValueError("get_prim_in_slab: P_C must be (3,3)")

    n_hat_c = np.asarray(n_hat_c, dtype=float).reshape(
        3,
    )
    n_norm = float(np.linalg.norm(n_hat_c))
    if not np.isfinite(n_norm) or n_norm == 0.0:
        raise ValueError("get_prim_in_slab: n_hat_c must be finite and nonzero")
    if abs(n_norm - 1.0) > 1e-10:
        raise ValueError(
            f"get_prim_in_slab: expected unit normal; ||n_hat_c||={n_norm:.16e}"
        )

    n_hat_s = np.array([0.0, 0.0, 1.0], dtype=float)
    n_c = np.linalg.solve(P_C, n_hat_c)

    G = P_C.T @ P_C
    G = 0.5 * (G + G.T)

    if det_tol is None:
        det_scale = float(
            np.sqrt(max(G[0, 0], 0.0) * max(G[1, 1], 0.0) * max(G[2, 2], 0.0))
        )
        det_tol = 1e-14 * det_scale

    def close(x: float, y: float) -> bool:
        return abs(x - y) <= (atol + rtol * abs(y))

    # Solve index choice: maximize |n_c[k]| for numerical stability
    k = int(np.argmax(np.abs(n_c)))
    nk = float(n_c[k])
    if abs(nk) < 1e-14:
        return None
    a, b = [c for c in (0, 1, 2) if c != k]
    na = float(n_c[a])
    nb = float(n_c[b])

    # Try a few origins
    for origin in range(min(N, max_origins)):
        # Build displacement array D excluding origin
        idx = np.arange(N) != origin
        D = pos[idx] - pos[origin]
        if D.shape[0] < 3:
            continue

        tree = spatial.cKDTree(D)  # type: ignore[attr-defined]
        D2 = np.einsum("ij,ij->i", D, D)

        # Candidate indices by squared norm (Å²)
        cand = []
        for col in (0, 1, 2):
            target = float(G[col, col])
            sel = np.abs(D2 - target) <= (atol + rtol * abs(target))
            cand.append(np.nonzero(sel)[0])

        idx_a, idx_b = cand[a], cand[b]
        if idx_a.size == 0 or idx_b.size == 0:
            continue

        # Pre-pull all b-candidates once for vectorized dot tests
        Tb = D[idx_b]
        target_ab = float(G[a, b])
        tol_ab = atol + rtol * abs(target_ab)

        for ia in idx_a:
            ta = D[int(ia)]

            # Vectorized dot constraint for tb
            dots = Tb @ ta
            ok = np.abs(dots - target_ab) <= tol_ab
            if not np.any(ok):
                continue

            for ib in idx_b[ok]:
                ib = int(ib)
                if ib == ia:
                    continue
                tb = D[ib]

                # Solve tk from normal constraint
                tk = (n_hat_s - na * ta - nb * tb) / nk

                # Metric checks (pre-snap)
                if not close(float(tk @ tk), float(G[k, k])):
                    continue
                if not close(float(ta @ tk), float(G[a, k])):
                    continue
                if not close(float(tb @ tk), float(G[b, k])):
                    continue

                # Snap and re-check with the actual displacement vector
                dist, ik = tree.query(tk, k=1)
                if dist > dist_tol:
                    continue
                ik = int(ik)
                if ik == ia or ik == ib:
                    continue
                tk = D[ik]

                if not close(float(tk @ tk), float(G[k, k])):
                    continue
                if not close(float(ta @ tk), float(G[a, k])):
                    continue
                if not close(float(tb @ tk), float(G[b, k])):
                    continue

                if k == 0:
                    t0, t1, t2 = tk, ta, tb
                elif k == 1:
                    t0, t1, t2 = ta, tk, tb
                else:
                    t0, t1, t2 = ta, tb, tk

                T = np.column_stack((t0, t1, t2))
                detT = float(np.linalg.det(T))

                detT = float(t0 @ np.cross(t1, t2))
                if detT <= det_tol:
                    continue

                return np.column_stack([t0, t1, t2])

    return None


def get_ortho_map(  # noqa: C901
    unstrained_slab,
    super_slab_atoms,
    *,
    strict=True,
    warn=True,
    check=True,
    tol=1e-8,
):
    """
    Return an orthogonal map Q from slab-frame orthonormal basis vectors (S)
    to conventional-cell orthonormal basis vectors (C).

    Intended semantics
    ------------------
    - Prefer a crystallographically aligned slab-frame basis using get_prim_in_slab(...)
      so that in-plane directions correspond to a chosen [u v w] direction.
    - If that primitive-basis identification fails:
        * non-strict mode: warn (optional) and fall back to a cell-vector basis
        * strict mode: raise ReferenceFrameError

    Guardrails
    ----------
    - If check=True, validate Q is a proper rotation (orthogonal, det ~ +1, finite).
    """

    import warnings

    import numpy as np

    from calm.exceptions import ReferenceFrameError, ReferenceFrameFallbackWarning

    # -- Extract bulk cells and Miller index from slab
    hkl = unstrained_slab.hkl

    # -- Lattice vectors
    A = unstrained_slab.bulk.conv_cell
    B = np.linalg.inv(A).T  # reciprocal lattice
    P_C = unstrained_slab.bulk.prim_cell
    P_C_inv = np.linalg.inv(P_C)

    # Slab (supercell) vectors (columns)
    S = super_slab_atoms.cell.array.T

    # -- Plane normal in conventional frame
    n_hat_c = B @ np.array(hkl, dtype=float)
    n_norm = np.linalg.norm(n_hat_c)
    if n_norm < tol:
        raise ReferenceFrameError(f"get_ortho_map: invalid plane normal for hkl={hkl}")
    n_hat_c = n_hat_c / n_norm

    # -- Slab normal in slab frame: prefer geometric normal from in-plane cell vectors
    n_hat_s = np.cross(S[:, 0], S[:, 1])
    ns_norm = np.linalg.norm(n_hat_s)
    if not np.isfinite(ns_norm) or ns_norm < tol:
        raise ReferenceFrameError(
            "get_ortho_map: slab in-plane vectors do not define a finite normal."
        )
    n_hat_s = n_hat_s / ns_norm

    # -- Conventional orthonormal basis aligned with an in-plane crystallographic direction
    uvw = in_plane_uvw(hkl, max_index=6, prefer_nonzero_w=True)
    t1_c = A @ uvw
    t1n = np.linalg.norm(t1_c)
    if t1n < tol:
        raise ReferenceFrameError(
            f"get_ortho_map: failed to build in-plane direction for hkl={hkl}"
        )
    t1_hat_c = t1_c / t1n

    t2_c = np.cross(n_hat_c, t1_hat_c)
    t2n = np.linalg.norm(t2_c)
    if t2n < tol:
        raise ReferenceFrameError(
            f"get_ortho_map: degenerate in-plane basis for hkl={hkl}"
        )
    t2_hat_c = t2_c / t2n

    E_c = np.column_stack([t1_hat_c, t2_hat_c, n_hat_c])

    # -- Preferred method: map the same in-plane direction into slab frame using primitive bases
    method = "primitive_basis"
    P_S = get_prim_in_slab(super_slab_atoms, P_C, n_hat_c)
    P_S_arr = None if P_S is None else np.asarray(P_S, dtype=float)
    if P_S_arr is not None and P_S_arr.shape != (3, 3):
        raise ReferenceFrameError(
            "get_ortho_map: recovered primitive basis must have shape (3, 3)."
        )

    if P_S_arr is None:
        method = "cell_vector_fallback"
        if strict:
            raise ReferenceFrameError(
                "get_ortho_map: primitive basis in slab frame not found; "
                "strict_reference_frame=True forbids fallback."
            )
        if warn:
            warnings.warn(
                "get_ortho_map: falling back to slab cell-vector basis (primitive basis not found). "
                "This may affect strained-bulk reference correctness for anisotropic materials. "
                "Set EnergyConfig.strict_reference_frame=True to raise instead.",
                ReferenceFrameFallbackWarning,
                stacklevel=2,
            )

        # Fallback slab-frame basis from in-plane cell vectors (Gram-Schmidt)
        v1 = S[:, 0]
        v2 = S[:, 1]

        e1 = v1 / np.linalg.norm(v1)
        v2p = v2 - np.dot(e1, v2) * e1
        if np.linalg.norm(v2p) < tol:
            # Extremely rare degeneracy: pick an in-plane vector perpendicular to e1
            v2p = np.cross(n_hat_s, e1)
        e2 = v2p / np.linalg.norm(v2p)

        # Ensure right-handed with slab normal
        e3 = np.cross(e1, e2)
        e3n = np.linalg.norm(e3)
        if e3n < tol:
            raise ReferenceFrameError(
                "get_ortho_map: degenerate fallback basis (cannot form normal)"
            )
        e3 = e3 / e3n

        if np.dot(e3, n_hat_s) < 0.0:
            e2 = -e2
            e3 = -e3

        E_s = np.column_stack([e1, e2, e3])

    else:
        # Preferred slab-frame basis aligned to the same crystallographic in-plane direction
        x = P_C_inv @ t1_c
        t1_s = P_S_arr @ x
        t1n = np.linalg.norm(t1_s)
        if t1n < tol:
            raise ReferenceFrameError(
                "get_ortho_map: primitive-based slab in-plane direction is degenerate"
            )
        t1_hat_s = t1_s / t1n

        t2_s = np.cross(n_hat_s, t1_hat_s)
        t2n = np.linalg.norm(t2_s)
        if t2n < tol:
            raise ReferenceFrameError(
                "get_ortho_map: primitive-based slab basis is degenerate"
            )
        t2_hat_s = t2_s / t2n

        # Right-handed triad
        e3 = np.cross(t1_hat_s, t2_hat_s)
        e3n = np.linalg.norm(e3)
        if e3n < tol:
            raise ReferenceFrameError(
                "get_ortho_map: failed to form right-handed slab triad"
            )
        e3 = e3 / e3n

        if np.dot(e3, n_hat_s) < 0.0:
            t2_hat_s = -t2_hat_s
            e3 = -e3

        E_s = np.column_stack([t1_hat_s, t2_hat_s, e3])

    # Q maps slab basis to conventional basis
    Q = E_c @ E_s.T

    if check:
        if not np.all(np.isfinite(Q)):
            raise ReferenceFrameError(
                f"get_ortho_map: non-finite values in Q (method={method})"
            )

        I_mat = np.eye(3)
        ortho_err = np.max(np.abs(Q.T @ Q - I_mat))
        if ortho_err > 10.0 * tol:
            raise ReferenceFrameError(
                f"get_ortho_map: Q not orthogonal within tolerance (err={ortho_err:.3e}, tol={tol:.3e}, method={method})"
            )

        detQ = float(np.linalg.det(Q))
        if abs(detQ - 1.0) > 10.0 * tol:
            raise ReferenceFrameError(
                f"get_ortho_map: det(Q) not ~ +1 (det={detQ:.6f}, tol={tol:.3e}, method={method})"
            )

    return Q
