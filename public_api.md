# CALM public API

This file is the maintainer-facing inventory of CALM's stable supported user
surface.

CALM exposes one Project-centered public API: 34 canonical imports and 68
`Project` operations. Supported imports originate from `calm`; implementation
packages are internal and are not parallel user APIs. Project persistence uses
schema `v2.0.0` with an exact-current, regeneration-only historical-project
policy.

The reviewed inventory is stored in
`engineering/architecture/current-public-contract.json` and verified by
`engineering/qualification/check_public_api_consistency.py`. Contract schema
``calm.public_api_contract.v4`` also records the fields, properties, and methods
that the generated MkDocs reference exposes for canonical inputs and returned
workflow objects. Those documentation members do not create additional import
surfaces.

## Canonical imports

<!-- public-api-table:begin -->
| Import path | Kind | Group | Purpose |
| --- | --- | --- | --- |
| calm.__version__ | constant | metadata | Installed CALM version. |
| calm.Project | class | project | Persistent scientific workflow entry point and query surface. |
| calm.open_project | function | project | Open or create a current-schema directory-backed CALM project. |
| calm.Material | class | inputs | User-authored bulk-material input and project-returned material projection. |
| calm.Potential | class | inputs | Typed calculator or machine-learned interatomic-potential input. |
| calm.SearchSettings | class | settings | Control deterministic interface-superlattice search and admissibility. |
| calm.StrainPartitionSettings | class | settings | Control authoritative strain-partition scanning and objective selection. |
| calm.BuildSettings | class | settings | Control atomistic interface construction from a persisted candidate. |
| calm.RegistrySettings | class | settings | Control deterministic in-plane registry refinement. |
| calm.RelaxSettings | class | settings | Control authoritative structural relaxation and convergence. |
| calm.EnergySettings | class | settings | Control authoritative raw total-energy evaluation. |
| calm.EnergyConvention | class | settings | Declare the formula and normalization for a derived interfacial quantity. |
| calm.ReferenceEnergySettings | class | settings | Supply explicit thermodynamic reference energies with named units. |
| calm.DatasetFeature | class | settings | Declare one named machine-learning feature from a joined dataset row. |
| calm.DatasetTarget | class | settings | Declare one named supervised-learning target from a joined dataset row. |
| calm.DatasetSplitSettings | class | settings | Configure deterministic group-preserving train/validation/test assignment. |
| calm.DatasetSettings | class | settings | Configure authoritative dataset schema, validation, splitting, and export behavior. |
| calm.CampaignCase | class | settings | Declare one named system and workflow case in a synchronous campaign. |
| calm.CampaignSettings | class | settings | Configure the stages and shared controls for a synchronous campaign. |
| calm.CalmPublicAPIError | class | errors | Base exception for errors intentionally exposed by the CALM public API. |
| calm.CalmDependencyError | class | errors | Report a missing optional dependency required by a requested operation. |
| calm.CalmNoCandidatesError | class | errors | Report that a workflow requiring candidates produced none. |
| calm.AmbiguousProjectQueryError | class | errors | Report a project query that requires further disambiguation. |
| calm.SearchIdentityConflictError | class | errors | Report reuse of a search name with incompatible scientific inputs. |
| calm.DatasetIdentityConflictError | class | errors | Report reuse of a dataset name with incompatible identity-bearing inputs. |
| calm.CampaignIdentityConflictError | class | errors | Report reuse of a campaign name with incompatible identity-bearing inputs. |
| calm.ProjectPersistenceError | class | errors | Report that a directory-backed project cannot be opened or persisted safely. |
| calm.ProjectReproducibilityError | class | errors | Report failure to create or verify a project reproducibility manifest. |
| calm.DatasetValidationError | class | errors | Report authoritative dataset validation failure. |
| calm.UnsupportedReferenceWorkflowError | class | errors | Report a thermodynamic reference workflow that CALM does not implement. |
| calm.tutorial_structure | function | utilities | Load one package-owned structure used by the public tutorials. |
| calm.load_structure | function | utilities | Load an atomistic structure from a supported file. |
| calm.write_structure | function | utilities | Write an atomistic structure to a supported file. |
| calm.write_json | function | utilities | Write canonical JSON output. |
<!-- public-api-table:end -->

