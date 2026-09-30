"""Public project facade for recovery and query workflows."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from calm.public.collections.candidates import CandidateCollection
from calm.public.queries.project import PublicProjectQueries
from calm.public.workflows.saving import PublicProjectSaver


class Project:
    """Canonical public owner of persistent CALM workflows.

    ``Project`` coordinates authoritative persistence, deterministic workflow
    execution and durable queries. Returned records and
    collection views support inspection and navigation; new workflow stages are
    always started through this object.
    """

    def __init__(self, workspace: Any, *, path: str | Path | None = None):
        self._workspace = workspace
        self.path = Path(path) if path is not None else None
        # Normalize the internal Workspace once at the composition root.
        from calm.public.persistence.adapter import WorkspaceAdapter

        adapter = WorkspaceAdapter(self._workspace)

        from calm.public.persistence.repository import PublicRepository

        self._adapter = adapter
        self._repo = PublicRepository(adapter)

        # Pass the canonical adapter instance to downstream helpers so they
        # do not re-wrap the workspace. This centralizes adapter ownership in
        # Project and prevents double-wrapping.
        self._queries = PublicProjectQueries(
            adapter,
            repo=self._repo,
            project=self,
        )
        self._saver = PublicProjectSaver(
            workspace=adapter,
            repo=self._repo,
        )
        from calm.public.workflows.material_optimization import (
            ProjectMaterialOptimizationService,
        )

        self._material_optimizations = ProjectMaterialOptimizationService(
            project=self,
            saver=self._saver,
        )
        from calm.public.workflows.interface_search import (
            ProjectInterfaceSearchWorkflowService,
        )

        self._search_workflows = ProjectInterfaceSearchWorkflowService(
            project=self,
            workspace=adapter,
            repository=self._repo,
            saver=self._saver,
        )
        from calm.public.workflows.interface_build import ProjectInterfaceBuildService
        from calm.public.workflows.interface_refinement import (
            ProjectInterfaceRefinementService,
        )

        self._interface_builds = ProjectInterfaceBuildService(
            project=self,
            workspace=adapter,
            repository=self._repo,
            saver=self._saver,
        )
        self._interface_refinements = ProjectInterfaceRefinementService(
            project=self,
            workspace=adapter,
            repository=self._repo,
        )
        from calm.public.workflows.relaxation import ProjectRelaxationWorkflowService

        self._relaxation_workflows = ProjectRelaxationWorkflowService(
            project=self,
            workspace=self._workspace,
            repository=self._repo,
        )
        from calm.public.workflows.energy import ProjectEnergyWorkflowService

        self._energy_workflows = ProjectEnergyWorkflowService(
            workspace=self._workspace,
            repository=self._repo,
        )
        from calm.public.workflows.datasets import ProjectDatasetWorkflowService

        self._dataset_workflows = ProjectDatasetWorkflowService(
            project=self,
            workspace=adapter,
            repository=self._repo,
        )
        from calm.public.workflows.campaigns import ProjectCampaignWorkflowService

        self._campaign_workflows = ProjectCampaignWorkflowService(
            project=self,
            workspace=adapter,
            repository=self._repo,
            search_workflows=self._search_workflows,
            interface_builds=self._interface_builds,
            interface_refinements=self._interface_refinements,
            relaxation_workflows=self._relaxation_workflows,
            energy_workflows=self._energy_workflows,
            dataset_workflows=self._dataset_workflows,
        )
        from calm.public.queries.lineage import ProjectLineageQueryService
        from calm.public.queries.structures import ProjectStructureQueryService

        self._lineage_queries = ProjectLineageQueryService(
            repository=self._repo,
        )
        self._structure_queries = ProjectStructureQueryService(
            workspace=adapter,
            repository=self._repo,
        )
        # Project-wide configuration is authoritative database state.
        from calm.public.inputs.project_config import load_configuration

        self._configuration = load_configuration(self)
        from calm.public.queries.health import ProjectHealthService

        self._health = ProjectHealthService(
            project=self,
            workspace=adapter,
            repository=self._repo,
            queries=self._queries,
        )

    def summary(self) -> str:
        """Return a compact human-readable identity for the open project.

        Returns:
            A one-line summary containing the project path. In-memory projects
            report ``path=None``.
        """
        return f"CALM project(path={self.path})"

    def reproducibility_manifest(self):
        """Build an in-memory reproducibility snapshot for the current project state."""

        from calm.public.records.reproducibility import _build_reproducibility_manifest

        return _build_reproducibility_manifest(self)

    def write_reproducibility_manifest(
        self,
        destination: str | Path | None = None,
        *,
        overwrite: bool = False,
    ):
        """Write an atomic project reproducibility manifest and return its typed snapshot."""

        from calm.project.reproducibility import DEFAULT_MANIFEST_FILENAME

        if self.path is None:
            from calm.public.errors import ProjectReproducibilityError

            raise ProjectReproducibilityError(
                "Reproducibility manifests require a directory-backed Project."
            )
        target = (
            Path(destination)
            if destination is not None
            else Path(self.path) / DEFAULT_MANIFEST_FILENAME
        )
        from calm.public.records.reproducibility import _build_reproducibility_manifest

        manifest = _build_reproducibility_manifest(self, exclude_paths=(target,))
        manifest.write(target, overwrite=overwrite)
        return manifest

    def verify_reproducibility_manifest(
        self,
        source: str | Path | None = None,
    ):
        """Compare a recorded manifest with the current project and runtime state."""

        from calm.project.reproducibility import DEFAULT_MANIFEST_FILENAME
        from calm.public.errors import ProjectReproducibilityError
        from calm.public.records.reproducibility import _verify_reproducibility_manifest

        if self.path is None:
            raise ProjectReproducibilityError(
                "Reproducibility manifests require a directory-backed Project."
            )
        target = (
            Path(source)
            if source is not None
            else Path(self.path) / DEFAULT_MANIFEST_FILENAME
        )
        return _verify_reproducibility_manifest(self, target)

    def configure(
        self,
        *,
        mlip: str | None = None,
        calculator: Any | None = None,
        defaults: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist authoritative project-wide workflow configuration.

        MLIP family and calculator identity are immutable once assigned.
        Workflow defaults are merged with the current database row. The
        project database is the sole configuration store.
        """
        from calm.public.inputs.project_config import configure as _configure

        return _configure(
            self,
            mlip=mlip,
            calculator=calculator,
            defaults=defaults,
        )

    def artifacts(self):
        """Return the project artifact-discovery helper."""
        from calm.public.records.artifacts import ProjectArtifacts

        return ProjectArtifacts(self.path)

    def materials(self):
        """Return the authoritative collection of persisted bulk materials.

        Returns:
            (MaterialCollection): A project-backed collection. Use its named table
                views, filters, and exact ``get`` lookup rather than inspecting
                storage rows.
        """
        return self._queries.materials()

    def add_material(
        self,
        material: Any,
        *,
        name: str | None = None,
        reporter: Any | None = None,
    ):
        """Persist one user-authored material and return its authoritative facade.

        This is the sole public material-ingest operation. Workflow-generated
        searches, interfaces, and energy results persist through their owning
        project workflows rather than through a generic save API.

        Args:
            material: A public ``Material``, ASE ``Atoms`` object, or supported
                structure input accepted by the material persistence boundary.
            name: Optional exact project label. When omitted, the input label or
                deterministic material identity supplies the persisted name.
            reporter: Optional progress reporter.

        Returns:
            (Material): The authoritative persisted material facade with stable
                project identifiers.

        Raises:
            TypeError: If ``material`` is not a supported structure input.
            ValueError: If the material structure or requested name is invalid.

        Notes:
            Re-adding scientifically identical material is deterministic under the
            current persistence identity contract.
        """
        return self._saver.persist_material(
            material,
            name=name,
            reporter=reporter,
        )

    def surfaces(
        self,
        *,
        material: Any | None = None,
        miller: tuple[int, int, int] | None = None,
        termination: str | None = None,
        termination_top: str | None = None,
        termination_bottom: str | None = None,
        termination_shift: int | None = None,
        include_empty: bool = False,
    ):
        """Return persisted surfaces, optionally filtered by exact identity.

        The collection is database-backed. Material selectors match exact
        labels, bulk short IDs, or bulk UIDs. Miller indices and termination
        metadata, including the ordered top/bottom termination pair, are
        matched exactly. No surface is chosen implicitly when a selection
        remains ambiguous.
        """
        coll = self._queries.surfaces()
        if not include_empty:
            coll = coll.usable_surfaces()
        return coll.select(
            material=material,
            miller=miller,
            termination=termination,
            termination_top=termination_top,
            termination_bottom=termination_bottom,
            termination_shift=termination_shift,
        )

    def searches(self):
        """Return the authoritative collection of persisted interface searches.

        Returns:
            (SearchCollection): Durable search records. Call ``search()`` to
                obtain the project-bound navigation view for one exact search.
        """
        return self._queries.searches()

    def search(self, search: Any) -> Any:
        """Return the durable project-bound view for one persisted search.

        Args:
            search: Exact search name, ``ProjectSearch`` record, or a
                ``PersistedInterfaceSearch`` already bound to this project.

        Returns:
            (PersistedInterfaceSearch): The durable view used to inspect
                candidates, buildability, interfaces, and downstream results.

        Raises:
            TypeError: If ``search`` is not a supported selector.
            ValueError: If a supplied record belongs to another project or does
                not match authoritative persisted identity.
            KeyError: If no persisted search matches the selector.
        """
        return self._search_workflows.search(search)

    def build_interfaces(
        self,
        search: Any,
        *,
        top: int = 1,
        settings: Any | None = None,
        name_prefix: str | None = None,
        reporter: Any | None = None,
    ):
        """Build and persist the top candidates from one named search.

        Candidate selection uses the authoritative Pareto classification followed
        by ascending public score. Construction is project-backed and preserves
        candidate, prototype, search, and deformation provenance.

        Args:
            search: Persisted search selector accepted by ``Project.search()``.
            top: Positive number of candidates to build. Default: ``1``.
            settings: Optional ``BuildSettings``. ``None`` uses
                ``BuildSettings()``.
            name_prefix: Optional prefix for deterministic indexed interface names.
            reporter: Optional progress reporter.

        Returns:
            (InterfaceCollection): The newly built authoritative interface models.

        Raises:
            TypeError: If ``settings`` is not ``BuildSettings`` or candidate rows
                do not expose the public mapping contract.
            ValueError: If ``top`` is not a positive integer.
            RuntimeError: If selected candidates are not buildable, lack persisted
                prototype identity, or cannot be persisted authoritatively.
        """
        return self._interface_builds.build_interfaces(
            search,
            top=top,
            settings=settings,
            name_prefix=name_prefix,
            reporter=reporter,
        )

    def refine_interfaces(
        self,
        search: Any,
        *,
        strain_settings: Any,
        registry_settings: Any | None = None,
        interfaces: Any | None = None,
        top: int | None = None,
        pareto: bool = True,
        label_prefix: str | None = None,
        on_error: str = "explain",
        reporter: Any | None = None,
    ):
        """Run strain partitioning and optional registry refinement.

        Omit ``registry_settings`` to stop after authoritative strain partitioning.
        Supplying it continues from the selected strain-partitioned interfaces into
        translation-only registry refinement.

        Args:
            search: Persisted search selector accepted by ``Project.search()``.
            strain_settings: Required ``StrainPartitionSettings`` defining the
                scan grid and scientific selection objective.
            registry_settings: Optional ``RegistrySettings``. Default: ``None``.
            interfaces: Optional explicit built-interface selection. When omitted,
                interfaces are selected from the search.
            top: Optional number of search interfaces selected for refinement.
            pareto: Restrict automatic selection to the authoritative Pareto front.
                Default: ``True``.
            label_prefix: Optional persisted lineage-label prefix.
            on_error: ``"explain"`` returns issues in the result; ``"raise"``
                propagates workflow failures. Default: ``"explain"``.
            reporter: Optional progress reporter.

        Returns:
            (InterfaceRefinementResult): Typed strain and optional registry runs,
                derived interfaces, status, and structured issues.

        Raises:
            TypeError: If either settings object has the wrong public type.
            ValueError: If selection controls conflict or ``on_error`` is invalid.
            RuntimeError: If an execution failure occurs with ``on_error="raise"``.
        """
        return self._interface_refinements.refine_interfaces(
            search,
            strain_settings=strain_settings,
            registry_settings=registry_settings,
            interfaces=interfaces,
            top=top,
            pareto=pareto,
            label_prefix=label_prefix,
            on_error=on_error,
            reporter=reporter,
        )

    def refine_registry(
        self,
        interfaces: Any,
        *,
        settings: Any,
        label_prefix: str | None = None,
        on_error: str = "explain",
        reporter: Any | None = None,
    ):
        """Run registry refinement from persisted strain-partitioned interfaces.

        Args:
            interfaces: Persisted strain-partitioned interface records, collection,
                or supported identifiers.
            settings: Required ``RegistrySettings``.
            label_prefix: Optional persisted lineage-label prefix.
            on_error: ``"explain"`` returns structured issues; ``"raise"``
                propagates workflow failures. Default: ``"explain"``.
            reporter: Optional progress reporter.

        Returns:
            (InterfaceRefinementResult): Registry run, refined interfaces, status,
                and structured issues.

        Raises:
            TypeError: If ``settings`` is not ``RegistrySettings``.
            ValueError: If the selection or ``on_error`` policy is invalid.
            RuntimeError: If an execution failure occurs with ``on_error="raise"``.
        """

        return self._interface_refinements.refine_registry(
            interfaces,
            settings=settings,
            label_prefix=label_prefix,
            on_error=on_error,
            reporter=reporter,
        )

    def candidates(self) -> CandidateCollection:
        """Return all authoritative interface candidates in the project.

        Returns:
            A project-backed ``CandidateCollection``. Candidate display IDs and
            ranks remain stable within their owning persisted search.
        """
        return self._queries.candidates()

    def interfaces(self):
        """Return all authoritative constructed or derived interfaces.

        Returns:
            (InterfaceCollection): A project-backed collection supporting stage,
                search, candidate, and named-view selection.
        """
        collection = self._queries.interfaces()
        collection._project = self
        return collection

    def refined_interfaces(
        self,
        *,
        stage: str | None = None,
        search_name: str | None = None,
    ):
        """Return authoritative persisted strain- or registry-refined interfaces."""
        coll = self.interfaces().where(authority="authoritative").refined(stage=stage)
        if search_name is not None:
            coll = coll.search(name=search_name)
        return coll

    def interface(self, id_or_name: str):
        """Return exactly one persisted interface record."""
        return self.interfaces().get(id_or_name)

    def interface_atoms(
        self,
        id_or_name: str,
        *,
        registry_shift: tuple[float, float] | None = None,
    ):
        """Return authoritative interface atoms or a registry-shifted variant.

        ``registry_shift`` is expressed in fractional in-plane lattice
        coordinates. An override reconstructs a non-persisted structure while
        retaining the authoritative prototype, strain allocation, internal gap,
        and boundary vacuum. It does not create a project interface or evaluate
        an energy.
        """
        return self._structure_queries.get_interface_atoms(
            id_or_name,
            registry_shift=registry_shift,
        )

    def relaxed_interfaces(
        self,
        *,
        run: str | None = None,
        search_name: str | None = None,
    ):
        """Return authoritative structurally relaxed interfaces."""
        collection = self.interfaces().where(authority="authoritative").relaxed()
        if run is not None:
            run_uid = self.run(run).uid_full
            collection = collection.where(source_run_uid=run_uid)
        if search_name is not None:
            collection = collection.search(name=search_name)
        return collection

    def relax_interfaces(
        self,
        interfaces: Any | None = None,
        *,
        settings: Any | None = None,
        backend: Any = "real",
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        stage: str = "registry_refined",
        reporter: Any | None = None,
    ):
        """Synchronously relax authoritative interfaces.

        Args:
            interfaces: Optional explicit interface selection. When omitted, CALM
                selects authoritative interfaces using ``stage`` and ``search_name``.
            settings: Optional ``RelaxSettings``. ``None`` uses
                ``RelaxSettings()``.
            backend: Calculator-backed relaxation backend or exact configured
                backend identifier. Default: ``"real"``.
            resume: Reuse an identical completed run when available.
                Default: ``True``.
            partial_resume: Reuse completed per-target results within an incomplete
                run. Default: ``True``.
            on_error: ``"raise"`` raises after persisting failure records;
                ``"record"`` returns them in the workflow result.
            search_name: Optional exact search filter used for implicit selection.
            stage: Interface stage used for implicit selection. Default:
                ``"registry_refined"``.
            reporter: Optional progress reporter.

        Returns:
            (RelaxationWorkflowResult): Authoritative run, per-target relaxation
                results, and relaxed-interface records.

        Raises:
            TypeError: If ``settings`` or ``backend`` violates the public contract.
            ValueError: If selection, stage, settings, or error policy is invalid.
            RuntimeError: If the backend fails or produces no result while
                ``on_error="raise"``.

        Notes:
            Variable-cell relaxation records its cell deformation separately from
            construction and matching deformation provenance.
        """
        return self._relaxation_workflows.relax_interfaces(
            interfaces,
            settings=settings,
            backend=backend,
            resume=resume,
            partial_resume=partial_resume,
            on_error=on_error,
            search_name=search_name,
            stage=stage,
            reporter=reporter,
        )

    def evaluate_reference_energies(
        self,
        interfaces: Any | None = None,
        *,
        convention: Any,
        settings: Any | None = None,
        surface_relaxation: Any | None = None,
        backend: Any = "real",
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        reporter: Any | None = None,
    ):
        """Calculate and persist per-interface thermodynamic references.

        The workflow supports coherently strained bulks, unrelaxed isolated
        surfaces, and independently relaxed fixed-cell surfaces according to the
        explicit convention.

        Args:
            interfaces: Optional explicit authoritative interface selection.
            convention: Required ``EnergyConvention`` defining the reference
                process and periodic normalization.
            settings: Optional ``EnergySettings``. ``None`` uses
                ``EnergySettings()``.
            surface_relaxation: Fixed-cell ``RelaxSettings`` required only for
                ``work_of_adhesion_relaxed_surfaces``.
            backend: Calculator-backed reference backend or configured identifier.
                Default: ``"real"``.
            resume: Reuse an identical completed run. Default: ``True``.
            partial_resume: Reuse completed per-target references. Default: ``True``.
            on_error: ``"raise"`` raises after persisting failures; ``"record"``
                returns them. Default: ``"raise"``.
            search_name: Optional exact search filter for implicit selection.
            reporter: Optional progress reporter.

        Returns:
            (ReferenceEnergyWorkflowResult): Authoritative run, typed reference
                results, convention, and reference-map helpers.

        Raises:
            TypeError: If convention, settings, surface relaxation, or backend has
                the wrong public type.
            ValueError: If the convention or reference-relaxation controls are
                inconsistent.
            UnsupportedReferenceWorkflowError: If the convention has no supported
                calculated-reference path.
            RuntimeError: If reference evaluation fails with
                ``on_error="raise"``.
        """
        return self._energy_workflows.evaluate_reference_energies(
            interfaces,
            convention=convention,
            settings=settings,
            surface_relaxation=surface_relaxation,
            backend=backend,
            resume=resume,
            partial_resume=partial_resume,
            on_error=on_error,
            search_name=search_name,
            reporter=reporter,
        )

    def evaluate_energies(
        self,
        interfaces: Any | None = None,
        *,
        settings: Any | None = None,
        backend: Any = "real",
        convention: Any | None = None,
        references: Any | None = None,
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        reporter: Any | None = None,
    ):
        """Evaluate raw energies and optionally derive an explicit quantity.

        Raw total energy and derived thermodynamic quantities are persisted in
        separate runs. CALM never infers a thermodynamic reference process.

        Args:
            interfaces: Optional explicit authoritative interface selection.
            settings: Optional ``EnergySettings``. ``None`` uses
                ``EnergySettings()``.
            backend: Calculator-backed energy backend or configured identifier.
                Default: ``"real"``.
            convention: Optional ``EnergyConvention``. It must be supplied together
                with ``references``.
            references: Optional ``ReferenceEnergyWorkflowResult`` or explicit
                ``ReferenceEnergySettings`` paired with ``convention``.
            resume: Reuse identical completed runs. Default: ``True``.
            partial_resume: Reuse completed per-target raw energies. Default:
                ``True``.
            on_error: ``"raise"`` raises after persisting failures; ``"record"``
                returns them. Default: ``"raise"``.
            search_name: Optional exact search filter for implicit selection.
            reporter: Optional progress reporter.

        Returns:
            (EnergyWorkflowResult): Raw-energy run and results, plus optional
                thermodynamic run and derived quantities.

        Raises:
            TypeError: If settings, convention, references, or backend has the
                wrong public type.
            ValueError: If convention and references are inconsistent or invalid.
            RuntimeError: If evaluation or derivation fails with
                ``on_error="raise"``.
        """
        return self._energy_workflows.evaluate_energies(
            interfaces,
            settings=settings,
            backend=backend,
            convention=convention,
            references=references,
            resume=resume,
            partial_resume=partial_resume,
            on_error=on_error,
            search_name=search_name,
            reporter=reporter,
        )

    def reference_energy_runs(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative reference-energy workflow runs."""
        return self.runs(run_type="reference_energy", status=status, limit=limit)

    def reference_energy_results(
        self,
        *,
        run: str | None = None,
        status: str | None = None,
        formula: str | None = None,
        reference_kind: str | None = None,
        limit: int = 100000,
    ):
        """Return authoritative per-interface reference-energy results."""
        from calm.public.collections.persistence import ReferenceEnergyResultCollection

        rows = self._repo.list_followup_results(
            run=run,
            kind="reference_energy",
            status=status,
            limit=limit,
        )
        collection = ReferenceEnergyResultCollection(rows)
        if formula is not None:
            collection = collection.where(formula_id=str(formula))
        if reference_kind is not None:
            collection = collection.reference_kind(str(reference_kind))
        return collection

    def reference_energy_result(self, id_or_uid: str):
        """Return one typed authoritative reference-energy result."""
        from calm.public.records.persistence import ProjectReferenceEnergyResult

        return ProjectReferenceEnergyResult.from_item(
            self._repo.get_followup_result(id_or_uid)
        )

    def energy_runs(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative raw-energy workflow runs."""
        return self.runs(run_type="energy_stage", status=status, limit=limit)

    def energy_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return typed authoritative raw total-energy results."""
        from calm.public.collections.persistence import EnergyResultCollection

        return EnergyResultCollection(
            self._repo.list_followup_results(
                run=run,
                prototype=prototype,
                kind="energy_stage",
                status=status,
                limit=limit,
            )
        )

    def energy_result(self, id_or_uid: str):
        """Return one typed authoritative raw total-energy result."""
        from calm.public.records.persistence import ProjectEnergyResult

        return ProjectEnergyResult.from_item(self._repo.get_followup_result(id_or_uid))

    def thermodynamic_runs(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative thermodynamic-derivation runs."""
        return self.runs(
            run_type="thermodynamic_derivation",
            status=status,
            limit=limit,
        )

    def thermodynamic_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return typed authoritative derived thermodynamic quantities."""
        from calm.public.collections.persistence import ThermodynamicResultCollection

        return ThermodynamicResultCollection(
            self._repo.list_followup_results(
                run=run,
                prototype=prototype,
                kind="thermodynamic_quantity",
                status=status,
                limit=limit,
            )
        )

    def thermodynamic_result(self, id_or_uid: str):
        """Return one typed authoritative thermodynamic quantity."""
        from calm.public.records.persistence import ProjectThermodynamicResult

        return ProjectThermodynamicResult.from_item(
            self._repo.get_followup_result(id_or_uid)
        )

    def datasets(self):
        """Return the authoritative collection of persisted datasets.

        Returns:
            (DatasetCollection): A project-backed collection whose records retain
                dataset membership, validation, split, export, and provenance
                operations.
        """
        return self._queries.datasets()

    def dataset(self, id_or_name: str):
        """Return one authoritative dataset bound to this open project."""
        return self.datasets().get(id_or_name)

    def dataset_items(self, dataset: str):
        """Return typed authoritative membership records for one dataset."""
        from calm.public.collections.persistence import DatasetItemCollection
        from calm.public.records.dataset_views import dataset_learning_columns

        record = self.dataset(dataset)
        identifier = record.uid_full or record.id_short or record.name or dataset
        return DatasetItemCollection(
            self._repo.list_dataset_items(identifier),
            learning_columns=dataset_learning_columns(record.settings),
        )

    def create_dataset(
        self,
        name: str,
        items: Any | None = None,
        *,
        settings: Any | None = None,
        description: str | None = None,
        tags: Any | None = None,
    ):
        """Create or reopen a deterministic authoritative dataset.

        Dataset declarations are immutable identity-bearing contracts. Membership
        may subsequently be appended under the persisted duplicate and failure
        policies.

        Args:
            name: Exact non-empty dataset name.
            items: Optional initial authoritative records, identifiers, or supported
                collections for the selected schema.
            settings: Optional ``DatasetSettings``. ``None`` uses
                ``DatasetSettings()``.
            description: Optional human-readable dataset description.
            tags: Optional JSON-compatible tags.

        Returns:
            (ProjectDataset): The project-bound authoritative dataset record.

        Raises:
            TypeError: If settings or initial items violate the schema contract.
            ValueError: If declarations, policies, provenance, or item values are
                invalid.
            DatasetIdentityConflictError: If the name is already bound to a
                different dataset declaration.
        """
        return self._dataset_workflows.create_dataset(
            name,
            items,
            settings=settings,
            description=description,
            tags=tags,
        )

    def add_dataset_items(self, dataset: str, items: Any):
        """Normalize and append authoritative records under persisted policy."""
        return self._dataset_workflows.add_dataset_items(dataset, items)

    def validate_dataset(self, dataset: str):
        """Validate authoritative membership, schema, and provenance."""
        from calm.public.records.datasets import validate_persisted_dataset

        return validate_persisted_dataset(self, self.dataset(dataset))

    def validate_ml_dataset(
        self,
        dataset: str,
        *,
        check_structures: bool = True,
    ):
        """Validate one joined dataset for leakage-safe ML consumption.

        Args:
            dataset: Dataset name, short ID, or full UID.
            check_structures: Verify authoritative structure availability in
                addition to metadata and lineage. Default: ``True``.

        Returns:
            (DatasetMLReadinessReport): Structured errors, warnings, split counts,
                declaration counts, and readiness status.

        Raises:
            KeyError: If no dataset matches the selector.
            ValueError: If the dataset is not ``calm.interface_learning.v1`` or its
                declarations are malformed.
        """
        from calm.public.records.dataset_learning import validate_ml_readiness

        return validate_ml_readiness(
            self,
            self.dataset(dataset),
            check_structures=check_structures,
        )

    def export_dataset(
        self,
        dataset: str,
        destination: str | Path,
        *,
        manifest_format: str = "json",
        include_structures: bool = True,
        structure_format: str = "extxyz",
        overwrite: bool = False,
    ):
        """Atomically export a validated dataset and checksum manifest."""
        from calm.public.records.datasets import export_persisted_dataset

        return export_persisted_dataset(
            self,
            self.dataset(dataset),
            destination,
            manifest_format=manifest_format,
            include_structures=include_structures,
            structure_format=structure_format,
            overwrite=overwrite,
        )

    def campaigns(self):
        """Return the authoritative collection of persisted campaigns.

        Returns:
            (CampaignCollection): A project-backed collection containing
                deterministic campaign specifications and their persisted runs.
        """
        return self._queries.campaigns()

    def runs(
        self,
        *,
        run_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative persisted workflow runs."""
        from calm.public.collections.persistence import RunCollection

        return RunCollection(
            self._repo.list_runs(
                run_type=run_type,
                status=status,
                limit=limit,
            )
        )

    def run(self, id_or_uid: str):
        """Return exactly one authoritative persisted workflow run."""
        from calm.public.records.persistence import ProjectRun

        return ProjectRun.from_item(self._repo.get_run(id_or_uid))

    def followups(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative persisted follow-up results."""
        from calm.public.collections.persistence import FollowupCollection

        return FollowupCollection(
            self._repo.list_followup_results(
                run=run,
                prototype=prototype,
                kind=kind,
                status=status,
                limit=limit,
            )
        )

    def registry_runs(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative registry-search workflow runs."""
        return self.runs(run_type="registry_search", status=status, limit=limit)

    def registry_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative persisted registry-search follow-up results."""
        return self.followups(
            run=run,
            prototype=prototype,
            kind="registry_search",
            status=status,
            limit=limit,
        )

    def relaxation_runs(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative structural-relaxation workflow runs."""
        return self.runs(run_type="relaxation_stage", status=status, limit=limit)

    def relaxation_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ):
        """Return typed authoritative structural-relaxation results."""
        from calm.public.collections.persistence import RelaxationResultCollection

        return RelaxationResultCollection(
            self._repo.list_followup_results(
                run=run,
                prototype=prototype,
                kind="relaxation_stage",
                status=status,
                limit=limit,
            )
        )

    def relaxation_result(self, id_or_uid: str):
        """Return one typed authoritative structural-relaxation result."""
        from calm.public.records.persistence import ProjectRelaxationResult

        return ProjectRelaxationResult.from_item(
            self._repo.get_followup_result(id_or_uid)
        )

    def followup(self, id_or_uid: str):
        """Return exactly one authoritative persisted follow-up result."""
        from calm.public.records.persistence import ProjectFollowupResult

        return ProjectFollowupResult.from_item(
            self._repo.get_followup_result(id_or_uid)
        )

    def run_artifacts(self, run: str):
        """Return authoritative artifacts attached to one persisted run."""
        from calm.public.collections.persistence import ArtifactCollection

        return ArtifactCollection(self._repo.list_artifacts(run))

    def edges(
        self,
        *,
        src: str | None = None,
        dst: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ):
        """Return authoritative persisted provenance edges."""
        from calm.public.collections.persistence import EdgeCollection

        return EdgeCollection(
            self._repo.list_edges(
                src=src,
                dst=dst,
                kind=kind,
                limit=limit,
            )
        )

    def lineage(
        self,
        target: Any,
        *,
        direction: str = "both",
        depth: int | None = None,
        kinds: tuple[str, ...] | list[str] | set[str] | None = None,
    ):
        """Return the authoritative persisted provenance subgraph for *target*.

        ``direction`` may be ``"upstream"``, ``"downstream"``, or ``"both"``.
        ``depth=None`` traverses the complete connected persisted subgraph.
        """
        return self._lineage_queries.lineage(
            target,
            direction=direction,
            depth=depth,
            kinds=kinds,
        )

    def create_campaign(
        self,
        *,
        name: str | None = None,
        spec: dict | None = None,
        cases: Any | None = None,
        settings: Any | None = None,
    ):
        """Create or reopen a deterministic authoritative campaign.

        Args:
            name: Required exact non-empty campaign name.
            spec: Optional complete persisted campaign specification mapping.
            cases: Optional sequence of validated ``CampaignCase`` declarations.
            settings: Optional ``CampaignSettings`` paired with ``cases``.

        Returns:
            (ProjectCampaign): The project-bound authoritative campaign record.

        Raises:
            TypeError: If cases, settings, or specification values violate the
                typed public contract.
            ValueError: If creation arguments are incomplete or the specification
                is invalid.
            CampaignIdentityConflictError: If the campaign name is already bound to
                a different specification.

        Notes:
            Supply either ``spec`` or typed ``cases`` plus settings; the two forms
            are alternative representations of one deterministic specification.
        """
        return self._campaign_workflows.create_campaign(
            name=name,
            spec=spec,
            cases=cases,
            settings=settings,
        )

    def run_campaign(
        self,
        campaign: Any,
        *,
        resume: bool = True,
        export_root: str | Path | None = None,
        reporter: Any | None = None,
    ):
        """Run a first-class campaign synchronously in the current process.

        Args:
            campaign: Campaign name, short ID, full UID, or project-bound
                ``ProjectCampaign``.
            resume: Reuse an identical completed campaign run and completed
                per-stage work where supported. Default: ``True``.
            export_root: Optional directory for case dataset exports. This does not
                participate in scientific campaign identity.
            reporter: Optional progress reporter.

        Returns:
            (CampaignWorkflowResult): Authoritative campaign/run records, per-case
                outcomes, comparison helpers, and reuse status.

        Raises:
            KeyError: If no campaign matches the selector.
            ValueError: If the supplied campaign belongs to another project or does
                not match authoritative specification identity.
            RuntimeError: If synchronous execution cannot produce or persist an
                authoritative campaign result.
        """
        return self._campaign_workflows.run_campaign(
            campaign,
            resume=resume,
            export_root=export_root,
            reporter=reporter,
        )

    def search_interfaces(
        self,
        surface_a,
        surface_b,
        *,
        settings=None,
        name: str | None = None,
        resume: bool = True,
        on_error: str = "raise",
        reporter: Any | None = None,
    ):
        """Run or resume one deterministic project-backed interface search.

        Args:
            surface_a (GeneratedSurface | str): First exact oriented surface or
                supported persisted-surface selector.
            surface_b (GeneratedSurface | str): Second exact oriented surface or
                supported persisted-surface selector.
            settings (SearchSettings | None): Search controls. ``None`` uses
                ``SearchSettings()``.
            name: Required non-empty persisted search name.
            resume: Reuse a completed search with identical surfaces and settings;
                incomplete or failed runs restart synchronously. Default: ``True``.
            on_error: ``"record"`` returns a failed durable view; ``"raise"``
                persists failure state and re-raises. Default: ``"raise"``.
            reporter: Optional progress reporter.

        Returns:
            (PersistedInterfaceSearch): Durable project-bound search view.

        Raises:
            TypeError: If surfaces or settings violate the public search contract.
            ValueError: If name, settings, or ``on_error`` is invalid.
            SearchIdentityConflictError: If ``name`` is already bound to different
                scientific inputs.
            RuntimeError: If search execution fails with ``on_error="raise"``.

        Notes:
            Scientific identity is derived from exact persisted surface identities
            and canonical settings; the human-readable name is an alias.
        """
        return self._search_workflows.search_interfaces(
            surface_a,
            surface_b,
            settings=settings,
            name=name,
            resume=resume,
            on_error=on_error,
            reporter=reporter,
        )

    def optimize_material(
        self,
        material,
        *,
        potential=None,
        calculator=None,
        fmax: float = 0.03,
        steps: int = 500,
        relax_cell: bool = True,
        optimizer: str = "BFGS",
        name: str | None = None,
        reporter: Any | None = None,
    ):
        """Optimize and persist one bulk material through the project.

        Args:
            material (Material | str): Public material or exact persisted selector.
            potential (Potential | None): Optional typed potential specification.
            calculator (Any | None): Optional explicit ASE-compatible calculator.
                Do not supply both an incompatible calculator and potential.
            fmax: Required maximum residual force, in eV/Å. Default: ``0.03``.
            steps: Maximum optimizer steps. Default: ``500``.
            relax_cell: Permit bulk cell degrees of freedom. Default: ``True``.
            optimizer: Exact optimizer name: ``"BFGS"``, ``"LBFGS"``, or
                ``"FIRE"``. Default: ``"BFGS"``.
            name: Optional persisted label for the optimized material.
            reporter: Optional progress reporter.

        Returns:
            (Material): Authoritative optimized-bulk material with calculator and
                convergence provenance.

        Raises:
            KeyError: If a material selector does not match.
            TypeError: If material, potential, or calculator is unsupported.
            ValueError: If optimizer or convergence controls are invalid.
            RuntimeError: If optimization fails or does not produce a persistable
                structure.
        """
        return self._material_optimizations.optimize_material(
            material,
            potential=potential,
            calculator=calculator,
            fmax=fmax,
            steps=steps,
            relax_cell=relax_cell,
            optimizer=optimizer,
            name=name,
            reporter=reporter,
        )

    def campaign(self, id_or_name: str):
        """Return exactly one persisted campaign bound to this project.

        Args:
            id_or_name: Campaign short ID, full UID, or exact persisted name.

        Returns:
            (ProjectCampaign): The matching campaign with project-bound ``runs``
                and ``run`` operations.

        Raises:
            KeyError: If no campaign matches.
            AmbiguousProjectQueryError: If the selector is not unique.
        """
        from calm.public.records.persistence import ProjectCampaign

        return ProjectCampaign.from_item(
            self.campaigns().get(id_or_name),
            project=self,
        )

    def campaign_run(self, id_or_name: str):
        """Return exactly one persisted campaign-run record."""
        from calm.public.records.persistence import ProjectCampaignRun

        return ProjectCampaignRun.from_item(self._repo.get_campaign_run(id_or_name))

    def campaign_for_dataset(self, dataset_id_or_uid: str):
        """Return the campaign that authoritatively produced one dataset.

        Args:
            dataset_id_or_uid: Persisted dataset short ID or full UID.

        Returns:
            (ProjectCampaign): The matching authoritative campaign record.

        Raises:
            KeyError: If the dataset has no persisted producing campaign.
        """
        from calm.public.records.persistence import ProjectCampaign

        return ProjectCampaign.from_item(
            self._repo.get_campaign_for_dataset(dataset_id_or_uid)
        )

    def campaign_run_for_dataset(self, dataset_id_or_uid: str):
        """Return the campaign run that authoritatively produced one dataset.

        Args:
            dataset_id_or_uid: Persisted dataset short ID or full UID.

        Returns:
            (ProjectCampaignRun): The matching authoritative campaign-run record.

        Raises:
            KeyError: If the dataset has no persisted producing campaign run.
        """
        from calm.public.records.persistence import ProjectCampaignRun

        return ProjectCampaignRun.from_item(
            self._repo.get_campaign_run_for_dataset(dataset_id_or_uid)
        )

    def plot_strain_partition_scan(
        self,
        run: str,
        *,
        filename: str = "strain_partition_scan.png",
        metric: str | None = None,
    ):
        """Render the persisted strain-partition scan for one run."""
        return self._workspace.strain_partition_plot(
            run,
            filename=filename,
            metric=metric,
        )

    def plot_registry_search(
        self,
        run: str,
        *,
        filename: str = "registry_search.png",
    ):
        """Render the persisted registry search for one run."""
        return self._workspace.registry_search_plot(run, filename=filename)

    def material(self, id_or_name: str):
        """Return exactly one authoritative persisted material."""
        return self.materials().get(id_or_name)

    def export_materials(
        self,
        *names: str,
        directory: str | Path,
        format: str = "vasp",
        reporter: Any | None = None,
    ) -> list[Path]:
        """Export named persisted materials to files and return written paths.

        Names may be labels or id_short values. This helper resolves each
        material via project.material(...) and calls Material.to_file on it.
        """

        from calm.public.presentation.reporting import ensure_console_reporter

        rep = ensure_console_reporter(reporter)
        from calm.public.workflows.surfaces import export_materials as _export_mat

        return _export_mat(
            self, *names, directory=directory, format=format, reporter=rep
        )

    def generate_surfaces(
        self,
        material: str | Any | list[Any],
        *,
        millers: list[tuple[int, int, int]],
        layers: int | None = None,
        thickness: float | None = None,
        vacuum: float | None = None,
        enumerate_terminations: bool = True,
        reporter: Any | None = None,
    ) -> list[Any]:
        """Generate and persist canonical oriented surface records.

        Args:
            material: Persisted material selector, public ``Material``, or sequence
                of either. Unpersisted public materials are ingested first.
            millers: Non-empty Miller-index triples generated for every material.
            layers: Optional exact slab layer count. Mutually exclusive with
                ``thickness`` where the construction backend requires one size mode.
            thickness: Optional target slab width, in angstrom.
            vacuum: Optional boundary-vacuum thickness, in angstrom.
            enumerate_terminations: Persist all canonical distinct terminations.
                Default: ``True``.
            reporter: Optional progress reporter.

        Returns:
            (list[GeneratedSurface]): Authoritative materialized surface records in
                deterministic material, Miller, and termination order.

        Raises:
            KeyError: If a persisted material selector does not match.
            TypeError: If material or Miller inputs violate the public contract.
            ValueError: If slab-size, vacuum, or Miller controls are invalid.
            RuntimeError: If the parent bulk or generated slabs lack authoritative
                atomistic structures.

        Notes:
            Positive-vacuum outputs use the canonical vertical boundary vector;
            physical construction deformation remains explicit provenance.
        """
        from calm.public.workflows.surfaces import (
            generate_surfaces as _generate_surfaces,
        )

        return _generate_surfaces(
            self,
            material,
            millers=millers,
            layers=layers,
            thickness=thickness,
            vacuum=vacuum,
            enumerate_terminations=enumerate_terminations,
            reporter=reporter,
        )

    def export_surfaces(
        self,
        *ids_or_names: str,
        directory: str | Path,
        format: str = "vasp",
        materials: list[str] | None = None,
        millers: list[tuple[int, int, int]] | None = None,
        reporter: Any | None = None,
    ) -> list[Path]:
        """Export authoritative surfaces by identifiers or exact criteria."""
        from calm.public.workflows.surfaces import export_surfaces as _export

        return _export(
            self,
            *ids_or_names,
            directory=directory,
            format=format,
            materials=materials,
            millers=millers,
            reporter=reporter,
        )

    def surface(
        self,
        id_or_name: str | None = None,
        *,
        material: Any | None = None,
        miller: tuple[int, int, int] | None = None,
        termination: str | None = None,
        termination_top: str | None = None,
        termination_bottom: str | None = None,
        termination_shift: int | None = None,
    ):
        """Return exactly one persisted surface.

        Resolve directly by stable slab short ID/full UID, or by an exact
        material + Miller + termination selection. Ordered top/bottom labels
        may be used to select the face that will participate in an interface.
        Zero matches raise ``KeyError``. Multiple matches raise
        ``AmbiguousProjectQueryError``; CALM never selects a termination by
        sort order or atom count.
        """
        from calm.public.workflows.surfaces import surface as _surface

        return _surface(
            self,
            id_or_name=id_or_name,
            material=material,
            miller=miller,
            termination=termination,
            termination_top=termination_top,
            termination_bottom=termination_bottom,
            termination_shift=termination_shift,
        )


def open_project(
    path: str | Path,
    *,
    reporter: Any | None = None,
    summarize: bool = False,
) -> Project:
    """Open or create a directory-backed project using the current schema.

    Existing databases must match the schema written by the current CALM
    codebase. CALM stable does not migrate or reinterpret older project formats;
    historical projects must be regenerated in a new current-format directory.

    Args:
        path: Project directory containing the database and artifact tree.
        reporter: Optional reporter used for human-readable progress output.
        summarize: Emit a concise project summary after opening.

    Returns:
        A public project facade bound to the opened workspace.

    Raises:
        ImportError: If the project-storage dependencies are unavailable.
        ProjectPersistenceError: If an existing database is not current.
    """
    try:
        from calm.project.bootstrap import open_workspace

        ws = open_workspace(path)
        project = Project(ws, path=path)
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "").split(".", 1)[0] == "sqlalchemy":
            raise ImportError(
                "CALM project storage requires SQLAlchemy. Install with "
                '`python -m pip install "SQLAlchemy>=2,<3"`.'
            ) from exc
        raise
    except RuntimeError as exc:
        from calm.public.errors import ProjectPersistenceError

        raise ProjectPersistenceError(str(exc)) from exc

    if summarize:
        from calm.public.presentation.reporting import ensure_console_reporter

        rep = ensure_console_reporter(reporter)
        try:
            project._health.report_open_project(rep)
        except Exception as exc:
            rep.warn(f"Project opened, but summary generation failed: {exc}")

    return project
