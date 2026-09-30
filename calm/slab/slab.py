"""Slab construction and utilities.

The :class:`~calm.slab.slab.Slab` class is a thin convenience wrapper that builds a
surface slab from a bulk structure and Miller index, and provides utilities for slab
bookkeeping (vacuum, centering, sorting, constraints, metadata).

Modern slabs are constructed via the oriented-slab pipeline (Zone-law construction)
implemented in :func:`calm.slab.oriented.model.build_oriented_slab`. This avoids the
legacy approach of building a conventional-cell slab and then attempting to discover a
primitive surface cell via a post-hoc search in the slab Cartesian frame.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property, reduce
from math import gcd
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from ase import Atoms
from ase.constraints import FixAtoms
from ase.formula import Formula

from calm.bulk.bulk import Bulk
from calm.exceptions import SlabError
from calm.slab.oriented._coordination import build_slab_coordination
from calm.slab.oriented.transforms import (
    ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
    OrientedSlabTransforms,
    from_transforms_payload,
)


def parse_oriented_slab_transforms_json(js: str) -> Dict[str, Any]:
    """Parse one exact-current oriented-slab transform payload.

    This is an explicit JSON import boundary. It accepts only the current
    compact payload vocabulary owned by
    :mod:`calm.slab.oriented.transforms`. Historical wrapper payloads,
    unversioned mappings, and retired key aliases are rejected.
    """

    if not isinstance(js, str) or not js.strip():
        raise TypeError("oriented-slab transforms JSON must be a non-empty string")
    try:
        payload = json.loads(js)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid oriented-slab transforms JSON") from exc
    return from_transforms_payload(payload).payload


def _transforms_from_atoms_info(obj: Any) -> OrientedSlabTransforms | None:
    info = getattr(obj, "info", None)
    if not isinstance(info, Mapping):
        return None
    if ORIENTED_SLAB_TRANSFORMS_INFO_KEY not in info:
        return None
    payload = info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]
    if not isinstance(payload, Mapping):
        raise ValueError(
            "Current oriented-slab transforms provenance in Atoms.info must "
            "be a mapping. Historical JSON-string carriers are unsupported."
        )
    return from_transforms_payload(payload)


def get_oriented_slab_transforms(
    obj: Any,
    *,
    strict: bool = False,
) -> Optional[OrientedSlabTransforms]:
    """Return exact-current oriented-slab provenance from a slab or atoms.

    Missing provenance returns ``None`` unless ``strict=True``. A present but
    malformed or historical payload always raises: invalid current project
    state is not reclassified as missing provenance.
    """

    if obj is None:
        if strict:
            raise KeyError(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
        return None

    candidate = getattr(obj, "oriented_slab_transforms", None)
    if isinstance(candidate, OrientedSlabTransforms):
        return candidate

    transforms = _transforms_from_atoms_info(obj)
    if transforms is None and strict:
        raise KeyError(f"Missing {ORIENTED_SLAB_TRANSFORMS_INFO_KEY!r} on object.")
    return transforms


def get_oriented_slab_transforms_payload(
    obj: Any,
    *,
    strict: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return a fresh exact-current oriented-slab provenance payload."""

    transforms = get_oriented_slab_transforms(obj, strict=strict)
    return None if transforms is None else transforms.payload


def get_oriented_slab_transforms_json(obj: Any) -> Optional[str]:
    """Return canonical JSON for exact-current oriented-slab provenance."""

    transforms = get_oriented_slab_transforms(obj)
    return None if transforms is None else transforms.json


Miller = Union[Tuple[int, int, int], Tuple[int, int, int, int]]