## Project operations

All persistent workflows begin with `calm.open_project(...)`. User-authored materials enter through `Project.add_material(...)`; searches and later stages persist their results automatically. The methods below are the reviewed operations on the returned `calm.Project`.

<!-- project-method-table:begin -->
| Method | Group | Purpose |
| --- | --- | --- |
| Project.summary | project | Return a compact summary of the open project. |
| Project.reproducibility_manifest | project | Build an in-memory reproducibility snapshot for the current project state. |
| Project.write_reproducibility_manifest | project | Write an atomic project reproducibility manifest and return its typed snapshot. |
| Project.verify_reproducibility_manifest | project | Compare a recorded manifest with the current project and runtime state. |
| Project.configure | project | Persist authoritative project-wide workflow configuration. |
| Project.artifacts | queries_and_provenance | Return the project artifact-discovery helper. |
| Project.materials | materials | Return persisted materials, optionally filtered by identity. |
| Project.add_material | materials | Persist one user-authored material and return its project projection. |
| Project.surfaces | surfaces | Return persisted surfaces, optionally filtered by exact identity. |
| Project.searches | search_and_refinement | Return persisted interface searches. |
| Project.search | search_and_refinement | Return the durable query view for one persisted interface search. |
| Project.build_interfaces | search_and_refinement | Build and persist top candidates from a search name or durable search view. |
| Project.refine_interfaces | search_and_refinement | Run authoritative strain-partition and registry refinement for one persisted search. |
| Project.refine_registry | search_and_refinement | Run authoritative registry refinement from persisted strain-partitioned interfaces. |
| Project.candidates | search_and_refinement | Return persisted interface candidates. |
| Project.interfaces | search_and_refinement | Return persisted interface models. |
| Project.refined_interfaces | search_and_refinement | Return authoritative persisted strain- or registry-refined interfaces. |
| Project.interface | search_and_refinement | Return exactly one persisted interface record. |
| Project.interface_atoms | search_and_refinement | Return authoritative interface atoms or reconstruct a non-persisted fractional registry-shift variant. |
| Project.relaxed_interfaces | relaxation_and_energy | Return authoritative structurally relaxed interfaces. |
| Project.relax_interfaces | relaxation_and_energy | Synchronously relax authoritative refined interfaces. |
| Project.evaluate_reference_energies | relaxation_and_energy | Calculate and persist per-interface thermodynamic references. |
| Project.evaluate_energies | relaxation_and_energy | Evaluate raw energies and optionally derive an explicit quantity. |
| Project.reference_energy_runs | relaxation_and_energy | Return authoritative reference-energy workflow runs. |
| Project.reference_energy_results | relaxation_and_energy | Return authoritative per-interface reference-energy results. |
| Project.reference_energy_result | relaxation_and_energy | Return one typed authoritative reference-energy result. |
| Project.energy_runs | relaxation_and_energy | Return authoritative raw-energy workflow runs. |
| Project.energy_results | relaxation_and_energy | Return typed authoritative raw total-energy results. |
| Project.energy_result | relaxation_and_energy | Return one typed authoritative raw total-energy result. |
| Project.thermodynamic_runs | relaxation_and_energy | Return authoritative thermodynamic-derivation runs. |
| Project.thermodynamic_results | relaxation_and_energy | Return typed authoritative derived thermodynamic quantities. |
| Project.thermodynamic_result | relaxation_and_energy | Return one typed authoritative thermodynamic quantity. |
| Project.datasets | datasets | Return persisted learning datasets. |
| Project.dataset | datasets | Return one authoritative dataset bound to this open project. |
| Project.dataset_items | datasets | Return typed authoritative membership records for one dataset. |
| Project.create_dataset | datasets | Create or reopen a deterministic authoritative dataset. |
| Project.add_dataset_items | datasets | Normalize and append authoritative records under persisted policy. |
| Project.validate_dataset | datasets | Validate authoritative membership, schema, and provenance. |
| Project.validate_ml_dataset | datasets | Validate one joined dataset for leakage-safe ML consumption. |
| Project.export_dataset | datasets | Atomically export a validated dataset and checksum manifest. |
| Project.campaigns | campaigns | Return persisted campaigns. |
| Project.runs | queries_and_provenance | Return authoritative persisted workflow runs. |
| Project.run | queries_and_provenance | Return exactly one authoritative persisted workflow run. |
| Project.followups | queries_and_provenance | Return authoritative persisted follow-up results. |
| Project.registry_runs | search_and_refinement | Return authoritative registry-search workflow runs. |
| Project.registry_results | search_and_refinement | Return authoritative persisted registry-search follow-up results. |
| Project.relaxation_runs | relaxation_and_energy | Return authoritative structural-relaxation workflow runs. |
| Project.relaxation_results | relaxation_and_energy | Return typed authoritative structural-relaxation results. |
| Project.relaxation_result | relaxation_and_energy | Return one typed authoritative structural-relaxation result. |
| Project.followup | queries_and_provenance | Return exactly one authoritative persisted follow-up result. |
| Project.run_artifacts | queries_and_provenance | Return authoritative artifacts attached to one persisted run. |
| Project.edges | queries_and_provenance | Return authoritative persisted provenance edges. |
| Project.lineage | queries_and_provenance | Return the authoritative persisted provenance subgraph for *target*. |
| Project.create_campaign | campaigns | Create or reopen a deterministic authoritative campaign. |
| Project.run_campaign | campaigns | Run a first-class campaign synchronously in the current process. |
| Project.search_interfaces | search_and_refinement | Run or resume one deterministic interface search and return its durable project view. |
| Project.optimize_material | materials | Optimize and persist a project material using the requested potential and settings. |
| Project.campaign | campaigns | Return exactly one persisted campaign. |
| Project.campaign_run | campaigns | Return exactly one persisted campaign-run record. |
| Project.campaign_for_dataset | campaigns | Return the campaign associated with one persisted dataset. |
| Project.campaign_run_for_dataset | campaigns | Return the campaign run associated with one persisted dataset. |
| Project.plot_strain_partition_scan | search_and_refinement | Render the persisted strain-partition scan for one run. |
| Project.plot_registry_search | search_and_refinement | Render the persisted registry-search trace for one run. |
| Project.material | materials | Return a public Material facade for a persisted material. |
| Project.export_materials | materials | Export named persisted materials to files and return written paths. |
| Project.generate_surfaces | surfaces | Generate and persist slabs through the canonical surface helper. |
| Project.export_surfaces | surfaces | Export persisted slabs/surfaces to POSCAR files and return written paths. |
| Project.surface | surfaces | Return exactly one persisted surface. |
<!-- project-method-table:end -->

