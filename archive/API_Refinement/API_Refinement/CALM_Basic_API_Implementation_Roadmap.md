# CALM Basic API Implementation Roadmap

Status: draft

Purpose
- Provide an executable, prioritized roadmap that guides Wave 1–3 implementation work bridging the current Basic API surface to the Scientific Workflow Map.
- Each roadmap item is measurable: code change + tests + public docs/spec updates.

How to read this document
- Items are grouped into Waves (priority). Within each item we list: goal, owner (role), acceptance criteria, dependencies, and risks.
- Status tokens: not_started, partial, implemented, blocked, deferred.

Wave 1 — Core Object Model, Registry, Energetics, Relaxation (High priority)

- 1.1 Registry search and result object
  - Goal: Wire InterfaceCandidate.search_registry(...) and add a RegistrySearchResult/MatchSearchResult object returned to users.
  - Owner: API maintainer
  - Acceptance: public API surface has a documented search_registry; unit tests cover query translation and result marshalling; docs updated in BASIC_API_Reference and User Guide.
  - Files: calm/public/results.py, calm/public/match_search_result.py, calm/public/interface_collections.py
  - Status: partial
  - Risks: backend registry semantics may evolve; provide adapter layer.

- 1.2 Interfacial energetics (compute and expose)
  - Goal: Implement InterfaceCollection.compute_interfacial_energies(...) and InterfaceModel.interfacial_energy(...).
  - Owner: Energetics engineer
  - Acceptance: public method computes energies for a collection or model using the Energetics API; unit tests validate on synthetic inputs; Reference docs updated.
  - Files: calm/public/interface_collections.py, calm/public/results.py, calm/energetics/*
  - Status: not_started
  - Dependencies: Energetics backend or mocked service; define API contract for energy calculators.

- 1.3 Relaxation object and collection
  - Goal: Add Relaxation model and RelaxationsCollection to represent structure relaxations and link to Project persistence.
  - Owner: Simulation engineer
  - Acceptance: Relaxation objects can be created, queried, and serialized; collection supports grouping and basic query operations; tests + docs updated.
  - Files: calm/public/relaxations.py, calm/public/relaxations_collections.py, calm/project/* for persistence hooks
  - Status: not_started

- 1.4 Project lineage and provenance hooks
  - Goal: Implement Project.lineage(...) and strengthen project-sidecar persistence for artifact provenance.
  - Owner: Platform engineer
  - Acceptance: lineage graph derivable for created artifacts; project.save/load round-trips full provenance; tests and user guide examples work.
  - Files: calm/public/project.py, calm/project/saving.py, API_Refinement docs
  - Status: partial

Wave 2 — Provenance, Persistence, Collections (Medium priority)

- 2.1 Persistent identity and recovery
  - Goal: Ensure object identity (stable ids), project-sidecar storage, and recovery across sessions.
  - Acceptance: tests exercising save/load across temporary filesystem projects pass; minimal migration support documented.
  - Status: not_started

- 2.2 Collections: Matches, Datasets, Campaigns
  - Goal: Finalize MatchesCollection/Metrics, DatasetCollection APIs and linkage to Project for navigation and persistence.
  - Acceptance: collection operations (filter, map, persistence) covered by tests; examples in User Guide.
  - Status: partial

Wave 3 — Analysis, Datasets, Campaign orchestration (Lower priority)

- 3.1 Analysis collection and orchestration
  - Goal: Define Analysis objects and ensure they can be applied to datasets/campaigns, with provenance recorded.
  - Acceptance: integration tests for a small analysis pipeline executing locally and recording outputs.
  - Status: not_started

Deliverables and gates
- Deliverable: For each roadmap item, a PR that includes code, unit tests, and documentation: BASIC_API_Reference and User Guide updates.
- Gate: CI green and explicit review signoff from API owner.

Timeline (high level)
- Wave 1: 2–4 sprints (can be broken into smaller PRs per item)
- Wave 2: 3–6 sprints
- Wave 3: ongoing / feature-driven

Risks and mitigations
- Risk: Backend contracts (energetics, registry) change. Mitigation: adapter interfaces and comprehensive unit tests with mocked backends.
- Risk: Large scope creep. Mitigation: enforce code+tests+docs per PR and prefer incremental PRs per API method.
