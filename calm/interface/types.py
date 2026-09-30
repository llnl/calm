"""calm.interface.types

Internal types for the interface enumeration/matching pipeline.

Important note on StrainState
-----------------------------
This module defines an *internal* StrainState container used by
:func:`calm.interface.refinement.strain.compute_strain_2d`. This is *not* the same as the
public/persisted StrainState exposed in :mod:`calm.interface.results` and
exported from :mod:`calm.interface`.

The internal StrainState contains detailed diagnostic fields (polar factors,
Hencky tensors, etc.) that are useful for building interfaces and debugging.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from calm.interface.matching.zur_mcgill import zur_mcgill_diagnostic_metadata

from calm.math2d._core import sym2
from calm.math2d.spd2x2 import invsqrt_spd, log_spd
from calm.math2d.sym2x2 import eigvals2_spd


@dataclass(frozen=True)
class AffineInvariantStrain2D:
    """
    Affine-invariant 2D strain summary derived from the relative metric M
    and Hencky strain E.

    Conventions
    -----------
    - M = G1^{-1/2} G2 G1^{-1/2} is SPD.
    - mu_i are eigenvalues of M (mu_i > 0).
    - principal stretches: lambda_i = sqrt(mu_i) > 0.
    - Hencky principal strains (log strains): eps_i = ln(lambda_i) = 0.5 ln(mu_i).
    - E is the Hencky strain tensor: E = 0.5 * log(M), symmetric.
    - E_iso = (tr(E)/2) I,  E_dev = E - E_iso (trace-free).
    """

    mu: np.ndarray  # shape (2,), eigenvalues of M (ascending)
    principal_strains: np.ndarray  # shape (2,), eps_i = 0.5 * ln(mu_i) (ascending)
    E: np.ndarray  # shape (2,2), symmetric
    E_iso: np.ndarray  # shape (2,2)
    E_dev: np.ndarray  # shape (2,2)

    def __post_init__(self) -> None:
        mu = np.asarray(self.mu, dtype=float)
        eps = np.asarray(self.principal_strains, dtype=float)
        E = np.asarray(self.E, dtype=float)
        E_iso = np.asarray(self.E_iso, dtype=float)
        E_dev = np.asarray(self.E_dev, dtype=float)

        if mu.shape != (2,):
            raise ValueError("mu must have shape (2,)")
        if np.any(mu <= 0.0):
            raise ValueError("mu must be positive (SPD eigenvalues).")
        if eps.shape != (2,):
            raise ValueError("principal_strains must have shape (2,)")
        if E.shape != (2, 2) or E_iso.shape != (2, 2) or E_dev.shape != (2, 2):
            raise ValueError("E, E_iso, E_dev must have shape (2,2).")

    @property
    def principal_stretches(self) -> np.ndarray:
        """Principal stretches lambda_i = exp(eps_i) > 0."""
        return np.exp(self.principal_strains)

    @property
    def trE(self) -> float:
        """Trace of Hencky strain: tr(E) = eps1 + eps2 = ln(lambda1*lambda2)."""
        return float(self.principal_strains.sum())

    @property
    def d_area(self) -> float:
        """Area component: sqrt(2) * |tr(E)|."""
        return float(np.sqrt(2.0) * abs(self.trE))

    @property
    def d_cell(self) -> float:
        """Total affine-invariant distance: 2*||E||_F = 2*sqrt(sum eps_i^2)."""
        return float(2.0 * np.linalg.norm(self.principal_strains))

    @property
    def d_shape(self) -> float:
        """Shape component: sqrt(2) * |eps1 - eps2|."""
        eps1, eps2 = self.principal_strains
        return float(np.sqrt(2.0) * abs(eps1 - eps2))

    @property
    def max_abs_principal_strain(self) -> float:
        """Max absolute Hencky principal strain."""
        return float(np.max(np.abs(self.principal_strains)))

    @property
    def norm_E(self) -> float:
        """Frobenius norm ||E||_F = sqrt(ε₁² + ε₂²)."""
        return float(np.linalg.norm(self.E, ord="fro"))

    @property
    def norm_E_area(self) -> float:
        """Frobenius norm ||E_area||_F = (sqrt(2)/2)|ε₁ + ε₂| = (sqrt(2)/2)|Tr(E)|."""
        return float((np.sqrt(2.0) / 2.0) * abs(self.trE))

    @property
    def norm_E_shape(self) -> float:
        """Frobenius norm ||E_shape||_F = (sqrt(2)/2)|ε₁ - ε₂|."""
        eps1, eps2 = self.principal_strains
        return float((np.sqrt(2.0) / 2.0) * abs(eps1 - eps2))

    @property
    def principal_directions(self) -> np.ndarray:
        """Principal strain directions (eigenvectors of E), columns."""
        eigvals, eigvecs = np.linalg.eigh(self.E)
        idx = np.argsort(eigvals)
        return eigvecs[:, idx]

    @classmethod
    def from_grams(
        cls,
        G1: np.ndarray,
        G2: np.ndarray,
    ) -> "AffineInvariantStrain2D":
        """Construct from two (2,2) SPD Gram tensors."""
        if G1.shape != (2, 2) or G2.shape != (2, 2):
            raise ValueError("Expected (2,2) matrices for G1 and G2")

        G1s = sym2(np.asarray(G1, dtype=float))
        G2s = sym2(np.asarray(G2, dtype=float))

        X = invsqrt_spd(G1s)
        M = sym2(X @ G2s @ X)

        mu = eigvals2_spd(M)
        if np.any(mu <= 0.0):
            raise ValueError(f"Relative metric M not SPD; eigenvalues={mu}")

        principal_strains = 0.5 * np.log(mu)

        H = log_spd(M)
        E = 0.5 * H
        E_iso = 0.5 * np.trace(E) * np.eye(2)
        E_dev = E - E_iso

        return cls(
            mu=mu,
            principal_strains=principal_strains,
            E=E,
            E_iso=E_iso,
            E_dev=E_dev,
        )


# --------------------------------------------------------------------------------------
# INTERNAL strain-splitting diagnostics container (required by calm.interface.refinement.strain)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StrainState:
    """Internal detailed strain-splitting diagnostics returned by `compute_strain_2d`.

    This type is an internal implementation detail of the interface builder.
    The public `StrainState` exposed via `calm.interface.StrainState` is defined in
    `calm.interface.results`.
    """

    alpha: float
    F_tot: np.ndarray  # Overall deformation gradient (3x3), T = F_tot @ S

    F_A: np.ndarray
    R_A: np.ndarray
    U_A: np.ndarray
    E_A: np.ndarray
    E_A_rms: float

    F_B: np.ndarray
    R_B: np.ndarray
    U_B: np.ndarray
    E_B: np.ndarray
    E_B_rms: float


@dataclass(frozen=True)
class ZMStrain2D:
    """Diagnostic-only Zur–McGill length/angle mismatch summary.

    These values are retained for historical comparison and reporting. They do
    not control hard admissibility, authoritative ranking, Pareto membership,
    crystallographic identity, or exact deduplication.
    """

    a_A: float
    b_A: float
    gamma_A_deg: float
    a_B: float
    b_B: float
    gamma_B_deg: float
    rel_da: float
    rel_db: float
    d_gamma_deg: float
    rel_dgamma: float

    def to_diagnostic_dict(self) -> dict[str, object]:
        """Return a self-describing diagnostic projection."""

        return {
            **zur_mcgill_diagnostic_metadata(),
            "rel_da": float(self.rel_da),
            "rel_db": float(self.rel_db),
            "d_gamma_deg": float(self.d_gamma_deg),
            "rel_dgamma": float(self.rel_dgamma),
        }

    @staticmethod
    def _abgamma_from_basis(A: np.ndarray, tol: float) -> tuple[float, float, float]:
        """Return a, b, and non-obtuse gamma from a 2D column basis."""
        v1 = A[:, 0]
        v2 = A[:, 1]

        n1 = float(np.linalg.norm(v1))
        n2 = float(np.linalg.norm(v2))

        if n1 <= n2 - float(tol):
            a, b = n1, n2
        else:
            a, b = n2, n1

        arg = float(np.dot(v1, v2) / (n1 * n2))
        arg = float(np.clip(arg, -1.0, 1.0))
        arg = abs(arg)  # enforce non-obtuse reduced angle

        gamma_deg = float(np.degrees(np.arccos(arg)))
        return float(a), float(b), float(gamma_deg)

    @classmethod
    def from_bases(
        cls,
        A1: np.ndarray,
        A2: np.ndarray,
        tol: float = 1e-6,
    ) -> "ZMStrain2D":
        """Construct Zur-McGill-style mismatch metrics for two 2D bases."""
        if A1.shape != (2, 2) or A2.shape != (2, 2):
            raise ValueError("Expected (2,2) matrices for A1 and A2")

        a_A, b_A, gamma_A_deg = cls._abgamma_from_basis(
            np.asarray(A1, dtype=float),
            tol,
        )
        a_B, b_B, gamma_B_deg = cls._abgamma_from_basis(
            np.asarray(A2, dtype=float),
            tol,
        )

        ma = 0.5 * (a_A + a_B)
        mb = 0.5 * (b_A + b_B)
        mg = 0.5 * (gamma_A_deg + gamma_B_deg)

        rel_da = abs(a_A - a_B) / ma if ma > 0 else float("inf")
        rel_db = abs(b_A - b_B) / mb if mb > 0 else float("inf")

        d_gamma_deg = abs(gamma_A_deg - gamma_B_deg)
        rel_dgamma = d_gamma_deg / mg if mg > 0 else float("inf")

        return cls(
            a_A=a_A,
            b_A=b_A,
            gamma_A_deg=gamma_A_deg,
            a_B=a_B,
            b_B=b_B,
            gamma_B_deg=gamma_B_deg,
            rel_da=rel_da,
            rel_db=rel_db,
            d_gamma_deg=d_gamma_deg,
            rel_dgamma=rel_dgamma,
        )
