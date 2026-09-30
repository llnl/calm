# CALM engineering workflow

This directory defines the durable engineering process for staged CALM development. It is intended to let a new chat, a new contributor, or a future maintainer resume work from the current green state without relying on implicit conversation memory.

The numbered examples in `examples/00_*.py` through `examples/12_*.py` are treated as the basic-facing public API contract unless a specific example is documented as an advanced template. Public facade behavior should be captured in tests before deep refactors are attempted.

The workflow is patch-based. The assistant produces numbered, `git apply`-compatible `.patch` files, exact patch application commands, exact install commands, exact test commands, expected results, and milestone tracking. The user downloads patches to `~/Downloads`, applies the patch locally, runs the commands, and reports pass/fail. If an update fails, the next update resolves that failure before expanding scope.

These are living documents. They should be revised whenever the workflow needs to be sharpened. Process corrections must be grounded here rather than remaining implicit in chat history.

## Quick start for a new chat

Read these files first, in order:

1. `continuation/project-state.md`
2. `continuation/next-chat-handoff.md`
3. `02-update-contract.md`
4. `03-patch-contract.md`
5. `developer/repository-resync-baseline.md`
6. `patch-ledger.md`

Then ask the user for the current repository snapshot unless the uploaded snapshot is already the verified green baseline.

## Core workflow files

- `01-interaction-protocol.md`: collaboration loop, responsibilities, and artifact discipline.
- `02-update-contract.md`: required format for patch-producing updates.
- `03-patch-contract.md`: patch artifact, filename, and application requirements.
- `04-install-and-test.md`: baseline install, patch application, and test command style.
- `05-milestones.md`: staged roadmap for public API and example repair.
- `06-handoff-template.md`: state template for continuing in a new chat.
- `07-failure-report-template.md`: template for reporting patch or test failures.
- `public-api-contract.md`: living map of the public API implied by the numbered examples.
- `patch-ledger.md`: patch-number history and current next-patch guidance.
- `CHANGELOG.md`: changes to this engineering workflow.

## Developer process files

- `developer/developer-guide.md`: contributor-facing entry point for resync, artifact choice, validation, documentation audience, and ontology-first development.
- `developer/engineering-principles.md`: non-negotiable engineering principles for CALM patches.
- `developer/repository-resync-baseline.md`: how to establish a trustworthy patch baseline.
- `developer/patch-generation-checklist.md`: preflight checklist for every patch-producing update.
- `developer/documentation-audience-policy.md`: audience split and page-placement policy for user, advanced, reference, and engineering docs.
- `developer/test-suite-policy.md`: test-suite tiers, marker ownership, optional-backend testing, and warning-policy integration.
- `developer/repository-artifact-hygiene.md`: generated-artifact, ignored-output, and clean snapshot policy.
- `developer/warning-policy.md`: accepted warnings and warning-regression policy.

## Architecture files

- `architecture/current-architecture.md`: current package ownership map.
- `architecture/import-boundary-guardrails.md`: conservative import-time and public/internal boundary tests for the cleanup milestone.
- `architecture/workspace-ux-ownership.md`: ownership map and decomposition guardrails for the advanced Workspace UX facade.
- `architecture/slab-generation-modernization.md`: closure notes for the modern slab-generation path.
- `architecture/public-api-boundaries.md`: basic public API versus advanced/core API boundaries.
- `architecture/public-facade-workflows.md`: ownership and contracts for Surface/search/candidate/dataset public workflows.
- `architecture/public-workflow-query-reporting.md`: target project-backed query, table export, plotting contracts, and public collection implementation ownership.
- `architecture/calculator-backend-architecture.md`: ownership and provider contract for ASE/MLIP calculators.



## Documentation consolidation files

- `documentation/documentation-inventory.md`: structural inventory and authority classification for engineering documentation after ontology closure.
- `documentation/documentation-consolidation-plan.md`: staged plan for the Documentation Consolidation and Reference Manual milestone.
- `documentation/engineering-documentation-cleanup.md`: current-state cleanup decisions for overview, roadmap, continuation, and handoff pages.
- `documentation/developer-guide-modernization.md`: consolidation record for the developer guide and contributor-process reading path.
- `documentation/navigation-crosslink-audit.md`: navigation, cross-link, orphan-page, duplicate-label, and reading-order audit for the consolidated engineering docs.
- `documentation/documentation-consolidation-closure.md`: final documentation architecture, retention policy, maintenance rules, and closure record for the milestone.
- `ontology/ontology-reference-manual.md`: canonical reader-oriented entry point for the closed CALM ontology.


