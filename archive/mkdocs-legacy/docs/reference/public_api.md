# CALM Public API Inventory

API stability
-------------

CALM intends to follow **semver-like** stability rules:

- **Public symbols listed below are supported**.
- Backwards-incompatible changes to public symbols should be avoided.
- When change is necessary, CALM will (where feasible):
  1) keep the old import path working via a shim,
  2) emit a :class:`DeprecationWarning` (or project-specific warning),
  3) remove the old path only in a future major release (or a clearly-marked breaking release).

The **canonical inventory** of public symbols is the table below. Tests enforce that these
import paths remain valid.

Inventory conventions
---------------------

- **Requires**: comma-separated Python module names that must be importable for the
  symbol to import (import-time dependencies). The test suite uses this column to
  skip import checks when optional/heavy requirements are not installed.
- **Stability**: one of `stable`, `provisional`, or `deprecated`.

<!-- public-api-table:begin -->
| Import path | Type | Purpose | Stability | Requires | Notes |
|---|---|---|---|---|---|
| calm | module | Top-level UX facade; provides `calm.api.PUBLIC_EXPORTS` | stable |  | Lazy exports via `__getattr__` |
| calm.api | module | Versioned public API contract module | stable |  | Import-light; lazy resolves symbols |
| calm.__version__ | constant | Package version string (best-effort; uses installed metadata when available). | stable |  | Falls back to 0.0.0+unknown when package metadata is unavailable. |
| calm.Bulk | class | Bulk crystal structure wrapper (ASE Atoms + symmetry metadata) | stable | ase, spglib |  |
| calm.SlabSpec | class | Declarative slab construction parameters (legacy) | deprecated | ase, spglib | Prefer oriented-slab APIs under `calm.slab`. |
| calm.Slab | class | Surface slab wrapper and matching helpers (legacy) | deprecated | ase, spglib | Prefer oriented-slab APIs under `calm.slab`. |
| calm.PrototypeSearchConfig | class | Configuration for prototype search and filtering | stable |  | Accepts `top_k=` as an init-time alias for `max_results=` |
| calm.PrototypeSearchResult | class | Result object for prototype search | stable | numpy |  |
| calm.SupercellRecipe2D | class | Encodes the 2D supercell mapping for a prototype | stable | ase, spglib |  |
| calm.InterfacePrototype | class | Candidate interface prototype (two slabs + mapping) | stable | ase, spglib |  |
| calm.StrainModel | class | Defines how strain is assigned between slabs | stable |  |  |
| calm.StrainState | class | Chosen strain variant for a prototype under a model | stable | numpy |  |
| calm.InterfaceBuildConfig | class | Configuration for building an atomic interface | stable |  |  |
| calm.Interface | class | Built interface structure with metadata | stable | ase, spglib |  |
| calm.EnergyConfig | class | Configuration for energy evaluation | stable |  |  |
| calm.EnergyResult | class | Result object for interfacial energy evaluation | stable | numpy |  |
| calm.InterfaceEnergyScalarResult | class | Scalar interface-energy arithmetic result container | stable |  | For workflows where energies, counts, and area are already known |
| calm.compute_interface_energy_from_scalars | function | Public scalar helper for gamma arithmetic from known energies/counts/area | stable |  | Arithmetic only; does not build interfaces or run calculators |
| calm.EV_PER_A2_TO_J_PER_M2 | constant | Conversion from eV/Å² to J/m² | stable |  | Canonical constant for gamma conversion (16.02176634) |
| calm.Material | class | Public Material facade (bulk wrapper and helpers) | stable | ase | High-level user-facing bulk/material representation |
| calm.Surface | class | Public Surface facade (slab request wrapper) | stable | ase | User-facing surface/slab request and metadata |
| calm.SurfacePair | class | Pairing of two Surfaces for interface requests | stable |  | Serializable surface pair container |
| calm.InterfaceRequest | class | Serializable interface search request (surface pair + settings) | stable |  | Supports to_yaml/from_yaml and run() |
| calm.SearchSettings | class | High-level search settings for interface search | stable |  | Accepts max_principal_strain, max_atoms, max_supercell_index, etc. |
| calm.StrainPartitionSettings | class | Settings for strain partitioning during interface builds and scans | stable |  | Controls strain partition model selection and scan density |
| calm.BuildSettings | class | High-level build settings for interface construction | stable |  | Strain partitioning, gap, vacuum, translation defaults |
| calm.RegistrySettings | class | Settings for registry search (grid/monte_carlo) | stable |  | Controls sampling and registry search behavior |
| calm.RelaxSettings | class | Relaxation settings for relax workflows | stable |  | fmax, steps, relax_cell, trajectory |
| calm.EnergyConvention | class | Energy/reference convention selection | stable |  | Controls reference choice and strain energy inclusion |
| calm.ReferenceEnergies | class | Reference energies container for interfacial energy eval | stable |  | values per-material and units |
| calm.EnergySettings | class | High-level settings for energy and interfacial-energy workflows | stable |  | Controls optional energy-evaluation behavior and defaults |
| calm.Potential | class | MLIP / calculator facade for energy/relax workflows | stable |  | Factory for MLIPs and calculator wrappers |
| calm.Selection | class | Reusable selection criteria for candidate/result collections | stable |  | Pareto, strain, atom-count, material-pair, and grouping filters |
| calm.StrainFilter | class | Query filter for candidate/structure strain metrics | stable |  | Filter iso/deviatoric/max_principal ranges |
| calm.search_interfaces | function | High-level search_interfaces facade (memory/project) | stable | ase, spglib | User-friendly wrapper for prototype search; supports store=None and dry_run |
| calm.search_interface_grid | function | High-level grid/campaign search wrapper | stable | ase, spglib | Cartesian product or explicit pairs; returns campaign-like result |
| calm.estimate_interface_search | function | Estimate interface-search cost and likely constraints before running a full search | stable | ase, spglib | Returns a lightweight diagnostic/estimate object |
| calm.compare_potentials | function | Compare MLIP/ASE potentials against reference energies/forces | provisional | ase | Reserved public benchmarking API; not yet wired in this branch |
| calm.load_result | function | Load a saved public CALM result/archive | stable |  | Rehydrates result-like public objects where possible |
| calm.load_recipe | function | Load a human-readable CALM recipe for reconstruction | stable |  | Returns a recipe/request object for rerun or build |
| calm.open_project | function | Open or create a workspace/project rooted at a directory | stable | sqlalchemy | Directory-backed workspace with SQLite DB + artifacts/ subdir |
| calm.compute_strained_bulk_reference_energies | function | Compute strained-bulk reference energies per formula unit (prototype/interface + calculator) | stable |  | Pedagogical helper; uses unrelaxed_scaled_positions convention |
| calm.StrainedBulkReferenceResult | class | Result container for strained-bulk reference energies per formula unit | stable | numpy | Returned by compute_strained_bulk_reference_energies; includes mu_* and provenance |
| calm.interface.RegistrySearchConfig | class | Configuration for Monte Carlo registry search | provisional |  | Enables optional z-padding exploration via bounds/step scale |
| calm.interface.StrainPartitionCandidate | class | Candidate strain partition (alpha, score, strain_state) | provisional | numpy | Best-effort container for scan results |
| calm.interface.StrainPartitionResult | class | Result of scanning strain partitions (best candidate + metadata) | provisional | numpy | Stores only best by default; optional trace for debugging |
| calm.interface.scan_geodesic_strain_partitions | function | Scan geodesic strain partitions (alpha grid) and select best by score_fn | provisional | numpy | Uses calm.compute_strain_2d internally |
| calm.interface.RegistrySearchResult | class | Result of Monte Carlo registry search (best translation + metadata) | provisional | numpy | Translation is fractional in [0,1)^2 by default |
| calm.interface.monte_carlo_registry_search | function | Monte Carlo translation-only registry search optimizer | provisional | numpy | Caller supplies an energy/score function |
| calm.interface.find_prototypes | function | Advanced kernel import path for prototype enumeration | stable | ase, spglib | Prefer `calm.search_interfaces` for basic workflows |
| calm.interface.compute_strain_state | function | Advanced kernel import path for strain-state computation | stable | ase, spglib | Prefer `InterfaceCandidate.build(...)` for basic workflows |
| calm.interface.build_interface | function | Advanced kernel import path for concrete interface construction | stable | ase, spglib | Prefer `InterfaceCandidate.build(...)` for basic workflows |
| calm.find_prototypes | function | Kernel: enumerate candidate interface prototypes | stable | ase, spglib | Pure-ish kernel; deterministic given inputs |
| calm.compute_strain_state | function | Kernel: compute/select strain state for a prototype | stable | ase, spglib | Accepts `strain_model=` keyword alias |
| calm.build_interface | function | Kernel: build a concrete interface structure | stable | ase, spglib |  |
| calm.compute_interfacial_energy | function | Kernel: compute interfacial energy from built interface | stable | ase, spglib | Requires ASE calculator attached |
| calm.public.results.InterfaceModel.energy | method | Compute interface energy using a Potential or ASE calculator; supports passing ReferenceEnergies via `references=` | stable | ase | Example: `iface.energy(potential=my_mlip, references=ReferenceEnergies({...}))` |
| calm.public.results.InterfaceModel.relax | method | Relax an InterfaceModel using an ASE-compatible calculator or Potential | stable | ase | Returns a new InterfaceModel wrapping the relaxed atoms; supports `fmax`/`steps` |
| calm.load_structure | function | I/O: load a structure file into an ASE Atoms object | stable | ase | Uses ASE I/O backends |
| calm.write_structure | function | I/O: write an ASE Atoms object to a structure file | stable | ase | Uses ASE I/O backends |
| calm.write_json | function | I/O: write JSON-serializable data to a file | stable |  |  |
| calm.prepare_bulk | function | Workflow: standardize/prepare a bulk for slab generation | stable | ase, spglib |  |
| calm.prepare_slab | function | Workflow: generate and prepare slabs from a bulk | stable | ase, spglib |  |
| calm.run_prototype_search | function | Workflow: end-to-end prototype search from slabs | stable | ase, spglib |  |
| calm.run_prototype_search_from_structures | function | Workflow: prototype search from structures (bulk/atoms inputs) | stable | ase, spglib |  |
| calm.run_prototype_search_from_files | function | Workflow: prototype search from input files | stable | ase, spglib |  |
| calm.run_interface_build | function | Workflow: end-to-end interface building for a chosen prototype | stable | ase, spglib |  |
| calm.run_interface_energy | function | Workflow: end-to-end energy evaluation for interfaces | stable | ase, spglib |  |
| calm.PrototypeSearchRun | class | Workflow record: metadata for a prototype search run | stable | ase, spglib |  |
| calm.InterfaceBuildRun | class | Workflow record: metadata for an interface build run | stable | ase, spglib |  |
| calm.InterfaceEnergyRun | class | Workflow record: metadata for an interface energy run | stable | ase, spglib |  |
| calm.ReducedSupercell2D | class | Advanced: reduced 2D supercell candidate with strain metrics | stable | ase, scipy | Considered advanced; may be moved behind a deeper namespace later |
| calm.AffineInvariantStrain2D | class | Advanced: affine-invariant 2D strain scalar/metric | stable | ase, scipy | Considered advanced; may be moved behind a deeper namespace later |
| calm.kernels | module | Namespace: low-level deterministic kernels | stable | ase, spglib | Mirrors core pipeline functions |
| calm.workflow | module | Namespace: UX wrappers around kernels (end-to-end runs) | stable | ase, spglib |  |
| calm.io | module | Namespace: I/O helpers | stable | ase |  |
| calm.viz | module | Namespace: visualization helpers | stable | matplotlib | Optional dependency |
| calm.calculators | module | Namespace: calculator providers + MLIP creation helpers | stable | ase | Provider-specific extras may be required at call-time |
| calm.calculators.list_providers | function | List known calculator providers and their availability | stable | ase | Returns ProviderInfo records |
| calm.calculators.list_models | function | List known model IDs for a calculator provider family | stable | ase | Returns an empty tuple when a provider does not publish a model list |
| calm.calculators.make_calculator | function | Create an ASE calculator from a CalculatorSpec | stable | ase | Defers heavy imports until calculator construction |
| calm.calculators.spec.CalculatorSpec | class | Calculator configuration record (family, model, device, dtype, etc.) | stable | ase | Serializable calculator configuration; may be persisted alongside workspace runs |
| calm.calculators.CalculatorSpec | class | Calculator spec (family/model/hyperparameters) for factory construction | stable | ase | Convenience re-export of `calm.calculators.spec.CalculatorSpec`. |
| calm.project.strain_partition_scan.run_geodesic_strain_partition_scan | function | Energy-guided scan over geodesic strain partitions; persists best strain state | provisional | ase | Defaults to unrelaxed interface energy density (eV/Å²); accepts custom score_fn |
| calm.project.optimize_interface.InterfaceOptimizationResult | class | Result container for run_interface_optimization | provisional | ase | |
| calm.project.optimize_interface.run_interface_optimization | function | One-call workflow: strain-partition scan (alpha) + MC registry search | provisional | ase | Persists only the best strain_state / interface / energy. |
| calm.project.runner.RunExecutionResult | class | Result container for execute_claimed_run / run_next | provisional |  | |
| calm.project.runner.execute_claimed_run | function | Execute a claimed run and update its status | provisional |  | Marks run succeeded/failed and stores optional metrics_json |
| calm.project.runner.run_next | function | Claim and execute the next queued run | provisional |  | Returns None when the queue is empty |
| calm.project.runner.run_until_empty | function | Execute queued runs until the queue is empty | provisional |  | Convenience loop over run_next |
| calm.project.runner.run_worker_loop | function | Worker loop: repeatedly claim+execute runs until stopped | provisional |  | Designed for simple single-process workers; supports kind filtering and idle backoff |
| calm.project.handlers.default_run_handlers | function | Convenience: built-in handler mapping for run queue execution | provisional |  | Includes handlers for built-in run kinds when available |
| calm.viz.pareto.pareto_front | function | Compute a Pareto front subset over a record sequence | stable |  | Pure helper; no matplotlib import |
| calm.viz.plot_pareto_front | function | Plot a 2D Pareto front (all points + Pareto subset) | provisional | matplotlib | Returns (fig, ax) from matplotlib |
| calm.public.structure_collections.StructureCollection | class | Structure catalog facade for workspace structures (to_rows/to_dataframe/write_table) | stable | pandas | Lightweight facade over workspace query results |
| calm.public.candidate_collections.CandidateCollection | class | Candidate collection facade: chainable filtering, Pareto selection, table export, and build helpers. | stable |  | Public candidate collection facade used by examples and tutorials |
| calm.public.interface_collections.InterfaceCollection | class | Interface collection facade for built/derived interfaces with export and query helpers. | stable |  | Public interface collection facade |
| calm.project | module | Workspace entrypoints and facade types. | stable | sqlalchemy | Includes `open_workspace` and `Workspace`. |
| calm.project.open_workspace | function | Open (or create) a workspace rooted at a directory. | stable | sqlalchemy | Recommended entrypoint for new workflows. |
| calm.project.Workspace | class | Workspace facade for the persistence/orchestration layer. | stable | sqlalchemy | Returned by `open_workspace`. |
| calm.project.display_table | function | Render objects as a table (text/Markdown) | stable |  | Convenience wrapper used by examples and notebooks |
| calm.project.Workspace.create_run | method | Create a run record | stable | sqlalchemy | |
| calm.project.Workspace.put_log | method | Attach a text log artifact to a run | stable | sqlalchemy | |
| calm.project.Workspace.put_plot | method | Attach a binary plot artifact to a run | stable | sqlalchemy | |
| calm.project.Workspace.put_structure | method | Attach a structure artifact to a run | stable | sqlalchemy | |
| calm.project.Workspace.add_bulk | method | Add a bulk record | stable | sqlalchemy | |
| calm.project.Workspace.relax_bulk | method | Variable-cell relaxation of a bulk and persist as an optimized bulk | stable | sqlalchemy | ASE is imported lazily inside the method |
| calm.project.Workspace.build_slabs | method | Build slab variants for a bulk | stable | sqlalchemy | |
| calm.project.Workspace.start_prototype_search | method | Start a prototype search run | stable | sqlalchemy | |
| calm.project.Workspace.list_prototypes | method | List prototypes produced by a run | stable | sqlalchemy | |
| calm.project.Workspace.start_strain_partition_scan | method | Start a strain-partition scan followup run | stable | sqlalchemy | |
| calm.project.Workspace.list_followup_results | method | List followup results for a run | stable | sqlalchemy | |
| calm.project.Workspace.pareto_plot | method | Write a Pareto plot artifact for a prototype-search run | stable | sqlalchemy | |
| calm.project.Workspace.strain_partition_plot | method | Write a strain-partition plot artifact for a scan run | stable | sqlalchemy | |
| calm.slab | module | Slab construction helpers: oriented-slab API + legacy slab wrappers. | stable | ase, spglib | Module-level imports are supported; top-level re-exports also exist. |
| calm.slab.OrientedSlab | class | Oriented slab result wrapper (alias of `OrientedSlabResult`) | stable | ase, spglib | Returned by `build_oriented_slab*`. |
| calm.slab.OrientedSlabResult | class | Result of oriented-slab construction (Atoms + transforms + metadata) | stable | ase, spglib |  |
| calm.slab.build_oriented_slab | function | Build an oriented slab from a `calm.bulk.Bulk` object | stable | ase, spglib | Preferred oriented-slab entrypoint. |
| calm.slab.build_oriented_slab_from_conventional | function | Build an oriented slab from a conventional bulk `ase.Atoms` | stable | ase, spglib | Legacy-friendly oriented entrypoint. |
| calm.slab.build_oriented_slabs_from_conventional | function | Build multiple oriented slabs from a conventional bulk `ase.Atoms` | stable | ase, spglib | Convenience for scanning candidates. |
| calm.slab.oriented_slab_surface_primitive_cell | function | Compute the surface primitive cell for a bulk + Miller index | stable | ase, spglib | Core oriented-slab primitive surface routine. |
| calm.slab.surface_primitive_from_slabs | function | Derive a shared surface primitive basis from two slabs | stable | ase, spglib | Used for interface matching. |
| calm.slab.compute_registered_positions | function | Map slab motif positions into a registered surface primitive frame | stable | ase, spglib | Used for registry search. |
| calm.slab.Slab | class | Slab domain object (legacy) | deprecated | ase, spglib | Also available as `calm.Slab`. |
| calm.slab.SlabSpec | class | Slab specification record (legacy) | deprecated | ase, spglib | Also available as `calm.SlabSpec`. |
| calm.slab.ORIENTED_SLAB_TRANSFORMS_INFO_KEY | constant | Key used in `Atoms.info` for oriented slab transform metadata. | stable | ase, spglib | Used by the oriented-slab transform helpers. |
| calm.slab.get_oriented_slab_transforms | function | Compute oriented-slab transforms (Python dict). | stable | ase, spglib |  |
| calm.slab.get_oriented_slab_transforms_json | function | Compute oriented-slab transforms (JSON string). | stable | ase, spglib |  |
| calm.slab.get_oriented_slab_transforms_payload | function | Compute oriented-slab transforms (JSON-serializable payload). | stable | ase, spglib |  |
| calm.bulk.Bulk | class | Explicit advanced import path for the bulk crystal wrapper | stable | ase, spglib | Prefer `calm.Material` for basic workflows |
| calm.open_workspace | function | Convenience re-export of calm.project.open_workspace | stable | sqlalchemy | Alias for calm.project.open_workspace |
| calm.calculators.get_calculator | function | Convenience alias for calm.calculators.make_calculator | stable | ase | Alias for calm.calculators.make_calculator |
| calm.calculators.require_calculator_available | function | Require that a calculator is available (raises if not) | stable | ase | Validation helper |
| calm.calculators.check_calculator_available | function | Check if a calculator is available | stable | ase | Returns bool |
| calm.calculators.require_calculator_spec_available | function | Require that a calculator spec is available | stable | ase | Validation helper for specs |
| calm.calculators.check_calculator_spec_available | function | Check if a calculator spec is available | stable | ase | Returns bool for specs |
| calm.calculators.list_calculator_availability | function | List availability status of all calculators | stable | ase | Returns availability info |
| calm.calculators.print_calculator_availability | function | Print availability status of all calculators | stable | ase | Console output helper |
| calm.calculators.registry.CalculatorRegistry | class | Registry for managing calculator providers | stable | ase | Central registry |
| calm.calculators.registry.CalculatorProvider | class | Provider interface for calculator families | stable | ase | Provider base class |
| calm.calculators.availability.check_calculator_available | function | Low-level availability check | stable | ase | Implementation detail |
| calm.util.atoms_validation.validate_atoms | function | Validate ASE Atoms object structure | stable | ase | Validation helper |
| calm.util.atoms_validation.check_duplicate_atoms | function | Check for duplicate atoms in structure | stable | ase | Returns duplicate info |
| calm.util.atoms_validation.normalize_atoms | function | Normalize ASE Atoms object (wrap, center, etc) | stable | ase | Returns normalized copy |
| calm.util.atoms_validation.remove_duplicate_atoms | function | Remove duplicate atoms from structure | stable | ase | Returns cleaned structure |
| calm.keys.uid.material_uid_from_conv_atoms | function | Compute material UID from conventional cell | stable | ase | UID generation |
| calm.keys.uid.hash_obj | function | Compute SHA256 hash of JSON-serializable object | stable |  | UID helper |
| calm.keys.uid.canonical_json | function | Convert object to canonical JSON string | stable |  | UID helper |
| calm.bulk.provenance.BulkCanonicalizationTransforms | class | Structured record of transforms applied during bulk canonicalization (stored in ASE Atoms.info). | provisional | ase, numpy | Returned by get_bulk_canonicalization_transforms(). |
| calm.bulk.provenance.get_bulk_canonicalization_transforms | function | Read bulk canonicalization transforms from a Bulk record (or ASE Atoms). | provisional | ase, numpy | Convenience wrapper for provenance inspection. |
| calm.public.project.open_project | function | Open a public-facing project facade (sidecar-backed) | stable | sqlalchemy | Alias for calm.project.open_workspace |
| calm.public.datasets.InterfaceDataset | class | Public dataset facade for interface collections and manifest/structure exports | stable | pandas (optional) | Provides to_rows(), write_manifest(), write() helpers used by Project.save and examples |
<!-- public-api-table:end -->


