# End-to-end workflow traceability

This page records the mathematical traceability of CALM's canonical interface workflow as an end-to-end composition. It is not a new algorithm specification. It is a verification map showing how the existing mathematical specifications compose, where scientific morphisms create new scientific objects, where representation morphisms project or serialize those objects, and where the current implementation has validation coverage or remaining gaps.

The canonical workflow is:

```text
Crystal
    -> Surface
    -> Slab
    -> Interface Candidate
    -> Built Interface Structure
    -> Evaluation Result
    -> Dataset
    -> Report
```

The purpose of this page is to make the whole chain auditable. A local algorithm can be mathematically valid while the composed workflow still loses provenance, changes identity, or silently crosses from a scientific morphism into a representation projection. End-to-end traceability therefore checks both mathematics and bookkeeping.

## Repository evidence reviewed

This traceability map is based on the current implementation owners and specifications:

- `calm.slab.ops.oriented_slab`
- `calm.slab.surface_primitive`
- `calm.interface.matching`
- `calm.interface.types`
- `calm.interface.strain`
- `calm.interface.strain_partition`
- `calm.interface.prototypes`
- `calm.interface.registry_search`
- `calm.interface.registry_search_geometry`
- `calm.interface._build_kernel`
- `calm.interface.pipeline`
- `calm.interface._energy_kernel`
- `calm.interface.interface_energy`
- `calm.project.application.*`
- `calm.project.infrastructure.db.*`
- `calm.public.*`
- `calm.reporting`

The corresponding mathematical specifications are:

- `docs/mathematics/algorithms/motif-compatible-surface-primitive-cells.md`
- `docs/mathematics/algorithms/surface-cell-matching-and-strain-optimization.md`
- `docs/mathematics/algorithms/deduplication-equivalence-and-canonicalization.md`
- `docs/mathematics/algorithms/monte-carlo-registry-alignment.md`
- `docs/mathematics/algorithms/geodesic-strain-partitioning.md`
- `docs/mathematics/algorithms/interface-construction.md`
- `docs/mathematics/algorithms/interfacial-energy-evaluation.md`
- `docs/mathematics/algorithms/persistence-report-projection.md`

## Traceability table

| Workflow stage | Ontology role | Mathematical operation | Implementation owner(s) | Specification status | Verification status | Remaining audit target |
| --- | --- | --- | --- | --- | --- | --- |
| Crystal -> Surface | Scientific morphism | Miller-index orientation; integer kernel basis; motif-compatible in-plane primitive cell. | `calm.slab.ops.oriented_slab`, `calm.slab.surface_primitive` | Covered by motif-compatible primitive-cell specification; full oriented-slab morphism still needs a dedicated page. | Strong local tests for Miller transforms, Bezout properties, motif preservation, and surface-basis validation. | Audit bounded primitive-vector search completeness and document fallback/heuristic contract. |
| Surface -> Slab | Scientific morphism plus representation gauge choices | Layer stacking, out-of-plane basis selection, optional tilt/vacuum treatment, atom wrapping, transform provenance. | `calm.slab.ops.oriented_slab`, `calm.slab.slab`, transform sidecars. | Partially covered by primitive-cell and foundations pages. | Good distributed tests, but not yet one canonical slab-construction traceability test. | Write oriented-slab construction specification and define slab invariant checklist. |
| Slab pair -> Interface Candidate | Scientific search morphism | HNF supercell enumeration, reduced 2D gauges, area-band admissibility, affine-invariant strain diagnostics, representative selection. | `calm.interface.matching`, `calm.interface.types`, `calm.interface.prototypes`, `calm.interface.prototype_grouping`. | Covered by surface-cell matching and deduplication specifications. | Good matching and candidate projection guardrails. | Add explicit trace test connecting selected candidate fields to match/prototype provenance. |
| Interface Candidate -> Strain State | Scientific/representation support morphism | SPD(2) geodesic target metric and deformation-gradient construction. | `calm.interface.strain`, `calm.interface.strain_partition`. | Covered by geodesic strain-partitioning specification. | Endpoint convention tests and strain metric tests exist. | Add scan-grid/tie-stability tests where finite-grid selection is exposed. |
| Candidate + Strain + Registry -> Built Interface Structure | Scientific build morphism with representation adapters | Common-cell assembly, rotations, deformation gradients, registry translation, z-placement, periodic wrapping, provenance projection. | `calm.interface.pipeline.build_interface`, `calm.interface._build_kernel`, `InterfaceBuildConfig`. | Covered by interface-construction specification. | Moderate-good build-kernel and workflow tests. | Add built-interface invariant tests for common cell, layer partition, registry translation, and provenance continuity. |
| Built Interface Structure -> Evaluation Result | Scientific evaluation morphism | Strained-bulk reference subtraction, formula-unit normalization, area denominator convention, scalar gamma reduction. | `calm.interface._energy_kernel`, `calm.interface.interface_energy`, `calm.interface.pipeline.compute_interfacial_energy`. | Covered by interfacial-energy evaluation specification. | Good scalar and public API tests. | Add explicit single-sided vs double-sided denominator tests if not already asserted at public boundary. |
| Evaluation Result -> Dataset | Representation morphism | Durable rows, public sidecars, manifests, identity/provenance field projection. | `calm.project.application.*`, `calm.project.infrastructure.db.*`, `calm.public.*`. | Covered by persistence/report projection specification. | Good persistence/projection and candidate identity guardrails. | Add full UID continuity test from candidate/prototype through result, sidecar, manifest, and public row. |
| Dataset -> Report | Representation morphism | Table/report projection, lossy public views, ranking/filtering. | `calm.public.*`, `calm.reporting`, workspace/report facades. | Covered by persistence/report projection specification. | Moderate public/report contract tests. | Add report-level trace test that verifies projected columns preserve declared identity/provenance semantics. |

