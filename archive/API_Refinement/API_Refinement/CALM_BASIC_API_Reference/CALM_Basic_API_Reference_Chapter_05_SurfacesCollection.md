# CALM Basic API Reference

# Chapter 5 — SurfacesCollection

## Overview

`SurfacesCollection` is the public interface for generating,
retrieving, querying, exporting, and deleting persisted surface models
within a CALM Project.

It owns every persisted `Surface` object.

Surface models are derived from previously persisted `Material`
objects and represent the first derived scientific objects in the CALM
workflow.

`SurfacesCollection` is accessed through:

```python
project.surfaces
```

---

# Purpose

The Surfaces Collection is responsible for generating crystallographic
surface models from persisted bulk materials.

It supports:

- surface generation,
- retrieval,
- querying,
- export,
- lifecycle management.

It does **not** perform:

- interface matching,
- interface construction,
- relaxation,
- analysis.

---

# Methods

## `generate`

### Signature

```python
generate(
    material,
    *,
    millers,
    enumerate_terminations=True,
    slab_thickness=None,
    vacuum_thickness=None,
    primitive=True,
    metadata=None,
) -> list[Surface]
```

### Description

Generates one or more persisted surface models from a persisted
Material.

Generated surfaces are immediately persisted within the Project.

The parent Material is never modified.

---

### Parameters

#### `material`

Type

```python
Material
```

The parent Material.

---

#### `millers`

Type

```python
Iterable[MillerIndex]
```

The Miller orientations to generate.

Example:

```python
[
    (1,0,0),
    (1,1,0),
    (1,1,1),
]
```

---

#### `enumerate_terminations`

Type

```python
bool
```

If `True`, generate every symmetry-unique termination.

Default:

```python
True
```

---

#### `slab_thickness`

Optional slab thickness.

---

#### `vacuum_thickness`

Optional vacuum thickness.

---

#### `primitive`

If `True`, generate primitive surface cells whenever possible.

---

#### `metadata`

Optional user-defined metadata.

---

### Returns

```python
list[Surface]
```

Every generated Surface.

---

### Side Effects

Creates one or more persisted Surface objects.

Updates project provenance.

---

### Raises

- `ObjectNotFoundError`
- `InvalidSurfaceError`
- `GenerationError`

---

## Example

```python
surfaces = project.surfaces.generate(
    material=lif,
    millers=[
        (1,0,0),
        (1,1,0),
    ],
)
```

---

## `list`

### Signature

```python
list() -> list[Surface]
```

### Description

Returns every persisted Surface contained within the Project.

---

## Example

```python
surfaces = project.surfaces.list()
```

---

## `get`

### Signature

```python
get(
    identifier,
) -> Surface
```

### Description

Retrieves exactly one persisted Surface.

---

### Returns

```python
Surface
```

---

### Raises

- `ObjectNotFoundError`

---

## Example

```python
surface = project.surfaces.get(
    "LiF (100)"
)
```

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Surface]
```

### Description

Returns every Surface satisfying the specified scientific criteria.

---

### Supported Criteria

Examples include:

- material,
- Miller index,
- termination,
- polarity,
- slab thickness,
- vacuum thickness.

---

## Example

```python
surfaces = project.surfaces.find(
    material=lif,
    miller=(1,0,0),
)
```

---

## `export`

### Signature

```python
export(
    surface,
    destination,
    *,
    format=None,
)
```

### Description

Exports one persisted Surface.

Export never modifies the Surface.

---

## Example

```python
project.surfaces.export(
    surface,
    "LiF_100.vasp",
)
```

---

## `delete`

### Signature

```python
delete(
    surface,
)
```

### Description

Removes one persisted Surface from the Project.

Deletion follows the dependency rules defined by the Basic API.

---

## Example

```python
project.surfaces.delete(
    surface,
)
```

---

# Collection Properties

`SurfacesCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Generate surfaces

```python
surfaces = project.surfaces.generate(
    material=lif,
    millers=[
        (1,0,0),
        (1,1,0),
    ],
)
```

---

## Retrieve a surface

```python
surface = project.surfaces.get(
    "LiF (100)"
)
```

---

## Query surfaces

```python
polar = project.surfaces.find(
    polarity=True,
)
```

---

## Export a surface

```python
project.surfaces.export(
    surface,
    "surface.vasp",
)
```

---

# See Also

- `Project`
- `Material`
- `Surface`
- `MatchesCollection`