## API tiers

The inventory above is intentionally broad: it includes the basic workflow API, advanced public entry points, and deprecated transitional aliases. The tier table below records how each inventory row should be interpreted by users and maintainers.

- **basic**: the recommended high-level surface for most users and examples.
- **advanced**: supported explicit-module APIs for methods developers, workflow infrastructure, or lower-level kernels.
- **deprecated**: transitional compatibility paths retained only while callers migrate to modern alternatives.

Tests enforce that every inventory row has exactly one tier and that every curated top-level export in `calm.api.PUBLIC_EXPORTS` is classified as `basic`.

<!-- public-api-tier-table:begin -->
| Import path | Tier | Rationale |
|---|---|---|
| calm.public.candidate_collections.CandidateCollection | advanced | Public candidate collection facade used for candidate filtering, Pareto, and build helpers. |
| calm.public.interface_collections.InterfaceCollection | advanced | Public interface collection facade used for interface query and export helpers. |
| calm.public.structure_collections.StructureCollection | advanced | Public structure collection facade for workspace structure catalogs and exports. |
| calm.public.project.open_project | advanced | Public helper to open a public-sidecar Project facade (alias for calm.project.open_workspace) |
| calm | basic | Curated user-facing workflow surface or high-level result method. |
| calm.api | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.__version__ | basic | Curated user-facing workflow surface or high-level result method. |
| calm.Bulk | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.SlabSpec | deprecated | Transitional compatibility path; prefer the modern alternative in the Notes column. |
| calm.Slab | deprecated | Transitional compatibility path; prefer the modern alternative in the Notes column. |
| calm.PrototypeSearchConfig | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.PrototypeSearchResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.SupercellRecipe2D | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.InterfacePrototype | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.StrainModel | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.StrainState | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.InterfaceBuildConfig | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.Interface | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.EnergyConfig | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.EnergyResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.InterfaceEnergyScalarResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.compute_interface_energy_from_scalars | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.EV_PER_A2_TO_J_PER_M2 | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.Material | basic | Curated user-facing workflow surface or high-level result method. |
| calm.Surface | basic | Curated user-facing workflow surface or high-level result method. |
| calm.SurfacePair | basic | Curated user-facing workflow surface or high-level result method. |
| calm.InterfaceRequest | basic | Curated user-facing workflow surface or high-level result method. |
| calm.SearchSettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.StrainPartitionSettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.BuildSettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.RegistrySettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.RelaxSettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.EnergyConvention | basic | Curated user-facing workflow surface or high-level result method. |
| calm.ReferenceEnergies | basic | Curated user-facing workflow surface or high-level result method. |
| calm.EnergySettings | basic | Curated user-facing workflow surface or high-level result method. |
| calm.Potential | basic | Curated user-facing workflow surface or high-level result method. |
| calm.Selection | basic | Curated user-facing workflow surface or high-level result method. |
| calm.StrainFilter | basic | Curated user-facing workflow surface or high-level result method. |
| calm.search_interfaces | basic | Curated user-facing workflow surface or high-level result method. |
| calm.search_interface_grid | basic | Curated user-facing workflow surface or high-level result method. |
| calm.estimate_interface_search | basic | Curated user-facing workflow surface or high-level result method. |
| calm.compare_potentials | basic | Curated user-facing workflow surface or high-level result method. |
| calm.load_result | basic | Curated user-facing workflow surface or high-level result method. |
| calm.load_recipe | basic | Curated user-facing workflow surface or high-level result method. |
| calm.open_project | basic | Curated user-facing workflow surface or high-level result method. |
| calm.compute_strained_bulk_reference_energies | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.StrainedBulkReferenceResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.RegistrySearchConfig | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.StrainPartitionCandidate | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.StrainPartitionResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.scan_geodesic_strain_partitions | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.RegistrySearchResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.monte_carlo_registry_search | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.find_prototypes | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.compute_strain_state | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.interface.build_interface | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.find_prototypes | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.compute_strain_state | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.build_interface | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.compute_interfacial_energy | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.public.results.InterfaceModel.energy | basic | Curated user-facing workflow surface or high-level result method. |
| calm.public.results.InterfaceModel.relax | basic | Curated user-facing workflow surface or high-level result method. |
| calm.load_structure | basic | Curated user-facing workflow surface or high-level result method. |
| calm.write_structure | basic | Curated user-facing workflow surface or high-level result method. |
| calm.write_json | basic | Curated user-facing workflow surface or high-level result method. |
| calm.prepare_bulk | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.prepare_slab | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.run_prototype_search | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.run_prototype_search_from_structures | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.run_prototype_search_from_files | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.run_interface_build | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.run_interface_energy | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.PrototypeSearchRun | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.InterfaceBuildRun | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.InterfaceEnergyRun | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.ReducedSupercell2D | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.AffineInvariantStrain2D | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.kernels | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.workflow | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.io | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.viz | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.list_providers | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.list_models | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.make_calculator | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.spec.CalculatorSpec | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.CalculatorSpec | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.strain_partition_scan.run_geodesic_strain_partition_scan | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.optimize_interface.InterfaceOptimizationResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.optimize_interface.run_interface_optimization | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.runner.RunExecutionResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.runner.execute_claimed_run | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.runner.run_next | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.runner.run_until_empty | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.runner.run_worker_loop | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.handlers.default_run_handlers | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.display_table | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
<!-- project.view.Records and accessors removed from the tier table during modernization; prefer Workspace UX facades (ws.query / ws.enrichment) -->
| calm.viz.pareto.pareto_front | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.viz.plot_pareto_front | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
```text
<!-- legacy calm.public.collections entries removed; prefer explicit calm.public.*_collections modules -->
```
| calm.project | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.open_workspace | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.create_run | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.put_log | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.put_plot | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.put_structure | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.add_bulk | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.relax_bulk | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.build_slabs | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.start_prototype_search | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.list_prototypes | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.start_strain_partition_scan | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.list_followup_results | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.pareto_plot | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.project.Workspace.strain_partition_plot | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.OrientedSlab | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.OrientedSlabResult | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.build_oriented_slab | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.build_oriented_slab_from_conventional | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.build_oriented_slabs_from_conventional | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.oriented_slab_surface_primitive_cell | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.surface_primitive_from_slabs | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.compute_registered_positions | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.Slab | deprecated | Transitional compatibility path; prefer the modern alternative in the Notes column. |
| calm.slab.SlabSpec | deprecated | Transitional compatibility path; prefer the modern alternative in the Notes column. |
| calm.slab.ORIENTED_SLAB_TRANSFORMS_INFO_KEY | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.get_oriented_slab_transforms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.get_oriented_slab_transforms_json | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.slab.get_oriented_slab_transforms_payload | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.bulk.Bulk | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.open_workspace | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.get_calculator | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.require_calculator_available | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.check_calculator_available | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.require_calculator_spec_available | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.check_calculator_spec_available | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.list_calculator_availability | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.print_calculator_availability | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.registry.CalculatorRegistry | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.registry.CalculatorProvider | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.calculators.availability.check_calculator_available | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.util.atoms_validation.validate_atoms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.util.atoms_validation.check_duplicate_atoms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.util.atoms_validation.normalize_atoms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.util.atoms_validation.remove_duplicate_atoms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.keys.uid.material_uid_from_conv_atoms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.keys.uid.hash_obj | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.keys.uid.canonical_json | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.bulk.provenance.BulkCanonicalizationTransforms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
| calm.bulk.provenance.get_bulk_canonicalization_transforms | advanced | Supported advanced workflow, explicit module, kernel, infrastructure, or utility API. |
<!-- public-api-tier-table:end -->

