"""benchmarks.run_pymatgen_zsl

Run pymatgen's ZSL (Zur SuperLattice) matching on the benchmark 2D lattice pairs.

Usage
-----
python -m benchmarks.run_pymatgen_zsl --out results_pymatgen.csv

Notes
-----
- This script is intentionally geometry-only. We construct two pymatgen Lattice
  objects from the 2D bases embedded in 3D with a large z-vector.
- The ZSL output is post-processed to compute the same metrics reported for
  slabgen (AIRM distance, principal strains, d_area/d_shape, size proxy, etc.).
- We also compute an optional canonical match signature for robust cross-tool
  comparisons (see benchmarks.signature).

"""

from __future__ import annotations

import argparse
import time
import importlib.metadata as importlib_metadata
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .benchmark_pairs import default_benchmark_pairs, basis_area, basis_to_3d_vectors
from .common_metrics import airm_distance_and_strains, zm_diagnostics, zm_diagnostics_extended, size_proxy_d_size, scalar_score
from .signature import match_signature, canonicalize_2d


ZSL_DETAIL_FIELDS = (
    "method",
    "method_version",
    "pair",
    "max_area",
    "max_length_tol",
    "max_angle_tol",
    "max_area_ratio_tol",
    "kA",
    "kB",
    "areaA",
    "areaB",
    "log_area_ratio",
    "d_cell",
    "d_area",
    "d_shape",
    "eps1",
    "eps2",
    "max_abs_principal_strain",
    "rel_da",
    "rel_db",
    "rel_dgamma",
    "d_gamma_deg",
    "d_gamma_rad",
    "eps_a_log",
    "eps_b_log",
    "eps_shear_approx",
    "gamma_mean_deg",
    "gamma_mean_rad",
    "d_size",
    "score",
    "sigA",
    "sigB",
    "match_sig",
)


def _pymatgen_version() -> str:
    try:
        return importlib_metadata.version("pymatgen")
    except Exception:
        return "unknown"


def _build_3d_lattice_from_2d(S2: np.ndarray, Lz: float = 25.0):
    """Return a pymatgen Lattice with in-plane vectors from S2."""

    try:
        from pymatgen.core import Lattice  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pymatgen is required. Install pymatgen and re-run.") from exc

    S2 = np.asarray(S2, float)
    v1, v2 = basis_to_3d_vectors(S2)
    v3 = np.array([0.0, 0.0, float(Lz)], dtype=float)
    mat = np.array([v1, v2, v3], dtype=float)
    return Lattice(mat)


def _zsl_call(zsl: Any, A2: np.ndarray, B2: np.ndarray) -> List[Any]:
    """Call pymatgen's ZSL generator across API variants.

    Newer pymatgen versions (2024+) expect two *iterables* of 3D vectors,
    i.e. (film_vectors, substrate_vectors). Older versions sometimes
    accepted (film_lattice, substrate_lattice).
    """

    # Preferred: pass explicit in-plane vectors.
    film_vectors = basis_to_3d_vectors(A2)
    sub_vectors = basis_to_3d_vectors(B2)

    # Pymatgen has had minor API variations here. We try to detect the
    # expected call signature and choose the most appropriate calling
    # convention.
    try:
        import inspect

        # ZSLGenerator is a callable object; inspect the bound __call__.
        param_names = list(inspect.signature(zsl.__call__).parameters.keys())
        if param_names and param_names[0] == "self":
            param_names = param_names[1:]
    except Exception:
        param_names = []

    # If the signature explicitly mentions vectors, use keyword calling.
    if {"film_vectors", "substrate_vectors"}.issubset(set(param_names)):
        try:
            return list(zsl(film_vectors=film_vectors, substrate_vectors=sub_vectors))
        except TypeError:
            # Some versions do not use keyword names consistently; fall back.
            pass

    # Default attempt: positional vectors.
    try:
        return list(zsl(film_vectors, sub_vectors))
    except TypeError as exc_vec:
        # Fallback: pass Lattice objects for older pymatgen versions.
        A_lat = _build_3d_lattice_from_2d(A2)
        B_lat = _build_3d_lattice_from_2d(B2)

        # If the signature explicitly mentions (film, substrate), prefer keyword.
        if {"film", "substrate"}.issubset(set(param_names)):
            try:
                return list(zsl(film=A_lat, substrate=B_lat))
            except TypeError:
                pass

        try:
            return list(zsl(A_lat, B_lat))
        except TypeError:
            # Re-raise the original vector-call exception with context.
            raise exc_vec


def _extract_superlattice_vectors(match_obj: Any) -> Tuple[np.ndarray, np.ndarray]:
    """Return (film_sl_vectors, substrate_sl_vectors) as two arrays of shape (2, 3)."""

    film = None
    sub = None

    # Object-style (older pymatgen)
    if hasattr(match_obj, "film_sl_vectors") and hasattr(match_obj, "substrate_sl_vectors"):
        film = getattr(match_obj, "film_sl_vectors")
        sub = getattr(match_obj, "substrate_sl_vectors")

    # Dict-style
    elif isinstance(match_obj, dict):
        for k_film in ("film_sl_vectors", "film_vectors", "film"):
            if k_film in match_obj:
                film = match_obj[k_film]
                break
        for k_sub in ("substrate_sl_vectors", "substrate_vectors", "substrate", "sub"):
            if k_sub in match_obj:
                sub = match_obj[k_sub]
                break

    # List/tuple style: [film_vectors, substrate_vectors, ...]
    elif isinstance(match_obj, (list, tuple)) and len(match_obj) >= 2:
        film, sub = match_obj[0], match_obj[1]

    if film is None or sub is None:
        raise TypeError(
            "Unrecognized pymatgen ZSL match format. "
            f"Got type={type(match_obj)} with keys/attrs={dir(match_obj)[:10]}"
        )

    film = np.asarray(film, dtype=float)
    sub = np.asarray(sub, dtype=float)

    # Normalize shapes to (2, 3)
    film = film.reshape((-1, 3))
    sub = sub.reshape((-1, 3))
    if film.shape[0] != 2 or sub.shape[0] != 2:
        raise ValueError(
            "Expected exactly two 3D vectors for each superlattice; "
            f"got film={film.shape}, sub={sub.shape}"
        )
    return film, sub


