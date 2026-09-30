# Surfaces and terminations

<p class="calm-lede">
Generate finite surface slabs from saved bulk materials, inspect the alternatives, and select the exact contact-facing terminations used by an interface model.
</p>

## Outcome

The project contains explicit oriented surface models selected by material, Miller index, and termination. Downstream searches can therefore refer to the intended contact faces without relying on list order or an implicit “best” termination.

## When to use it

Use this workflow after the required bulk material states are saved and before an interface search. Return to it when changing:

- surface orientation;
- slab thickness or layer count;
- vacuum thickness;
- top or bottom termination; or
- the material state from which the surface is generated.

These changes define a different physical model and should not be hidden inside search tuning.

## Prerequisites

The parent material must have a valid periodic bulk structure.

```python
from calm import open_project

project = open_project("interface-study.calm")
print(project.material("LiF").summary())
```

Choose either an exact layer count or a target physical thickness where the surface backend requires one size mode. Vacuum is measured in ångström.

## Scientific decisions

### Choose the orientation

Miller indices define the bulk plane normal used to construct a surface model. CALM can enumerate and save models for several orientations, but it does not determine which orientation is experimentally exposed or stable.

### Choose a finite slab

The slab must be thick enough that the interior represents the intended bulk-like environment for the downstream calculation. More layers generally increase cost and may change available terminations.

Vacuum separates periodic slab images normal to the surface. Its adequacy depends on the calculator and the quantity being evaluated.

### Choose the contact face explicitly

A finite slab has ordered top and bottom faces. In the normal interface assembly convention, side A contributes its top face and side B contributes its bottom face. The contacting chemistry therefore depends on both the selected surface and which side of the interface it occupies.

CALM enumerates distinct terminations when requested. CALM does not infer the physically correct termination from stoichiometry, atom count, or sort order.

## Minimal procedure

### Generate surfaces

```python
from calm import open_project

project = open_project("interface-study.calm")
project.generate_surfaces(
    ["LiF", "Li2O"],
    millers=[(1, 0, 0), (1, 1, 0)],
    layers=4,
    vacuum=15.0,
    enumerate_terminations=True,
)
```

The call saves every generated surface in deterministic material, orientation, and termination order. Treat that order as presentation, not as a scientific ranking.

### Inspect the alternatives

```python
surfaces = project.surfaces()
surfaces.to_table(view="characterization").display()
```

Filter before selecting:

```python
li2o_100 = project.surfaces(material="Li2O", miller=(1, 0, 0))
li2o_100.to_table().display()
```

### Select exact contact faces

```python
surface_a = project.surface(
    material="LiF",
    miller=(1, 0, 0),
    termination="LiF",
    termination_shift=0,
)

surface_b = project.surface(
    material="Li2O",
    miller=(1, 0, 0),
    termination_bottom="O",
    termination_shift=1,
)
```

The second selection states that the bottom face of the Li₂O slab—the face used on side B—is O terminated.

## Inspect the result

A selected surface exposes user-relevant geometry and characterization:

```python
print(surface_a.summary())
print(surface_a.characterize().summary())

atoms = surface_a.to_ase()
print(atoms.cell)
print(atoms.pbc)
```

Export selected surfaces through the project:

```python
project.export_surfaces(
    surface_a.id_short,
    surface_b.id_short,
    directory="exports/surfaces",
    format="vasp",
)
```

For a broad export by criteria:

```python
project.export_surfaces(
    materials=["LiF", "Li2O"],
    millers=[(1, 0, 0)],
    directory="exports/surfaces-100",
)
```

## Interpretation

A saved surface is a finite periodic slab derived from one saved bulk state under explicit orientation, size, vacuum, and termination choices. It is an input model, not a prediction of the equilibrium surface.

Changing the contact termination changes the interface chemistry even when the Miller indices and coherent matching settings remain identical. Search results from different terminations should therefore be treated as different scientific cases.

## Common variations

### Generate by physical thickness

```python
project.generate_surfaces(
    "LiF",
    millers=[(1, 1, 1)],
    thickness=18.0,
    vacuum=20.0,
)
```

Do not supply both `layers` and `thickness` when the construction mode treats them as mutually exclusive.

### Generate only one canonical termination

```python
project.generate_surfaces(
    "LiF",
    millers=[(1, 0, 0)],
    layers=6,
    vacuum=15.0,
    enumerate_terminations=False,
)
```

Use this only when the reduced termination policy is scientifically intentional. It is not a replacement for considering chemically distinct faces.

### Select by stable identifier

```python
surface = project.surface("s_<short identifier>")
```

Identifiers are useful after inspecting the surface table and are safer than repeating a long filter in a later script.

## Common problems

### More terminations were generated than expected

Inspect `termination_top`, `termination_bottom`, and `termination_shift`. Different cleavage shifts can produce distinct ordered faces even when the orientation is the same.

### A surface query is ambiguous

Add the exact material, Miller index, termination labels, and shift, or select the short identifier from the table. CALM will not select a face implicitly.

### The slab is empty or has incompatible periodicity

Review the parent bulk, Miller index, thickness or layer count, and surface-generation diagnostics. Do not proceed to matching with an invalid slab.

### The chosen contact face is reversed

Remember the assembly convention: side A uses its top face and side B uses its bottom face. Swap the surfaces or select the opposite ordered termination deliberately.

## Exact API

- [`Project.generate_surfaces`, `surfaces`, `surface`, and `export_surfaces`](../reference/api/project.md)
- [Generated surfaces and surface collections](../reference/api/returned-objects.md)
- [Surface-model interpretation](../understand/surface-models.md)
- [Surface cells and supercells](../understand/surface-supercells.md)