Workspace Facade API
--------------------

**Status:** ✅ Stable (100% backward compatible)

The `Workspace` class provides a **facade-based API** for improved organization and discoverability. Methods are grouped into 6 focused facades based on their purpose:

### Facade Overview

| Facade | Purpose | Example Methods |
|--------|---------|-----------------|
| `ws.query` | **Read-only query operations** | `list_bulks()`, `get_bulk()`, `list_slabs()`, `get_slab()` |
| `ws.mutations` | **Create/update operations** | `add_bulk()`, `build_slabs()`, `start_prototype_search()` |
| `ws.enrichment` | **Data enrichment** | `list_slabs_enriched()`, `get_workspace_stats()`, `format_table()` |
| `ws.artifacts` | **Artifact storage/retrieval** | `put_plot()`, `put_log()`, `out_dir`, `resolve_uri()` |
| `ws.visualization` | **Plot generation** | `pareto_plot()`, `strain_partition_plot()` |
| `ws.export` | **Structure export** | `export_bulks_as_poscar()`, `export_slabs_as_poscar()` |

### Benefits

- ✅ **Better organization** - Methods grouped by responsibility instead of flat namespace
- ✅ **Improved discoverability** - IDE autocomplete shows ~10 relevant methods instead of 56
- ✅ **Clear intent** - Method location indicates whether you're reading or writing
- ✅ **100% backward compatible** - All existing code continues to work
- ✅ **Easier testing** - Each facade can be tested in isolation