## Returned workflow objects

These objects are returned by project operations. Users do not construct or
import them from implementation packages; their public behavior is reached
through the open project that produced them.

<!-- workflow-object-table:begin -->
| Object | Implementation owner | Role |
| --- | --- | --- |
| GeneratedSurface | calm.public.records.generated_surface.GeneratedSurface | Surface record returned by Project surface generation and queries. |
| SurfaceCollection | calm.public.collections.structures.SurfaceCollection | Typed collection returned by Project.surfaces(). |
| PersistedInterfaceSearch | calm.public.records.search.PersistedInterfaceSearch | Durable query and navigation view returned by Project.search_interfaces() and Project.search(). |
| CandidateCollection | calm.public.collections.candidates.CandidateCollection | Typed candidate query and selection result. |
| InterfaceCollection | calm.public.collections.interfaces.InterfaceCollection | Typed collection of constructed, refined, or relaxed interfaces. |
| ProjectRun | calm.public.records.persistence.ProjectRun | Authoritative persisted workflow run record. |
| ProjectSearch | calm.public.records.persistence.ProjectSearch | Authoritative persisted search record. |
| ProjectFollowupResult | calm.public.records.persistence.ProjectFollowupResult | Authoritative persisted refinement or follow-up result. |
| ProjectInterface | calm.public.records.persistence.ProjectInterface | Authoritative persisted interface record. |
| ProjectEnergyResult | calm.public.records.persistence.ProjectEnergyResult | Authoritative raw energy result. |
| ProjectThermodynamicResult | calm.public.records.persistence.ProjectThermodynamicResult | Authoritative derived thermodynamic result. |
| ProjectDataset | calm.public.records.persistence.ProjectDataset | Project-bound authoritative dataset record. |
| ProjectDatasetItem | calm.public.records.persistence.ProjectDatasetItem | Authoritative dataset membership record. |
| ProjectCampaign | calm.public.records.persistence.ProjectCampaign | Project-bound campaign record. |
| ProjectCampaignRun | calm.public.records.persistence.ProjectCampaignRun | Authoritative campaign execution record. |
| ProjectArtifact | calm.public.records.persistence.ProjectArtifact | Authoritative artifact record. |
| ProjectEdge | calm.public.records.persistence.ProjectEdge | Authoritative provenance edge. |
| LineageGraph | calm.public.records.persistence.LineageGraph | Typed provenance graph returned by Project.lineage(). |
| RelaxationWorkflowResult | calm.public.records.followups.RelaxationWorkflowResult | Composite result of Project.relax_interfaces(). |
| EnergyWorkflowResult | calm.public.records.followups.EnergyWorkflowResult | Composite result of Project.evaluate_energies(). |
| CampaignWorkflowResult | calm.public.inputs.campaigns.CampaignWorkflowResult | Composite result of Project.run_campaign(). |
| DatasetValidationReport | calm.public.records.datasets.DatasetValidationReport | Structured dataset validation report. |
| DatasetExportResult | calm.public.records.datasets.DatasetExportResult | Structured dataset export result. |
| ProjectReproducibilityManifest | calm.public.records.reproducibility.ProjectReproducibilityManifest | Immutable project reproducibility snapshot. |
| ReproducibilityVerificationReport | calm.public.records.reproducibility.ReproducibilityVerificationReport | Structured manifest verification report. |
<!-- workflow-object-table:end -->

