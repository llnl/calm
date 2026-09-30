# Relax and evaluate

<p class="calm-lede">
Relax selected interfaces, inspect convergence, calculate raw total energies, and derive interfacial quantities only under an explicit and complete reference convention.
</p>

## Outcome

The project contains saved relaxation results, raw interface energies, reference energies when required, and optional derived quantities with explicit normalization and reference meaning.

## When to use it

Use this workflow when geometric construction and refinement are complete and the scientific question requires calculator-backed structural or energetic information.

Relaxation is optional when CALM is used only to construct structures for another simulation system. Energy derivation is optional when raw structures or raw total energies are the desired outputs.

## Prerequisites

A calculator provider and scientifically suitable model must be available. Configure the project or pass a calculator backend explicitly.

```python
from calm import Potential

potential = Potential(family="ase", model="EMT")
potential.validate()
project.configure(calculator=potential)
```

The EMT example demonstrates workflow mechanics only. Use a model validated for the elements, bonding environments, magnetic state, charge state, and accuracy required by the study.

Start from saved interfaces at an explicit stage such as `strain_partitioned` or `registry_refined`.

## Scientific decisions

### Select relaxation constraints

`RelaxSettings` controls the force threshold, maximum steps, and whether the cell can relax. A fixed-cell relaxation preserves the coherent periodic cell established by the matching workflow. Cell relaxation changes the model and may invalidate a reference process that assumes the original coherent cell.

### Distinguish convergence from stability

A completed optimizer run indicates that its stopping rule was satisfied. It does not prove that the structure is the global minimum or the experimentally realized interface.

### Separate raw energies from derived quantities

A raw total energy belongs to one structure and calculator setup. An interface energy or work of adhesion additionally requires:

- a formula;
- compatible reference states;
- an interface area;
- the number of interfaces represented by the periodic cell; and
- consistent calculator and relaxation protocols.

CALM does not infer these scientific choices.

## Minimal procedure

### Relax selected interfaces

```python
from calm import RelaxSettings

relaxation = project.relax_interfaces(
    search_name="cu-ni-100-emt",
    settings=RelaxSettings(
        fmax=0.08,
        steps=150,
        relax_cell=False,
    ),
    backend="real",
    stage="registry_refined",
    resume=True,
    partial_resume=True,
    on_error="raise",
)

print(relaxation.summary())
relaxation.write_table("exports/relaxation-results.csv")
```

`resume=True` reuses completed compatible work. `partial_resume=True` permits a multi-target run to continue incomplete targets while retaining completed results.

### Declare and calculate references

```python
from calm import EnergyConvention, EnergySettings, RelaxSettings

convention = EnergyConvention(
    formula="work_of_adhesion_relaxed_surfaces",
    n_interfaces=2,
)

references = project.evaluate_reference_energies(
    convention=convention,
    search_name="cu-ni-100-emt",
    settings=EnergySettings(mode="single_point"),
    surface_relaxation=RelaxSettings(
        fmax=0.08,
        steps=150,
        relax_cell=False,
    ),
    backend="real",
    on_error="raise",
)
```

This convention uses independently relaxed fixed-cell surface references. Inspect `convention.reference_capability()` before requesting calculated references for another formula.

### Calculate raw and derived results

```python
energies = project.evaluate_energies(
    search_name="cu-ni-100-emt",
    settings=EnergySettings(mode="single_point"),
    backend="real",
    convention=convention,
    references=references,
    on_error="raise",
)

energies.write_table("exports/raw-energies.csv", kind="raw")
energies.write_table(
    "exports/work-of-adhesion.csv",
    kind="thermodynamic",
)
```

Omit `convention` and `references` when only raw energies are required.

## Inspect the result

Check workflow status before using values:

```python
print(relaxation.ok)
print(relaxation.failures)
print(energies.ok)
print(energies.failures)
```

Query saved results:

```python
project.relaxation_results(status="completed").to_table().display()
project.energy_results(status="completed").to_table().display()
project.thermodynamic_results(status="completed").to_table().display()
```

Important relaxation fields include final force, step count, status, target interface, and backend identity. Important thermodynamic fields include:

- quantity and units;
- value in eV/Å² and J/m² where provided;
- normalization area;
- `n_interfaces`; and
- completion status.

Retrieve one exact result by its identifier when writing analysis code:

```python
result = project.thermodynamic_result("<result short ID>")
print(result.value_J_per_m2)
```

## Interpretation

A relaxed interface is a local result under one starting structure, calculator, optimizer, constraint set, and convergence threshold.

A raw total energy can be compared only when the calculator identity, composition, boundary conditions, and scientific protocol make the comparison meaningful.

A derived interfacial quantity has the meaning of its declared reference cycle. For example, `work_of_adhesion_relaxed_surfaces` compares the interface with independently relaxed fixed-cell surface blocks and normalizes by the selected area and interface multiplicity. Changing any of those choices changes the quantity.

## Common variations

### Evaluate raw energies only

```python
raw = project.evaluate_energies(
    search_name="cu-ni-100-emt",
    settings=EnergySettings(mode="single_point"),
    backend="real",
)
raw.write_table("exports/raw-energies.csv", kind="raw")
```

### Supply manual references

Use `ReferenceEnergySettings` only when the reference values, counts, and units are known and compatible with the interface calculation. Record their source in metadata.

### Relax strain-partitioned interfaces directly

```python
project.relax_interfaces(
    search_name="cu-ni-100-emt",
    stage="strain_partitioned",
    settings=RelaxSettings(fmax=0.05, steps=300, relax_cell=False),
)
```

This bypasses registry refinement intentionally; it should not happen accidentally because a registry-refined collection was empty.

### Inspect previous runs

```python
project.relaxation_runs().to_table().display()
project.reference_energy_runs().to_table().display()
project.energy_runs().to_table().display()
project.thermodynamic_runs().to_table().display()
```

## Common problems

### The calculator is unavailable or incompatible

Confirm provider installation, model name, supported elements, device configuration, and calculator construction. Availability is a technical prerequisite, not scientific validation.

### Relaxation does not converge

Inspect the starting geometry, overlaps, force history, constraints, maximum steps, and calculator behavior. Increasing `steps` without diagnosing the model is not a sufficient remedy.

### A derived quantity is unavailable

Inspect the convention capability and result explanation. Missing, failed, or incompatible references should produce an unavailable result rather than a silently combined number.

### Reference and interface calculations use different protocols

Recalculate a consistent set. Calculator identity, cell constraints, and reference meaning must match the declared convention.

### A value has an unexpected sign or magnitude

Check the formula, reference states, area, interface multiplicity, units, terminations, strain, registry, and relaxation status before interpreting it physically.

## Exact API

- [`RelaxSettings`, `EnergySettings`, `EnergyConvention`, and `ReferenceEnergySettings`](../reference/api/inputs-settings.md)
- [`Project.relax_interfaces`, reference-energy, raw-energy, and thermodynamic operations](../reference/api/project.md)
- [Relaxation and energy workflow results](../reference/api/returned-objects.md)
- [Energy and reference interpretation](../understand/energetics.md)
