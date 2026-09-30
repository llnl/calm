"""Internal project runtime composition.

Guiding principles
------------------
- Runtime composition must not import SQLAlchemy / sqlite3 / DB-table modules directly.
- Persistence is wired via dependency injection (UnitOfWork), typically by a
  composition root such as :func:`calm.project.bootstrap.open_workspace`.

The supported user boundary is ``calm.Project``.  This internal runtime composes
application services without SQL or DB-driver awareness.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from calm.analysis.pareto import (
    AGGREGATE_STRAIN_SIZE_PARETO_POLICY,
    AGGREGATE_STRAIN_SIZE_PARETO_SCOPE,
    WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_POLICY,
    WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_SCOPE,
    strain_size_pareto,
)
from calm.calculators.spec import CalculatorSpec
from ..application._uow import fresh_uow, require_uow_factory
from ..application.artifacts import ArtifactsService
from ..application.bulks import BulksService
from ..application.calculators import CalculatorsService
from ..application.campaigns import CampaignService
from ..application.derived_interfaces import DerivedInterfaceService
from ..application.followups.service import FollowupsService
from ..application.interface_derivation import InterfaceDerivationService
from ..application.interface_searches import (
    InterfaceSearchPreparation,
    InterfaceSearchesService,
)
from ..application.prototype_analysis import PrototypeAnalysisService
from ..application.prototypes import PrototypeSearchService, PrototypesService
from ..application.runs import RunsService
from ..application.slabs import SlabsService
from ..domain.models import (
    ArtifactRef,
    Bulk,
    BulkSummary,
    Calculator,
    CalculatorSummary,
    DerivedInterface,
    Edge,
    FollowupResult,
    InterfaceSearch,
    Prototype,
    PrototypeSummary,
    Run,
    Slab,
    SlabSummary,
)
from ..presentation.workspace import (
    enriched_followup_row,
    enriched_interface_row,
    enriched_prototype_row,
    enriched_slab_row,
    format_mapping_table,
    format_payload_mapping,
    material_name,
    registry_search_plot_series,
    strain_partition_plot_series,
)
from .helpers import merge_payload


_RECONSTRUCTIBLE_DERIVED_INTERFACE_STAGES = frozenset(
    {"built", "strain_partitioned", "registry_refined"}
)


def _rehydrate_persisted_atoms(payload: Any) -> Any:
    """Decode a present persisted structure instead of masking malformed state."""

    if not isinstance(payload, Mapping):
        return payload

    from calm.exceptions import OptionalDependencyError
    from calm.structure.payloads import canonical_atoms_payload, dict_to_atoms

    from calm.slab.oriented.cell_contract import (
        validate_interface_deformation_provenance,
        validate_persisted_interface_deformation_payload,
    )

    canonical = validate_persisted_interface_deformation_payload(
        canonical_atoms_payload(dict(payload))
    )
    try:
        atoms = dict_to_atoms(canonical)
    except OptionalDependencyError:
        # The workspace artifact API remains dependency-light by returning the
        # exact validated persistence representation when ASE is unavailable.
        return canonical
    validate_interface_deformation_provenance(atoms)
    return atoms


def _workspace_plot_pareto_membership(
    prototypes: Sequence[PrototypeSummary],
) -> tuple[set[str], dict[str, Any]]:
    """Return fixed plot membership and its named population provenance."""

    records = list(prototypes)
    signatures = {
        (
            item.pareto_policy,
            item.pareto_policy_version,
            item.pareto_population_scope,
            item.pareto_population_size,
        )
        for item in records
        if item.pareto_policy is not None
        and item.pareto_policy_version is not None
        and item.pareto_population_scope is not None
        and item.pareto_d_cell_key is not None
    }
    complete_source = (
        bool(records)
        and len(signatures) == 1
        and all(
            item.pareto_policy is not None
            and item.pareto_policy_version is not None
            and item.pareto_population_scope is not None
            and item.pareto_d_cell_key is not None
            for item in records
        )
    )
    if complete_source:
        policy, version, scope, population_size = next(iter(signatures))
        front_ids = {item.uid_full for item in records if item.is_pareto}
        return front_ids, {
            "pareto_policy": policy,
            "pareto_policy_version": version,
            "pareto_population_scope": scope,
            "pareto_population_size": population_size,
            "pareto_front_uids": sorted(front_ids),
        }

    result = strain_size_pareto(
        records,
        atom_count="natoms",
        d_cell="d_cell",
        ids="uid_full",
        policy=WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_POLICY,
        population_scope=WORKSPACE_FILTERED_STRAIN_SIZE_PARETO_SCOPE,
    )
    return set(result.front_ids), {
        "pareto_policy": result.policy,
        "pareto_policy_version": result.version,
        "pareto_population_scope": result.population_scope,
        "pareto_population_size": result.population_size,
        "pareto_front_uids": list(result.front_ids),
    }


class Workspace:
    """Internal database-authoritative project runtime.

    ``Project`` is the sole supported user workflow boundary.  This class
    composes application services and exposes exact internal operations to the
    public adapter; it does not provide a second namespaced facade API.
    """

    def __init__(
        self,
        *,
        out_dir: Path,
        artifact_store: Any,
        uow_factory: Any,
        default_relaxation_backend: Any | None = None,
    ) -> None:
        self._out_dir = Path(out_dir).resolve()
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="Workspace",
        )
        # Optional default backend name for relaxation orchestration
        # (e.g. "deterministic" or "real").
        self._default_relaxation_backend = default_relaxation_backend

        self._bulks = BulksService(uow_factory=self._uow_factory)
        self._calculators = CalculatorsService(uow_factory=self._uow_factory)
        self._slabs = SlabsService(uow_factory=self._uow_factory)
        self._prototype_search = PrototypeSearchService(uow_factory=self._uow_factory)
        self._interface_searches = InterfaceSearchesService(
            uow_factory=self._uow_factory
        )
        self._prototypes = PrototypesService(uow_factory=self._uow_factory)
        # Artifacts service is used by derived interface service to persist
        # atom payloads as run-scoped artifacts. Create it before the
        # DerivedInterfaceService so it can be injected.
        self._artifacts = ArtifactsService(
            uow_factory=self._uow_factory,
            store=artifact_store,
        )
        self._derived_interfaces = DerivedInterfaceService(
            uow_factory=self._uow_factory,
            artifacts=self._artifacts,
        )
        self._campaigns = CampaignService(uow_factory=self._uow_factory)
        from calm.project.application.datasets import DatasetService

        self._dataset_service = DatasetService(uow_factory=self._uow_factory)
        # Pass uow_factory so FollowupsService constructs orchestrators from fresh UoWs
        self._followups = FollowupsService(
            uow_factory=self._uow_factory,
            artifacts=self._artifacts,
        )
        self._interface_derivation = InterfaceDerivationService(
            uow_factory=self._uow_factory,
            artifacts=self._artifacts,
        )
        self._prototype_analysis = PrototypeAnalysisService(
            uow_factory=self._uow_factory,
        )
        # Workspace methods are internal project-operation seams.

    def _fresh_uow(self) -> Any:
        """Return one fresh, non-entered Unit of Work for a single operation."""

        return fresh_uow(self._uow_factory, owner="Workspace")

    def _runs_service(self) -> RunsService:
        """Return a run service bound to one fresh Unit of Work."""

        return RunsService(self._fresh_uow())

    def create_or_get_dataset(
        self,
        *,
        name: str,
        settings: dict,
        description: str | None = None,
        tags: Sequence[str] | None = None,
    ):
        """Create or reopen a deterministic authoritative dataset."""
        return self._dataset_service.create_or_get(
            name=name,
            settings=settings,
            description=description,
            tags=tags,
        )

    def add_dataset_items(
        self,
        dataset: str,
        items: Sequence[dict],
        *,
        duplicate_policy: str = "error",
    ):
        """Append canonical authoritative item rows atomically."""
        return self._dataset_service.add_items(
            dataset,
            items,
            duplicate_policy=duplicate_policy,
        )

    def list_datasets(self, *, limit: int | None = None):
        """List authoritative datasets."""
        return self._dataset_service.list_datasets(limit=limit)

    def get_dataset(self, identifier: str):
        """Return one authoritative dataset by full ID, short ID, or name."""
        return self._dataset_service.get_dataset(identifier)

    def list_dataset_items(self, dataset: str):
        """List authoritative item rows for one dataset."""
        return self._dataset_service.list_items(dataset)

    def create_campaign(
        self,
        *,
        name: str | None = None,
        spec: dict | None = None,
        uid_full: str | None = None,
    ):
        """Create or reopen an authoritative campaign row."""
        return self._campaigns.create_or_get(
            name=name,
            spec=spec,
            uid_full=uid_full,
        )

    def create_or_get_campaign_run(
        self,
        campaign_uid_full: str,
        *,
        run_spec: dict,
        backend_id: str | None = None,
        status: str | None = None,
    ):
        """Create or get a deterministic campaign run for a campaign and spec."""
        return self._campaigns.create_or_get_run(
            campaign_uid_full,
            run_spec=run_spec,
            backend_id=backend_id,
            status=status,
        )

    def mark_campaign_run(self, campaign_run_uid_full: str, *, status: str):
        """Update the persisted status/timestamps of one campaign run."""
        return self._campaigns.mark_run(
            campaign_run_uid_full,
            status=status,
        )

    def add_provenance_edge(
        self,
        *,
        src_uid_full: str,
        dst_uid_full: str,
        kind: str,
        payload: dict | None = None,
    ):
        """Persist one authoritative provenance edge."""
        with self._fresh_uow() as uow:
            return uow.edges.add(
                src_uid_full=src_uid_full,
                dst_uid_full=dst_uid_full,
                kind=kind,
                payload=payload,
            )

    def list_campaigns(self, *, limit: int | None = None):
        """List campaigns stored in the workspace (authoritative).

        Returns a list of campaign row mappings from the repository.
        """
        with self._fresh_uow() as uow:
            return uow.campaigns.list_campaigns(limit=limit)

    def get_campaign(self, uid_or_short: str):
        """Get a campaign by uid_full or short id (y_...)."""
        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="y")
            row = uow.campaigns.get_campaign(uid_full)
        if row is None:
            raise KeyError(f"Campaign not found: {uid_or_short!r}")
        return row

    def get_campaign_run(self, uid_or_short: str):
        """Get a campaign run by uid_full or short id (x_...)."""
        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="x")
            row = uow.campaigns.get_campaign_run(uid_full)
        if row is None:
            raise KeyError(f"Campaign run not found: {uid_or_short!r}")
        return row

    def list_campaign_runs(
        self,
        *,
        campaign: str | None = None,
        limit: int | None = None,
    ):
        """List campaign runs, optionally filtered by campaign id/uid."""
        with self._fresh_uow() as uow:
            if campaign is None:
                return uow.campaigns.list_campaign_runs(limit=limit)
            campaign_uid_full = uow.ids.resolve(campaign, expected_tag="y")
            return uow.campaigns.list_campaign_runs(
                campaign_uid_full=campaign_uid_full,
                limit=limit,
            )

    def get_campaign_run_for_dataset(self, dataset: str):
        """Find the campaign_run that produced a dataset via provenance edges."""
        with self._fresh_uow() as uow:
            ds_uid = uow.ids.resolve(dataset, expected_tag="d")
            edges = uow.edges.list(src_uid_full=ds_uid, kind="produced_by", limit=1)
            if not edges:
                raise KeyError(f"No campaign run found for dataset {dataset!r}")
            run_uid = edges[0].dst_uid_full
            run_row = uow.campaigns.get_campaign_run(run_uid)
            if run_row is None:
                raise KeyError(f"Campaign run not found for dataset {dataset!r}")
            return run_row

    def get_campaign_for_dataset(self, dataset: str):
        """Find a dataset campaign through its production provenance edges."""
        with self._fresh_uow() as uow:
            ds_uid = uow.ids.resolve(dataset, expected_tag="d")
            produced = uow.edges.list(src_uid_full=ds_uid, kind="produced_by", limit=1)
            if not produced:
                raise KeyError(f"No campaign found for dataset {dataset!r}")
            run_uid = produced[0].dst_uid_full
            run_edges = uow.edges.list(
                src_uid_full=run_uid,
                kind="run_of_campaign",
                limit=1,
            )
            if not run_edges:
                raise KeyError(f"No campaign found for dataset {dataset!r}")
            campaign_uid = run_edges[0].dst_uid_full
            campaign_row = uow.campaigns.get_campaign(campaign_uid)
            if campaign_row is None:
                raise KeyError(f"Campaign not found for dataset {dataset!r}")
            return campaign_row

    def persist_interface_prototypes(
        self,
        prototypes: Sequence[Any],
        *,
        run_uid_full: str | None = None,
    ) -> dict[str, dict[str, str]]:
        """Persist current interface prototypes through the owning service."""
        return self._prototypes.persist_interface_prototypes(
            prototypes,
            run_uid_full=run_uid_full,
        )

    # ================= Canonical direct API =================

    # --------------------------- Bulks ---------------------------

    def add_bulk(
        self,
        *,
        structure: Any | None = None,
        label: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
        kind: str = "reference",
        optimized_with: CalculatorSpec | str | None = None,
    ) -> Bulk:
        """Add a bulk structure to the workspace.

        Args:
            structure: ASE-compatible structure or supported structure input.
            label: Optional user-facing material label.
            payload: Additional persisted metadata.
            kind: Bulk-state classification, such as ``'reference'``.
            optimized_with: Optional calculator provenance.

        Returns:
            The persisted bulk record.
        """
        return self._bulks.add_bulk(
            structure=structure,
            label=label,
            payload=payload,
            kind=kind,
            optimized_with=optimized_with,
        )

    def add_bulk_from_poscar(
        self,
        poscar_path: str | Path,
        *,
        label: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
        kind: str = "reference",
        optimized_with: CalculatorSpec | str | None = None,
    ) -> Bulk:
        """Load a POSCAR/CONTCAR-like file and upsert a bulk.

        Notes
        -----
        - The Bulk UID is computed from a canonicalized structure fingerprint (see
          ``calm.project.application.bulks``). This makes the operation idempotent
          across script re-runs and tolerant to small numerical noise in the file.
        - File provenance is recorded in payload metadata (name + sha256).
        """

        # Local import keeps runtime composition lightweight without ASE.
        try:
            from ase.io import read as ase_read  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("ASE is required to load POSCAR files") from exc

        from calm.serialization.regression import sha256_hex

        p = Path(poscar_path)
        if not p.exists():
            raise FileNotFoundError(f"POSCAR file not found: {p}")

        if label is None:
            label = p.stem

        atoms = ase_read(str(p), format="vasp")

        meta: dict[str, Any] = dict(payload) if payload is not None else {}
        meta.setdefault("source_format", "poscar")
        meta.setdefault("source_name", p.name)
        meta.setdefault("source_sha256", sha256_hex(p.read_bytes()))

        return self._bulks.add_bulk(
            structure=atoms,
            label=label,
            payload=meta,
            kind=kind,
            optimized_with=optimized_with,
        )

    def list_bulks(self, *, limit: int | None = None) -> list[BulkSummary]:
        return self._bulks.list_bulks(limit=50 if limit is None else limit)

    def get_bulk(self, uid_or_short: str) -> Bulk:
        """Get a bulk by uid_full ("bulk:...") or short id ("b_...")."""
        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="b")
            bulk = uow.bulks.get_by_uid_full(uid_full)

        if bulk is None:
            raise KeyError(f"Bulk not found: {uid_or_short!r}")
        return bulk

    def find_bulk_by_material(
        self,
        material: str,
        *,
        kind: str | None = None,
        limit: int = 200,
    ) -> Bulk | None:
        """Find a bulk by material name and optional kind.

        Parameters
        ----------
        material : str
            Material name to search for (e.g., "LiF", "Li2O").
            Matches if material appears in the bulk's label.
        kind : str, optional
            Bulk kind to filter by (e.g., "optimized", "experimental").
            If None, any kind is accepted.
        limit : int, default=200
            Maximum number of bulks to search through.

        Returns
        -------
        Bulk or None
            The first matching bulk, or None if not found.

        Examples
        --------
        >>> lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
        >>> li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")
        """
        all_bulks = self.list_bulks(limit=limit)

        # Filter by kind if specified
        if kind is not None:
            bulks = [b for b in all_bulks if b.kind == kind]
        else:
            bulks = all_bulks

        # Find first bulk matching material name in label
        for bulk in bulks:
            if bulk.label and material in bulk.label:
                return self.get_bulk(bulk.id_short)

        return None

    # ------------------------ Bulk Relaxation ---------------------

    def relax_bulk(
        self,
        bulk: str | Bulk,
        *,
        optimized_with: CalculatorSpec,
        label: str | None = None,
        kind: str = "optimized",
        fmax: float = 0.03,
        steps: int = 200,
        logfile: str | None = None,
        reuse_existing: bool = True,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Bulk:
        """Relax a bulk with variable-cell degrees of freedom and persist it.

        This is a common workflow step (reference bulk → relaxed bulk). It is
        provided as a first-class CALM UX method so example scripts do not need
        to implement their own relaxation helper functions.

        Parameters
        ----------
        bulk:
            Reference bulk id_short or a :class:`~calm.project.domain.models.Bulk`.
        optimized_with:
            Calculator spec (e.g., GRACE) to attach during relaxation.
        label:
            Label for the optimized bulk. If omitted, a label is derived from the
            reference bulk.
        kind:
            Kind string for the stored bulk (default: ``"optimized"``).
        fmax, steps:
            ASE optimizer stopping criteria.
        logfile:
            Optional ASE optimizer logfile path.
        reuse_existing:
            If True, return an existing optimized bulk when present (matched
            by (label, kind) and, when available, the (family:model) calculator tag).
        payload:
            Optional payload JSON merged into the stored optimized bulk payload.

        Returns
        -------
        Bulk
            The optimized bulk record.
        """

        # Resolve reference bulk.
        ref = bulk if isinstance(bulk, Bulk) else self.get_bulk(bulk)

        # Derive output label early so we can also use it for cache/reuse checks.
        out_label = label or (ref.label + " (optimized)")

        # Optional fast-path: reuse an existing optimized record.
        #
        # For user-facing UX, the simplest and most reliable key is the label.
        # We additionally check the (family:model) calculator tag when available.
        if reuse_existing:
            expected_calc = f"{optimized_with.family}:{optimized_with.model}"
            for b in self.list_bulks(limit=500):
                if b.kind != kind:
                    continue
                if b.label != out_label:
                    continue
                if b.calculator is not None and b.calculator != expected_calc:
                    continue
                return self.get_bulk(b.id_short)

        # Build calculator.
        from calm.calculators.api import make_calculator

        calc = make_calculator(optimized_with)

        # Prepare an ASE Atoms working copy.
        atoms_ref = ref.atoms_conventional
        if atoms_ref is None:
            raise ValueError(
                f"Bulk {ref.id_short!r} does not have a stored structure. "
                "Create the bulk with `add_bulk(structure=...)` before "
                "calling relax_bulk()."
            )
        atoms = atoms_ref.copy()
        atoms.calc = calc

        # Run a variable-cell relaxation (ASE BFGS + UnitCellFilter).
        try:
            from ase.optimize import BFGS  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "ASE is required for relax_bulk(). Install with: pip install ase"  # noqa: E501
            ) from e

        # UnitCellFilter moved across ASE versions; prefer the modern location.
        try:
            from ase.filters import UnitCellFilter  # type: ignore
        except ImportError:  # pragma: no cover
            from ase.constraints import UnitCellFilter  # type: ignore

        ucf = UnitCellFilter(atoms)
        opt = BFGS(ucf, logfile=logfile)
        opt.run(fmax=fmax, steps=steps)

        # Persist optimized structure.
        out_payload: dict[str, Any] = {}
        if payload:
            out_payload.update(dict(payload))
        out_payload.update(
            {
                "optimized_from": ref.id_short,
                "optimized_from_uid_full": ref.uid_full,
                "relaxation": {
                    "driver": "ase.optimize.BFGS+UnitCellFilter",
                    "fmax": fmax,
                    "steps": steps,
                },
            }
        )

        return self.add_bulk(
            structure=atoms,
            label=out_label,
            kind=kind,
            optimized_with=optimized_with,
            payload=out_payload,
        )

    # ------------------------ Calculators ------------------------

    def register_calculator(self, spec: CalculatorSpec) -> Calculator:
        """Register a calculator spec and return the persisted record."""

        return self._calculators.register(spec)

    def get_calculator(self, uid_or_short: str) -> Calculator | None:
        """Get a calculator by uid_full ("calc:...") or short id ("c_...")."""

        return self._calculators.get(uid_or_short)

    def list_calculators(self, *, limit: int | None = None) -> list[CalculatorSummary]:
        return self._calculators.list(limit=50 if limit is None else limit)

    # --------------------------- Slabs ---------------------------

    def add_slab(
        self,
        *,
        bulk: str,
        miller: Sequence[int] | None = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Slab:
        """Convenience wrapper to build a single slab."""

        if miller is None:
            raise ValueError("miller must be provided")

        slabs = self._slabs.build_slabs(bulk, millers=[tuple(miller)], payload=payload)
        return slabs[0]

    def build_slabs(
        self,
        bulk: str,
        *,
        millers: Sequence[Sequence[int]],
        payload: Optional[Mapping[str, Any]] = None,
        params: Optional[Mapping[str, Any]] = None,
        enumerate_terminations: bool = False,
    ) -> list[Slab]:
        """Build and persist slabs through the owning application service."""
        return self._slabs.build_slabs(
            bulk,
            millers=[tuple(miller) for miller in millers],
            payload=None if payload is None else dict(payload),
            params=None if params is None else dict(params),
            enumerate_terminations=enumerate_terminations,
        )

    def list_slabs(
        self,
        bulk: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[SlabSummary]:
        """List durable slab summaries without mutating persisted identity."""
        return self._slabs.list_slabs(
            bulk_id=bulk,
            limit=50 if limit is None else limit,
        )

    def get_slab(self, uid_or_short: str) -> Slab:
        """Get a slab by current full or short identifier."""
        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="s")
            slab = uow.slabs.get_by_uid_full(uid_full)
        if slab is None:
            raise KeyError(f"Slab not found: {uid_or_short!r}")
        return slab

    def list_slabs_enriched(
        self,
        bulk: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List current slabs with typed material and geometry context."""

        summaries = self.list_slabs(bulk=bulk, limit=limit)
        rows: list[dict[str, Any]] = []
        with self._fresh_uow() as uow:
            bulk_cache: dict[str, Bulk] = {}
            for summary in summaries:
                slab = uow.slabs.get_by_uid_full(summary.uid_full)
                if slab is None:
                    raise RuntimeError(
                        f"Slab summary {summary.uid_full!r} has no full record."
                    )
                parent = bulk_cache.get(summary.bulk_uid_full)
                if parent is None:
                    parent = uow.bulks.get_by_uid_full(summary.bulk_uid_full)
                    if parent is None:
                        raise RuntimeError(
                            f"Slab {summary.uid_full!r} has no parent bulk."
                        )
                    bulk_cache[summary.bulk_uid_full] = parent
                rows.append(enriched_slab_row(summary, slab=slab, bulk=parent))
        return rows

    def list_runs(
        self,
        *,
        run_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """List runs with optional filtering.

        Parameters
        ----------
        run_type
            Filter by run type, such as ``prototype_search``,
            ``strain_partition_scan``, or ``registry_search``.
        status
            Filter by status (e.g., "queued", "running", "done", "failed")
        limit
            Maximum number of runs to return

        Returns
        -------
        list
            List of Run objects matching the criteria
        """
        # Use repository-backed runs listing to avoid adding list_runs to the
        # query facade; preserve original DB-backed behavior.
        with self._fresh_uow() as uow:
            return uow.runs.list(limit=limit, run_type=run_type, status=status)

    def list_prototypes_enriched(
        self,
        *,
        run: str | None = None,
        pareto: bool = False,
        limit: int | None = None,
        order_by: str | None = "match_score",
    ) -> list[dict[str, Any]]:
        """List current prototypes with exact slab and bulk context."""

        prototypes = self.list_prototypes(
            run=run,
            pareto=pareto,
            limit=limit,
            order_by=order_by,
        )
        rows: list[dict[str, Any]] = []
        slab_cache: dict[str, Slab] = {}
        bulk_cache: dict[str, Bulk] = {}
        with self._fresh_uow() as uow:
            for prototype in prototypes:
                slab_a = slab_cache.get(prototype.slab_a_uid_full)
                if slab_a is None:
                    slab_a = uow.slabs.get_by_uid_full(prototype.slab_a_uid_full)
                    if slab_a is None:
                        raise RuntimeError(
                            f"Prototype {prototype.uid_full!r} has no slab A."
                        )
                    slab_cache[prototype.slab_a_uid_full] = slab_a

                slab_b = slab_cache.get(prototype.slab_b_uid_full)
                if slab_b is None:
                    slab_b = uow.slabs.get_by_uid_full(prototype.slab_b_uid_full)
                    if slab_b is None:
                        raise RuntimeError(
                            f"Prototype {prototype.uid_full!r} has no slab B."
                        )
                    slab_cache[prototype.slab_b_uid_full] = slab_b

                bulk_a = bulk_cache.get(slab_a.bulk_uid_full)
                if bulk_a is None:
                    bulk_a = uow.bulks.get_by_uid_full(slab_a.bulk_uid_full)
                    if bulk_a is None:
                        raise RuntimeError(
                            f"Slab {slab_a.uid_full!r} has no parent bulk."
                        )
                    bulk_cache[slab_a.bulk_uid_full] = bulk_a

                bulk_b = bulk_cache.get(slab_b.bulk_uid_full)
                if bulk_b is None:
                    bulk_b = uow.bulks.get_by_uid_full(slab_b.bulk_uid_full)
                    if bulk_b is None:
                        raise RuntimeError(
                            f"Slab {slab_b.uid_full!r} has no parent bulk."
                        )
                    bulk_cache[slab_b.bulk_uid_full] = bulk_b

                rows.append(
                    enriched_prototype_row(
                        prototype,
                        slab_a=slab_a,
                        slab_b=slab_b,
                        bulk_a=bulk_a,
                        bulk_b=bulk_b,
                    )
                )
        return rows

    def get_slab_param(
        self,
        slab: Slab,
        param_name: str,
        default: Any = None,
    ) -> Any:
        """Return one parameter from the current slab payload schema."""

        if not isinstance(slab, Slab):
            raise TypeError("get_slab_param() requires a current Slab record.")
        params = (slab.payload or {}).get("params")
        if params is None:
            return default
        if not isinstance(params, Mapping):
            raise TypeError("Slab payload 'params' must be a mapping.")
        return params.get(param_name, default)

    def group_slabs_by_material(
        self,
        slabs: list[Slab] | None = None,
    ) -> dict[str, list[Slab]]:
        """Group current slab records by their exact parent material."""

        summaries = None if slabs is not None else self.list_slabs(limit=10000)
        grouped: dict[str, list[Slab]] = defaultdict(list)
        bulk_cache: dict[str, Bulk] = {}
        with self._fresh_uow() as uow:
            if slabs is None:
                records: list[Slab] = []
                for summary in summaries or []:
                    record = uow.slabs.get_by_uid_full(summary.uid_full)
                    if record is None:
                        raise RuntimeError(
                            f"Slab summary {summary.uid_full!r} has no full record."
                        )
                    records.append(record)
            else:
                records = list(slabs)

            for slab in records:
                if not isinstance(slab, Slab):
                    raise TypeError("group_slabs_by_material() requires Slab records.")
                parent = bulk_cache.get(slab.bulk_uid_full)
                if parent is None:
                    parent = uow.bulks.get_by_uid_full(slab.bulk_uid_full)
                    if parent is None:
                        raise RuntimeError(
                            f"Slab {slab.uid_full!r} has no parent bulk."
                        )
                    bulk_cache[slab.bulk_uid_full] = parent
                grouped[material_name(parent)].append(slab)
        return dict(grouped)

    def group_slabs_by_miller(
        self,
        slabs: list[Slab],
    ) -> dict[str, list[Slab]]:
        """Group current slab records by exact Miller index."""

        grouped: dict[str, list[Slab]] = defaultdict(list)
        for slab in slabs:
            if not isinstance(slab, Slab):
                raise TypeError("group_slabs_by_miller() requires Slab records.")
            grouped[str(tuple(int(value) for value in slab.miller))].append(slab)
        return dict(grouped)

    def list_derived_interfaces_enriched(
        self,
        *,
        prototype: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List current derived-interface specifications as display rows."""

        return [
            enriched_interface_row(interface)
            for interface in self.list_derived_interfaces(
                prototype=prototype,
                limit=limit,
            )
        ]

    def list_followup_results_enriched(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List current follow-up records as stable JSON-friendly rows."""

        results = self.list_followup_results(
            run=run,
            prototype=prototype,
            kind=kind,
            limit=limit,
        )
        if status is not None:
            results = [result for result in results if result.status == status]
        return [enriched_followup_row(result) for result in results]

    def export_poscar(
        self,
        obj: Any,
        path: str | Path,
        *,
        format: str = "vasp",
    ) -> Path:
        """Export one current ASE, Bulk, or Slab structure."""

        try:
            from ase import Atoms
            from ase.io import write
        except ImportError as exc:
            raise RuntimeError("ASE is required for structure export.") from exc

        if isinstance(obj, Atoms):
            atoms = obj
        elif isinstance(obj, Bulk):
            atoms = obj.atoms_conventional
        elif isinstance(obj, Slab):
            atoms = obj.atoms
        else:
            raise TypeError("export_poscar() accepts ase.Atoms, Bulk, or Slab records.")
        if atoms is None:
            raise ValueError(f"{type(obj).__name__} has no persisted atoms.")

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write(output_path, atoms, format=format)
        return output_path

    def export_bulks_as_poscar(
        self,
        bulk_ids: list[str] | None = None,
        output_dir: str | Path = "bulk_poscars",
        *,
        include_primitive: bool = True,
        include_conventional: bool = True,
    ) -> dict[str, list[Path]]:
        """Export selected current bulk cells without suppressing failures."""

        if not include_primitive and not include_conventional:
            raise ValueError("Select at least one bulk cell representation.")
        identifiers = (
            [bulk.id_short for bulk in self.list_bulks(limit=10000)]
            if bulk_ids is None
            else list(bulk_ids)
        )
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        exported: dict[str, list[Path]] = {}
        for identifier in identifiers:
            bulk = self.get_bulk(identifier)
            stem = bulk.label.strip().replace(" ", "_") or bulk.id_short
            paths: list[Path] = []
            if include_conventional:
                atoms = bulk.atoms_conventional
                if atoms is None:
                    raise ValueError(
                        f"Bulk {bulk.id_short!r} has no conventional atoms."
                    )
                paths.append(
                    self.export_poscar(
                        atoms,
                        directory / f"{stem}_conventional.vasp",
                    )
                )
            if include_primitive:
                atoms = bulk.atoms_primitive
                if atoms is None:
                    raise ValueError(f"Bulk {bulk.id_short!r} has no primitive atoms.")
                paths.append(
                    self.export_poscar(
                        atoms,
                        directory / f"{stem}_primitive.vasp",
                    )
                )
            exported[bulk.id_short] = paths
        return exported

    def export_slabs_as_poscar(
        self,
        slab_ids: list[str] | None = None,
        output_dir: str | Path = "slab_poscars",
    ) -> dict[str, Path]:
        """Export selected current slabs with explicit failure propagation."""

        identifiers = (
            [slab.id_short for slab in self.list_slabs(limit=10000)]
            if slab_ids is None
            else list(slab_ids)
        )
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        exported: dict[str, Path] = {}
        for identifier in identifiers:
            slab = self.get_slab(identifier)
            if slab.atoms is None:
                raise ValueError(f"Slab {slab.id_short!r} has no persisted atoms.")
            bulk = self.get_bulk(slab.bulk_id_short)
            miller = "".join(str(int(value)) for value in slab.miller)
            path = directory / (f"{material_name(bulk)}_{miller}_{slab.id_short}.vasp")
            exported[slab.id_short] = self.export_poscar(slab, path)
        return exported

    def export_derived_interfaces_as_poscar(
        self,
        output_dir: str | Path,
        *,
        interface_ids: list[str] | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Path]:
        """Export exact current derived interfaces as POSCAR files."""

        from calm.project.application.followups.interface_energy import (
            build_interface_from_prototype_with_strain,
        )

        interfaces = (
            self.list_derived_interfaces(limit=10000)
            if interface_ids is None
            else [
                self.get_derived_interface(identifier) for identifier in interface_ids
            ]
        )
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        exported: dict[str, Path] = {}
        for interface in interfaces:
            if interface.atoms_artifact_uid is not None:
                atoms = self.get_derived_interface_atoms(interface.id_short)
            else:
                alpha = interface.strain_alpha
                z_padding = interface.z_padding
                translation = interface.registry_shift_frac_a
                with self._fresh_uow() as uow:
                    atoms = build_interface_from_prototype_with_strain(
                        uow=uow,
                        prototype_uid_full=interface.prototype_uid_full,
                        alpha=alpha,
                        translation_frac=translation,
                        z_padding=z_padding,
                        vacuum_padding=interface.vacuum,
                    )

            prototype = self.get_prototype(interface.prototype_uid_full)
            stem = interface.id_short
            if include_metadata:
                stem = f"{stem}_{prototype.id_short}_alpha{interface.strain_alpha:.2f}"
            path = directory / f"{stem}.vasp"
            exported[interface.id_short] = self.export_poscar(atoms, path)
        return exported

    def format_payload(self, obj: Any, max_list_items: int = 5) -> str:
        """Format one current project payload mapping for display."""

        if isinstance(obj, Mapping):
            payload = obj
        elif isinstance(obj, (Bulk, Slab, Prototype)):
            payload = obj.payload
        else:
            raise TypeError(
                "format_payload() accepts a mapping, Bulk, Slab, or Prototype."
            )
        return format_payload_mapping(
            payload,
            max_list_items=max_list_items,
        )

    def get_workspace_stats(self) -> dict[str, int]:
        """Return current database-authoritative workspace counts."""

        prototypes = self.list_prototypes(limit=10000)
        runs = self.list_runs(limit=10000)
        return {
            "bulks": len(self.list_bulks(limit=10000)),
            "slabs": len(self.list_slabs(limit=10000)),
            "prototypes": len(prototypes),
            "pareto_prototypes": sum(
                1 for prototype in prototypes if prototype.is_pareto
            ),
            "derived_interfaces": len(self.list_derived_interfaces(limit=10000)),
            "runs": len(runs),
            "prototype_search_runs": sum(
                1 for run in runs if run.run_type == "prototype_search"
            ),
            "strain_scan_runs": sum(
                1 for run in runs if run.run_type == "strain_partition_scan"
            ),
            "registry_search_runs": sum(
                1 for run in runs if run.run_type == "registry_search"
            ),
        }

    def format_table(
        self,
        data: Sequence[Mapping[str, Any]],
        headers: Sequence[str] | None = None,
        *,
        style: str = "grid",
    ) -> str:
        """Format current mapping rows for terminal or notebook display."""

        return format_mapping_table(data, headers=headers, style=style)

    def analyze_prototype_strain(
        self,
        prototype_id: str,
        *,
        alpha: float = 0.5,
        eigengap_atol: float = 1.0e-12,
        eigengap_rtol: float = 1.0e-3,
    ) -> dict[str, Any]:
        """Analyze current prototype strain through the application service."""

        return self._prototype_analysis.analyze_prototype_strain(
            prototype_id,
            alpha=alpha,
            eigengap_atol=eigengap_atol,
            eigengap_rtol=eigengap_rtol,
        )

    def get_principal_strain_directions_crystallographic(
        self,
        prototype_id: str,
        *,
        alpha: float = 0.5,
        eigengap_atol: float = 1.0e-12,
        eigengap_rtol: float = 1.0e-3,
        max_index: int = 6,
        max_angular_error_deg: float = 1.0,
    ) -> dict[str, Any]:
        """Map resolved prototype strain axes into conventional coordinates."""

        return (
            self._prototype_analysis.get_principal_strain_directions_crystallographic(
                prototype_id,
                alpha=alpha,
                eigengap_atol=eigengap_atol,
                eigengap_rtol=eigengap_rtol,
                max_index=max_index,
                max_angular_error_deg=max_angular_error_deg,
            )
        )

    def check_prototype_buildability(self, prototype: str):
        """Workspace-level adapter that exposes application-layer buildability.

        This opens a UnitOfWork and calls the application service helper so
        callers (public layer) can perform authoritative checks without
        importing infrastructure modules.
        """
        from ..application.buildability import check_prototype_buildability

        with self._fresh_uow() as uow:
            return check_prototype_buildability(uow, prototype)

    def check_prototypes_buildability(self, prototypes: list[str]) -> dict[str, object]:
        """Batch authoritative buildability adapter.

        Returns a mapping uid_full -> PrototypeBuildability (application-level)
        for prototypes that could be resolved. If none resolved, returns {}.
        """
        from ..application.buildability import check_prototypes_buildability

        with self._fresh_uow() as uow:
            return check_prototypes_buildability(uow, prototypes)

    # --------------------------- Prototypes ---------------------------

    def start_prototype_search(
        self,
        slab_a: str,
        slab_b: str,
        *,
        label: str | None = None,
        params: Optional[Mapping[str, Any]] = None,
        n_candidates: int = 12,
        k_max: int = 10,
        w_match: float = 0.5,
        eps_principal_max: float = 0.15,
        N_at_max: int = 1000,
        surface_symmetry_mode: str = "discover",
        surface_symprec: float = 1e-5,
        surface_angle_tolerance: float = 1e-8,
        surface_metric_tolerance: float = 1e-5,
    ) -> Run:
        """Start a prototype search between two slabs.

        Parameters
        ----------
        slab_a, slab_b : str
            Slab IDs (short or full) to match.
        label : str, optional
            Human-readable label for this search.
        params : Mapping, optional
            Additional parameters to store.
        n_candidates : int, default=12
            Maximum number of top matches to return.
        k_max : int, default=10
            Maximum supercell index (determinant) to enumerate.
        w_match : float, default=0.5
            Weight for match score = w_match × d̃_cell + (1-w_match) × d̃_size.
            Range [0, 1]: 0=prioritize small interfaces, 1=prioritize lattice match.
        eps_principal_max : float, default=0.15
            Maximum principal strain (in natural log units) to accept.
        N_at_max : int, default=1000
            Maximum total atoms in interface to accept.

        Returns
        -------
        Run
            The created search run record.
        """
        merged = dict(params or {})
        if label is not None:
            merged["label"] = str(label)

        return self._prototype_search.start_search(
            slab_a=slab_a,
            slab_b=slab_b,
            params=merged,
            n_candidates=n_candidates,
            k_max=k_max,
            w_match=w_match,
            eps_principal_max=eps_principal_max,
            N_at_max=N_at_max,
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=surface_symprec,
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=surface_metric_tolerance,
        )

    def run_miller_combination_search(
        self,
        slabs_a: list[SlabSummary],
        slabs_b: list[SlabSummary],
        *,
        n_candidates: int = 500,
        k_max: int = 12,
        w_match: float = 0.5,
        eps_principal_max: float = 0.15,
        N_at_max: int = 1000,
        generate_plots: bool = True,
        x: str = "natoms",
        y: str = "hencky_norm",
    ) -> list[Run]:
        """Run prototype searches for all combinations of two slab lists.

        This is a convenience method for comprehensive Miller index searches.
        It runs a prototype search for every (slab_a, slab_b) pair and optionally
        generates individual Pareto plots for each search.

        Parameters
        ----------
        slabs_a : list
            List of slabs from first material (e.g., all LiF slabs).
        slabs_b : list
            List of slabs from second material (e.g., all Li2O slabs).
        n_candidates : int, default=500
            Maximum number of prototypes to return per search.
        k_max : int, default=12
            Maximum supercell determinant to enumerate.
        w_match : float, default=0.5
            Weight for match score balancing.
        eps_principal_max : float, default=0.15
            Maximum principal strain to accept.
        N_at_max : int, default=1000
            Maximum total atoms in interface to accept.
        generate_plots : bool, default=True
            If True, generates individual Pareto plot for each search.
        x : str, default="natoms"
            X-axis attribute for plots.
        y : str, default="hencky_norm"
            Y-axis attribute for plots.

        Returns
        -------
        list[Run]
            List of all search runs created.

        Examples
        --------
        >>> # Get slabs for two materials
        >>> lif_bulk = ws.find_bulk_by_material("LiF", kind="optimized")
        >>> li2o_bulk = ws.find_bulk_by_material("Li2O", kind="optimized")
        >>> all_slabs = ws.list_slabs(limit=100)
        >>> lif_slabs = [s for s in all_slabs if s.bulk_id_short == lif_bulk.id_short]
        >>> li2o_slabs = [s for s in all_slabs if s.bulk_id_short == li2o_bulk.id_short]
        >>>
        >>> # Run comprehensive search
        >>> runs = ws.run_miller_combination_search(
        ...     lif_slabs,
        ...     li2o_slabs,
        ...     n_candidates=500,
        ...     generate_plots=True,
        ... )
        >>>
        >>> # Generate aggregate analysis
        >>> ws.pareto_plot_aggregate([r.id_short for r in runs])
        >>> ws.display_pareto_summary([r.id_short for r in runs])
        """
        if not slabs_a or not slabs_b:
            raise ValueError("Both slab lists must be non-empty.")
        if any(not isinstance(slab, SlabSummary) for slab in [*slabs_a, *slabs_b]):
            raise TypeError(
                "run_miller_combination_search() requires SlabSummary records."
            )

        bulk_a = self.get_bulk(slabs_a[0].bulk_uid_full)
        bulk_b = self.get_bulk(slabs_b[0].bulk_uid_full)
        material_a = material_name(bulk_a)
        material_b = material_name(bulk_b)

        n_pairs = len(slabs_a) * len(slabs_b)
        print(
            f"\nRunning prototype searches for all {len(slabs_a)} × "
            f"{len(slabs_b)} = {n_pairs} slab pairs..."
        )

        runs = []
        for slab_a in slabs_a:
            for slab_b in slabs_b:
                # Create descriptive label
                label = f"{material_a}-{slab_a.miller} vs {material_b}-{slab_b.miller}"
                print(f"\n  Searching: {label}")

                # Run search
                run = self.start_prototype_search(
                    slab_a.id_short,
                    slab_b.id_short,
                    n_candidates=n_candidates,
                    k_max=k_max,
                    w_match=w_match,
                    eps_principal_max=eps_principal_max,
                    N_at_max=N_at_max,
                    label=label,
                )

                # Get results count
                protos = self.list_prototypes(run=run.id_short)
                pareto = self.list_prototypes(run=run.id_short, pareto=True)
                print(
                    f"    Run {run.id_short}: {len(protos)} prototypes, "
                    f"{len(pareto)} Pareto optimal"
                )

                # Generate plot if requested
                if generate_plots:
                    plot_filename = (
                        f"pareto_{run.id_short[:8]}_{slab_a.miller}_{slab_b.miller}.png"
                    )
                    self.pareto_plot(
                        run.id_short,
                        filename=plot_filename,
                        x=x,
                        y=y,
                    )

                runs.append(run)

        print(f"\nCompleted {len(runs)} prototype searches")
        return runs

    def list_prototypes(
        self,
        *,
        run: str | None = None,
        pareto: bool | None = None,
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[PrototypeSummary]:
        """List prototype matches produced by persisted searches.

        Args:
            run: Optional run identifier used to restrict the query.
            pareto: Restrict by persisted Pareto membership when specified.
            max_hencky_norm: Optional upper strain bound.
            min_match_score: Optional lower match-score bound.
            order_by: Optional supported ordering key.
            limit: Maximum number of summaries to return.

        Returns:
            Prototype summaries satisfying the requested filters.
        """
        return self._prototypes.list_prototypes(
            run=run,
            pareto_only=pareto,
            max_hencky_norm=max_hencky_norm,
            min_match_score=min_match_score,
            order_by=order_by,
            limit=limit,
        )

    def get_prototype(self, uid_or_short: str) -> Prototype:
        """Get a prototype by uid_full ("proto:...") or short id ("p_...")."""

        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="p")
            proto = uow.prototypes.get_by_uid_full(uid_full)

        if proto is None:
            raise KeyError(f"Prototype not found: {uid_or_short!r}")
        return proto

    # -----------------------------------------------------------------------------
    # Derived interfaces
    # -----------------------------------------------------------------------------

    def create_derived_interface(
        self,
        prototype: str,
        *,
        label: str | None = None,
        stage: str | None = None,
        strain_alpha: float | None = None,
        registry_shift_frac_a: tuple[float, float] | None = None,
        z_padding: float | None = None,
        vacuum: float | None = None,
        params: Optional[Mapping[str, Any]] = None,
        atoms: Any | None = None,
        strain_state: Optional[Mapping[str, Any]] = None,
    ) -> DerivedInterface:
        """Create (or reuse) a spec-only derived interface variant.

        The returned record stores a content-addressed spec that can be used to
        reconstruct an instantiated interface on demand.

        Notes
        -----
        - ``label`` is metadata and does *not* affect the derived-interface UID.
        - ``params`` *does* affect the UID.
        """

        return self._derived_interfaces.create(
            prototype=prototype,
            label=label,
            stage=stage,
            strain_alpha=strain_alpha,
            registry_shift_frac_a=registry_shift_frac_a,
            z_padding=z_padding,
            vacuum=vacuum,
            params=params,
            atoms=atoms,
            strain_state=strain_state,
        )

    def list_derived_interfaces(
        self,
        *,
        prototype: str | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[DerivedInterface]:
        """List derived interfaces, optionally filtered by prototype."""

        return self._derived_interfaces.list(
            prototype=prototype,
            limit=limit,
            order_by=order_by,
            descending=descending,
        )

    def get_derived_interface(self, uid_or_short: str) -> DerivedInterface:
        """Get a derived interface by uid_full ("iface:...") or short id ("i_...")."""

        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(uid_or_short, expected_tag="i")
            iface = uow.derived_interfaces.get_by_uid_full(uid_full)

        if iface is None:
            raise KeyError(f"Derived interface not found: {uid_or_short!r}")
        return iface

    def get_derived_interface_atoms(self, iface: str):
        """Return the current artifact-backed atoms for a derived interface.

        Serialized mappings are rehydrated to ``ase.Atoms`` whenever ASE is
        installed; dependency-light callers receive the persisted mapping.
        """
        with self._fresh_uow() as uow:
            uid_full = uow.ids.resolve(iface, expected_tag="i")
            derived_interface = uow.derived_interfaces.get_by_uid_full(uid_full)
            if derived_interface is None:
                raise KeyError(f"Derived interface not found: {iface!r}")

            artifact_uid = derived_interface.atoms_artifact_uid
            if artifact_uid is None:
                raise KeyError(f"No atoms available for derived interface: {iface!r}")

            artifact = uow.artifacts.get_by_uid_full(artifact_uid)
            if artifact is None:
                raise KeyError(f"Artifact not found: {artifact_uid}")

            data = self.open_artifact(artifact, mode="json")
            return _rehydrate_persisted_atoms(data)

    def materialize_derived_interface_atoms(
        self,
        iface: str,
        *,
        registry_shift_frac_a: Sequence[float] | None = None,
    ):
        """Return exact current atoms for an artifact-backed or reconstructible interface.

        Artifact-backed structures are loaded verbatim. Spec-only ``built``,
        ``strain_partitioned``, and ``registry_refined`` interfaces are
        reconstructed from their persisted prototype, strain allocation,
        registry coordinate, internal gap, and vacuum. An explicit registry
        coordinate requests a non-persisted structural variant.
        """

        derived_interface = self.get_derived_interface(iface)
        if (
            registry_shift_frac_a is None
            and derived_interface.atoms_artifact_uid is not None
        ):
            return self.get_derived_interface_atoms(derived_interface.uid_full)

        stage = derived_interface.stage
        if stage not in _RECONSTRUCTIBLE_DERIVED_INTERFACE_STAGES:
            if registry_shift_frac_a is not None:
                raise KeyError(
                    "An alternate registry shift cannot be reconstructed for "
                    f"persisted interface stage {stage!r}."
                )
            raise KeyError(
                "No atoms artifact is available for persisted interface stage "
                f"{stage!r}; that stage cannot be reconstructed from its "
                "construction specification."
            )

        from calm.project.domain.contracts.derived_interface import (
            canonical_registry_shift,
        )

        stored_shift = derived_interface.registry_shift_frac_a
        requested = (
            stored_shift
            if registry_shift_frac_a is None
            else registry_shift_frac_a
        )
        shift = canonical_registry_shift(requested)
        built = self.build_interface_from_prototype(
            derived_interface.prototype_uid_full,
            alpha=float(derived_interface.strain_alpha),
            translation_frac=(float(shift[0]), float(shift[1])),
            z_padding=float(derived_interface.z_padding),
            vacuum=derived_interface.vacuum,
        )
        atoms = getattr(built, "atoms", None)
        if atoms is None:
            raise RuntimeError(
                "Interface reconstruction did not return atomistic content."
            )
        from calm.slab.oriented.cell_contract import (
            validate_interface_deformation_provenance,
        )

        validate_interface_deformation_provenance(atoms, require_source=True)
        return atoms

    def derive_interfaces_from_strain_partition_scan(
        self,
        scan_run: str,
        *,
        label: str | None = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> list[DerivedInterface]:
        """Create derived interfaces from a completed strain-partition scan.

        This is a convenience for chaining workflows:

        1) Run ``start_strain_partition_scan`` over one or more seeds.
        2) Convert the best (prototype, alpha) summary in each followup result
           into a spec-only :class:`~calm.project.domain.models.DerivedInterface`.
        3) Feed those interface ids (``i_...``) into downstream followups such as
           ``start_registry_search``.

        If the scan was *seeded with a derived interface* (``i_...``), any
        existing registry-shift/vacuum parameters from that seed are preserved
        in the newly created derived interface.

        Parameters
        ----------
        scan_run
            Run id (``r_...``) or uid for a ``strain_partition_scan``.
        label
            Optional metadata label applied to created interfaces.
        params
            Optional params mapping. Note that params affect the derived-interface
            content hash; if the scan seed was an interface with params, those are
            preserved and merged (seed params first, then ``params`` overrides).
        """
        return self._interface_derivation.derive_from_strain_scan(
            scan_run,
            label=label,
            params=params,
        )

    def build_interface_from_prototype(
        self,
        prototype: str,
        *,
        alpha: float = 0.5,
        translation_frac: tuple[float, float] = (0.0, 0.0),
        z_padding: float = 1.5,
        vacuum: float | None = None,
    ):
        """Build live interface atoms from current authoritative records."""
        from ..application.interface_building import (
            build_interface_model_from_prototype,
        )

        with self._fresh_uow() as uow:
            return build_interface_model_from_prototype(
                uow,
                prototype,
                alpha=alpha,
                translation_frac=translation_frac,
                z_padding=z_padding,
                vacuum=vacuum,
            )

    def run_build_stage(
        self,
        prototypes: list[str],
        *,
        run_name: str | None = None,
        alpha: float = 0.5,
        translation_frac: tuple[float, float] = (0.0, 0.0),
        z_padding: float = 1.5,
        resume: bool = True,
    ) -> list[dict]:
        """Run the authoritative persisted build-stage orchestrator."""
        from ..application.build_stage import BuildStageOrchestrator

        results = BuildStageOrchestrator(self._uow_factory).build_from_prototypes(
            prototypes,
            run_name=run_name,
            alpha=alpha,
            translation_frac=translation_frac,
            z_padding=z_padding,
            resume=resume,
        )
        return [
            {
                "prototype_uid": result.prototype_uid,
                "status": result.status,
                "reason": result.reason,
                "run_uid": result.run_uid,
                "derived_interface_uid": result.derived_interface_uid,
            }
            for result in results
        ]

    def derive_interfaces_from_registry_search(
        self,
        reg_run: str,
        *,
        label: str | None = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> list[DerivedInterface]:
        """Create derived interfaces from a completed registry-search run.

        For each followup result in the registry search, this creates (or reuses)
        a :class:`~calm.project.domain.models.DerivedInterface` encoding the best
        registry shift found (stored in the followup payload as
        ``registry_shift_frac_a``).

        Registry coordinates, internal gap, and boundary vacuum are read from
        the exact current follow-up payload written by the registry stage.

        Parameters
        ----------
        reg_run
            Run id (``r_...``) or uid for a ``registry_search``.
        label
            Optional metadata label applied to created interfaces.
        params
            Optional params mapping. If the run seed was an interface with params,
            those are preserved and merged (seed params first, then ``params``
            overrides).
        """
        return self._interface_derivation.derive_from_registry_search(
            reg_run,
            label=label,
            params=params,
        )

    def pareto_plot(
        self,
        run: str,
        *,
        filename: str = "pareto.png",
        x: str = "natoms",
        y: str = "hencky_norm",
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
    ) -> ArtifactRef:
        """Create a simple pareto scatter plot for prototypes in a run."""

        protos = self.list_prototypes(
            run=run,
            pareto=None,
            max_hencky_norm=max_hencky_norm,
            min_match_score=min_match_score,
            limit=None,
        )

        # Lazy import to keep import-time light.
        import io

        # Avoid pyplot here: it triggers backend selection and can fail in
        # headless / minimal environments. A Figure + Agg canvas is robust.
        try:
            import matplotlib as mpl
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            from matplotlib.figure import Figure
        except ImportError as e:
            from calm.exceptions import optional_dependency_error

            raise optional_dependency_error(
                missing=["matplotlib"],
                symbol="calm.project.Workspace.pareto_plot",
            ) from e

        pareto_members, pareto_metadata = _workspace_plot_pareto_membership(protos)

        # Project fixed named membership into the requested display coordinates.
        # Filtering rows with complete source provenance does not promote
        # candidates that were dominated in the source population.
        x_p: list[float] = []
        y_p: list[float] = []
        x_vals: list[float] = []
        y_vals: list[float] = []
        for prototype in protos:
            xv = getattr(prototype, x)
            yv = getattr(prototype, y)
            if xv is None or yv is None:
                continue
            is_member = prototype.uid_full in pareto_members
            target_x = x_p if is_member else x_vals
            target_y = y_p if is_member else y_vals
            target_x.append(float(xv))
            target_y.append(float(yv))

        style = {
            # Slightly heavier defaults than matplotlib's; still conservative.
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.0,
            "lines.markersize": 6,
        }

        with mpl.rc_context(style):
            fig = Figure(figsize=(6.0, 4.0), dpi=140)
            FigureCanvas(fig)  # attach non-interactive canvas for savefig()
            ax = fig.add_subplot(1, 1, 1)

            candidate_color = "C0"
            pareto_color = "C1"

            # Non-pareto candidates.
            if x_vals:
                ax.scatter(
                    x_vals,
                    y_vals,
                    marker="o",
                    s=36,
                    color=candidate_color,
                    label="Candidates",
                )

            # Pareto set.
            if x_p:
                ax.scatter(
                    x_p,
                    y_p,
                    marker="x",
                    s=48,
                    color=pareto_color,
                    linewidths=2.0,
                    label="Pareto",
                )

            # Connecting Pareto front (sorted by x).
            if len(x_p) >= 2:
                front = sorted(zip(x_p, y_p), key=lambda t: t[0])
                fx, fy = zip(*front)
                ax.plot(fx, fy, color=pareto_color, label="Pareto front")

            ax.set_xlabel(x)
            ax.set_ylabel(y)
            ax.set_title("Pareto candidates")
            ax.grid(True, alpha=0.25)
            if x_vals or x_p:
                ax.legend()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")

        return self.put_plot(
            run,
            data=buf.getvalue(),
            filename=filename,
            metadata={
                "x": x,
                "y": y,
                **pareto_metadata,
            },
        )

    def pareto_plot_aggregate(  # noqa: C901
        self,
        runs: list[str],
        *,
        filename: str = "pareto_aggregate.png",
        x: str = "natoms",
        y: str = "hencky_norm",
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
    ) -> ArtifactRef:
        """Create an aggregated Pareto plot combining prototypes from multiple runs.

        This method is useful for comparing different Miller index combinations
        or surface orientations on a single plot. It collects prototypes from
        all specified runs and computes an explicitly scoped aggregate
        strain--size front across the selected-run population.

        Parameters
        ----------
        runs : list[str]
            List of run IDs (short or full) to aggregate.
        filename : str, default="pareto_aggregate.png"
            Output filename for the plot.
        x : str, default="natoms"
            Prototype attribute used only for the displayed x-axis.
        y : str, default="hencky_norm"
            Prototype attribute for y-axis (e.g., "hencky_norm", "match_score").
        max_hencky_norm : float, optional
            Filter prototypes with hencky_norm <= this value.
        min_match_score : float, optional
            Filter prototypes with match_score >= this value.
        Returns
        -------
        ArtifactRef
            The created plot artifact reference.

        Examples
        --------
        # Create individual searches for different Miller index pairs
        run1 = ws.start_prototype_search(lif_100, li2o_110)
        run2 = ws.start_prototype_search(lif_110, li2o_100)
        run3 = ws.start_prototype_search(lif_111, li2o_111)

        # Create single aggregate plot
        plot = ws.pareto_plot_aggregate(
            [run1.id_short, run2.id_short, run3.id_short],
            filename="lif_li2o_all_millers.png",
            x="natoms",
            y="hencky_norm"
        )
        """
        if not runs:
            raise ValueError("runs must contain at least one run identifier.")

        # Lazy import
        import io

        try:
            import matplotlib as mpl
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            from matplotlib.figure import Figure
        except ImportError as e:
            from calm.exceptions import optional_dependency_error

            raise optional_dependency_error(
                missing=["matplotlib"],
                symbol="calm.project.Workspace.pareto_plot_aggregate",
            ) from e

        # Collect the complete filtered population from the selected runs.
        all_protos = []

        for run_id in runs:
            protos = self.list_prototypes(
                run=run_id,
                pareto=None,
                max_hencky_norm=max_hencky_norm,
                min_match_score=min_match_score,
                limit=None,
            )

            all_protos.extend(protos)

        aggregate = strain_size_pareto(
            all_protos,
            atom_count="natoms",
            d_cell="d_cell",
            ids="uid_full",
            policy=AGGREGATE_STRAIN_SIZE_PARETO_POLICY,
            population_scope=AGGREGATE_STRAIN_SIZE_PARETO_SCOPE,
        )
        aggregate_members = set(aggregate.front_ids)

        # Project the fixed aggregate membership into the requested display axes.
        x_p: list[float] = []
        y_p: list[float] = []
        x_vals: list[float] = []
        y_vals: list[float] = []
        for prototype in all_protos:
            xv = getattr(prototype, x)
            yv = getattr(prototype, y)
            if xv is None or yv is None:
                continue
            is_member = str(prototype.uid_full) in aggregate_members
            (x_p if is_member else x_vals).append(float(xv))
            (y_p if is_member else y_vals).append(float(yv))

        # Create plot
        style = {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 9,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.0,
            "lines.markersize": 6,
        }

        with mpl.rc_context(style):
            fig = Figure(figsize=(6.0, 4.5), dpi=140)
            FigureCanvas(fig)
            ax = fig.add_subplot(1, 1, 1)

            # Simple, clean coloring: candidates in one color, Pareto in another
            candidate_color = "#7AA0C4"  # Muted blue
            pareto_color = "#E74C3C"  # Strong red

            # Plot all non-Pareto candidates
            if x_vals:
                ax.scatter(
                    x_vals,
                    y_vals,
                    marker="o",
                    s=20,
                    color=candidate_color,
                    alpha=0.6,
                    label=f"Candidates ({len(x_vals)})",
                    edgecolors="none",
                )

            # Plot Pareto-optimal prototypes with larger, more visible markers
            if x_p:
                ax.scatter(
                    x_p,
                    y_p,
                    marker="s",
                    s=60,
                    color=pareto_color,
                    alpha=0.9,
                    label=f"Aggregate strain-size front ({len(x_p)})",
                    edgecolors="white",
                    linewidths=0.5,
                    zorder=10,
                )

            # Connecting Pareto front with line
            if len(x_p) >= 2:
                front = sorted(zip(x_p, y_p), key=lambda t: t[0])
                fx, fy = zip(*front)
                ax.plot(
                    fx,
                    fy,
                    color=pareto_color,
                    linewidth=1.5,
                    linestyle="--",
                    alpha=0.7,
                    zorder=9,
                )

            ax.set_xlabel(x)
            ax.set_ylabel(y)
            ax.set_title(
                f"Aggregate strain-size front "
                f"({len(runs)} runs, {len(all_protos)} prototypes)"
            )
            ax.grid(True, alpha=0.25)
            if x_vals or x_p:
                ax.legend(loc="best", fontsize=8)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")

        # Store plot with first run as primary reference
        return self.put_plot(
            runs[0],
            data=buf.getvalue(),
            filename=filename,
            metadata={
                "x": x,
                "y": y,
                "runs": runs,
                "n_runs": len(runs),
                "n_prototypes": len(all_protos),
                "n_pareto": int(aggregate.mask.sum()),
                "pareto_policy": aggregate.policy,
                "pareto_policy_version": aggregate.version,
                "pareto_population_scope": aggregate.population_scope,
                "pareto_population_size": aggregate.population_size,
                "pareto_front_uids": list(aggregate.front_ids),
            },
        )

    def get_global_pareto_prototypes(
        self,
        runs: list[str],
        *,
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
    ) -> list[PrototypeSummary]:
        """Get the selected-run aggregate strain--size front.

        Membership always minimizes exact ``natoms`` and the persisted
        dimensionless ``d_cell`` objective.

        Parameters
        ----------
        runs : list[str]
            List of run IDs to aggregate.
        max_hencky_norm : float, optional
            Filter prototypes with hencky_norm <= this value.
        min_match_score : float, optional
            Filter prototypes with match_score >= this value.

        Returns
        -------
        list[PrototypeSummary]
            Aggregate front members in deterministic strain--size order.

        Examples
        --------
        # Get the aggregate front across selected Miller-index searches
        runs = [r1.id_short, r2.id_short, r3.id_short]
        global_pareto = ws.get_global_pareto_prototypes(runs)

        print(f"Found {len(global_pareto)} aggregate front interfaces")
        for p in global_pareto:
            print(f"  {p.id_short}: {p.natoms} atoms, {p.hencky_norm:.4f} strain")
        """
        # Collect all prototypes
        all_protos = []
        for run_id in runs:
            protos = self.list_prototypes(
                run=run_id,
                pareto=None,
                max_hencky_norm=max_hencky_norm,
                min_match_score=min_match_score,
                limit=None,
            )
            all_protos.extend(protos)

        if not all_protos:
            return []

        aggregate = strain_size_pareto(
            all_protos,
            atom_count="natoms",
            d_cell="d_cell",
            ids="uid_full",
            policy=AGGREGATE_STRAIN_SIZE_PARETO_POLICY,
            population_scope=AGGREGATE_STRAIN_SIZE_PARETO_SCOPE,
        )
        return [all_protos[index] for index in aggregate.front_idx]

    def display_pareto_summary(  # noqa: C901
        self,
        runs: list[str],
        *,
        x: str = "natoms",
        y: str = "hencky_norm",
        show_per_run: bool = True,
        show_global: bool = True,
    ) -> None:
        """Display formatted tables of Pareto-optimal prototypes.

        Prints summary tables showing:
        1. Per-run Pareto optimal prototypes (if show_per_run=True)
        2. Aggregate strain--size front across selected runs (if show_global=True)

        This is a convenience method that reduces boilerplate for the common
        task of displaying Pareto analysis results.

        Parameters
        ----------
        runs : list[str]
            List of run IDs to analyze.
        x : str, default="natoms"
            Prototype attribute used for display and sorting only.
        y : str, default="hencky_norm"
            Prototype attribute for second objective.
        show_per_run : bool, default=True
            If True, show Pareto prototypes for each individual run.
        show_global : bool, default=True
            If True, show the aggregate strain--size front across all runs.

        Examples
        --------
        # Simple one-liner to display all Pareto analysis
        ws.display_pareto_summary(
            [r1.id_short, r2.id_short, r3.id_short],
            x="natoms",
            y="hencky_norm"
        )
        """
        print("=" * 80)
        print("PARETO ANALYSIS SUMMARY")
        print("=" * 80)

        # Per-run Pareto optimal prototypes
        if show_per_run:
            print(f"\nPer-run Pareto-optimal prototypes ({len(runs)} runs):\n")

            for run_id in runs:
                run_obj = self.get_run(run_id)
                run_label = (
                    run_obj.spec.get("label", run_id[:8])
                    if run_obj.spec
                    else run_id[:8]
                )

                pareto_protos = self.list_prototypes(run=run_id, pareto=True)

                if pareto_protos:
                    print(f"  {run_label} ({run_id}):")
                    print(f"    {len(pareto_protos)} Pareto-optimal prototypes")

                    # Show top 3
                    top_prototypes = sorted(
                        pareto_protos,
                        key=lambda pr: getattr(pr, x),
                    )[:3]
                    for i, p in enumerate(top_prototypes):
                        xv = getattr(p, x)
                        yv = getattr(p, y)
                        print(
                            f"      {i + 1}. {p.id_short}: {x}={xv:.1f}, {y}={yv:.4f}"
                        )

                    if len(pareto_protos) > 3:
                        print(f"      ... and {len(pareto_protos) - 3} more")
                else:
                    print(f"  {run_label} ({run_id}): No Pareto-optimal prototypes")

                print()

        # Aggregate selected-run strain--size front.
        if show_global:
            global_pareto = self.get_global_pareto_prototypes(runs)

            print(f"\nAggregate strain-size front across all {len(runs)} runs:")
            print(f"  {len(global_pareto)} aggregate front prototypes\n")

            if global_pareto:
                # Show detailed breakdown with Miller indices
                print(f"Aggregate strain-size interfaces (sorted by {x}):")
                for p in global_pareto[:15]:
                    xv = getattr(p, x)
                    yv = getattr(p, y)

                    slab_a = self.get_slab(p.slab_a_uid_full)
                    slab_b = self.get_slab(p.slab_b_uid_full)
                    miller_info = f"Miller {slab_a.miller} × {slab_b.miller}"

                    print(f"  {p.id_short}: {x}={xv:.1f}, {y}={yv:.4f} | {miller_info}")

                if len(global_pareto) > 15:
                    print(f"  ... and {len(global_pareto) - 15} more")

        print("\n" + "=" * 80)

    # --------------------------- Runs + Artifacts ---------------------------

    def prepare_interface_search(
        self,
        *,
        name: str,
        search_identity: str,
        run_spec: Mapping[str, Any],
        resume: bool,
    ) -> InterfaceSearchPreparation:
        """Create, resume, or reuse one authoritative named search."""

        return self._interface_searches.prepare(
            name=name,
            search_identity=search_identity,
            run_spec=run_spec,
            resume=resume,
        )

    def complete_interface_search(
        self,
        run_uid_full: str,
        *,
        n_candidates: int,
        enumeration_audit: Mapping[str, Any] | None = None,
    ) -> InterfaceSearch:
        """Mark one authoritative named search complete."""

        return self._interface_searches.complete(
            run_uid_full,
            n_candidates=n_candidates,
            enumeration_audit=enumeration_audit,
        )

    def fail_interface_search(
        self,
        run_uid_full: str,
        *,
        error: Mapping[str, Any],
    ) -> InterfaceSearch:
        """Persist one authoritative named-search failure."""

        return self._interface_searches.fail(run_uid_full, error=error)

    def list_interface_searches(
        self,
        *,
        limit: int | None = None,
    ) -> list[InterfaceSearch]:
        """List authoritative named interface searches."""

        return self._interface_searches.list(limit=limit)

    def get_interface_search(self, identifier: str) -> InterfaceSearch:
        """Resolve one named search by name, identity, or run identifier."""

        return self._interface_searches.get(identifier)

    def create_run(self, *, run_type: str, spec: Mapping[str, Any]) -> Run:
        """Create an authoritative workflow-run record.

        Args:
            run_type: Stable run-kind identifier.
            spec: Identity-bearing run specification.

        Returns:
            The newly created persisted run record.
        """
        return self._runs_service().create(run_type=run_type, spec=spec)

    def get_run(self, run: str) -> Run:
        return self._runs_service().get(run)

    def mark_run_running(
        self,
        run: str,
        *,
        progress: Mapping[str, Any] | None = None,
    ) -> Run:
        return self._runs_service().mark_running(run, progress=progress)

    def mark_run_done(
        self,
        run: str,
        *,
        progress: Mapping[str, Any] | None = None,
    ) -> Run:
        return self._runs_service().mark_done(run, progress=progress)

    def mark_run_failed(self, run: str, *, error: Mapping[str, Any]) -> Run:
        return self._runs_service().mark_failed(run, error=error)

    def put_log(
        self,
        run: str,
        *,
        text: str,
        filename: str = "log.txt",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactRef:
        """Attach a text log artifact to a persisted run.

        Args:
            run: Full or short run identifier.
            text: UTF-8 log contents.
            filename: Artifact filename within the run artifact area.
            metadata: Optional descriptive metadata.

        Returns:
            A persisted artifact reference.
        """
        return self._artifacts.put_log(
            run,
            text=text,
            filename=filename,
            metadata=metadata,
        )

    def put_plot(
        self,
        run: str,
        *,
        data: bytes,
        filename: str = "plot.png",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactRef:
        """Attach a binary plot artifact to a persisted run.

        Args:
            run: Full or short run identifier.
            data: Encoded plot bytes.
            filename: Artifact filename within the run artifact area.
            metadata: Optional descriptive metadata.

        Returns:
            A persisted artifact reference.
        """
        return self._artifacts.put_plot(
            run,
            data=data,
            filename=filename,
            metadata=metadata,
        )

    def put_structure(
        self,
        run: str,
        *,
        text: str,
        filename: str = "structure.xyz",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactRef:
        """Attach a text structure artifact to a persisted run.

        Args:
            run: Full or short run identifier.
            text: Serialized structure contents.
            filename: Artifact filename within the run artifact area.
            metadata: Optional descriptive metadata.

        Returns:
            A persisted artifact reference.
        """
        return self._artifacts.put_structure(
            run,
            text=text,
            filename=filename,
            metadata=metadata,
        )

    def put_json(
        self,
        run: str,
        *,
        obj: Any,
        filename: str = "data.json",
        category: str = "data",
        kind: str = "json",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactRef:
        return self._artifacts.put_json(
            run,
            obj=obj,
            filename=filename,
            category=category,
            kind=kind,
            metadata=metadata,
        )

    def list_artifacts(self, run: str) -> list[ArtifactRef]:
        return self._artifacts.list_for_run(run)

    # ----------------------------
    # Artifact convenience helpers
    # ----------------------------

    @property
    def out_dir(self) -> Path:
        """Workspace output directory.

        Current artifact files are stored beneath this directory.
        """

        return self._out_dir

    def resolve_uri(self, uri: str) -> Path:
        """Resolve one current absolute ``file://`` artifact URI."""
        from .artifact_uri import resolve_artifact_uri

        path = resolve_artifact_uri(uri)
        try:
            path.relative_to(self._out_dir)
        except ValueError as exc:
            raise ValueError(
                "Artifact URI is outside the workspace output directory."
            ) from exc
        return path

    def artifact_path(self, artifact: ArtifactRef | str) -> Path:
        """Resolve an ``ArtifactRef`` or current raw URI string."""

        if isinstance(artifact, ArtifactRef):
            uri = artifact.uri
        elif isinstance(artifact, str):
            uri = artifact
        else:
            raise TypeError("artifact must be an ArtifactRef or URI string.")
        if not isinstance(uri, str) or not uri:
            raise ValueError("Artifact reference is missing its URI.")
        return self.resolve_uri(uri)

    def open_artifact(
        self,
        artifact: ArtifactRef | str,
        *,
        mode: str = "auto",
        encoding: str = "utf-8",
    ) -> Any:
        """Open a stored artifact and return a convenient Python object.

        Parameters
        ----------
        artifact
            ArtifactRef or URI string.
        mode
            - "path": return the resolved ``Path`` only.
            - "bytes": return raw bytes.
            - "text": return decoded text.
            - "json": parse JSON and return the loaded object.
            - "auto" (default): choose based on file extension.
        encoding
            Text encoding used when reading "text" or "json" modes.
        """

        if mode not in {"auto", "path", "bytes", "text", "json"}:
            raise ValueError("mode must be one of: auto, path, bytes, text, json.")

        path = self.artifact_path(artifact)

        if mode == "path":
            return path
        if mode == "bytes":
            return path.read_bytes()
        if mode == "text":
            return path.read_text(encoding=encoding)
        if mode == "json":
            return json.loads(path.read_text(encoding=encoding))

        # Auto mode.
        suf = path.suffix.lower()
        if suf == ".json":
            return json.loads(path.read_text(encoding=encoding))
        if suf in {".txt", ".log", ".md", ".csv"}:
            return path.read_text(encoding=encoding)
        return path

    def artifacts_by_category(self, run: str) -> dict[str, list[ArtifactRef]]:
        """Group a run's artifacts by their on-disk category.

        The default artifact layout is:

        ``runs/<r_short>/{plots,logs,structures,data}/...``
        """

        grouped: dict[str, list[ArtifactRef]] = defaultdict(list)
        for artifact in self.list_artifacts(run):
            relative = self.artifact_path(artifact).relative_to(self._out_dir)
            parts = relative.parts
            category = parts[2] if len(parts) >= 3 and parts[0] == "runs" else "unknown"
            grouped[category].append(artifact)
        return dict(grouped)

    def artifact_paths_by_category(self, run: str) -> dict[str, list[Path]]:
        """Like :meth:`artifacts_by_category`, but returns resolved Paths."""

        return {
            cat: [self.artifact_path(a) for a in arts]
            for cat, arts in self.artifacts_by_category(run).items()
        }

    # ----------------------------
    # Follow-up analyses (Step 4)
    # ----------------------------

    def start_strain_partition_scan(
        self,
        prototypes: Sequence[str],
        *,
        alphas: Sequence[float] | None = None,
        label: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        """Run a deterministic strain-partition follow-up."""

        merged = merge_payload(payload=payload, label=label)
        return self._followups.start_strain_partition_scan(
            prototypes=prototypes,
            alphas=alphas,
            payload=merged,
        )

    def start_registry_search(
        self,
        prototypes: Sequence[str],
        *,
        n_steps: int = 10,
        label: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        """Run a finite stochastic registry-search follow-up."""

        merged = merge_payload(payload=payload, label=label)
        return self._followups.start_registry_search(
            prototypes=prototypes,
            n_steps=n_steps,
            payload=merged,
        )

    def start_relaxation_run(
        self,
        prototypes: Sequence[str],
        *,
        protocol: str = "ionic_positions_v1",
        convergence: Optional[Mapping[str, Any]] = None,
        max_steps: int = 500,
        payload: Optional[Mapping[str, Any]] = None,
        resume: bool = True,
        backend: Any | None = None,
        relax_cell: bool = False,
        partial_resume: bool = False,
    ) -> Run:
        """Run a persisted structural-relaxation follow-up."""

        return self._followups.start_relaxation_run(
            prototypes=prototypes,
            protocol=protocol,
            convergence=convergence,
            max_steps=max_steps,
            payload=payload,
            resume=resume,
            backend=backend,
            relax_cell=relax_cell,
            partial_resume=partial_resume,
        )

    def run_registry_stage(
        self,
        prototypes: Sequence[str],
        *,
        n_steps: int = 10,
        run_name: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
        resume: bool = True,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
    ) -> list[dict]:
        """Run registry-search orchestration and return structured results.

        This adapter delegates to RegistrySearchOrchestrator and returns a list
        of JSON-friendly per-target result dicts. It preserves the no-sidecar
        mutation invariant.
        """
        from ..application.stage_results import normalize_stage_results

        merged = merge_payload(payload=payload, label=run_name)
        from ..application.followups.registry_search import (
            RegistrySearchOrchestrator,
        )

        orchestrator = RegistrySearchOrchestrator(self._uow_factory())
        _, results = orchestrator.run_stage(
            prototypes=prototypes,
            n_steps=n_steps,
            payload=merged,
            resume=resume,
            campaign_uid_full=campaign_uid_full,
            campaign_run_uid_full=campaign_run_uid_full,
        )
        return normalize_stage_results(results)

    def run_relaxation_stage(
        self,
        prototypes: Sequence[str],
        *,
        protocol: str = "ionic_positions_v1",
        convergence: Optional[Mapping[str, Any]] = None,
        max_steps: int = 500,
        run_name: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
        resume: bool = True,
        backend: Any | None = None,
        relax_cell: bool = False,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
        reporter: Any | None = None,
    ) -> list[dict]:
        """Run relaxation orchestration and return structured results.

        This adapter delegates to RelaxationOrchestrator and returns a list
        of JSON-friendly per-target result dicts. It preserves the no-sidecar
        mutation invariant.
        """
        del reporter

        from ..application.stage_results import normalize_stage_results

        merged = merge_payload(payload=payload, label=run_name)
        # Stage-oriented APIs propagate unexpected errors so callers can
        # distinguish execution failure from a legitimate empty result set.
        factory = self._uow_factory
        from ..application.followups.relaxation import RelaxationOrchestrator

        orchestrator = RelaxationOrchestrator(
            factory(),
            artifacts=self._artifacts,
            target_atoms_loader=self.materialize_derived_interface_atoms,
        )
        # Backend selection: explicit `backend` parameter overrides workspace default.
        from ..application.followups.relaxation_backends import make_relaxation_backend

        selected = backend if backend is not None else self._default_relaxation_backend
        if selected is not None:
            b = (
                make_relaxation_backend(selected)
                if isinstance(selected, str)
                else selected
            )
            orchestrator.with_backend(b)

        _, results = orchestrator.run_stage(
            prototypes=prototypes,
            protocol=protocol,
            convergence=convergence,
            max_steps=max_steps,
            relax_cell=relax_cell,
            payload=merged,
            resume=resume,
            partial_resume=partial_resume,
            campaign_uid_full=campaign_uid_full,
            campaign_run_uid_full=campaign_run_uid_full,
        )
        return normalize_stage_results(results)

    def run_energy_stage(
        self,
        prototypes: Sequence[str],
        *,
        backend: str | None = None,
        calculation: Optional[Mapping[str, Any]] = None,
        run_name: str | None = None,
        payload: Optional[Mapping[str, Any]] = None,
        resume: bool = True,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
    ) -> list[dict]:
        """Stage-oriented wrapper around energy evaluation orchestration.

        This adapter uses EnergyOrchestrator to compute per-target energy
        summaries and returns JSON-friendly dicts. Backend selection follows the
        same pattern as run_relaxation_stage.
        """
        from ..application.stage_results import normalize_stage_results

        merged = merge_payload(payload=payload, label=run_name)
        # Use fresh UoW factory to create orchestrator-run UoWs rather than
        # reusing the workspace UoW connection.
        factory = self._uow_factory
        from ..application.followups.energy import EnergyOrchestrator

        orchestrator = EnergyOrchestrator(
            factory(),
            target_atoms_loader=self.materialize_derived_interface_atoms,
            artifacts=self._artifacts,
        )
        selected = backend if backend is not None else "deterministic"
        from ..application.followups.energy_backends import make_energy_backend

        backend_impl = (
            make_energy_backend(selected) if isinstance(selected, str) else selected
        )
        orchestrator.with_backend(backend_impl)
        _, results = orchestrator.run_stage(
            prototypes=prototypes,
            backend=str(getattr(backend_impl, "name", selected)),
            calculation=calculation or {},
            payload=merged,
            resume=resume,
            partial_resume=partial_resume,
            campaign_uid_full=campaign_uid_full,
            campaign_run_uid_full=campaign_run_uid_full,
        )
        return normalize_stage_results(results)

    def run_reference_energy_stage(
        self,
        interfaces: Sequence[str],
        *,
        formula: str,
        backend: Any | None = None,
        calculation: Optional[Mapping[str, Any]] = None,
        payload: Optional[Mapping[str, Any]] = None,
        resume: bool = True,
        partial_resume: bool = True,
    ) -> list[dict]:
        """Persist per-interface bulk or isolated-surface reference energies."""
        factory = self._uow_factory
        from ..application.followups.energy_backends import make_energy_backend
        from ..application.followups.reference_energy import (
            ReferenceEnergyOrchestrator,
        )

        uow_obj = factory()
        orchestrator = ReferenceEnergyOrchestrator(
            uow_obj,
            interface_atoms_loader=self.materialize_derived_interface_atoms,
            artifacts=self._artifacts,
        )
        selected = backend if backend is not None else "deterministic"
        backend_impl = (
            make_energy_backend(selected) if isinstance(selected, str) else selected
        )
        orchestrator.with_backend(backend_impl)
        _run, results = orchestrator.run_stage(
            interfaces=interfaces,
            formula=formula,
            calculation=calculation or {},
            payload=payload or {},
            resume=resume,
            partial_resume=partial_resume,
        )
        return [
            {
                "source_interface_uid": result.source_interface_uid,
                "prototype_uid": result.prototype_uid,
                "reference_kind": result.reference_kind,
                "side": result.side,
                "status": result.status,
                "run_uid": result.run_uid,
                "followup_uid": result.followup_uid,
                "energy_eV": result.energy_eV,
                "energy_eV_per_formula_unit": result.energy_eV_per_formula_unit,
                "reason": result.reason,
            }
            for result in results
        ]

    def run_thermodynamic_stage(
        self,
        raw_energy_results: Sequence[str],
        *,
        convention: Mapping[str, Any],
        references: Mapping[str, Any],
        resume: bool = True,
        partial_resume: bool = True,
    ) -> list[dict]:
        """Persist explicit thermodynamic quantities derived from raw energies."""
        factory = self._uow_factory
        from ..application.followups.thermodynamics import ThermodynamicOrchestrator

        uow_obj = factory()
        orchestrator = ThermodynamicOrchestrator(uow_obj)
        _run, results = orchestrator.run_stage(
            raw_energy_results=raw_energy_results,
            convention=convention,
            references=references,
            resume=resume,
            partial_resume=partial_resume,
        )
        return [
            {
                "target_uid": result.target_uid,
                "prototype_uid": result.prototype_uid,
                "status": result.status,
                "quantity": result.quantity,
                "value_eV_per_A2": result.value_eV_per_A2,
                "value_J_per_m2": result.value_J_per_m2,
                "run_uid": result.run_uid,
                "followup_uid": result.followup_uid,
                "raw_energy_followup_uid": result.raw_energy_followup_uid,
                "reason": result.reason,
            }
            for result in results
        ]

    def list_followup_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[FollowupResult]:
        """List follow-up results, optionally filtered by run/prototype/kind."""
        return self._followups.list_results(
            run=run,
            prototype=prototype,
            kind=kind,
            limit=limit,
        )

    def get_followup_result(self, identifier: str) -> FollowupResult:
        """Return one authoritative follow-up result."""
        return self._followups.get_result(identifier)

    def resolve_identifier(self, identifier: str) -> str:
        """Resolve one current project identifier without allocating it."""
        with self._fresh_uow() as uow:
            return str(uow.ids.resolve(identifier))

    def list_edges(
        self,
        *,
        src: str | None = None,
        dst: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[Edge]:
        """List recorded provenance edges.

        Parameters
        ----------
        src, dst
            Optional source/destination identifiers. These may be either full
            uids ("b_..."), or short ids ("b_abcd123").
        kind
            Optional edge kind filter (e.g. "run_to_prototype").
        limit
            Optional maximum number of edges to return.
        """

        # Resolve filters and query edges within one fresh read transaction.
        with self._fresh_uow() as uow:
            src_uid_full = uow.ids.resolve(src) if src else None
            dst_uid_full = uow.ids.resolve(dst) if dst else None
            return uow.edges.list(
                src_uid_full=src_uid_full,
                dst_uid_full=dst_uid_full,
                kind=kind,
                limit=limit,
            )

    def strain_partition_plot(
        self,
        run: str,
        *,
        filename: str = "strain_partition_scan.png",
        metric: str | None = None,
    ) -> ArtifactRef:
        """Render and persist one exact-current strain-partition scan plot."""

        results = self.list_followup_results(
            run=run,
            kind="strain_partition_scan",
            limit=1,
        )
        if not results:
            raise ValueError(
                f"No follow-up results found for run {run!r} "
                "(kind='strain_partition_scan')"
            )

        result = results[0]
        selected_metric, alphas, energies = strain_partition_plot_series(
            result.payload or {},
            metric=metric,
        )

        try:
            import matplotlib as mpl
            from matplotlib.backends.backend_agg import (
                FigureCanvasAgg as FigureCanvas,
            )
            from matplotlib.figure import Figure
        except ImportError as exc:  # pragma: no cover
            from ...exceptions import optional_dependency_error

            raise optional_dependency_error(
                missing=["matplotlib"],
                symbol="calm.project.Workspace.strain_partition_plot",
            ) from exc

        style = {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.0,
            "lines.markersize": 6,
        }

        with mpl.rc_context(style):
            fig = Figure(figsize=(6.0, 4.0), dpi=140)
            FigureCanvas(fig)
            ax = fig.add_subplot(1, 1, 1)
            ax.plot(alphas, energies, marker="o", label="energy")

            from calm.project.domain.contracts.refinement_result import (
                strain_partition_selection,
            )

            _stored_metric, best_alpha, _best_value = strain_partition_selection(
                result.payload or {}
            )
            best_index = min(
                range(len(alphas)),
                key=lambda index: abs(alphas[index] - best_alpha),
            )
            ax.scatter(
                [alphas[best_index]],
                [energies[best_index]],
                marker="x",
                s=90,
                linewidths=2.5,
                color="C1",
                label="best",
                zorder=3,
            )

            ax.set_xlabel(r"Geodesic strain partition, $\alpha$")
            ax.set_title("Strain partition scan")
            if selected_metric == "gamma_eV_per_A2":
                ylabel = r"Interfacial energy, $\gamma$ (eV/\AA$^2$)"
            else:
                ylabel = (
                    r"Potential energy density, $E_\mathrm{interface}/A$ "
                    r"(eV/\AA$^2$)"
                )
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.25)
            ax.legend()

            import io

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)

        return self.put_plot(
            run,
            data=buf.getvalue(),
            filename=filename,
            metadata={
                "kind": "strain_partition_scan",
                "metric": selected_metric,
            },
        )

    def registry_search_plot(
        self,
        run: str,
        *,
        filename: str = "registry_search.png",
    ) -> ArtifactRef:
        """Render and persist one exact-current registry-search plot."""

        results = self.list_followup_results(
            run=run,
            kind="registry_search",
            limit=1,
        )
        if not results:
            raise ValueError(
                f"No follow-up results found for run {run!r} (kind='registry_search')"
            )

        steps, best_scores = registry_search_plot_series(results[0].payload or {})

        try:
            import matplotlib as mpl
            from matplotlib.backends.backend_agg import (
                FigureCanvasAgg as FigureCanvas,
            )
            from matplotlib.figure import Figure
        except ImportError as exc:  # pragma: no cover
            from ...exceptions import optional_dependency_error

            raise optional_dependency_error(
                missing=["matplotlib"],
                symbol="calm.project.Workspace.registry_search_plot",
            ) from exc

        style = {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.0,
            "lines.markersize": 6,
        }

        with mpl.rc_context(style):
            fig = Figure(figsize=(6.0, 4.0), dpi=140)
            FigureCanvas(fig)
            ax = fig.add_subplot(1, 1, 1)
            ax.plot(steps, best_scores)
            ax.set_title("Registry search")
            ax.set_xlabel("step")
            ax.set_ylabel("best score")
            ax.grid(True, alpha=0.25)

            import io

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)

        return self.put_plot(
            run,
            data=buf.getvalue(),
            filename=filename,
            metadata={"kind": "registry_search"},
        )

    def validate_workspace(
        self,
        *,
        check_references: bool = True,
        check_orphans: bool = False,
        check_duplicates: bool = True,
        check_provenance: bool = False,
    ) -> Any:
        """Validate workspace database consistency.

        Checks for broken references, orphaned records, and other consistency
        issues in the workspace database.

        Parameters
        ----------
        check_references : bool
            If True, check for broken references (entities referencing
            non-existent entities). Default True.
        check_orphans : bool
            If True, check for orphaned records (entities not referenced by
            anything). This can be slow on large workspaces. Default False.
        check_duplicates : bool
            If True, check for duplicate UIDs. Default True.
        check_provenance : bool
            If True, validate provenance payloads stored in ``Atoms.info``.

        Returns
        -------
        ValidationReport
            Report containing all issues found, with summary statistics.

        Examples
        --------
        >>> ws = open_workspace("path/to/workspace")
        >>> report = ws.validate_workspace()
        >>> print(f"Found {report.error_count} errors, {report.warning_count} warnings")

        >>> # Print all issues
        >>> for issue in report.issues:
        ...     print(f"{issue.severity.upper()}: {issue.message}")

        >>> # Check if workspace is valid
        >>> if report.is_valid:
        ...     print("Workspace is valid!")
        ... else:
        ...     print(f"Found {report.error_count} errors")

        >>> # Check for orphans (can be slow)
        >>> report = ws.validate_workspace(check_orphans=True)
        >>> orphan_count = sum(
        ...     1 for issue in report.issues
        ...     if issue.category == "orphaned_record"
        ... )
        >>> print(f"Found {orphan_count} orphaned records")
        """
        from ..application.workspace_validation import WorkspaceValidator

        validator = WorkspaceValidator(uow_factory=self._uow_factory)
        return validator.validate(
            check_references=check_references,
            check_orphans=check_orphans,
            check_duplicates=check_duplicates,
            check_provenance=check_provenance,
        )