### API Examples

**Old API (still works):**
```python
from calm.project import open_workspace

ws = open_workspace("./my_workspace")

# Query operations
bulks = ws.list_bulks()
bulk = ws.get_bulk("b_abc123")

# Mutation operations
new_bulk = ws.add_bulk(structure=atoms, label="Al")
slabs = ws.build_slabs(new_bulk.id_short, millers=[(1,1,1)])

# Export operations
ws.export_bulks_as_poscar(output_dir="exported")
```

**New Facade API (recommended):**
```python
from calm.project import open_workspace

ws = open_workspace("./my_workspace")

# Query operations - clearly read-only
bulks = ws.query.list_bulks()
bulk = ws.query.get_bulk("b_abc123")

# Mutation operations - clearly creating/modifying data
new_bulk = ws.mutations.add_bulk(structure=atoms, label="Al")
slabs = ws.mutations.build_slabs(new_bulk.id_short, millers=[(1,1,1)])

# Export operations - clearly exporting to disk
ws.export.export_bulks_as_poscar(output_dir="exported")
```

### Migration

**Recommendation:** Use the new facade API for all new code. Existing code will continue to work without changes.

**Complete migration guide:** See `FACADE_MIGRATION_GUIDE.md` for detailed examples and a complete API reference.

### Facade Method Reference

