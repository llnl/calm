"""benchmarks.run_slabgen

Run the external legacy SlabGen matcher on benchmark 2D lattice pairs.

This script builds *dummy* ASE slabs whose in-plane cell matches the specified
2D lattice basis. This avoids any dependence on real surface terminations while
exercising the same code paths used in the real workflow:

- right-HNF enumeration
- deterministic canonical 2D Gauss reduction
- (optional) point-group orbit-key deduplication
- affine-invariant metric screening (principal Hencky strains)
- mismatch–size scalarization and Pareto-style outputs

Usage
-----
python -m benchmarks.benchmarks.run_slabgen --out results_slabgen.csv

Requirements
------------
- the legacy `slabgen` distribution
- ase

For current CALM qualification, use `python -m benchmarks.run_coupled_qualification`.

Notes
-----
- The dummy slabs use a maximally symmetric motif (single atom at the origin).
  This is sufficient for the lattice-matching routines; symmetry details depend
  on your slabgen configuration.

"""

from __future__ import annotations

import argparse
import time
import importlib.metadata as importlib_metadata
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .benchmark_pairs import default_benchmark_pairs, basis_area
from .common_metrics import size_proxy_d_size, scalar_score, zm_diagnostics, zm_diagnostics_extended, airm_distance_and_strains
from .signature import match_signature, canonicalize_2d


@dataclass
class DummySlab:
    """Minimal slab-like wrapper expected by external SlabGen enumeration."""

    atoms: Any

    @property
    def n_atoms(self) -> int:
        return int(len(self.atoms))


def _main_pkg_version() -> Tuple[str, str]:
    """Return the external legacy SlabGen method name and version."""

    try:
        return "slabgen", importlib_metadata.version("slabgen")
    except Exception:
        return "slabgen", "unknown"


def _dummy_slab_from_basis(
    S2: np.ndarray,
    *,
    symbol: str = "H",
    n_atoms: int = 1,
    Lz: float = 25.0,
) -> DummySlab:
    """Create a dummy ASE Atoms object whose in-plane cell vectors equal S2."""

    try:
        from ase import Atoms  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ASE is required for slabgen benchmarks. Install ase and re-run.") from exc

    S2 = np.asarray(S2, dtype=float)
    if S2.shape != (2, 2):
        raise ValueError("S2 must be (2,2)")

    # ASE convention: lattice vectors are stored as ROWS.
    cell = np.zeros((3, 3), dtype=float)
    cell[0, :2] = S2[:, 0]
    cell[1, :2] = S2[:, 1]
    cell[2, 2] = float(Lz)

    positions = np.zeros((int(n_atoms), 3), dtype=float)
    symbols = [symbol] * int(n_atoms)

    atoms = Atoms(symbols=symbols, positions=positions, cell=cell, pbc=True)
    return DummySlab(atoms=atoms)


def _kmax_from_max_area(max_area: float, prim_area: float) -> int:
    if (not np.isfinite(prim_area)) or prim_area <= 0:
        return 1
    return max(1, int(np.floor(float(max_area) / float(prim_area) + 1e-12)))


