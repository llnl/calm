# Mathematical and algorithmic specification

CALM constructs, searches, builds, evaluates, stores, queries, and reports crystalline interface models. The ontology defines the scientific objects and morphisms in that workflow. This specification defines the mathematics and algorithms those morphisms are intended to realize.

## Authority

This manual is the scientific specification layer between the ontology and implementation:

```text
Scientific ontology
    -> mathematical specification
    -> algorithm specification
    -> implementation
    -> verification
```

Implementation behavior should conform to this specification. When implementation behavior and this specification disagree, the discrepancy should be resolved explicitly by either correcting the implementation, correcting the specification, or recording a compatibility-boundary decision.

## Initial specification targets

The first high-priority topics are:

1. motif-compatible surface primitive unit-cell generation;
2. surface-cell matching and strain optimization for interface generation;
3. deduplication of equivalent structures and interfaces;
4. Monte Carlo registry alignment;
5. strain partitioning.

This list is intentionally non-exhaustive. Additional transformations and algorithms should be added as they are identified in the ontology, implementation, tests, or user-facing workflows.

## Standard page structure

Transformation and algorithm pages should use the templates in:

- `transformations/transformation-template.md`
- `algorithms/algorithm-template.md`

Each page should describe the mathematical problem, derivation, assumptions, representation mappings, algorithmic workflow, correctness properties, numerical limitations, implementation owners, and verification coverage.

## Current completed specifications

The current mathematics manual includes specifications for motif-compatible primitive surface cells, surface-cell matching and strain optimization, deduplication and canonicalization, Monte Carlo registry alignment, geodesic strain partitioning, interface construction, oriented slab construction, interfacial-energy evaluation, and persistence/report projection.

## Current inventory and audit control documents

The [mathematical traceability inventory](verification/mathematical-traceability-inventory.md) maps implemented transformations to ontology morphisms, implementation owners, current specification status, validity findings, and verification coverage.

The [mathematical audit inventory](verification/mathematical-audit-inventory.md) is the audit-phase control document. It ranks the next transformation audits and requires each audit to separately assess mathematical validity and implementation validity.
