# CALM Basic API User Guide

# Chapter 3 — Surface Models

## Scientific Objective

Interfaces are formed between surfaces rather than bulk materials.

In this chapter you will generate crystallographic Surface models from
the persisted Materials imported in the previous chapter.

By the end of this chapter you will be able to:

- generate Surface models from persisted Materials,
- generate multiple Miller orientations,
- enumerate surface terminations,
- retrieve persisted Surfaces,
- query Surfaces,
- inspect Surface properties,
- export Surface models.

These Surface objects become the foundation for interface matching.

---

## Workflow

### Retrieve a Material

Surface generation begins by retrieving a persisted Material from the
Project.

```python
lif = project.materials.get(
    "LiF",
)

li2o = project.materials.get(
    "Li2O",
)
```

No new Materials are created.

Previously imported Materials are retrieved from the Project.

---

### Generate Surface Models

Generate Surface models for several crystallographic orientations.

```python
lif_surfaces = project.surfaces.generate(
    material=lif,
    millers=[
        (1, 0, 0),
        (1, 1, 0),
        (1, 1, 1),
    ],
)

li2o_surfaces = project.surfaces.generate(
    material=li2o,
    millers=[
        (1, 0, 0),
        (1, 1, 0),
    ],
)
```

Every generated Surface is immediately persisted within the Project.

The parent Materials remain unchanged.

---

### Enumerate Surface Terminations

By default, CALM generates every symmetry-unique termination.

```python
lif_surfaces = project.surfaces.generate(
    material=lif,
    millers=[
        (1, 0, 0),
    ],
    enumerate_terminations=True,
)
```

Each termination becomes a separate persisted Surface.

---

### List Surface Models

Retrieve every Surface currently stored in the Project.

```python
surfaces = project.surfaces.list()
```

The returned collection contains every persisted Surface generated
during the investigation.

---

### Retrieve a Surface

Retrieve one persisted Surface.

```python
surface = project.surfaces.get(
    "LiF (100)",
)
```

As with Materials, Surfaces should always be retrieved from the Project
rather than regenerated.

---

### Query Surfaces

Scientific queries allow Surfaces to be located using their scientific
properties.

```python
polar_surfaces = project.surfaces.find(
    material=lif,
    polarity=True,
)

surface_100 = project.surfaces.find(
    material=lif,
    miller=(1, 0, 0),
)
```

Queries return persisted Surface objects.

---

### Inspect Surface Properties

Every Surface exposes the information required for scientific
decision-making.

```python
print(surface.material)

print(surface.miller)

print(surface.termination)

print(surface.surface_area)

print(surface.is_polar)
```

These properties describe the persisted Surface object.

---


### Retrieve Related Matches

Discover matches involving a surface via the Matches collection query API:

```python
matches = project.matches.find(film=surface)
```

This keeps a clear separation between persisted objects and exploratory
search results.

---

### Export a Surface

Export a persisted Surface.

```python
surface.export(
    "LiF_100.vasp",
)
```

or

```python
project.surfaces.export(
    surface,
    "LiF_100.vasp",
)
```

Export never modifies the persisted Surface.

---

## Discussion

Surface generation represents the first derived stage of the scientific
workflow.

Unlike Materials, which originate outside the Project, Surfaces are
derived scientific objects.

The Basic API therefore follows the object lifecycle established in the
previous chapters:

```text
Material
      ↓
Surface
```

The parent Material remains unchanged.

Every generated Surface records:

- its parent Material,
- its Miller orientation,
- its termination,
- the parameters used during generation.

Because Surfaces are persisted within the Project, later workflow stages
retrieve them rather than generating them again.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Surfaces are generated from persisted Materials | ✓ |
| Multiple Miller orientations can be generated in one operation | ✓ |
| Surface terminations can be enumerated | ✓ |
| Generated Surfaces become persisted scientific objects | ✓ |
| Surfaces can be listed | ✓ |
| Surfaces can be retrieved | ✓ |
| Surfaces can be queried using scientific criteria | ✓ |
| Surface properties are directly accessible | ✓ |
| Surfaces can be exported | ✓ |
| Downstream workflows retrieve persisted Surfaces rather than regenerating them | ✓ |

---

## Summary

In this chapter you generated crystallographic Surface models from the
persisted Materials contained within the Project.

The Project now contains:

- Materials,
- Surface models,
- complete provenance linking every Surface to its parent Material.

These persisted Surface objects become the inputs for interface
matching.

In the next chapter you will retrieve these Surface models and perform
crystallographic interface matching to identify compatible interface
relationships.