def run_slabgen_for_pair(
    *,
    pair_name: str,
    A2: np.ndarray,
    B2: np.ndarray,
    max_area: float,
    cond_max: float,
    eps_area: float = 0.3,
    tau_max: Optional[float] = None,
    eps_principal_max: float,
    dedupe_by_key: bool = True,
    niggli_tol: float,
    nA_prim: int,
    nB_prim: int,
    N_at_max: int,
    w_match: float,
    sig_tol: float,
    sig_scale: float,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """Run the external legacy SlabGen matcher for one benchmark pair.

    Notes
    -----
    CALM's pairing gate is a symmetric log-area band ``|log(A_A/A_B)| <= eps_area``.
    In the manuscript and figure scripts we often denote this tolerance as ``tau_max``.
    To keep the benchmark harness ergonomic (and to avoid parameter-name drift across
    scripts), ``tau_max`` is accepted as an alias that overrides ``eps_area`` when
    provided.
    """

    try:
        from slabgen.interface.matching import enumerate_matches  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "The legacy slabgen distribution is required for this historical "
            "comparison benchmark. Use benchmarks.run_coupled_qualification "
            "for current CALM results."
        ) from exc

    slabA = _dummy_slab_from_basis(A2)
    slabB = _dummy_slab_from_basis(B2)

    areaA_prim = float(basis_area(A2))
    areaB_prim = float(basis_area(B2))

    kA_max = _kmax_from_max_area(max_area, areaA_prim)
    kB_max = _kmax_from_max_area(max_area, areaB_prim)
    k_max = max(kA_max, kB_max)

    niggli_kwargs = {"tol": float(niggli_tol)}

    # Compatibility: some figure scripts and paper text use tau_max to denote
    # the symmetric log-area-ratio tolerance |log(A_A/A_B)| <= tau_max.  CALM's
    # matcher uses the same quantity but names it eps_area.
    if tau_max is not None:
        eps_area = float(tau_max)

    t0 = time.perf_counter()
    matches = enumerate_matches(
        slabA,
        slabB,
        k_max=int(k_max),
        cond_max=float(cond_max),
        eps_area=float(eps_area),
        eps_principal_max=float(eps_principal_max),
        w_match=float(w_match),
        N_at_max=int(N_at_max),
        dedupe_by_key=bool(dedupe_by_key),
        niggli_kwargs=niggli_kwargs,
    )
    t1 = time.perf_counter()

    method_name, method_version = _main_pkg_version()

    rows: List[Dict[str, Any]] = []

    for cand in matches:
        scA = cand.reduced_A
        scB = cand.reduced_B

        SA = np.array(scA.S_red, dtype=float)
        SB = np.array(scB.S_red, dtype=float)
        # Ensure a deterministic gauge before computing any metrics
        SA, _, _ = canonicalize_2d(SA)
        SB, _, _ = canonicalize_2d(SB)

        # Enforce max_area on both sides.
        areaA = float(abs(np.linalg.det(SA)))
        areaB = float(abs(np.linalg.det(SB)))
        if areaA > max_area + 1e-12 or areaB > max_area + 1e-12:
            continue

        kA = int(scA.k)
        kB = int(scB.k)

        # Compute metrics in the same harness code path used for pymatgen output.
        GA = SA.T @ SA
        GB = SB.T @ SB
        d_cell, d_area, d_shape, eps = airm_distance_and_strains(GA, GB)
        max_abs_eps = float(np.max(np.abs(eps)))

        rel_da, rel_db, rel_dgamma, d_gamma_deg = zm_diagnostics(SA, SB)
        zmx = zm_diagnostics_extended(SA, SB)

        d_size = size_proxy_d_size(kA=kA, kB=kB, nA_prim=nA_prim, nB_prim=nB_prim)
        score = scalar_score(
            d_cell=d_cell,
            d_size=d_size,
            eps_principal_max=eps_principal_max,
            nA_prim=nA_prim,
            nB_prim=nB_prim,
            N_at_max=N_at_max,
            w_match=w_match,
        )

        sigA, sigB, sig_pair = match_signature(SA, SB, tol=sig_tol, scale=sig_scale)

        rows.append(
            dict(
                method=method_name,
                method_version=method_version,
                pair=pair_name,
                max_area=float(max_area),
                cond_max=float(cond_max),
                eps_area=float(eps_area),
                eps_principal_max=float(eps_principal_max),
                dedupe_by_key=bool(dedupe_by_key),
                niggli_tol=float(niggli_tol),
                # geometry
                kA=kA,
                kB=kB,
                areaA=areaA,
                areaB=areaB,
                # AIRM-based
                d_cell=d_cell,
                d_area=d_area,
                d_shape=d_shape,
                eps1=float(eps[0]),
                eps2=float(eps[1]),
                max_abs_principal_strain=max_abs_eps,
                # ZM-style diagnostics
                rel_da=rel_da,
                rel_db=rel_db,
                rel_dgamma=rel_dgamma,
                d_gamma_deg=d_gamma_deg,
                d_gamma_rad=zmx["d_gamma_rad"],
                eps_a_log=zmx["eps_a_log"],
                eps_b_log=zmx["eps_b_log"],
                eps_shear_approx=zmx["eps_shear_approx"],
                gamma_mean_deg=zmx["gamma_mean_deg"],
                gamma_mean_rad=zmx["gamma_mean_rad"],
                # size + scalar
                d_size=d_size,
                score=score,
                # canonical signatures
                sigA=sigA,
                sigB=sigB,
                match_sig=sig_pair,
            )
        )

    if debug:
        print(
            f"[{pair_name} @ max_area={max_area}] matches={len(rows)} time={t1-t0:.3f}s (k_max={k_max})"
        )

    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="results_slabgen.csv")
    p.add_argument("--max-areas", type=str, default="50,100,200,400")
    p.add_argument("--cond-max", type=float, default=1e3)
    p.add_argument("--eps-area", type=float, default=0.09)
    p.add_argument(
        "--tau-max",
        type=float,
        default=None,
        help=(
            "Alias for --eps-area: symmetric log-area mismatch tolerance used for pairing "
            "(|log(A_A/A_B)| <= tau_max). If provided, overrides --eps-area."
        ),
    )
    p.add_argument("--eps-principal-max", type=float, default=0.03)
    p.add_argument("--dedupe-by-key", action="store_true")
    p.add_argument("--no-dedupe-by-key", action="store_true")
    p.add_argument("--niggli-tol", type=float, default=1e-12)
    p.add_argument("--nA-prim", type=int, default=1)
    p.add_argument("--nB-prim", type=int, default=1)
    p.add_argument("--N-at-max", type=int, default=5000)
    p.add_argument("--w-match", type=float, default=0.7)
    p.add_argument("--sig-tol", type=float, default=1e-12)
    p.add_argument("--sig-scale", type=float, default=1e10)
    p.add_argument("--debug", action="store_true")

    args = p.parse_args()
    max_areas = [float(x.strip()) for x in args.max_areas.split(",") if x.strip()]

    dedupe_by_key = True
    if args.no_dedupe_by_key:
        dedupe_by_key = False
    if args.dedupe_by_key:
        dedupe_by_key = True

    rows: List[Dict[str, Any]] = []
    for pair in default_benchmark_pairs():
        for max_area in max_areas:
            rows.extend(
                run_slabgen_for_pair(
                    pair_name=pair.name,
                    A2=pair.A,
                    B2=pair.B,
                    max_area=max_area,
                    cond_max=args.cond_max,
                    eps_area=args.eps_area,
                    tau_max=args.tau_max,
                    eps_principal_max=args.eps_principal_max,
                    dedupe_by_key=dedupe_by_key,
                    niggli_tol=args.niggli_tol,
                    nA_prim=args.nA_prim,
                    nB_prim=args.nB_prim,
                    N_at_max=args.N_at_max,
                    w_match=args.w_match,
                    sig_tol=args.sig_tol,
                    sig_scale=args.sig_scale,
                    debug=args.debug,
                )
            )

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} match records to: {args.out}")


if __name__ == "__main__":
    main()