# Documentation consolidation plan

Update: `0176-documentation-inventory-consolidation-plan.zip`

This plan opens the Documentation Consolidation and Reference Manual milestone. The milestone uses the closed ontology as a stable foundation and reorganizes the engineering documentation around current authority rather than update chronology.

## Milestone objective

Transform the engineering documentation into a coherent reference system where:

- canonical pages explain how CALM works today;
- developer-process pages explain how to change CALM safely;
- roadmap and continuation pages identify the current state and next work;
- history pages preserve why prior decisions were made;
- MkDocs navigation guides readers through current references before historical records.

The milestone should preserve evidence while reducing duplicated explanations and stale next-step guidance.

## Governing rule

> History documents explain how CALM reached the current architecture; reference documents explain how CALM should be understood and changed now.

## Planned update sequence

| Update | Name | Type | Purpose |
| --- | --- | --- | --- |
| `0176` | Documentation inventory and consolidation plan | ZIP overlay | Establish the documentation classification scheme, topic ownership map, and milestone plan. |
| `0177` | Ontology reference manual | ZIP overlay | Add a reader-oriented ontology manual that integrates objects, spaces, representations, morphisms, identity, admissibility, provenance, verification, symbols, and compatibility boundaries. |
| `0178` | Engineering documentation cleanup | ZIP overlay | Reduce duplicated closed-milestone narrative in roadmap, continuation, and overview pages while preserving required historical guardrail phrases. |
| `0179` | Developer guide modernization | ZIP overlay | Consolidate contributor-facing process guidance around repository resync, artifact policy, validation, warnings, documentation audience, and ontology-first design. |
| `0180` | Navigation and cross-link audit | ZIP overlay | Audit MkDocs navigation, internal links, orphan pages, and reading order after consolidation. Complete. |
| `0181` | Documentation consolidation closure | ZIP overlay | Close the milestone with a documentation architecture record, maintenance policy, and remaining technical-debt list if any. |

## Workstream 1: ontology reference manual

The ontology milestone closed in `0175`, but its reference material is spread across many documents. `0177` should create a cohesive manual-style entry point that summarizes the current ontology and links to detailed chapters.

The manual should cover:

- scientific object hierarchy;
- mathematical spaces and representations;
- scientific morphisms, representation morphisms, and projections;
- invariants, metrics, and provenance;
- identity and equivalence;
- admissibility;
- verification and conformance;
- symbol and terminology ownership;
- compatibility boundaries.

Existing ontology documents should remain available as detailed chapters and historical evidence. The manual should reduce the need for new contributors to read ontology documents chronologically.

## Workstream 2: active-state simplification

`0178` should simplify current-state documents so they serve current work instead of recording every completed transition.

Targets:

- `docs/engineering/roadmap/current-roadmap.md`;
- `docs/engineering/continuation/project-state.md`;
- `docs/engineering/continuation/next-chat-handoff.md`;
- `docs/engineering/README.md`.

The update must preserve any historical phrases explicitly retained for architecture tests. Ordinary completed-update detail should move to or remain in history records and closure documents.

## Workstream 3: developer guide modernization

`0179` should make developer documentation the authoritative place for contributor procedure. It should reduce repeated instructions in update-specific documents while retaining the required response and artifact discipline.

Topics:

- repository resync baseline;
- ZIP overlay versus patch selection;
- source/test validation policy;
- documentation audience placement;
- warning policy;
- artifact hygiene;
- ontology-first change justification.

## Workstream 4: navigation and cross-link audit

`0180` should ensure the documentation is navigable after consolidation. It should check:

- MkDocs nav coverage;
- internal link validity where practical;
- orphaned pages;
- duplicate or confusing nav labels;
- whether current references appear before history records;
- whether history records remain discoverable but not primary reading paths.

## Workstream 5: closure and maintenance policy

`0181` should close the milestone by documenting:

- the final documentation architecture;
- canonical owners for major documentation domains;
- maintenance rules for future updates;
- remaining documentation debt if any;
- validation commands for future documentation-only updates.

## Success criteria

The milestone is complete when:

1. A new contributor can find the current ontology, architecture, developer process, and active roadmap without reading update history chronologically.
2. Every major engineering documentation domain has a clear owner.
3. Historical records are preserved but are no longer the default source of current-state truth.
4. Closed-milestone details are summarized in current-state pages and available in history or closure pages.
5. MkDocs navigation reflects the authority hierarchy.
6. Documentation-only updates continue to preserve source, public API, persistence, sidecar, export, report, provider, formula, unit, validation, exception, and runtime behavior unless a later source patch explicitly changes them.

## Immediate next work

Proceed to `0181-documentation-consolidation-closure.zip`, a documentation-only update that closes the milestone with the final documentation architecture, maintenance policy, and remaining technical-debt list if any.


## Navigation audit status

Update `0180-documentation-navigation-crosslink-audit.zip` completed the navigation and cross-link audit workstream. The remaining milestone work is `0181-documentation-consolidation-closure.zip`.
