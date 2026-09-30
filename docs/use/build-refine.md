# Build and refine interfaces

<p class="calm-lede">
Construct atomistic interfaces from selected coherent candidates, control gap, vacuum, strain allocation, and in-plane registry, and preserve each derived structure for inspection and downstream calculations.
</p>

## Outcome

The project contains one or more built interfaces and, when a calculator is available, optional strain-partitioned and registry-refined descendants. Each stage remains inspectable, exportable, and traceable to the candidate and settings that produced it.

## When to use it

Use construction after a candidate shortlist has been selected. Use refinement when:

- the two materials should not share coherent deformation equally;
- several strain allocations must be compared under one calculator;
- the initial in-plane registry is arbitrary; or
- downstream relaxation should start from a calculator-screened geometry.

Construction is calculator-free. Energy-based strain and registry refinement require a configured calculator.

## Prerequisites

Retrieve a saved search and verify that it can be built:

```python
search = project.search("lif-li2o-100")
readiness = search.buildability_summary()
readiness.raise_for_errors()
```

Select one or more candidates deliberately. `build_interfaces(..., top=n)` uses the saved Pareto classification and public score to choose up to `n` candidates; for tighter control, filter the candidate collection before construction.

## Scientific decisions

### Allocate coherent strain

`BuildSettings.strain_partition` accepts:

- `"a"`: place the coherent deformation on side A;
- `"b"`: place it on side B; or
- `"both"`: interpolate between the two sides using `alpha`.

For `strain_partition="both"`, `alpha=0` leaves side A unstrained, `alpha=1` leaves side B unstrained, and `alpha=0.5` selects the geometric midpoint.

### Choose the initial gap

`gap` is the initial separation between the selected contact faces. Too small a gap can create severe overlap; too large a gap can start the model outside the attractive region of the calculator. CALM does not infer an equilibrium separation during construction.

### Choose boundary vacuum

`vacuum` separates periodic images along the interface normal. Adequacy depends on slab thickness, calculator range, electrostatics, and the later reference calculation.

### Choose or refine registry

`translation=(u, v)` is a fractional in-plane shift of side B in the matched interface lattice. Values are periodic. The unshifted registry is a convention, not a physical optimum.

## Minimal procedure

### Build several candidates

```python
from calm import BuildSettings

interfaces = project.build_interfaces(
    "lif-li2o-100",
    top=3,
    settings=BuildSettings(
        strain_partition="both",
        alpha=0.5,
        gap=1.5,
        vacuum=15.0,
        translation=(0.0, 0.0),
    ),
    name_prefix="lif-li2o-interface",
)
```

The returned `InterfaceCollection` contains in-memory atomistic models for immediate inspection and export. Saved identity and workflow stage are obtained through `project.interface()` or `project.interfaces()`.

### Scan strain allocation and registry

```python
from calm import RegistrySettings, StrainPartitionSettings

refinement = project.refine_interfaces(
    "lif-li2o-100",
    top=3,
    pareto=True,
    strain_settings=StrainPartitionSettings(
        target_metric="potential_energy_density_eV_per_A2",
        alphas=(0.0, 0.25, 0.5, 0.75, 1.0),
    ),
    registry_settings=RegistrySettings(
        steps=64,
        translation_step=0.08,
        seed=2026,
    ),
    label_prefix="lif-li2o-refined",
    on_error="raise",
)
```

The supported strain objectives are:

- `gamma_eV_per_A2`; and
- `potential_energy_density_eV_per_A2`.

The chosen metric determines which sampled `alpha` is selected. Registry refinement then holds that strain allocation, gap, and vacuum fixed while exploring periodic in-plane translations.

## Inspect the result

```python
print(refinement.summary())
refinement.write_outputs(
    "exports/refinement",
    filename_prefix="lif-li2o-",
    plots=("potential_energy_density_eV_per_A2",),
)
```

Query saved stages directly:

```python
built = project.interfaces().stage("built")
strain_refined = project.refined_interfaces(stage="strain_partitioned")
registry_refined = project.refined_interfaces(stage="registry_refined")

registry_refined.to_table().display()
registry_refined.write_structures(
    "exports/registry-refined",
    format="vasp",
)
```

Inspect a temporary registry-shift variant without saving it:

```python
atoms = project.interface_atoms(
    "lif-li2o-interface_0000",
    registry_shift=(0.25, 0.50),
)
```

Use this for visualization or diagnostics, not as an untracked substitute for the saved refinement workflow.

## Interpretation

Construction turns a lattice candidate into a finite atomistic model with explicit contact faces, coherent deformation, gap, vacuum, and registry.

Strain refinement compares only the sampled allocations under the selected calculator-backed objective. Registry refinement compares only the explored translations under its fixed protocol. A selected point is the best among evaluated choices, not proof of a global minimum.

The `built`, `strain_partitioned`, and `registry_refined` stages communicate workflow history. They do not imply structural relaxation or thermodynamic stability.

## Common variations

### Stop after strain partitioning

Omit `registry_settings`:

```python
refinement = project.refine_interfaces(
    "lif-li2o-100",
    top=3,
    strain_settings=StrainPartitionSettings(
        target_metric="potential_energy_density_eV_per_A2",
        alphas=(0.0, 0.5, 1.0),
    ),
)
```

### Refine registry for an existing strain-partitioned collection

```python
strain_refined = project.refined_interfaces(stage="strain_partitioned")
registry = project.refine_registry(
    strain_refined,
    settings=RegistrySettings(steps=100, seed=2026),
    label_prefix="registry-screen",
)
```

### Build a specific candidate set

Filter the search candidate collection first, then supply the supported selection to the build workflow. Preserve a table of the selected candidate identifiers with the exported structures.

### Plot saved scans

```python
project.plot_strain_partition_scan(
    "<strain run ID>",
    filename="exports/strain-partition.png",
)
project.plot_registry_search(
    "<registry run ID>",
    filename="exports/registry-search.png",
)
```

## Common problems

### Atoms overlap after construction

Review the contact faces, `gap`, surface thicknesses, and registry. Do not expect relaxation to rescue a severely unphysical starting model.

### Refinement reports no eligible interfaces

Confirm that built interfaces exist for the named search and that the requested `top` and Pareto filters select them.

### Registry refinement is irreproducible

Set an explicit nonnegative seed and preserve all registry settings. An omitted seed is deterministically derived from saved identities, but an explicit seed is clearer when comparing protocols.

### The refinement metric is unavailable

Confirm that the calculator is configured and supports every element and structure. Use the exact supported metric name including units.

## Exact API

- [`BuildSettings`, `StrainPartitionSettings`, and `RegistrySettings`](../reference/api/inputs-settings.md)
- [`Project.build_interfaces`, `refine_interfaces`, `refine_registry`, and interface queries](../reference/api/project.md)
- [Interface collections and composite refinement results](../reference/api/returned-objects.md)
- [Strain allocation and registry interpretation](../understand/strain-registry.md)