## Mathematical specification files

- `mathematical-specification/mathematical-specification-framework.md`: milestone-opening record for the Mathematical and Algorithmic Specification effort. The user-visible mathematical reference lives in `docs/mathematics/` and is wired into MkDocs as the normative mathematics and algorithm layer between ontology and implementation.
- `mathematical-specification/motif-compatible-surface-primitive-specification.md`: engineering record for the first substantive algorithm specification, which documents motif-compatible surface primitive unit-cell generation in `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md`.
- `mathematical-specification/primitive-surface-generation-mathematical-audit.md`: transformation-centric audit record for primitive surface generation, linking the exact Bravais-kernel proof, implementation checks, verification coverage, and remaining bounded motif/search gaps.

## Implementation conformance files

- `implementation-conformance/implementation-conformance-audit-plan.md`: audit schema and milestone rules for applying the closed ontology to implementation, tests, public APIs, persistence, projection, reporting, and documentation before further source modernization.
- `implementation-conformance/implementation-conformance-inventory.md`: first populated conformance inventory mapping ontology concepts and morphisms to current implementation owners, verification coverage, compatibility boundaries, and prioritized follow-on guardrail work.
- `implementation-conformance/implementation-conformance-guardrail-plan.md`: ranked modernization queue and final planning gate before focused source/test patches begin.

## Ontology files

- `ontology/README.md`: overview of CALM mathematical ontology and semantic traceability.
- `ontology/ontology-reference-manual.md`: manual-style current reference for the closed ontology and reading order.
- `ontology/scientific-object-model.md`: canonical scientific object hierarchy for CALM's crystallographic-interface workflow.
- `ontology/scientific-transformation-model.md`: directed transformation catalogue for CALM workflow semantics.
- `ontology/verification-ontology.md`: verification taxonomy linking scientific transformations to tests.
- `ontology/symbol-semantics-policy.md`: rules for symbol classification, compatibility boundaries, and future semantic cleanup.
- `ontology/semantic-traceability-roadmap.md`: staged roadmap for the ontology milestone.
- `ontology/surface-slab-math2d-semantic-inventory.md`: first semantic inventory covering surface, slab, Math2D, HNF, and transform-provenance symbols.
- `ontology/interface-matching-strain-prototype-semantic-inventory.md`: second semantic inventory covering interface matching, strain/deformation, prototype grouping, registry-search, and candidate/result semantics.
- `ontology/build-energy-persistence-public-projection-semantic-inventory.md`: third semantic inventory covering build, energy, persistence, sidecar, public records, collections, datasets, and reporting projections.
- `ontology/mathematical-ontology-foundations.md`: formal mathematical foundation for objects, spaces, representations, morphisms, invariants, metrics, and provenance.
- `ontology/mathematical-ontology-roadmap.md`: staged roadmap for completing the formal ontology before source modernization.
- `ontology/mathematical-spaces-and-representations.md`: formal mathematical-space definitions for CALM objects and workflow contexts.
- `ontology/representation-equivalence-rules.md`: rules for distinguishing representation changes from scientific object changes.
- `ontology/transformations-and-morphisms.md`: formal morphism contracts for CALM workflow transformations.
- `ontology/morphism-contract-catalogue.md`: compact catalogue of morphism identifiers, composition chains, owners, and verification focus.
- `ontology/invariants-metrics-and-provenance.md`: preservation properties, metrics, units, objective quantities, and provenance obligations for formal morphism contracts.
- `ontology/invariant-metric-catalogue.md`: compact invariant, metric, and provenance identifier catalogue for symbol-atlas and verification planning.
- `ontology/energy-terminology-decision.md`: decision record for energy quantity names, unit classes, and compatibility boundaries.
- `ontology/interface-object-name-boundary-audit.md`: boundary audit for internal interface structures, public interface models, persisted derived-interface records, and report/export projections.
- `ontology/compatibility-guardrail-expansion.md`: compatibility guardrails for public, storage, provider, report, exported-field, energy, and projection names during source semantic modernization.
- `ontology/admissibility-criteria.md`: admissibility criteria for scientific morphisms, using `AD-*` statements tied to identity, representation, provenance, and verification obligations.
- `ontology/representation-morphisms.md`: framework distinguishing scientific morphisms, representation morphisms, and persistence projections for the representation-ontology phase.
- `ontology/representation-catalogue.md`: detailed catalogue of CALM representations, owners, compatibility boundaries, information classes, invertibility expectations, and verification status.

