# Materials

<p class="calm-lede">
Add bulk structures to a project, distinguish imported and optimized states, inspect crystallographic metadata, associate calculators when needed, and export structures through the public API.
</p>

## Outcome

A material is the bulk structural input from which CALM generates surfaces. By the end of this chapter, the project contains clearly named material states that can be queried, characterized, optimized when appropriate, and exported through supported project operations.

## When to use it

Use this workflow when:

- beginning a study from an ASE `Atoms` object or a structure file;
- preserving both an imported reference structure and a calculator-optimized state;
- checking composition, periodicity, cell, or crystallographic characterization before surface generation; or
- exporting a saved bulk structure for another tool.

## Prerequisites

Geometry-only material input requires ASE. Calculator-backed optimization additionally requires a registered calculator provider and a scientifically suitable model.

Package-owned tutorial structures can be loaded directly:

```python
from calm import Material, open_project, tutorial_structure

project = open_project("material-study.calm")
cu = Material.from_ase(tutorial_structure("cu"), name="Cu-reference")
project.add_material(cu)
```

For a user file:

```python
from calm import Material

material = Material.from_file("POSCAR", name="sample-reference")
```

## Scientific decisions

### Decide which structural state is the input

CALM does not decide whether an experimental structure, a repository structure, or a calculator-relaxed structure is appropriate. Preserve distinctions in the names and metadata rather than replacing one state silently.

A useful pattern is:

```text
Cu-reference
Cu-EMT-optimized
Cu-production-model-optimized
```

### Verify periodicity and cell meaning

Bulk inputs should represent the periodic structure intended for surface generation. Check that:

- all three bulk directions are periodic;
- cell vectors and atomic positions use consistent units;
- occupancy or disorder has already been represented explicitly; and
- the cell is appropriate for the surface orientations to be explored.

### Choose calculators scientifically

A calculator being loadable does not make it valid for the material. Before optimization, establish that the model supports the chemical elements and relevant configurations and that its accuracy is adequate for the intended question.

## Minimal procedure

### Add an existing structure

```python
from calm import Material, open_project, tutorial_structure

project = open_project("material-study.calm")
material = Material.from_ase(
    tutorial_structure("ni"),
    name="Ni-reference",
    metadata={"role": "tutorial bulk reference"},
)
saved = project.add_material(material)
print(saved.summary())
```

`add_material()` returns the saved public material. Adding a scientifically distinct state should use a distinct name.

### Inspect saved materials

```python
materials = project.materials()
materials.to_table(title="Project materials").display()
materials.to_table(view="characterization").display()

ni = project.material("Ni-reference")
print(ni.characterize().summary())
```

Characterization provides structural descriptors for inspection and comparison. It does not certify that the structure is the correct phase under the conditions of interest.

### Optimize a material

```python
from calm import Potential

potential = Potential(family="ase", model="EMT")
potential.validate()

optimized = project.optimize_material(
    "Ni-reference",
    potential=potential,
    fmax=0.05,
    steps=300,
    relax_cell=True,
    name="Ni-EMT-optimized",
)
print(optimized.summary())
```

`relax_cell=True` permits the bulk cell to change. Set it to `False` when the scientific protocol requires a fixed cell.

## Inspect the result

Filter by material role or state:

```python
optimized = project.materials().where(kind="optimized")
optimized.to_table(view="characterization").display()
```

Recover ASE objects only through the public conversion:

```python
atoms = project.material("Ni-EMT-optimized").to_ase()
print(atoms.get_chemical_formula())
print(atoms.cell)
print(atoms.pbc)
```

Export named states:

```python
written = project.export_materials(
    "Ni-reference",
    "Ni-EMT-optimized",
    directory="exports/materials",
    format="vasp",
)
for path in written:
    print(path)
```

## Interpretation

A saved material identifies a particular bulk structure and its role in the project. An optimized state records the result of a declared calculator and optimization protocol; it is not automatically a thermodynamic ground state.

Surface generation inherits the material's cell, positions, composition, and structural state. A material mistake therefore propagates into every downstream surface, search, interface, and energy result.

## Common variations

### Add several structures from ASE

```python
for name in ("lif", "li2o"):
    project.add_material(
        Material.from_ase(tutorial_structure(name), name=name.upper())
    )
```

### Export directly from a standalone material

```python
material = Material.from_file("input.cif", name="input")
material.to_file("input-normalized.vasp", format="vasp")
```

Use the project export helper once the material is saved so the exported structure is tied to the study state.

### Use project calculator defaults

```python
project.configure(calculator=potential)
project.optimize_material(
    "Ni-reference",
    fmax=0.05,
    relax_cell=True,
    name="Ni-default-optimized",
)
```

Explicit calculator arguments are clearer when comparing models in one project.

## Common problems

### The structure cannot be loaded

Check the file format, ASE support, cell, positions, chemical symbols, and periodic boundary flags. Convert or repair the structure before adding it to CALM rather than editing saved project data.

### Optimization fails immediately

Confirm that the provider is installed, the model supports every element, and the source material can be converted to ASE `Atoms`. Inspect the calculator error rather than treating a failed optimization as a material result.

### Two materials have confusingly similar names

Use descriptive state names and inspect `id_short` in the material table. Exact identifiers are preferable when a name is ambiguous.

### An optimized cell is physically unreasonable

Stop the workflow. Review calculator suitability, units, optimizer settings, cell constraints, and the starting structure before generating surfaces.

## Exact API

- [`Material`, `Potential`, and calculator inputs](../reference/api/inputs-settings.md)
- [`Project.add_material`, `material`, `materials`, `optimize_material`, and exports](../reference/api/project.md)
- [Returned material collections](../reference/api/returned-objects.md)