**WorkspaceQuery (ws.query.*)** - 14 read-only methods:
- `list_bulks()`, `get_bulk()`
- `list_slabs()`, `get_slab()`
- `list_prototypes()`, `get_prototype()`
- `list_derived_interfaces()`, `get_derived_interface()`
- `list_followup_results()`, `get_run()`
- `list_artifacts()`, `list_edges()`
- `list_calculators()`, `get_calculator()`

**WorkspaceMutations (ws.mutations.*)** - 14 create/update methods:
- `add_bulk()`, `add_bulk_from_poscar()`, `relax_bulk()`
- `register_calculator()`
- `add_slab()`, `build_slabs()`
- `start_prototype_search()`
- `create_derived_interface()`
- `derive_interfaces_from_strain_partition_scan()`
- `derive_interfaces_from_registry_search()`
- `create_run()`
- `start_strain_partition_scan()`
- `start_registry_search()`
- `start_registry_search_from_strain_partition_scan()`

**WorkspaceEnrichment (ws.enrichment.*)** - 9 enrichment methods:
- `list_slabs_enriched()`, `list_runs()`, `list_prototypes_enriched()`
- `get_slab_param()`, `group_slabs_by_material()`
- `list_derived_interfaces_enriched()`, `list_followup_results_enriched()`
- `get_workspace_stats()`, `format_table()`