## Continuation and roadmap files

- `continuation/project-state.md`: concise current verified project state aligned to the currently active execution roadmap.
- `continuation/next-chat-handoff.md`: concise current handoff prompt for future chats; historical update detail belongs in `history/`.
- `roadmap/current-roadmap.md`: repository roadmap registry and activation ledger.
- `workflow-realization/active-roadmap.md`: current active execution roadmap for implementation work.
- `roadmap/ontology-long-term-roadmap.md`: strategic endpoint for ontology and semantic-modernization work after the active roadmap.
- `roadmap/stable-architecture-hardening-roadmap.md`: living roadmap for moving CALM from transitional architecture to stable public API, persistence, packaging, and module boundaries.
- `roadmap/architecture-cleanup-roadmap.md`: ownership, dead-code, boundary, test-suite, optional-dependency, and sidecar-audit plan for the architecture cleanup milestone.
- `roadmap/mlip-calculator-roadmap.md`: staged plan for expanding first-class MLIP provider coverage.

Roadmap governance and index
---------------------------

The canonical governance rules for living roadmap files live in:

- `docs/engineering/roadmap/README.md` — roadmap governance and update rules
- `docs/engineering/roadmap/index.md` — inventory of roadmap files and current statuses

Authority rules
---------------
The repository-level source of truth for roadmap activation is
`docs/engineering/roadmap/current-roadmap.md`, which functions as the roadmap
registry and activation ledger.

The repository may maintain multiple living roadmap documents concurrently, but
exactly one roadmap may be designated the active execution roadmap at a time.
Program-scoped roadmaps (for example
`docs/engineering/workflow-realization/active-roadmap.md`) become the current
execution source only when designated as active by `current-roadmap.md`.
- `history/primitive-slab-modernization-closure.md`: historical closure report for the slab-generation modernization.
- `history/public-workflow-query-reporting-closure.md`: closure report for the public project query/reporting sidecar milestone.
- `history/architecture-cleanup-closure.md`: closure report for the architecture cleanup and boundary hardening milestone.
- `history/public-api-packaging-audit-0036a.md`: audit report for public API/package/docs consistency.
- `history/public-api-tiering-0037.md`: audit report for public API audience-tier metadata.
- `history/calculator-provider-support-audit-0038.md`: audit report for provider support matrix and docs/provider-registry alignment.
- `history/repository-artifact-hygiene-0039.md`: audit report for generated-artifact hygiene and clean snapshot export.
- `history/public-project-sidecar-extraction-0040.md`: extraction report for public sidecar persistence and record-construction ownership.
- `history/public-sidecar-validation-migration-0041.md`: validation and migration-policy report for the public project sidecar.
- `history/public-collection-module-decomposition-0042.md`: ownership report for splitting public collection implementations while preserving the stable import path.
- `history/public-project-facade-decomposition-0043.md`: ownership report for reducing `calm.public.project` into query and save orchestration helpers.
- `history/persistence-projection-guardrail-tests-0185.md`: report for the first Implementation Conformance source/test guardrails protecting persistence and projection compatibility keys.
- `history/workspace-ux-responsibility-audit-0044.md`: responsibility audit for the advanced Workspace UX facade and its future decomposition path.
- `history/transitional-public-api-audit-0045.md`: disposition audit for deprecated public API entries.
- `history/make-slab-removal-0046.md`: call-site audit and removal report for the `calm.slab.make_slab` shim.
- `history/test-suite-tier-marker-cleanup-0047.md`: marker-rule cleanup report for test-suite tier selection.
- `history/warning-policy-tier-cleanup-0048.md`: structured warning-policy and accepted warning filter guardrail report.
- `history/test-suite-warning-policy-closure-0049.md`: closure report for Phase E test-suite and warning-policy cleanup.
- `history/documentation-audience-split-0050.md`: report for the Phase F documentation audience split.
- `history/numbered-example-classification-0051.md`: report for the numbered example classification catalog and guardrails.


