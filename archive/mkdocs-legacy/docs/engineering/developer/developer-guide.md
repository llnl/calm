# Developer guide

Update: `0179-developer-guide-modernization.zip`

This guide is the contributor-facing entry point for CALM engineering work after the Mathematical Ontology Formalization milestone and the first documentation-consolidation cleanup passes. It consolidates the current process into one reading path while leaving the detailed policy documents as the authoritative sources for individual rules.

## Purpose

The developer guide answers one practical question:

> What should a contributor or future chat read and do before changing CALM?

Use this page as the first process reference after the current project-state and roadmap files. When a detailed rule is needed, follow the linked policy document rather than duplicating that rule here.

## Standard development loop

Every update should follow this loop:

1. Establish a trustworthy repository baseline.
2. Identify the active milestone and next update from the roadmap and continuation files.
3. Read the canonical reference documents for the affected domain.
4. Decide whether the update is documentation-only or source/test-affecting.
5. Make the smallest coherent change.
6. Validate honestly.
7. Package the correct artifact type.
8. Update roadmap, ledger, continuation, changelog, and history records as required.

This loop is intentionally conservative. CALM has many historical records, compatibility boundaries, and optional dependencies, so repository state must be explicit before an artifact is prepared.

## Baseline and resynchronization

Repository resync is governed by `repository-resync-baseline.md`. Prefer a freshly uploaded clean snapshot or a user-confirmed green checkout. Do not prepare a forward artifact from an uncertain working tree.

Before changing files, determine:

- the latest applied update;
- the active milestone;
- whether the user reported local changes;
- which validation commands are expected to pass in the available environment;
- whether the update should be a ZIP overlay or a patch.

## Artifact policy

Use the narrowest artifact that matches the change:

| Change type | Artifact | Rule |
| --- | --- | --- |
| Documentation additions or edits only | ZIP overlay | Preferred for documentation-only updates. |
| Source, tests, or deletions | Patch | Required when `git apply` semantics or file deletion tracking matter. |
| Correction to a prior update | Letter-suffixed artifact | Use the original number plus a suffix, for example `0179a-...`. |

When documents need to be added or modified, use a ZIP overlay unless the user requests otherwise. When documents need to be deleted, prefer a patch so deletion intent is explicit and reviewable.

## Validation policy

Use `04-install-and-test.md`, `test-suite-policy.md`, and `warning-policy.md` for detailed validation rules.

The default lightweight validation loop is:

```bash
python3 -m compileall -q calm tests
pytest -q tests/arch
pytest -q tests/test_docs_public_api_imports.py tests/test_docs_python_code_blocks_compile.py
```

Documentation updates should also run:

```bash
mkdocs build --strict
```

when MkDocs is available. Full validation remains:

```bash
pytest -q
```

Do not claim validation that was not performed. If optional dependencies such as ASE, spglib, calculator backends, or MkDocs are unavailable, report the exact blocker.

## Documentation audience and ownership

Documentation placement is governed by `documentation-audience-policy.md` and the inventory in `../documentation/documentation-inventory.md`.

Use the current authority model:

| Question | Canonical owner |
| --- | --- |
| How does CALM's scientific model work? | `../ontology/ontology-reference-manual.md` |
| How should repository documentation be organized? | `../documentation/documentation-consolidation-plan.md` |
| What is the active work item? | `../roadmap/current-roadmap.md` (selection) and `../workflow-realization/active-roadmap.md` (current execution roadmap) |
| What should the next chat know? | `../continuation/next-chat-handoff.md` |
| How should artifacts be produced? | `patch-generation-checklist.md` and this guide |
| What warnings are accepted? | `warning-policy.md` |
| How are tests categorized? | `test-suite-policy.md` |
| What generated artifacts are forbidden in snapshots? | `repository-artifact-hygiene.md` |

Current-state pages should route readers to canonical owners. Historical records should explain why decisions were made, not become the primary onboarding path.

## Ontology-first development

The closed ontology is the semantic authority for future work. Before renaming concepts, moving ownership, changing public records, or modifying storage/export/report labels, identify the relevant ontology concept and compatibility boundary.

Use `../ontology/ontology-reference-manual.md` as the entry point. Detailed chapters remain available for scientific objects, spaces, representations, morphisms, identity, admissibility, provenance, verification, conformance, symbols, and compatibility.

Future implementation changes should extend or cite the ontology rather than bypass it.

## Public API and compatibility

Public API and compatibility work should cite:

- `../public-api-contract.md` for contract surfaces;
- `documentation-audience-policy.md` for user-facing placement;
- the ontology reference manual for scientific terminology;
- compatibility-specific ontology and history records where public names, provider identifiers, persistence fields, report labels, or exported fields are involved.

Because CALM is still under active development, obsolete compatibility layers may be removed when there is a documented disposition and validation coverage. Do not preserve thin legacy facades without a current test, example, or public contract.

## Snapshot hygiene

Repository snapshots should exclude generated local artifacts. Follow `repository-artifact-hygiene.md`, and prefer the clean snapshot exporter when preparing handoff archives:

```bash
python scripts/export_clean_snapshot.py --output ~/Downloads/calm-clean-snapshot.zip
```

Common generated paths such as `site/`, caches, egg-info directories, local workspaces, and `.calm/` outputs are not source documentation.

## Delivery checklist

Before delivering an update, confirm:

- the active milestone and subtask are stated;
- the artifact type matches the change;
- roadmap, ledger, continuation, history, changelog, and MkDocs navigation are updated when applicable;
- validation commands and limitations are reported honestly;
- no unrelated cleanup is included;
- public API, schema, export, report, provider, formula, unit, warning, and runtime changes are explicitly called out if present.

## Relationship to detailed policy pages

This guide is an index and process route, not a replacement for the detailed policies. The detailed policy pages remain authoritative for their narrow domains. Update this guide when the process route changes; update the detailed policy pages when the rule itself changes.