## Internal namespaces

The following namespaces are implementation boundaries, not supported user APIs:

- `calm.public`
- `calm.project`
- `calm.interface`
- `calm.slab`
- `calm.bulk`
- `calm.calculators`
- `calm.viz`

## Retired duplicate entry points

The consolidation intentionally retires the following alternate routes:

- `calm.Surface`
- `calm.SurfacePair`
- `calm.InterfaceRequest`
- `calm.Selection`
- `calm.StrainFilter`
- `calm.search_interfaces`
- `calm.search_interface_grid`
- `calm.viz`
- `Material.optimize`
- `InterfaceCandidate.build`
- `InterfaceCandidate.search_registry`
- `InterfaceSearchResult.build`
- `InterfaceSearchResult.build_all`
- `CandidateCollection.build_all`
- `InterfaceModel.energy`
- `InterfaceModel.relax`
- `InterfaceCollection.relax`
- `InterfaceCollection.evaluate_reference_energies`
- `InterfaceCollection.evaluate_energies`
- `PersistedInterfaceSearch.build_top`
- `PersistedInterfaceSearch.refine_interfaces`
- `PersistedInterfaceSearch.relax_interfaces`
- `PersistedInterfaceSearch.evaluate_reference_energies`
- `PersistedInterfaceSearch.evaluate_energies`

CALM 1.0 follows semantic versioning for the supported public API. Changes are
reviewed for coherence and scientific correctness, with incompatible public API
changes reserved for a future major release.
