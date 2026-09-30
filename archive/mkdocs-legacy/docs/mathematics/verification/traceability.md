# Traceability

Each mathematical specification should map to implementation and verification.

## Required chain

```text
Ontology object(s)
    -> scientific morphism
    -> mathematical specification
    -> algorithmic realization
    -> implementation owner(s)
    -> public API or compatibility boundary
    -> tests and expected invariants
```

## Gap handling

If any link in the chain is missing, record the gap in the relevant transformation or algorithm page and in the engineering continuation state when it affects near-term work.

## End-to-end workflow traceability

The page [End-to-end workflow traceability](end-to-end-workflow-traceability.md) records the canonical Crystal -> Surface -> Slab -> Interface Candidate -> Built Interface Structure -> Evaluation Result -> Dataset -> Report chain as a composed verification object. It should be used when adding tests that check provenance, identity, metric, strain, energy, dataset, or report continuity across more than one local algorithm.
