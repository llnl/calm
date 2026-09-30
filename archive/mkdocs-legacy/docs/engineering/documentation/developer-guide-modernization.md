# Developer guide modernization

Update: `0179-developer-guide-modernization.zip`

This record documents the developer-facing consolidation pass in the Documentation Consolidation and Reference Manual milestone.

## Purpose

Earlier engineering guidance was correct but distributed across several process documents, roadmap files, and continuation notes. This update adds a single contributor-facing route through that material without deleting the detailed policy pages.

The goal is to make the first developer reading path obvious:

1. current state;
2. current roadmap;
3. developer guide;
4. domain-specific policy pages;
5. canonical ontology/reference documents as needed.

## Changes in authority model

| Topic | Current owner after this update |
| --- | --- |
| Contributor reading path | `docs/engineering/developer/developer-guide.md` |
| Resync baseline | `docs/engineering/developer/repository-resync-baseline.md` |
| Artifact checklist | `docs/engineering/developer/patch-generation-checklist.md` |
| Validation and test tiers | `docs/engineering/developer/test-suite-policy.md` and `docs/engineering/04-install-and-test.md` |
| Warning handling | `docs/engineering/developer/warning-policy.md` |
| Documentation audience placement | `docs/engineering/developer/documentation-audience-policy.md` |
| Generated artifact hygiene | `docs/engineering/developer/repository-artifact-hygiene.md` |
| Ontology-first semantic guidance | `docs/engineering/ontology/ontology-reference-manual.md` |

## Consolidation decisions

| Area | Decision | Rationale |
| --- | --- | --- |
| Developer overview | Add `developer/developer-guide.md` as the process entry point. | Contributors need a route through existing policy without reading every historical file first. |
| Detailed policies | Preserve existing policy pages. | They remain the narrow authoritative owners for specific rules. |
| Artifact policy | Record the ZIP-versus-patch rule in the guide and point to the checklist for details. | The current milestone often uses documentation overlays, while deletions and source/test changes need patch semantics. |
| Ontology-first design | Route semantic changes through the ontology reference manual. | The closed ontology is now the governing semantic reference. |
| Continuation and roadmap | Update next-work guidance from 0179 to 0180. | The developer guide modernization pass is complete after this overlay. |

## Non-goals

This update does not delete process pages, rewrite the interaction contract, change validation behavior, modify tests, alter source code, change public APIs, or change compatibility boundaries.

## Next update

The next planned update is `0180-documentation-navigation-crosslink-audit.zip`, which should audit MkDocs navigation, cross-links, orphan pages, duplicate labels, and reading order after the developer guide is in place.
