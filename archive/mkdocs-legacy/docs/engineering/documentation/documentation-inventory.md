# Documentation inventory

Update: `0176-documentation-inventory-consolidation-plan.zip`

This inventory opens the Documentation Consolidation and Reference Manual milestone after the Mathematical Ontology Formalization milestone closed in `0175`. It classifies the engineering documentation by durable role so later consolidation work can reduce duplication without losing historical context.

The inventory is intentionally structural. It does not retire pages by itself, rename public documentation, or move historical records. It establishes the ownership map that later updates should use when consolidating content.

## Classification scheme

| Class | Meaning | Editing rule |
| --- | --- | --- |
| Canonical reference | Describes how CALM works today. | Prefer improving this page over repeating the same explanation elsewhere. |
| Developer process | Defines how contributors prepare, validate, package, or review changes. | Keep operational and current; avoid historical narrative. |
| Roadmap / continuation | Records current planned work and handoff state. | Keep concise and current; move completed detail to history. |
| Historical record | Explains why a past change happened. | Preserve as evidence; do not treat as the current source of truth unless explicitly referenced. |
| Project governance | Defines project-facing rules or public contracts. | Keep stable and cite from implementation-facing docs when needed. |

## Directory-level inventory

| Location | Current role | Canonical owner for durable content | Consolidation disposition |
| --- | --- | --- | --- |
| `docs/engineering/README.md` | Project governance / entry point | Engineering overview | Keep as the top-level map; reduce detailed milestone narrative over time. |
| `docs/engineering/01-*.md` through `07-*.md` | Developer process | Engineering workflow | Keep as process references; cross-link instead of duplicating instructions in handoff pages. |
| `docs/engineering/public-api-contract.md` | Project governance | Public API contract | Keep as the public-contract reference until superseded by a broader public API manual. |
| `docs/engineering/patch-ledger.md` | Roadmap / continuation | Update ledger | Keep as append-only patch index; avoid storing full milestone rationale here. |
| `docs/engineering/CHANGELOG.md` | Historical record / change summary | Engineering changelog | Keep as brief change log; detailed rationale belongs in history or reference docs. |
| `docs/engineering/architecture/` | Canonical reference plus historical architecture records | Architecture reference | Split current architecture references from old audit/closure pages during later cleanup. |
| `docs/engineering/continuation/` | Roadmap / continuation | Current project state and next handoff | Keep concise; remove stale completed-update detail once it is represented in history. |
| `docs/engineering/developer/` | Developer process | Contributor and validation policies | Keep as the source of contributor procedure; consolidate overlapping warning/test/docs policy statements. |
| `docs/engineering/history/` | Historical record | Milestone evidence and closure records | Preserve; do not use as primary onboarding path. |
| `docs/engineering/ontology/` | Canonical reference plus ontology history chapters | Ontology reference manual | Consolidate into a cohesive reference manual while retaining detailed chapters. |
| `docs/engineering/roadmap/` | Roadmap / continuation | Active and strategic roadmaps | Keep active roadmap current; move completed detail to history or closure records. |
| `docs/engineering/documentation/` | Canonical reference for documentation architecture | Documentation consolidation milestone | New in `0176`; owns inventory, consolidation plan, and later docs-architecture policy. |

## Current document counts

The repository snapshot used for `0176` contains the following first-level engineering-documentation counts:

| Location | Markdown files |
| --- | ---: |
| `docs/engineering/` root | 11 |
| `docs/engineering/architecture/` | 80 |
| `docs/engineering/continuation/` | 2 |
| `docs/engineering/developer/` | 7 |
| `docs/engineering/history/` | 148 |
| `docs/engineering/ontology/` | 49 |
| `docs/engineering/roadmap/` | 9 |

These counts intentionally include historical milestone records. The consolidation goal is not to minimize file count alone; it is to make the reading path and authority model obvious.

## Topic ownership map

| Topic | Canonical owner | Supporting / historical sources | Consolidation need |
| --- | --- | --- | --- |
| Engineering workflow and patch discipline | `docs/engineering/01-*.md` through `07-*.md`, developer policy pages | `patch-ledger.md`, history records | Keep process instructions in process docs; remove repeated validation boilerplate from handoff pages where practical. |
| Current project state | `docs/engineering/continuation/project-state.md` | `next-chat-handoff.md`, `current-roadmap.md` | Keep current state short; avoid append-only milestone narration. |
| Active roadmap | `docs/engineering/roadmap/current-roadmap.md` | `patch-ledger.md`, milestone history | Record next executable work only; summarize closed milestones instead of retaining full phase detail. |
| Architecture ownership | `docs/engineering/architecture/current-architecture.md` and active architecture reference pages | architecture audit/closure history | Distinguish current references from historical architecture-audit pages. |
| Ontology | future ontology reference manual; current detailed ontology chapters | ontology history and closure records | Create a reader-oriented manual that cites detailed chapters instead of requiring chronological reading. |
| Documentation architecture | `docs/engineering/documentation/documentation-consolidation-plan.md` | `0137`-`0141` docs-hardening history | New owner for consolidation decisions. |
| Public API contract | `docs/engineering/public-api-contract.md` | public API tier and packaging audit history | Preserve; link from developer/process pages rather than duplicating public-boundary rules. |
| Validation policy | `docs/engineering/developer/test-suite-policy.md`, `warning-policy.md`, `repository-resync-baseline.md` | update templates and history | Consolidate overlapping validation wording into developer policies and cite them from update templates. |

## Initial duplication and fragmentation findings

1. The ontology is complete but distributed across many chronological chapters. Later consolidation should introduce a manual-style entry point that explains the current model first and treats the update sequence as supporting detail.
2. The active roadmap still carries substantial closed-milestone detail. Later cleanup should retain historical guardrail phrases that tests require, but move ordinary completed-phase narrative to history or closure records.
3. The continuation pages contain useful current handoff information mixed with older update notes. Later cleanup should keep only current state and next-action guidance.
4. Architecture pages contain both current ownership references and audit artifacts. Later cleanup should classify each architecture page as current reference or history-backed audit record.
5. Validation and artifact-policy guidance appears in several places. Later cleanup should make the developer policy pages authoritative and replace repeated instructions with links.

## Non-goals for this update

- Do not delete, move, or rename existing documentation pages.
- Do not change Python source, tests, public APIs, persistence schemas, or runtime behavior.
- Do not collapse history pages into reference pages.
- Do not reopen the Mathematical Ontology Formalization milestone.

