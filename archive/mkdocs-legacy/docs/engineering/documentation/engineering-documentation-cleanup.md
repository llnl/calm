# Engineering documentation cleanup

Update: `0178-engineering-documentation-cleanup.zip`

This document records the first cleanup pass after the ontology reference manual was introduced in `0177`. The cleanup keeps the historical record intact while reducing current-state duplication in the engineering overview, roadmap, and continuation handoff pages.

## Purpose

The Documentation Consolidation and Reference Manual milestone distinguishes current references from historical update evidence. This update applies that distinction to the engineering state documents that are read first during repository resync.

Current-state pages should answer three questions quickly:

1. What is the active milestone?
2. What reference documents govern current work?
3. What is the next executable update?

Detailed chronology remains available in `docs/engineering/history/`, `docs/engineering/patch-ledger.md`, closed-roadmap records, and closure documents.

## Cleanup decisions

| Area | Decision | Rationale |
| --- | --- | --- |
| Engineering overview | Keep as a top-level map and add the documentation-cleanup record under the documentation owner. | The overview should route readers to canonical owners instead of repeating milestone history. |
| Active roadmap | Keep only the active Documentation Consolidation sequence and concise summaries of closed ontology work. | The roadmap should identify the next executable update, not require chronological reading of closed ontology phases. |
| Project state | Replace append-only ontology/update narration with a compact current-state summary and historical-guardrail section. | Handoff readers need the verified state and next action; history pages preserve detailed rationale. |
| Next-chat handoff | Keep the actionable startup list and required historical guardrail phrases, then point to canonical documents. | New chats should resync from current references without inheriting stale transition instructions. |
| Patch ledger | Keep append-only update rows but move prose next-update guidance forward to 0179. | The ledger remains an index, not the primary roadmap. |

## Preserved guardrails

This cleanup intentionally preserves phrases that architecture tests use as durable historical evidence:

- `Internal Modernization is open`
- `Internal Modernization is the active milestone`
- `0098-root-architecture-test-relocation.patch`
- `Root-level architecture-policy tests were relocated`
- `deletion-review queue`
- `per-test deletion-review queue from `0100``

These phrases are historical guardrails, not current milestone instructions.

## Authority model after cleanup

| Reader question | Current owner |
| --- | --- |
| What is the current engineering state? | `docs/engineering/continuation/project-state.md` |
| What should the next chat do? | `docs/engineering/continuation/next-chat-handoff.md` |
| What is the patch/update sequence? | `docs/engineering/roadmap/current-roadmap.md` |
| What is the completed ontology? | `docs/engineering/ontology/ontology-reference-manual.md` |
| How is documentation being consolidated? | `docs/engineering/documentation/documentation-consolidation-plan.md` |
| How should updates be validated and packaged? | `docs/engineering/developer/` policy pages |

## Non-goals

This update does not delete history files, move architecture records, alter tests, rename public APIs, change persistence formats, or modify runtime behavior. It is a documentation-architecture cleanup only.

## Next update

The next planned update is `0179-developer-guide-modernization.zip`, which should consolidate contributor-facing process guidance around repository resync, artifact policy, validation, warnings, documentation audience, and ontology-first design.