## Architecture

Note: several architecture and policy documents are archived under the top-level
`engineering/` ledger rather than duplicated under `docs/`. If you need to read
the Transitional public API policy, consult `engineering/architecture/transitional-public-api-policy.md` in the repository root.

- `history/representation-morphism-catalogue-0169.md`: report for the representation morphism catalogue.


## 0171 - Object identity and equivalence

Update `0171-object-identity-and-equivalence.zip` adds `ontology/object-identity-and-equivalence.md` as the `ID-*` ontology reference for scientific identity, representation-preserving equivalence, identity-changing transformations, and deferred verification obligations. The update is documentation-only and preserves source behavior, public APIs, storage schemas, sidecar fields, report/export labels, provider names, compatibility aliases, formulas, units, and runtime behavior.


## Ontology milestone closure

Update `0175-ontology-closure.zip` closes the Mathematical Ontology Formalization milestone. The ontology documents now define the governing reference model for CALM scientific objects, representations, morphisms, identity/equivalence, admissibility, provenance, verification, and compatibility boundaries. Future semantic work should cite or extend the ontology before changing implementation names, public records, storage/export/report fields, provider identifiers, formulas, units, or validation behavior.

Update `0176-documentation-inventory-consolidation-plan.zip` opens the Documentation Consolidation and Reference Manual milestone. Documentation consolidation now has a dedicated owner under `docs/engineering/documentation/`; future documentation updates should distinguish current reference material from historical update records.

Update `0178-engineering-documentation-cleanup.zip` records the first cleanup pass for current-state engineering documents. The engineering overview, roadmap, continuation state, and handoff pages should now point to canonical owners instead of repeating closed-milestone chronology.

Update `0180-documentation-navigation-crosslink-audit.zip` records the navigation and cross-link audit for the consolidated engineering documentation. It wires the audit page and recent missing history records into MkDocs navigation and identifies documentation consolidation closure as the next step.


## Documentation consolidation closure

Update `0181-documentation-consolidation-closure.zip` closes the Documentation Consolidation and Reference Manual milestone. Current-state documentation now has explicit canonical owners, history records are retained as design provenance, and future documentation work should modify the relevant owner rather than reopen the consolidation milestone.

## 0187 surface symmetry helper cleanup

`0187-surface-symmetry-helper-cleanup.patch` begins focused source modernization by consolidating duplicated internal surface point-group representation helpers into `calm.interface._surface_symmetry.surface_pointgroup_ops_2d`. It preserves optional dependency fallback behavior and adds dependency-light tests for the ownership boundary.

- `0189-application-uid-helper-cleanup.patch` consolidates duplicated application UID JSON/digest helpers under `calm.project.application._uid`.

## 0191 oriented slab transform JSON cleanup

`0191-oriented-slab-transform-json-cleanup.patch`, `0192-oriented-slab-ops-json-cleanup.patch` continues representation morphism cleanup by consolidating oriented-slab transform provenance JSON-native conversion under `calm.slab._json.json_native`. It preserves transform payload schema boundaries while removing a facade-local conversion helper.

## 0195 slab UID helper cleanup

`0195-slab-uid-helper-cleanup.patch` consolidates slab UID payload hashing under the shared application UID helper owner while preserving the legacy ASCII-escaped JSON digest contract.

## 0196 public API helper boundary guardrails

The Implementation Conformance milestone now includes public API boundary tests for internal helper owners introduced by the cleanup sequence. These guardrails ensure representation helpers remain private unless explicitly promoted through the public API inventory and tier process.

## 0197 slab numeric helper cleanup

`0197-slab-numeric-helper-cleanup.patch` consolidates duplicate slab-operation near-zero tolerance predicates under `calm.slab.ops._numeric.is_near_zero`. This is a representation-helper cleanup for slab construction and validation checks; it preserves scientific morphism behavior and public compatibility boundaries.

## 0198 application JSON helper cleanup

`0198-application-json-helper-cleanup.patch` consolidates application record JSON-native payload projection under `calm.project.application._json.json_native`. This is a representation-morphism cleanup for derived-interface strain-state specs and preserves public APIs, UID semantics, persistence schemas, and compatibility aliases.
## Implementation Conformance update 0199