**WorkspaceArtifacts (ws.artifacts.*)** - 11 artifact methods:
- `put_log()`, `put_plot()`, `put_structure()`, `put_json()`
- `out_dir` (property)
- `resolve_uri()`, `artifact_path()`, `open_artifact()`
- `artifacts_by_category()`, `artifact_paths_by_category()`

**WorkspaceVisualization (ws.visualization.*)** - 4 plotting methods:
- `pareto_plot()`, `strain_partition_plot()`
- `strain_partition_scan_plot()`, `registry_search_plot()`

**WorkspaceExport (ws.export.*)** - 4 export methods:
- `export_poscar()`, `export_bulks_as_poscar()`
- `export_slabs_as_poscar()`, `format_payload()`

Not Public API
--------------

Any module, function, class, or attribute **not listed above** is **not** part of the
public API, even if it is importable. Internal modules may change at any time without
a deprecation period.


<!-- generated-api-anchors:begin -->
### calm {#calm}

### calm.api {#calm.api}

### calm.__version__ {#calm.__version__}

### calm.Bulk {#calm.Bulk}

### calm.SlabSpec {#calm.SlabSpec}

### calm.Slab {#calm.Slab}

### calm.PrototypeSearchConfig {#calm.PrototypeSearchConfig}

### calm.PrototypeSearchResult {#calm.PrototypeSearchResult}

