# CALM Basic API Workflow Gap Checklist

Status: draft

Purpose
- Track per-level (0–10) conformance gaps between the implemented Basic API and the Scientific Workflow Map.
- Each row should be actionable: owner, files to change, tests, docs, status token.

How to use
- This file is a living checklist. Update status and add notes when work progresses. Keep items small and testable.

Workflow-level checklist (0–10)

Level 0 — Project Setup
  - Item: Project creation/opening, project-sidecar metadata, Project.configure(), Project.artifacts() and MLIP selection helpers
  - Owner: Platform engineer
  - Files: calm/public/project.py, calm/project/saving.py, calm/project/ux/workspace.py, API_Refinement/CALM_Basic_API_Reference/CALM_Basic_API_Reference_Chapter_01_Project.md
  - Tests: create/open project, configure MLIP, save/load sidecar metadata, round-trip tests
  - Docs: User Guide Chapter 01, Reference for Project API
  - Status: partial

Level 1 — Materials
  - Item: MaterialsCollection CRUD, import/export helpers, database download adapters, stable object identity for materials
  - Owner: Materials engineer
  - Files: calm/public/materials.py, calm/public/materials_collection.py, calm/plugins/*, tests/materials/test_materials_collection.py
  - Tests: import, list, retrieve, export, identifier stability
  - Docs: Reference and User Guide materials chapters
  - Status: partial

Level 2 — Surface Models
  - Item: Surface primitive cell generation, slab enumeration, terminations, storage and retrieval APIs
  - Owner: Surfaces engineer
  - Files: calm/public/surfaces.py, calm/public/surfaces_collection.py, calm/public/surface_construction.py, tests/surfaces/test_surface_generation.py
  - Tests: generate slabs, multiple miller indices, terminations, serialization
  - Docs: Reference + User Guide chapter on Surface Models
  - Status: partial

Level 3 — Interface Matching
  - Item: Lattice matching, match storage, MatchesCollection, Pareto filtering and query helpers
  - Owner: Matching engineer
  - Files: calm/public/matches.py, calm/public/match_collections.py, calm/public/match_search_result.py, tests/matches/test_matching.py
  - Tests: run lattice match on small systems, store/list/filter matches, result facades
  - Docs: Reference + User Guide matching chapter
  - Status: partial

Level 4 — Interface Construction
  - Item: Candidate interface generation, strain partitioning, stacking registries and serialization of InterfaceModel
  - Owner: Interface engineer
  - Files: calm/public/results.py, calm/public/interface_collections.py, calm/public/interface_construction.py, tests/interfaces/test_interface_construction.py
  - Tests: generate candidate interfaces, enumerate registries, serialize models
  - Docs: Reference + User Guide Interface Construction chapter
  - Status: partial

Level 5 — Registry Optimization
  - Item: Monte Carlo / optimizer plumbing for registry search/optimization, storage of optimized interfaces
  - Owner: Optimization engineer
  - Files: calm/public/registry.py, calm/public/optimization.py, calm/public/match_search_result.py, tests/registry/test_registry_optimization.py
  - Tests: deterministic optimization on toy systems, persistence of optimized result
  - Docs: Reference + User Guide examples
  - Status: not_started

Level 6 — Structural Relaxation
  - Item: Relaxation model, RelaxationsCollection, job lifecycle (submit/monitor/restart), convergence metadata, linkage to Project persistence
  - Owner: Simulation engineer
  - Files: calm/public/relaxations.py, calm/public/relaxations_collections.py, calm/executors/*, calm/project/saving.py, tests/relaxation/test_relaxation_workflow.py
  - Tests: create/track relaxations, simulate interrupted jobs and restart, round-trip persistence
  - Docs: Reference + User Guide relaxation chapter
  - Status: not_started

Level 7 — Energetics
  - Item: Energy calculators, InterfaceModel.interfacial_energy(), InterfaceCollection.compute_interfacial_energies(), storage of computed properties
  - Owner: Energetics engineer
  - Files: calm/energetics/*, calm/public/results.py, calm/public/interface_collections.py, tests/energetics/test_interface_energies.py
  - Tests: unit tests with mock calculators, integration test hooking compute_interfacial_energies through collection -> model -> backend
  - Docs: Reference + User Guide energetics chapter
  - Status: not_started

Level 8 — Analysis
  - Item: Analysis primitives (strain, bonding, charge), AnalysesCollection, reproducible analysis workflows and provenance capture
  - Owner: Analysis engineer
  - Files: calm/public/analyses.py, calm/public/analyses_collections.py, calm/analysis/*, tests/analysis/test_strain_analysis.py
  - Tests: run analysis on relaxed structures, verify outputs and provenance
  - Docs: Reference + User Guide analysis chapter
  - Status: not_started

Level 9 — Dataset Generation
  - Item: Dataset export utilities (structures, descriptors, metadata), Dataset objects and DatasetCollection, ensure reproducible exports and provenance included
  - Owner: Data engineer
  - Files: calm/public/datasets.py, calm/public/datasets_collections.py, calm/io/exporters.py, tests/datasets/test_dataset_export.py
  - Tests: create dataset exports, validate included metadata and provenance
  - Docs: Reference + User Guide datasets chapter
  - Status: not_started

Level 10 — Campaigns
  - Item: Campaign orchestration primitives (parameter sweeps, resume, aggregation), CampaignsCollection and linkage to Project and Datasets
  - Owner: Campaign engineer
  - Files: calm/public/campaigns.py, calm/public/campaigns_collections.py, calm/campaign/*, tests/campaigns/test_campaign_resume.py
  - Tests: execute small campaign locally, resume after interruption, aggregate results
  - Docs: Reference + User Guide campaigns chapter
  - Status: not_started

Cross-cutting items (Provenance, Persistence, Reproducibility, Querying)
  - Item: Stable object ids, project-sidecar completeness, query language support, provenance graphs and lineage APIs
  - Owner: Platform engineer
  - Files: calm/public/project.py, calm/project/saving.py, calm/public/project_queries.py, calm/public/project_lineage.py, tests/project/test_provenance_roundtrip.py
  - Tests: provenance instrumentation and round-trip persistence across multiple workflows
  - Docs: Reference appendix on provenance and reproducibility
  - Status: partial

Next actions
- Assign owners for any "not_started" items, break large items into PR-sized tasks, and schedule work into Waves per the Implementation Roadmap.