`0199-public-api-scientific-morphism-boundary-guardrails.patch` records public API guardrails that keep basic workflow facades separate from advanced scientific morphism kernel aliases while preserving compatibility exports.

## 0200 - Implementation Conformance closure

Update `0200-implementation-conformance-closure.patch` closes the Implementation Conformance milestone. The closure record is `implementation-conformance/implementation-conformance-closure.md`; historical details remain in `history/implementation-conformance-closure-0200.md`. Future implementation work should build on the established guardrails and should not reopen broad ontology or compatibility-boundary decisions without a new migration plan.

## Mathematical and Algorithmic Specification milestone

The Mathematical and Algorithmic Specification milestone is open. It establishes `docs/mathematics/` as the normative mathematical and algorithmic reference layer between the ontology and implementation. Update `0203-surface-cell-matching-strain-optimization-specification.zip` adds the surface-cell matching and strain optimization specification for the interface matching algorithm.


## Mathematical and Algorithmic Specification milestone

The milestone is active. Updates `0201` through `0204` establish the mathematics framework and initial algorithm specifications for motif-compatible primitive surface cells, surface-cell matching/strain optimization, and deduplication/equivalence/canonicalization.

## 0207 - Monte Carlo registry alignment specification

`0207-monte-carlo-registry-alignment-specification.zip` adds the mathematical and algorithmic specification for registry search. The update is documentation-only and maps the implemented Monte Carlo kernel, z-padding behavior, geometry proposal helper, and registry-search workflow orchestration to correctness and verification targets.

Next recommended mathematical specification: strain partitioning.

## 0208 - Geodesic strain partitioning specification

`0208-geodesic-strain-partitioning-specification.zip` adds the mathematical and algorithmic specification for strain partitioning. The specification documents the affine-invariant SPD(2) geodesic target metric, corrected alpha endpoint convention, deformation-gradient construction, Hencky diagnostics, finite alpha-grid scan behavior, and verification targets.

Next recommended mathematical specification: interface construction.

## 0209 interface construction specification

Update `0209-interface-construction-specification.zip` adds the mathematical and algorithmic specification for CALM's interface-build morphism and maps it to the current build pipeline and geometry kernel.


## 0210 interfacial-energy evaluation specification

`0210-interfacial-energy-evaluation-specification.zip` adds the mathematical and algorithmic specification for strained-bulk interfacial-energy evaluation. It maps the Evaluate morphism to the current pipeline, energy kernel, scalar arithmetic helper, strained-bulk reference construction, and EnergyResult provenance fields. No source/runtime behavior changed.

## 0211 - Persistence/report projection specification

`0211-persistence-report-projection-specification.zip` documents persistence, public sidecar projection, dataset manifest projection, and report tables as representation morphisms. The specification records identity/provenance preservation requirements and the lossy nature of public/report projections.

## 0212 - End-to-end workflow traceability

The Mathematical and Algorithmic Specification milestone now includes an end-to-end workflow traceability page connecting ontology objects, mathematical operations, implementation owners, verification status, and remaining audit targets across the canonical CALM workflow.

## 0213 oriented slab construction specification

`0213-oriented-slab-construction-specification.zip` adds the mathematical and algorithmic specification for CALM oriented slab construction. It treats the workflow as a composed `Construct Slab` morphism and records the distinction between integer basis changes, Cartesian frame rotations, physical shear orthogonalization, vacuum representation, and transform-provenance projection.

## Mathematical specification audit status

Update `0220` adds the built-interface construction validity audit. It treats `calm.interface.pipeline.build_interface` and `calm.interface._build_kernel.build_interface_atoms` as the canonical build path and records assumptions, correctness properties, and verification gaps for deterministic interface geometry assembly.

## 0223 - Surface matching mathematical audit

Prepared `0223-surface-matching-mathematical-audit.zip` for the Mathematical and Algorithmic Specification milestone. The update records a transformation-centric audit of bounded HNF surface-cell matching and identifies dependency-light synthetic matching guardrails as the next verification target.

## 0226 - Surface matching mathematical invariant guardrails

Status: prepared. This update converts surface-matching audit findings into executable mathematical guardrails for area-band necessity, reduced-supercell determinant/area preservation, and the distinction between exact cell-distance invariants and composite ranking scores.

Next recommended work: continue transformation-focused audit with oriented slab construction or decorated motif/search semantics.