### calm.SupercellRecipe2D {#calm.SupercellRecipe2D}

### calm.InterfacePrototype {#calm.InterfacePrototype}

### calm.StrainModel {#calm.StrainModel}

### calm.StrainState {#calm.StrainState}

### calm.InterfaceBuildConfig {#calm.InterfaceBuildConfig}

### calm.Interface {#calm.Interface}

### calm.EnergyConfig {#calm.EnergyConfig}

### calm.EnergyResult {#calm.EnergyResult}

### calm.InterfaceEnergyScalarResult {#calm.InterfaceEnergyScalarResult}

### calm.compute_interface_energy_from_scalars {#calm.compute_interface_energy_from_scalars}

### calm.EV_PER_A2_TO_J_PER_M2 {#calm.EV_PER_A2_TO_J_PER_M2}

### calm.Material {#calm.Material}

### calm.Surface {#calm.Surface}

### calm.SurfacePair {#calm.SurfacePair}

### calm.InterfaceRequest {#calm.InterfaceRequest}

### calm.SearchSettings {#calm.SearchSettings}

### calm.StrainPartitionSettings {#calm.StrainPartitionSettings}

### calm.BuildSettings {#calm.BuildSettings}

### calm.RegistrySettings {#calm.RegistrySettings}

### calm.RelaxSettings {#calm.RelaxSettings}

### calm.EnergyConvention {#calm.EnergyConvention}

### calm.ReferenceEnergies {#calm.ReferenceEnergies}

### calm.EnergySettings {#calm.EnergySettings}

### calm.Potential {#calm.Potential}

### calm.Selection {#calm.Selection}

### calm.StrainFilter {#calm.StrainFilter}

### calm.search_interfaces {#calm.search_interfaces}

### calm.search_interface_grid {#calm.search_interface_grid}

### calm.estimate_interface_search {#calm.estimate_interface_search}

### calm.compare_potentials {#calm.compare_potentials}

### calm.load_result {#calm.load_result}

### calm.load_recipe {#calm.load_recipe}

### calm.open_project {#calm.open_project}

### calm.compute_strained_bulk_reference_energies {#calm.compute_strained_bulk_reference_energies}

### calm.StrainedBulkReferenceResult {#calm.StrainedBulkReferenceResult}

### calm.interface.RegistrySearchConfig {#calm.interface.RegistrySearchConfig}

### calm.interface.StrainPartitionCandidate {#calm.interface.StrainPartitionCandidate}

### calm.interface.StrainPartitionResult {#calm.interface.StrainPartitionResult}

### calm.interface.scan_geodesic_strain_partitions {#calm.interface.scan_geodesic_strain_partitions}

### calm.interface.RegistrySearchResult {#calm.interface.RegistrySearchResult}

### calm.interface.monte_carlo_registry_search {#calm.interface.monte_carlo_registry_search}

### calm.interface.find_prototypes {#calm.interface.find_prototypes}

### calm.interface.compute_strain_state {#calm.interface.compute_strain_state}

### calm.interface.build_interface {#calm.interface.build_interface}

### calm.find_prototypes {#calm.find_prototypes}

### calm.compute_strain_state {#calm.compute_strain_state}

### calm.build_interface {#calm.build_interface}

### calm.compute_interfacial_energy {#calm.compute_interfacial_energy}

### calm.public.results.InterfaceModel.energy {#calm.public.results.InterfaceModel.energy}

### calm.public.results.InterfaceModel.relax {#calm.public.results.InterfaceModel.relax}

### calm.load_structure {#calm.load_structure}

### calm.write_structure {#calm.write_structure}

### calm.write_json {#calm.write_json}

### calm.prepare_bulk {#calm.prepare_bulk}

### calm.prepare_slab {#calm.prepare_slab}

### calm.run_prototype_search {#calm.run_prototype_search}

### calm.run_prototype_search_from_structures {#calm.run_prototype_search_from_structures}

### calm.run_prototype_search_from_files {#calm.run_prototype_search_from_files}

### calm.run_interface_build {#calm.run_interface_build}

### calm.run_interface_energy {#calm.run_interface_energy}

### calm.PrototypeSearchRun {#calm.PrototypeSearchRun}

### calm.InterfaceBuildRun {#calm.InterfaceBuildRun}

### calm.InterfaceEnergyRun {#calm.InterfaceEnergyRun}

### calm.ReducedSupercell2D {#calm.ReducedSupercell2D}

### calm.AffineInvariantStrain2D {#calm.AffineInvariantStrain2D}

### calm.kernels {#calm.kernels}

### calm.workflow {#calm.workflow}

### calm.io {#calm.io}

### calm.viz {#calm.viz}

### calm.calculators {#calm.calculators}

### calm.calculators.list_providers {#calm.calculators.list_providers}

### calm.calculators.list_models {#calm.calculators.list_models}

### calm.calculators.make_calculator {#calm.calculators.make_calculator}

### calm.calculators.spec.CalculatorSpec {#calm.calculators.spec.CalculatorSpec}

### calm.calculators.CalculatorSpec {#calm.calculators.CalculatorSpec}

### calm.project.strain_partition_scan.run_geodesic_strain_partition_scan {#calm.project.strain_partition_scan.run_geodesic_strain_partition_scan}

### calm.project.optimize_interface.InterfaceOptimizationResult {#calm.project.optimize_interface.InterfaceOptimizationResult}

### calm.project.optimize_interface.run_interface_optimization {#calm.project.optimize_interface.run_interface_optimization}

### calm.project.runner.RunExecutionResult {#calm.project.runner.RunExecutionResult}

### calm.project.runner.execute_claimed_run {#calm.project.runner.execute_claimed_run}