## Composition validity assessment

The current workflow appears mathematically coherent as a composition under the assumptions already recorded in the algorithm specifications:

1. Surface and slab construction depend on nondegenerate lattice inputs, valid Miller indices, and optional symmetry-detection quality.
2. Interface matching is complete only within the explicit search bounds, gauge choices, conditioning threshold, and deduplication policy.
3. Strain partitioning uses the affine-invariant SPD(2) geodesic convention with corrected endpoint semantics.
4. Registry alignment is stochastic optimization, not a proof of global optimality.
5. Interface construction is deterministic geometry assembly once the prototype, strain state, registry translation, z-padding, and build configuration are fixed.
6. Energy evaluation is valid under the documented strained-bulk reference and denominator convention.
7. Persistence, dataset, and report operations are representation morphisms that may be lossy but must preserve declared identity and provenance fields.

The main current limitation is not a known mathematical contradiction. It is that several guarantees remain local. The repository has strong tests for individual stages, but fewer tests that assert identity, provenance, metric, and energy invariants across the whole workflow.

## End-to-end invariants

A future verification-hardening update should express the following invariants as tests wherever dependency-light fixtures permit.

### Identity and provenance continuity

Candidate display identifiers, candidate UIDs, prototype UIDs, strain-state specifications, build configuration choices, registry decisions, energy-result identifiers, dataset rows, manifests, and report projections must not be conflated. Lossy report rows may omit fields, but any field they do expose must retain its declared meaning.

### Metric and strain continuity

The target in-plane metric used to build a strained interface must correspond to the recorded strain state. The `alpha=0` and `alpha=1` endpoints must continue to match the documented convention:

```text
alpha=0 -> slab A target metric; A unstrained, B strained to A
alpha=1 -> slab B target metric; B unstrained, A strained to B
```

### Cell and atom-placement continuity

The built interface cell must represent the common in-plane cell selected by the candidate and strain state. Registry translations and z-padding are build choices, not new match or strain computations. Atom wrapping and representation adapters must not change the scientific identity of the selected candidate.

### Energy provenance continuity

Interfacial-energy records must distinguish raw interface total energy, strained-bulk reference energies, the interface excess-energy numerator, the denominator convention, and the area-normalized scalar value. A report projection may expose only a subset, but it must not rename or conflate these quantities.

### Representation-loss accounting

Database rows, public sidecar rows, manifests, CSV-like tables, and reports are not complete scientific objects. They are projections. Their correctness depends on preserving the stated subset of identity, provenance, units, and convention fields.

## Verification priorities

The following near-term tests would most directly strengthen workflow-level conformance.

| Priority | Verification target | Rationale |
| --- | --- | --- |
| High | UID/provenance continuity from candidate to dataset/report projection. | Protects the most important representation-morphism boundary. |
| High | Built-interface invariant fixture checking common cell, layer ownership, registry translation, z-padding, and transform provenance. | Connects the interface-construction specification to executable checks. |
| Medium-high | End-to-end strained-energy fixture checking scalar gamma inputs, denominator convention, and public projection fields. | Connects evaluation mathematics to reporting semantics. |
| Medium | Slab construction traceability fixture connecting Miller basis, transform sidecar, and generated slab cell. | Closes the Surface -> Slab gap. |
| Medium | Finite-grid strain-partition selection/tie-stability fixture. | Clarifies finite scan semantics distinct from continuous optimization. |

## Documentation priorities after this page

This page closes the first end-to-end map, but it also identifies two important remaining mathematical documents:

1. **Oriented slab construction specification**: the full Surface -> Slab morphism, including layer stacking, gauge reduction, atom wrapping, optional vacuum, and transform provenance.
2. **Primitive surface-cell completeness audit**: a focused audit of exact integer-kernel/HNF operations versus bounded primitive-basis vector search.

Those two documents should be prioritized before closing the Mathematical and Algorithmic Specification milestone.