def run_zsl_for_pair(
    *,
    pair_name: str,
    A2: np.ndarray,
    B2: np.ndarray,
    max_area: float,
    max_length_tol: float,
    max_angle_tol: float,
    max_area_ratio_tol: float,
    nA_prim: int,
    nB_prim: int,
    N_at_max: int,
    eps_principal_max: float,
    w_match: float,
    sig_tol: float,
    sig_scale: float,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """Run ZSL for a single pair + max_area and return list of row dicts."""

    try:
        from pymatgen.analysis.interfaces.zsl import ZSLGenerator  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pymatgen.analysis.interfaces.zsl is required.") from exc

    zsl = ZSLGenerator(
        max_area=float(max_area),
        max_area_ratio_tol=float(max_area_ratio_tol),
        max_length_tol=float(max_length_tol),
        max_angle_tol=float(max_angle_tol),
    )

    t0 = time.perf_counter()
    matches = _zsl_call(zsl, A2, B2)
    t1 = time.perf_counter()

    rows: List[Dict[str, Any]] = []

    areaA_prim = float(basis_area(A2))
    areaB_prim = float(basis_area(B2))

    for m in matches:
        film_vecs, sub_vecs = _extract_superlattice_vectors(m)
        # Take xy components; columns are the two in-plane vectors.
        SA = np.array(
            [[film_vecs[0, 0], film_vecs[1, 0]], [film_vecs[0, 1], film_vecs[1, 1]]],
            dtype=float,
        )
        SB = np.array(
            [[sub_vecs[0, 0], sub_vecs[1, 0]], [sub_vecs[0, 1], sub_vecs[1, 1]]],
            dtype=float,
        )
        SAc, _, _ = canonicalize_2d(SA)
        SBc, _, _ = canonicalize_2d(SB)

        GA = SAc.T @ SAc
        GB = SBc.T @ SBc

        d_cell, d_area, d_shape, eps = airm_distance_and_strains(GA, GB)
        max_abs_eps = float(np.max(np.abs(eps)))

        # Indices from areas (robust rounding).
        areaA = float(abs(np.linalg.det(SAc)))
        areaB = float(abs(np.linalg.det(SBc)))
        log_area_ratio = float(abs(np.log(areaA / areaB)))
        kA = int(np.rint(areaA / max(1e-18, areaA_prim)))
        kB = int(np.rint(areaB / max(1e-18, areaB_prim)))

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

        rel_da, rel_db, rel_dgamma, d_gamma_deg = zm_diagnostics(SAc, SBc)
        zmx = zm_diagnostics_extended(SAc, SBc)

        sigA, sigB, sig_pair = match_signature(SAc, SBc, tol=sig_tol, scale=sig_scale)

        rows.append(
            dict(
                method="pymatgen_zsl",
                method_version=_pymatgen_version(),
                pair=pair_name,
                max_area=float(max_area),
                max_length_tol=float(max_length_tol),
                max_angle_tol=float(max_angle_tol),
                max_area_ratio_tol=float(max_area_ratio_tol),
                # geometry
                kA=kA,
                kB=kB,
                areaA=areaA,
                areaB=areaB,
                log_area_ratio=log_area_ratio,
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
        if tuple(rows[-1]) != ZSL_DETAIL_FIELDS:
            raise RuntimeError("legacy pymatgen ZSL row schema mismatch")

    if debug:
        print(
            f"[{pair_name} @ max_area={max_area}] raw_matches={len(matches)} rows={len(rows)} time={t1-t0:.3f}s"
        )

    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="results_pymatgen.csv")
    p.add_argument("--max-areas", type=str, default="50,100,200,400")
    p.add_argument("--max-length-tol", type=float, default=0.03)
    p.add_argument("--max-angle-tol", type=float, default=0.01)
    p.add_argument("--max-area-ratio-tol", type=float, default=0.09)
    p.add_argument("--nA-prim", type=int, default=1, help="primitive atom count proxy for slab A")
    p.add_argument("--nB-prim", type=int, default=1, help="primitive atom count proxy for slab B")
    p.add_argument("--N-at-max", type=int, default=5000, help="max atom count for d_size normalization")
    p.add_argument("--eps-principal-max", type=float, default=0.03, help="used only for score normalization")
    p.add_argument("--w-match", type=float, default=0.7, help="score weight on mismatch vs size")
    p.add_argument("--sig-tol", type=float, default=1e-12)
    p.add_argument("--sig-scale", type=float, default=1e10)
    p.add_argument("--debug", action="store_true")

    args = p.parse_args()
    max_areas = [float(x.strip()) for x in args.max_areas.split(",") if x.strip()]

    rows: List[Dict[str, Any]] = []
    for pair in default_benchmark_pairs():
        for max_area in max_areas:
            rows.extend(
                run_zsl_for_pair(
                    pair_name=pair.name,
                    A2=pair.A,
                    B2=pair.B,
                    max_area=max_area,
                    max_length_tol=args.max_length_tol,
                    max_angle_tol=args.max_angle_tol,
                    max_area_ratio_tol=args.max_area_ratio_tol,
                    nA_prim=args.nA_prim,
                    nB_prim=args.nB_prim,
                    N_at_max=args.N_at_max,
                    eps_principal_max=args.eps_principal_max,
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