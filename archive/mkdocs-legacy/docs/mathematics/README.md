# CALM mathematical and algorithmic specification

This directory is the normative mathematical and algorithmic reference for CALM. It complements the ontology by specifying the mathematical problems, derivations, assumptions, computational algorithms, correctness properties, numerical conventions, implementation mappings, and verification obligations for CALM scientific morphisms.

The specification is organized by mathematical content rather than by source modules. Source modules are referenced only through implementation-mapping sections.

## Reading order

1. `index.md` for scope, authority, and traceability rules.
2. `foundations/` for shared notation, coordinate systems, lattice, symmetry, strain, and numerical conventions.
3. `transformations/` for ontology-aligned scientific morphism specifications.
4. `algorithms/` for concrete computational algorithms used to realize those morphisms.
5. `verification/` for invariants, correctness properties, numerical stability, and test traceability.
6. `bibliography.md` for references used across the specification.

## Traceability rule

Every substantive mathematical or algorithmic page should identify the chain:

```text
Ontology object(s) and morphism(s)
    -> mathematical specification
    -> algorithmic realization
    -> implementation owner(s)
    -> public API boundary, if any
    -> verification coverage
```

If a transformation is implemented but cannot be mapped to this chain, it is a documentation and verification gap.

## Traceability-driven workflow

Use the [mathematical traceability inventory](verification/mathematical-traceability-inventory.md) before adding new specifications. Each new specification should address a documented transformation, verify the mathematics against the current implementation, and record any implementation or documentation corrections discovered during the audit.

## Audit-phase workflow

Use the [mathematical audit inventory](verification/mathematical-audit-inventory.md) to select audit work after a specification page exists. Audit updates should separately assess mathematical validity and implementation validity, then record any verification gaps or required corrections.