@dataclass(frozen=True)
class SlabSpec:
    """Specification for building a slab from a bulk structure.

    Stage B (v2) intent
    -------------------
    - The spec is a *pure* configuration object (safe to hash and persist).
    - Fields are explicit and future-proofed for provenance.

    Notes
    -----
    - `miller` supports either 3-index (h,k,l) or 4-index (h,k,i,l) notation.
    - `fixed_layers` and translation variants are build-stage concepts; only
      `fixed_layers` is applied at slab construction time.
    """

    miller: Miller

    # Geometry
    n_layers: int = 4
    vacuum: float = 10.0
    target_width: Optional[float] = None
    width_tol: float = 1e-4
    max_n_layers: int = 10

    # DFT-friendly convention: periodic in all directions (vacuum decouples images).
    pbc: Tuple[bool, bool, bool] = (True, True, True)

    # Optional constraint policy
    fixed_layers: int = 0
    fixed_layers_symmetric: bool = False
    rad_scalar: float = 1.05

    # Optional chemistry/magnetism knobs (stored for provenance; not all
    # are applied yet)
    magmom: Optional[float] = None
    termination: Optional[str] = None

    # Standardization / reproducibility knobs (currently owned by Bulk, but kept here
    # so the full slab intent can be serialized without reaching into Bulk internals).
    symprec: float = 1e-5
    no_idealize: bool = False

    # Result-affecting finite gauges for primitive surface construction.
    primitive_max_denominator: int = 12
    primitive_reduction_max_iter: int = 100
    stacking_search_radius: int = 2
    c_tilt_search: int = 6
    c_tilt_singular_tolerance: float = 1e-12

    # Output hygiene
    wrap: bool = True
    verbose: bool = False

    # Transform provenance persistence
    stamp_transforms: bool = True
    """If True (default), stamp oriented-slab transform provenance to
    ``atoms.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]``.

    Setting this to False avoids injecting CALM-specific metadata into the
    underlying :class:`ase.atoms.Atoms` object. The transforms remain
    available via :attr:`Slab.oriented_slab_transforms` or
    :attr:`Slab.oriented_slab_transforms_json`.
    """


