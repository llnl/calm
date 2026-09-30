# CALM Basic API Reference

# Chapter 6 — Surface

## Overview

`Surface` represents a persisted crystallographic surface model within a
CALM Project.

A Surface is derived from exactly one persisted `Material` and forms the
foundation for all subsequent interface matching workflows.

Surface objects are created by the `SurfacesCollection` and retrieved
from the Project rather than instantiated directly by users.

---

# Construction

`Surface` objects are not constructed directly.

They are generated through the Surfaces Collection.

Examples:

```python
surfaces = project.surfaces.generate(
    material=lif,
    millers=[
        (1,0,0),
    ],
)

surface = surfaces[0]
```

---

# Properties

## `id`

Type

```python
ObjectId
```

Persistent scientific identity.

Read-only.

---

## `material`

Type

```python
Material
```

Parent Material from which this Surface was generated.

Read-only.

---

## `miller`

Type

```python
MillerIndex
```

Crystallographic Miller orientation.

Examples:

```python
(1,0,0)

(1,1,0)

(1,1,1)
```

Read-only.

---

## `termination`

Type

```python
Termination
```

Surface termination.

Read-only.

---

## `structure`

Type

```python
Structure
```

Atomistic slab structure.

Read-only.

---

## `slab_thickness`

Type

```python
float
```

Physical slab thickness.

Read-only.

---

## `vacuum_thickness`

Type

```python
float
```

Vacuum thickness.

Read-only.

---

## `surface_area`

Type

```python
float
```

Surface area.

Read-only.

---

## `is_polar`

Type

```python
bool
```

Indicates whether the generated surface is polar.

Read-only.

---

## `metadata`

Type

```python
Metadata
```

Scientific and administrative metadata.

Read-only.

---

## `project`

Type

```python
Project
```

Owning Project.

Read-only.

---

# Relationships

## Related matches

Matches involving this Surface are discoverable through the Matches
collection. Use the collection query API to locate related matches rather
than accessing a property on the Surface object:

```python
project.matches.find(film=surface)
project.matches.find(substrate=surface)
```

This preserves the conceptual separation between persisted scientific
objects and exploratory search results.

---

## `material`

Type

```python
Material
```

Parent Material.

Read-only.

---

# Methods

Surface intentionally exposes very few methods.

Scientific workflow operations belong to collections.

---

## `export`

### Signature

```python
export(
    destination,
    *,
    format=None,
)
```

### Description

Convenience wrapper for

```python
project.surfaces.export(
    surface,
    destination,
)
```

Export never modifies the Surface.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise scientific summary.

Typical information includes:

- parent material,
- Miller orientation,
- termination,
- slab thickness,
- polarity,
- surface area.

---

# Immutability

Surface objects are immutable.

The following properties cannot be modified after generation:

- parent material,
- Miller orientation,
- termination,
- slab geometry,
- scientific identity.

Any workflow that fundamentally changes these properties shall generate
a new Surface.

---

# Equality

Two Surface objects are equal if they represent the same persisted
scientific object.

Example:

```python
surface_a == surface_b
```

evaluates scientific identity.

---

# Scientific Questions

A Surface enables users to answer questions such as:

- Which Material produced this Surface?
- Which Miller orientation does it represent?
- Which termination is this?
- Is the Surface polar?
- Which interface matches involve this Surface?

---

# Examples

## Retrieve a Surface

```python
surface = project.surfaces.get(
    "LiF (100)"
)
```

---

## Inspect crystallographic information

```python
print(surface.material)

print(surface.miller)

print(surface.termination)

print(surface.surface_area)
```

---

## Retrieve interface matches

```python
matches = project.matches.find(film=surface)
```
---

## Export

```python
surface.export(
    "LiF_100.vasp",
)
```

---

# Design Notes

A Surface represents a crystallographic object rather than an interface.

It is intentionally immutable so that:

- provenance remains stable,
- interface matching is reproducible,
- downstream workflows consume well-defined scientific objects.

All operations that create or query Surfaces belong to the
`SurfacesCollection`.

The Surface itself serves primarily as a persisted scientific record and
a navigable node within the project provenance graph.

---

# See Also

- `Project`
- `Material`
- `SurfacesCollection`
- `Match`
