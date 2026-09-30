# CALM Basic API Module Execution Plan

Status: draft

Purpose
- Map roadmap items to concrete file-level changes and tests. This lets developers pick bounded tasks that can be completed and reviewed independently.

Format
- Each entry: Module, Goal, Files to edit/add, Tests to add, Docs to update, Est. difficulty (S/M/L).

Seeded entries
- Module: Registry search (S)
  - Goal: Provide InterfaceCandidate.search_registry and return MatchSearchResult
  - Files: calm/public/results.py, calm/public/match_search_result.py, calm/public/interface_collections.py, tests/public/test_registry_search.py
  - Tests: unit test for query translation and result marshalling; minimal integration with mocked registry
  - Docs: BASIC_API_Reference chapter on MatchSearchResult; User Guide example

- Module: Energetics (M)
  - Goal: implement compute_interfacial_energies on InterfaceCollection and interfacial_energy on InterfaceModel
  - Files: calm/public/interface_collections.py, calm/public/results.py, calm/energetics/*, tests/energetics/test_interface_energies.py
  - Tests: unit tests with deterministic mock calculators; integration test that exercises end-to-end call chain

- Module: Relaxations (M)
  - Goal: Relaxation model and collection; persistence hooks
  - Files: calm/public/relaxations.py, calm/public/relaxations_collections.py, calm/project/saving.py, tests/relaxation/test_relaxation_roundtrip.py
  - Tests: create-relaxation -> save project -> load project -> verify object and provenance

Estimates and sequencing
- Prefer implementing Registry search first (small, unlocks other use cases).
- Energetics and Relaxations can be worked on in parallel by separate engineers.
