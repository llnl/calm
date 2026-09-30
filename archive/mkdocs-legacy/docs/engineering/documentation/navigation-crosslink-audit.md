# Documentation navigation and cross-link audit

Update: `0180-documentation-navigation-crosslink-audit.zip`

This audit records the navigation and cross-link pass for the Documentation Consolidation and Reference Manual milestone. It follows the inventory, ontology reference manual, engineering-documentation cleanup, and developer-guide modernization passes.

## Purpose

After consolidation, the documentation should be navigable by authority rather than by update chronology. Current-state readers should encounter living reference pages first, while historical records remain discoverable as evidence.

This update checks the engineering-documentation navigation after the developer guide modernization and records the remaining closure work for `0181`.

## Audit method

The audit used the current repository snapshot and reviewed:

- MkDocs navigation coverage for engineering documentation;
- engineering Markdown files that were present on disk but absent from MkDocs navigation;
- internal Markdown links under `docs/engineering/`;
- duplicate or confusing labels in the active Documentation Consolidation section;
- reading order among overview, developer, documentation, ontology, architecture, continuation, roadmap, and history pages.

The automated checks available in this environment verified that all parsed MkDocs navigation paths exist and that relative Markdown links under `docs/engineering/` resolve. `mkdocs build --strict` remains the authoritative navigation check in a fully provisioned local environment.

## Navigation authority model

The intended reading order after this update is:

1. `docs/engineering/README.md` for the engineering entry point.
2. `docs/engineering/continuation/project-state.md` and `docs/engineering/roadmap/current-roadmap.md` for active work.
3. `docs/engineering/developer/developer-guide.md` for contributor procedure.
4. `docs/engineering/documentation/documentation-consolidation-plan.md` for the documentation-consolidation milestone.
5. `docs/engineering/ontology/ontology-reference-manual.md` for the closed ontology.
6. Narrow policy, architecture, roadmap, and history pages as needed.

History pages remain navigable but are not the primary current-state reading path.

## Audit findings

| Area | Finding | Disposition |
| --- | --- | --- |
| MkDocs path existence | Parsed MkDocs navigation paths resolve to files in `docs/`. | Satisfactory in the available static check. Confirm with `mkdocs build --strict` locally. |
| Engineering internal links | Relative links under `docs/engineering/` resolve in the available static check. | Satisfactory. |
| Documentation milestone pages | `0176` through `0179` pages are grouped under the Documentation section. | Add this `0180` audit page to the same group. |
| History coverage | Several recent history records existed on disk but were not linked from MkDocs history navigation. | Wire the missing recent records into the history section. |
| Reading order | Current-state pages already route readers to canonical owners before historical records. | Satisfactory; preserve this order for `0181`. |
| Duplicate labels | Recent documentation-consolidation labels are distinct and update-scoped. | Satisfactory. |

## Navigation changes made

This update wires the following current or recent pages into MkDocs navigation:

- `engineering/documentation/navigation-crosslink-audit.md`;
- `engineering/history/navigation-crosslink-audit-0180.md`;
- recent missing history records for representation verification mapping, energy provenance verification mapping, provenance algebra, ontology conformance, ontology closure, ontology reference manual, and engineering documentation cleanup.

The wiring keeps current documentation and ontology references before history records.

## Remaining closure checks for 0181

`0181` should close the milestone by documenting the final documentation architecture and maintenance policy. It should verify, in a MkDocs-capable environment:

- `mkdocs build --strict`;
- no intentionally current engineering page is absent from navigation;
- no historical page is treated as the primary current reference;
- future documentation-only updates continue to use ZIP overlays unless deletion is required;
- source/test/runtime changes continue to use patches.

## Non-goals

This update does not delete pages, rewrite historical records, change source code, alter public APIs, modify schemas, change report/export/provider names, change formulas or units, or alter validation/runtime behavior.