class Slab:
    """Internal wrapper for constructed and authoritative materialized slabs.

    The normal constructor builds a slab from a standardized bulk and current
    ``SlabSpec``. :meth:`from_materialized` wraps an already-persisted finite slab
    without interpreting its atoms as a new bulk.

    Conventions
    ----------
    - The slab is constructed via
      :func:`calm.slab.oriented.model.build_oriented_slab`. This uses a
      Zone-law construction to determine the in-plane basis vectors and the
      surface normal from the Miller index.
    - The generated cell is motif-compatible and primitive in-plane (subject to the
      optional in-plane reduction knobs in the oriented-slab kernel).
    - Transform provenance can be stamped into ``atoms.info`` under
      :data:`ORIENTED_SLAB_TRANSFORMS_INFO_KEY`.
    """

    def __init__(self, bulk: Bulk, spec: SlabSpec):
        if not isinstance(bulk, Bulk):
            raise TypeError("Slab: bulk must be a calm.bulk.Bulk instance.")
        if spec is None:
            raise TypeError("Slab requires a SlabSpec instance in the v2 API.")

        self.bulk: Bulk = bulk
        self.spec: SlabSpec = spec

        self.hkl: Tuple[int, int, int] = self._parse_miller_index(spec.miller)
        self.vacuum: float = float(spec.vacuum)

        # May be overridden by target width logic
        self.Nlay: int = int(spec.n_layers)

        # Built outputs
        self.atoms: Atoms
        self.slab_center: float
        self.slab_width: float

        self.is_stoichiometric: bool = False
        self.stoich_info: Dict[str, Any] = {}

        target_width = None
        width_tolerance = float(spec.width_tol)
        max_n_layers = int(spec.max_n_layers)
        if spec.target_width is not None:
            target_width = float(spec.target_width)
            self.Nlay = self._get_nlay_for_target_width(
                bulk=self.bulk.conv,
                hkl=self.hkl,
                target_width=target_width,
                max_n_layers=max_n_layers,
                width_tol=width_tolerance,
            )

        # Build slab via the modern oriented-slab pipeline.
        #
        # This path constructs the primitive surface cell directly from the
        # bulk conventional/primitive description and Miller index
        # (Zone-law construction), avoiding the legacy post-hoc
        # primitive-cell search in the slab Cartesian frame.
        from calm.slab.oriented.model import (
            build_oriented_slab as _build_oriented_slab,
        )
        from calm.slab.oriented._thickness import (
            SlabThicknessLimitError,
            target_width_is_satisfied,
        )

        def build_result(layer_count: int):
            return _build_oriented_slab(
                self.bulk,
                hkl=self.hkl,
                layers=int(layer_count),
                symprec=float(self.spec.symprec),
                primitive_max_denominator=self.spec.primitive_max_denominator,
                primitive_reduction_max_iter=(self.spec.primitive_reduction_max_iter),
                stacking_search_radius=self.spec.stacking_search_radius,
                c_tilt_search=self.spec.c_tilt_search,
                c_tilt_singular_tolerance=(self.spec.c_tilt_singular_tolerance),
                vacuum=float(self.vacuum),
                wrap=bool(self.spec.wrap),
            )

        result = build_result(self.Nlay)
        if target_width is not None:
            while not target_width_is_satisfied(
                self._get_width(result.block),
                target_width_A=target_width,
                width_tolerance_A=width_tolerance,
            ):
                if self.Nlay >= max_n_layers:
                    measured = self._get_width(result.block)
                    raise SlabThicknessLimitError(
                        "The constructed slab did not satisfy target_width "
                        f"within max_n_layers={max_n_layers}: measured "
                        f"atom span={measured:.12g} angstrom, requested "
                        f"target_width={target_width:.12g} angstrom with "
                        f"width_tol={width_tolerance:.12g} angstrom."
                    )
                self.Nlay += 1
                result = build_result(self.Nlay)

        self.atoms = result.slab

        payload = self.atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
        if not isinstance(payload, Mapping):
            raise RuntimeError(
                "Current oriented-slab construction did not attach its "
                "required transform provenance payload."
            )
        self._oriented_slab_transforms_obj = from_transforms_payload(payload)

        if not bool(self.spec.stamp_transforms):
            self.atoms.info.pop(ORIENTED_SLAB_TRANSFORMS_INFO_KEY, None)

        # Derived properties
        self.slab_width = self._get_width(self.atoms)
        z = self.atoms.positions[:, 2]
        self.slab_center = 0.5 * (float(np.max(z)) + float(np.min(z)))

        # Stoichiometry check (always stamps fields)
        self._check_slab_stoichiometry()

        # Deterministic ordering (safe only before constraints exist)
        self.sort_atomic_pos(allow_if_constrained=False)

        # Optional magnetism initialization. Invalid requested state is a
        # construction error; it is never discarded silently.
        if spec.magmom is not None:
            mm = float(spec.magmom)
            self.atoms.set_initial_magnetic_moments([mm] * len(self.atoms))

        # Optional wrapping
        if bool(spec.wrap):
            self.atoms.wrap()

        # Optional constraint policy
        if int(spec.fixed_layers) > 0:
            self.fix_layers(
                n_layers=int(spec.fixed_layers),
                rad_scalar=float(spec.rad_scalar),
                symmetric=bool(spec.fixed_layers_symmetric),
                store_mask=True,
            )

        # Provenance/metadata
        self._stamp_metadata()

    @classmethod
    def from_materialized(
        cls,
        atoms: Atoms,
        *,
        miller: Miller,
        project_slab_uid_full: str,
        project_slab_id_short: str | None = None,
        layers: int | None = None,
        vacuum: float | None = None,
    ) -> "Slab":
        """Wrap an authoritative persisted slab without rebuilding its geometry.

        Persisted surface records already contain the oriented finite slab.  This
        constructor preserves that atom ordering, cell, constraints, and transform
        metadata while supplying the minimal current ``Slab`` interface required by
        matching and interface construction.
        """

        if not isinstance(atoms, Atoms):
            raise TypeError("atoms must be an ASE Atoms instance.")
        if not isinstance(project_slab_uid_full, str):
            raise TypeError("project_slab_uid_full must be a string.")
        uid = project_slab_uid_full.strip()
        if not uid:
            raise ValueError("project_slab_uid_full must not be empty.")
        short_id = None
        if project_slab_id_short is not None:
            if not isinstance(project_slab_id_short, str):
                raise TypeError("project_slab_id_short must be a string or None.")
            short_id = project_slab_id_short.strip()
            if not short_id:
                raise ValueError("project_slab_id_short must not be empty.")

        self = cls.__new__(cls)
        self.bulk = None
        self.spec = None
        self.hkl = self._parse_miller_index(miller)
        self.project_slab_uid_full = uid
        self.project_slab_id_short = short_id
        self.atoms = atoms.copy()
        if len(self.atoms) == 0:
            raise ValueError("A materialized slab must contain at least one atom.")

        info = dict(getattr(self.atoms, "info", {}) or {})
        self.atoms.info = info
        layer_value = info.get("calm:Nlay", 0) if layers is None else layers
        if isinstance(layer_value, bool) or not isinstance(
            layer_value,
            (int, np.integer),
        ):
            raise TypeError("layers must be an integer or None.")
        self.Nlay = int(layer_value)
        if self.Nlay < 0:
            raise ValueError("layers must be nonnegative.")

        vacuum_value = info.get("calm:vacuum", 0.0) if vacuum is None else vacuum
        if isinstance(vacuum_value, bool):
            raise TypeError("vacuum must be a real number or None.")
        self.vacuum = float(vacuum_value)
        if not np.isfinite(self.vacuum) or self.vacuum < 0.0:
            raise ValueError("vacuum must be finite and nonnegative.")

        self.slab_width = self._get_width(self.atoms)
        z = np.asarray(self.atoms.positions[:, 2], dtype=float)
        self.slab_center = 0.5 * (float(np.max(z)) + float(np.min(z)))
        self.is_stoichiometric = None
        self.stoich_info = {
            "ok": None,
            "reason": "parent bulk unavailable for authoritative persisted slab",
        }
        return self

    # ---------------------------
    # Public API
    # ---------------------------

    @property
    def cell(self):
        return self.atoms.cell.array.T

    @property
    def n_atoms(self) -> int:
        """Returns the number of atoms in the slab."""
        return len(self.atoms)

    @cached_property
    def uid(self) -> str:
        """Stable UID for this slab.

        This is a convenience façade for example scripts and downstream tools.

        Internally, slab UIDs are content-addressed and derived from:

        - the standardized **material UID** of the bulk conventional cell
        - the Miller index ``(h, k, l)``
        - the canonical **slab spec UID**

        Stage D note
        ------------
        If the bulk corresponds to a non-reference *bulk state* (e.g. relaxed),
        the slab spec UID is anchored to the bulk state UID to avoid collisions.
        This is detected via bulk.conv.info fields set by workspace persistence:

            calm:material_uid
            calm:bulk_uid
            calm:bulk_kind

        If absent, the UID falls back to the Stage B convention (reference bulk).
        """

        project_uid = getattr(self, "project_slab_uid_full", None)
        if isinstance(project_uid, str) and project_uid:
            return project_uid
        if self.bulk is None or self.spec is None:
            raise SlabError(
                "Materialized slab has no authoritative project UID and no "
                "Bulk/SlabSpec identity pair."
            )

        from calm.keys.uid import (
            material_uid_from_conv_atoms,
            reference_bulk_uid,
            slab_spec_uid,
            slab_spec_uid_for_bulk,
        )
        from calm.keys.uid import (
            slab_uid as slab_uid_fn,
        )

        # Prefer material_uid stamped by the persistence layer for stability/speed.
        info = getattr(self.bulk.conv, "info", {}) or {}
        mat_uid = info.get("calm:material_uid")
        if mat_uid is None:
            mat_uid = material_uid_from_conv_atoms(
                self.bulk.conv,
                symprec=float(self.bulk.symprec),
                no_idealize=bool(self.bulk.no_idealize),
            )
        mat_uid = str(mat_uid)

        bulk_kind = str(info.get("calm:bulk_kind") or "reference")
        bulk_uid = info.get("calm:bulk_uid")
        if bulk_uid is None:
            bulk_uid = reference_bulk_uid(mat_uid)
        bulk_uid = str(bulk_uid)

        if bulk_kind == "reference":
            ss_uid = slab_spec_uid(self.spec)
        else:
            ss_uid = slab_spec_uid_for_bulk(
                self.spec, bulk_uid=bulk_uid, bulk_kind=bulk_kind
            )

        return slab_uid_fn(material_uid=mat_uid, miller=self.hkl, slab_spec_uid=ss_uid)

    def fix_layers(
        self,
        n_layers: int = 2,
        rad_scalar: float = 1.05,
        symmetric: bool = False,
        store_mask: bool = True,
    ) -> None:
        """Fix atoms in the slab, leaving the top ``n_layers`` unconstrained.

        Layers are identified via an iterative "peeling" approach that
        uses undercoordination relative to the maximum coordination in the
        connectivity graph.
        """
        if n_layers <= 0:
            raise ValueError("n_layers must be positive.")

        z = np.round(self.atoms.positions[:, 2], 6)

        coordination = build_slab_coordination(
            self.atoms,
            rad_scalar=float(rad_scalar),
        )
        coord_mat = coordination.matrix.copy()
        max_coord = coordination.maximum

        layers: Dict[int, np.ndarray] = {}
        bottom_layer: Optional[np.ndarray] = None
        layer_idx = 0

        while True:
            coord_numbers = coord_mat.sum(axis=1)
            surface_sites = np.where((coord_numbers > 0) & (coord_numbers < max_coord))[
                0
            ]
            if surface_sites.size == 0:
                break

            z_vals = z[surface_sites]
            tmp_center = 0.5 * (float(np.min(z_vals)) + float(np.max(z_vals)))

            mask_top = z_vals >= tmp_center
            top_layer = surface_sites[mask_top]

            if bottom_layer is None:
                bottom_layer = surface_sites[~mask_top]

            layers[layer_idx] = top_layer
            layer_idx += 1

            coord_mat[:, top_layer] = 0
            coord_mat[top_layer, :] = 0

        if bottom_layer is not None:
            layers[layer_idx] = bottom_layer

        n_eff_layers = len(layers)
        if n_eff_layers == 0:
            raise SlabError(
                "fix_layers: could not identify layers from coordination graph."
            )

        if symmetric:
            max_pairs = n_eff_layers // 2
            n_layers = min(n_layers, max_pairs)
        else:
            n_layers = min(n_layers, n_eff_layers)

        peeled: list[int] = []
        if symmetric:
            for i in range(n_layers):
                peeled.extend(layers[i].tolist())
                peeled.extend(layers[n_eff_layers - i - 1].tolist())
        else:
            for i in range(n_layers):
                peeled.extend(layers[i].tolist())

        peeled_set = set(peeled)
        fix_idx = [i for i in range(len(self.atoms)) if i not in peeled_set]

        self.atoms.set_constraint(FixAtoms(indices=fix_idx))

        if store_mask:
            free_mask = np.zeros(len(self.atoms), dtype=bool)
            free_mask[list(peeled_set)] = True
            self.atoms.arrays["calm_free_mask"] = free_mask
            self.atoms.arrays["calm_fixed_mask"] = ~free_mask

    def sort_atomic_pos(self, allow_if_constrained: bool = False) -> None:
        """Sort atoms by (z, x, y) deterministically.

        WARNING: sorting after constraints can invalidate index-based constraints.
        """
        if (not allow_if_constrained) and self.atoms.constraints:
            raise SlabError(
                "Cannot sort atoms after constraints are set. "
                "Sort before applying FixAtoms, or implement constraint remapping."
            )
        pos = self.atoms.get_positions()
        idx = np.lexsort((pos[:, 1], pos[:, 0], pos[:, 2]))
        self.atoms = self.atoms[idx]

    # ---------------------------
    # Internals / helpers
    # ---------------------------

    def _stamp_metadata(self) -> None:
        info: Dict[str, Any] = self.atoms.info
        info["calm:slab_uid"] = self.uid
        info["calm:hkl"] = tuple(int(x) for x in self.hkl)
        info["calm:Nlay"] = int(self.Nlay)
        info["calm:vacuum"] = float(self.vacuum)
        info["calm:slab_width"] = (
            float(self.slab_width) if self.slab_width is not None else None
        )
        info["calm:slab_center"] = (
            float(self.slab_center) if self.slab_center is not None else None
        )
        info["calm:pbc"] = tuple(bool(x) for x in self.atoms.pbc)
        if self.spec.target_width is not None:
            from calm.slab.oriented._thickness import (
                SLAB_TARGET_WIDTH_POLICY,
                SLAB_TARGET_WIDTH_POLICY_VERSION,
            )

            info["calm:target_width"] = float(self.spec.target_width)
            info["calm:width_tol"] = float(self.spec.width_tol)
            info["calm:max_n_layers"] = int(self.spec.max_n_layers)
            info["calm:target_width_policy"] = SLAB_TARGET_WIDTH_POLICY
            info["calm:target_width_policy_version"] = SLAB_TARGET_WIDTH_POLICY_VERSION

        # Ensure tilt metadata is present in atoms.info for downstream consumers.
        # Compute once here and persist into atoms.info so repository insert uses
        # the stamped value rather than recomputing from scaled positions.
        from calm.slab.oriented.tilt import compute_slab_tilt_metadata

        transforms = self.oriented_slab_transforms
        # This is identity-bearing scientific provenance. Recompute and own the
        # current value rather than preserving a stale or user-supplied record.
        info["calm:tilt"] = compute_slab_tilt_metadata(
            self.atoms,
            transforms=transforms,
        )

    @staticmethod
    def _parse_miller_index(miller: Miller) -> Tuple[int, int, int]:
        if not isinstance(miller, (tuple, list)):
            raise SlabError("Miller indices must be a tuple/list of ints.")

        if len(miller) == 4:
            h, k, i, l = miller  # noqa: E741 - canonical Miller index triple (h,k,l) plus 4-index i
            if not all(isinstance(x, (int, np.integer)) for x in (h, k, i, l)):
                raise SlabError("Non-integer Miller indices provided.")
            if (h + k + i) != 0:
                raise SlabError(
                    "Invalid 4-index Miller notation: require h + k + i = 0."
                )
            if (h, k, l) == (0, 0, 0):
                raise SlabError("Miller index (0,0,0) is invalid.")
            return int(h), int(k), int(l)

        if len(miller) == 3:
            h, k, l = miller  # noqa: E741 - canonical Miller index triple (h,k,l)
            if not all(isinstance(x, (int, np.integer)) for x in (h, k, l)):
                raise SlabError("Non-integer Miller indices provided.")
            if (h, k, l) == (0, 0, 0):
                raise SlabError("Miller index (0,0,0) is invalid.")
            return int(h), int(k), int(l)

        raise SlabError("Invalid number of Miller indices provided (expected 3 or 4).")

    @staticmethod
    def _get_nlay_for_target_width(
        bulk: Atoms,
        hkl: Tuple[int, int, int],
        target_width: float,
        max_n_layers: int,
        width_tol: float,
    ) -> int:
        """Return the authoritative initial target-width layer estimate.

        ``target_width`` is a requested minimum Cartesian atom span for the
        final finite slab before vacuum. The reciprocal-lattice plan supplies
        an initial count; :class:`Slab` then verifies the measured atom span and
        increments the count until the request is met or ``max_n_layers`` is
        exhausted.
        """
        from calm.slab.oriented._thickness import plan_target_width_layers

        plan = plan_target_width_layers(
            np.asarray(bulk.cell.array, dtype=float),
            hkl,
            target_width_A=target_width,
            width_tolerance_A=width_tol,
            max_n_layers=max_n_layers,
        )
        return int(plan.required_layers)

    @staticmethod
    def _get_width(atoms: Atoms) -> float:
        z = atoms.positions[:, 2]
        return float(np.max(z) - np.min(z))

    def _check_slab_stoichiometry(self) -> None:
        """Determine whether the slab composition is an integer multiple of bulk.conv's formula unit.

        Always sets:
          - self.is_stoichiometric : bool
          - self.stoich_info : dict
        """

        def composition_counts(atoms: Atoms) -> Dict[str, int]:
            f = Formula(atoms.get_chemical_formula())
            return {k: int(v) for k, v in f.count().items()}

        def reduce_counts(counts: Dict[str, int]) -> Tuple[Dict[str, int], int]:
            g = reduce(gcd, counts.values())
            return {el: n // g for el, n in counts.items()}, int(g)

        bulk_counts = composition_counts(self.bulk.conv)
        slab_counts = composition_counts(self.atoms)

        bulk_red, _ = reduce_counts(bulk_counts)
        slab_red, _ = reduce_counts(slab_counts)

        if bulk_red != slab_red:
            self.is_stoichiometric = False
            self.stoich_info = {
                "ok": False,
                "reason": "Reduced composition differs from bulk.",
                "bulk_reduced": bulk_red,
                "slab_reduced": slab_red,
                "bulk_counts": bulk_counts,
                "slab_counts": slab_counts,
            }
            return

        # ratios match: check slab is an integer multiple of bulk formula unit
        k_values: list[int] = []
        for el, n_bulk_fu in bulk_red.items():
            n_slab = slab_counts.get(el, 0)
            if n_slab % n_bulk_fu != 0:
                self.is_stoichiometric = False
                self.stoich_info = {
                    "ok": False,
                    "reason": (
                        "Ratios match but slab is not an integer multiple of bulk "
                        "formula unit."
                    ),
                    "bulk_fu": bulk_red,
                    "slab_counts": slab_counts,
                }
                return
            k_values.append(n_slab // n_bulk_fu)

        ok = len(set(k_values)) == 1
        self.is_stoichiometric = bool(ok)
        self.stoich_info = {
            "ok": bool(ok),
            "bulk_fu": bulk_red,
            "slab_counts": slab_counts,
            "multiple_k": int(k_values[0]) if ok else k_values,
        }

    @property
    def oriented_slab_transforms_json(self) -> str:
        """Canonical JSON for the current compact transform payload."""

        transforms = self.oriented_slab_transforms
        return "" if transforms is None else transforms.json

    @property
    def oriented_slab_transforms(self) -> Optional[OrientedSlabTransforms]:
        """Current compact oriented-slab transform provenance, if present."""

        obj = getattr(self, "_oriented_slab_transforms_obj", None)
        if isinstance(obj, OrientedSlabTransforms):
            return obj

        payload = self.atoms.info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise ValueError(
                "Current oriented-slab transforms provenance in Atoms.info "
                "must be a mapping."
            )
        obj = from_transforms_payload(payload)
        self._oriented_slab_transforms_obj = obj
        return obj

    @property
    def oriented_slab_transforms_payload(self) -> Dict[str, Any]:
        """Return a fresh current compact transform payload."""

        transforms = self.oriented_slab_transforms
        return {} if transforms is None else transforms.payload

    def to_atoms(self, *, stamp_transforms: bool | None = None) -> Atoms:
        """Return a copy, optionally adding or removing current provenance.

        ``stamp_transforms`` controls the current mapping payload under
        :data:`ORIENTED_SLAB_TRANSFORMS_INFO_KEY`.
        """

        atoms_copy = self.atoms.copy()
        atoms_copy.info = dict(getattr(self.atoms, "info", {}) or {})

        if stamp_transforms is True:
            transforms = self.oriented_slab_transforms
            if transforms is not None:
                atoms_copy.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = transforms.payload
        elif stamp_transforms is False:
            atoms_copy.info.pop(ORIENTED_SLAB_TRANSFORMS_INFO_KEY, None)

        return atoms_copy

    def __repr__(self) -> str:
        h, k, l = self.hkl  # noqa: E741 - canonical Miller index triple (h,k,l)
        f = Formula(self.atoms.get_chemical_formula(mode="metal"))
        composition = f.count()

        lines = [
            "Slab(",
            f"  composition    = {composition}",
            f"  stoichiometric = {self.is_stoichiometric}",
            f"  hkl            = ({h} {k} {l})",
            f"  Nlay           = {self.Nlay}",
        ]
        if self.spec.target_width is not None and float(self.spec.target_width) > 0.0:
            lines.append(f"  target_width   = {float(self.spec.target_width):.4f} Å")
        lines += [
            f"  slab_width     = {self.slab_width:.4f} Å",
            f"  vacuum         = {self.vacuum:.4f} Å",
            f"  pbc            = {tuple(self.atoms.pbc)}",
            ")",
        ]
        return "\n".join(lines)
