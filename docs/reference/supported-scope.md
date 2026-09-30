# Supported scientific scope

<p class="calm-lede">
Understand what CALM constructs, evaluates, and records—and which scientific conclusions remain the user's responsibility.
</p>

## Purpose

CALM is a workflow tool for constructing periodic coherent solid–solid interface models and preserving the evidence needed to inspect, continue, and compare those workflows. It does not turn a geometrically valid model or a completed calculator run into a general prediction of interface stability.

## Canonical import or convention

Interpret every CALM result according to the stage that produced it:

| Stage | CALM establishes | CALM does not establish |
| --- | --- | --- |
| Surface generation | One or more ideal bulk-derived finite slab models | The equilibrium facet, reconstruction, polarity compensation, or physically preferred termination |
| Coherent search | Feasible bounded common-cell candidates under explicit limits | Experimental occurrence, dislocation structure, kinetic accessibility, or thermodynamic preference |
| Interface construction | One atomistic coherent model with explicit contact faces, strain allocation, registry, gap, and boundary settings | A relaxed structure or stable interface |
| Refinement | A selected state from a declared finite strain or registry exploration | A global optimum outside the sampled domain |
| Relaxation | A local optimizer result and convergence evidence under one calculator and protocol | The global minimum or experimental stability |
| Raw energy | A calculator total energy for one exact structure and calculator identity | An interface excess energy by itself |
| Derived quantity | A value under one explicit reference convention, area, and interface multiplicity | Convention-independent thermodynamic truth |
| Dataset or campaign | A reproducible declaration, membership, split, execution, and comparison record | Statistical validity outside the declared population and assumptions |

## Exact behavior

### Supported core workflow

CALM supports the following public workflow stages:

1. import periodic bulk structures as materials;
2. optionally optimize materials with a registered calculator provider;
3. construct ideal bulk-derived surfaces for explicit Miller orientations;
4. enumerate and select ordered surface terminations;
5. search a finite, declared domain of coherent surface-supercell matches;
6. inspect mismatch, size, buildability, and Pareto tradeoffs;
7. build atomistic coherent interfaces;
8. assign coherent strain between the two sides;
9. explore periodic in-plane registry;
10. run calculator-backed local structural relaxation;
11. evaluate raw total energies and supported reference calculations;
12. derive supported interfacial quantities under an explicit convention;
13. assemble validated datasets and execute declared campaigns; and
14. preserve names, identifiers, lineage, artifacts, and reproducibility evidence in a project.

### Geometric model assumptions

The core interface model assumes:

- two selected periodic surface slabs;
- one common periodic in-plane cell;
- coherent deformation of both sides into that cell;
- finite slab thickness;
- explicit ordered contact faces;
- a finite gap, registry, and boundary construction; and
- no misfit dislocations inside the chosen periodic cell.

The search is complete only relative to its declared finite bounds. Increasing a supercell, strain, area, atom-count, or candidate limit changes the admitted problem.

### Surface limitations

CALM does not currently infer or model, unless the user supplies them explicitly as atomistic inputs:

- equilibrium surface populations;
- reconstructions requiring larger or different surface cells;
- adsorbates;
- vacancies or antisites;
- segregation;
- charge compensation;
- oxidation states;
- electrostatic polarity corrections; or
- chemical-potential phase diagrams.

CALM does not infer the physically correct termination. A Miller orientation and a valid finite slab are not enough to determine the physically relevant termination.

### Coherency limitations

CALM's periodic coherent models do not directly represent:

- semicoherent or incoherent interfaces containing misfit dislocations;
- long-range moiré structures outside the selected cell;
- crack fronts, steps, ledges, or finite lateral boundaries;
- kinetic interface formation pathways; or
- mesoscale defect networks.

A low-strain coherent candidate may still be physically inappropriate because the real system relieves mismatch through mechanisms excluded from the model.

### Calculator and relaxation limitations

A registered provider means CALM knows how to construct an ASE-compatible calculator from a typed specification. It does not mean:

- the dependency is installed;
- the requested model is available;
- the model supports every element or configuration;
- stresses or cell relaxation are reliable;
- the model is accurate for surfaces and interfaces; or
- the model is scientifically validated for the user's material pair.

Relaxation is a local numerical optimization. A converged run can remain trapped in a metastable structure or constrained by the finite periodic cell, fixed composition, selected registry, and chosen relaxation degrees of freedom.

### Supported energy-reference workflows

The current public formulas are:

| Formula | Derived quantity | Calculated references | Important boundary |
| --- | --- | --- | --- |
| `interface_excess_strained_bulk` | Interface excess energy | Strained bulk A and B | Requires exact integer formula-unit accounting; non-stoichiometric reservoir conventions are unsupported |
| `work_of_separation_unrelaxed_surfaces` | Work of separation | Isolated unrelaxed surface A and B | Represents mechanical cleavage to the corresponding unrelaxed fixed-cell surfaces |
| `work_of_adhesion_relaxed_surfaces` | Work of adhesion | Independently relaxed fixed-cell surface A and B | Requires a fixed-cell relaxed interface and one calculator identity shared by interface and references |

Inspect support at runtime before creating reference calculations:

```python
from calm import EnergyConvention

convention = EnergyConvention(
    formula="work_of_adhesion_relaxed_surfaces",
    n_interfaces=1,
)
capability = convention.reference_capability()
print(capability.summary())
capability.raise_for_calculated_references()
```

All three current formulas provide a first-class calculated-reference path. Explicit manual references remain available through `ReferenceEnergySettings` when their meaning and provenance are independently defensible.

For relaxed-surface adhesion:

- the interface must be calculator-relaxed with a fixed cell;
- each cleaved slab block is relaxed independently at fixed cell;
- the interface and references must use the same calculator identity; and
- the surface relaxations remain local optimizations, not guarantees of globally stable surfaces.

Variable-cell relaxed interfaces are outside the current relaxed-surface reference workflow.

### Data and orchestration limitations

Dataset validation checks the declared schema, membership, values, grouping, splits, required structures, and provenance relationships. It does not prove that the chosen features, targets, population, or split strategy answer the intended scientific question.

Campaign execution records exact case settings and failures. A comparison table is scientifically meaningful only when cases report compatible quantities under compatible conventions.

### Execution and portability boundary

CALM executes synchronously in the calling Python process. It does not provide a task queue, distributed scheduler, or background worker. Batch systems may invoke CALM scripts, but coordination of jobs, external potential files, model downloads, accelerator drivers, and licensed resources remains external.

Projects are reopenable within the current supported project format. For an older or incompatible project, preserve the original directory, create a new project, and rerun supported workflows from retained scientific inputs and exports. Do not edit project files to simulate a migration.

## Related workflow

- [Build your first interface](../learn/first-interface.md) demonstrates the calculator-free supported core.
- [Surfaces and terminations](../use/surfaces.md) explains explicit contact-face selection.
- [Searches and candidates](../use/searches.md) explains finite search completeness and Pareto interpretation.
- [Relax and evaluate](../use/relax-evaluate.md) explains calculator and reference requirements.
- [Calculator support](calculator-support.md) distinguishes registration, availability, compatibility, and scientific suitability.
- [Relaxation, energy, and reference conventions](../understand/energetics.md) gives the scientific interpretation of supported formulas.