### calm.project.runner.run_next {#calm.project.runner.run_next}

### calm.project.runner.run_until_empty {#calm.project.runner.run_until_empty}

### calm.project.runner.run_worker_loop {#calm.project.runner.run_worker_loop}

### calm.project.handlers.default_run_handlers {#calm.project.handlers.default_run_handlers}

### calm.viz.pareto.pareto_front {#calm.viz.pareto.pareto_front}

### calm.viz.plot_pareto_front {#calm.viz.plot_pareto_front}

### calm.public.structure_collections.StructureCollection {#calm.public.structure_collections.StructureCollection}

### calm.public.candidate_collections.CandidateCollection {#calm.public.candidate_collections.CandidateCollection}

### calm.public.interface_collections.InterfaceCollection {#calm.public.interface_collections.InterfaceCollection}

### calm.project {#calm.project}

### calm.project.open_workspace {#calm.project.open_workspace}

### calm.project.Workspace {#calm.project.Workspace}

### calm.project.display_table {#calm.project.display_table}

### calm.project.Workspace.create_run {#calm.project.Workspace.create_run}

### calm.project.Workspace.put_log {#calm.project.Workspace.put_log}

### calm.project.Workspace.put_plot {#calm.project.Workspace.put_plot}

### calm.project.Workspace.put_structure {#calm.project.Workspace.put_structure}

### calm.project.Workspace.add_bulk {#calm.project.Workspace.add_bulk}

### calm.project.Workspace.relax_bulk {#calm.project.Workspace.relax_bulk}

### calm.project.Workspace.build_slabs {#calm.project.Workspace.build_slabs}

### calm.project.Workspace.start_prototype_search {#calm.project.Workspace.start_prototype_search}

### calm.project.Workspace.list_prototypes {#calm.project.Workspace.list_prototypes}

### calm.project.Workspace.start_strain_partition_scan {#calm.project.Workspace.start_strain_partition_scan}

### calm.project.Workspace.list_followup_results {#calm.project.Workspace.list_followup_results}

### calm.project.Workspace.pareto_plot {#calm.project.Workspace.pareto_plot}

### calm.project.Workspace.strain_partition_plot {#calm.project.Workspace.strain_partition_plot}

### calm.slab {#calm.slab}

### calm.slab.OrientedSlab {#calm.slab.OrientedSlab}

### calm.slab.OrientedSlabResult {#calm.slab.OrientedSlabResult}

### calm.slab.build_oriented_slab {#calm.slab.build_oriented_slab}

### calm.slab.build_oriented_slab_from_conventional {#calm.slab.build_oriented_slab_from_conventional}

### calm.slab.build_oriented_slabs_from_conventional {#calm.slab.build_oriented_slabs_from_conventional}

### calm.slab.oriented_slab_surface_primitive_cell {#calm.slab.oriented_slab_surface_primitive_cell}

### calm.slab.surface_primitive_from_slabs {#calm.slab.surface_primitive_from_slabs}

### calm.slab.compute_registered_positions {#calm.slab.compute_registered_positions}

### calm.slab.Slab {#calm.slab.Slab}

### calm.slab.SlabSpec {#calm.slab.SlabSpec}

### calm.slab.ORIENTED_SLAB_TRANSFORMS_INFO_KEY {#calm.slab.ORIENTED_SLAB_TRANSFORMS_INFO_KEY}

### calm.slab.get_oriented_slab_transforms {#calm.slab.get_oriented_slab_transforms}

### calm.slab.get_oriented_slab_transforms_json {#calm.slab.get_oriented_slab_transforms_json}

### calm.slab.get_oriented_slab_transforms_payload {#calm.slab.get_oriented_slab_transforms_payload}

### calm.bulk.Bulk {#calm.bulk.Bulk}

### calm.open_workspace {#calm.open_workspace}

### calm.calculators.get_calculator {#calm.calculators.get_calculator}

### calm.calculators.require_calculator_available {#calm.calculators.require_calculator_available}

### calm.calculators.check_calculator_available {#calm.calculators.check_calculator_available}

### calm.calculators.require_calculator_spec_available {#calm.calculators.require_calculator_spec_available}

### calm.calculators.check_calculator_spec_available {#calm.calculators.check_calculator_spec_available}

### calm.calculators.list_calculator_availability {#calm.calculators.list_calculator_availability}

### calm.calculators.print_calculator_availability {#calm.calculators.print_calculator_availability}

### calm.calculators.registry.CalculatorRegistry {#calm.calculators.registry.CalculatorRegistry}

### calm.calculators.registry.CalculatorProvider {#calm.calculators.registry.CalculatorProvider}

### calm.calculators.availability.check_calculator_available {#calm.calculators.availability.check_calculator_available}

### calm.util.atoms_validation.validate_atoms {#calm.util.atoms_validation.validate_atoms}

### calm.util.atoms_validation.check_duplicate_atoms {#calm.util.atoms_validation.check_duplicate_atoms}

### calm.util.atoms_validation.normalize_atoms {#calm.util.atoms_validation.normalize_atoms}

### calm.util.atoms_validation.remove_duplicate_atoms {#calm.util.atoms_validation.remove_duplicate_atoms}

### calm.keys.uid.material_uid_from_conv_atoms {#calm.keys.uid.material_uid_from_conv_atoms}

### calm.keys.uid.hash_obj {#calm.keys.uid.hash_obj}

### calm.keys.uid.canonical_json {#calm.keys.uid.canonical_json}

### calm.bulk.provenance.BulkCanonicalizationTransforms {#calm.bulk.provenance.BulkCanonicalizationTransforms}

### calm.bulk.provenance.get_bulk_canonicalization_transforms {#calm.bulk.provenance.get_bulk_canonicalization_transforms}

### calm.public.project.open_project {#calm.public.project.open_project}

### calm.public.datasets.InterfaceDataset {#calm.public.datasets.InterfaceDataset}

<!-- generated-api-anchors:end -->
