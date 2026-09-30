# CALM Basic API Reference

# Chapter 4 — Material

## Overview

`Material` represents a persisted bulk crystal structure within a CALM
Project.

A Material is the root scientific object from which all downstream
workflow objects are derived.

Materials are immutable scientific records. Once created, they represent
the canonical bulk structure for the remainder of the scientific
workflow.

Materials are created by the `MaterialsCollection` and retrieved from
the Project rather than instantiated directly by users.

---

# Construction

`Material` objects are not constructed directly.

They are created through the Materials Collection.

Examples:

```python
lif = project.materials.import(
    "LiF.vasp",
)

li2o = project.materials.create(
    structure,
    name="Li2O",
)
```

---

# Properties

## `id`

Type

```python
ObjectId
```

Persistent scientific identity.

The identity remains constant for the lifetime of the Material.

Read-only.

---

## `name`

Type

```python
str
```

Human-readable material name.

Examples:

```python
"LiF"

"Li₂O"
```

Read-only.

---

## `composition`

Type

```python
Composition
```

Chemical composition.

Examples:

```python
LiF

Li2O
```

Read-only.

---

## `structure`

Type

```python
Structure
```

Bulk crystal structure represented by the Material.

This is the canonical bulk structure used throughout downstream
workflows.

Read-only.

---

## `lattice`

Type

```python
Lattice
```

Crystal lattice.

Read-only.

---

## `space_group`

Type

```python
SpaceGroup
```

Crystallographic space group.

Read-only.

---

## `crystal_system`

Type

```python
CrystalSystem
```

Crystal system.

Examples:

- cubic
- tetragonal
- monoclinic

Read-only.

---

## `metadata`

Type

```python
Metadata
```

Scientific and administrative metadata associated with the Material.

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

## `surfaces`

Type

```python
list[Surface]
```

Every persisted Surface derived from this Material.

Example:

```python
surfaces = material.surfaces
```

This relationship is maintained automatically by the Project.

Read-only.

---

# Methods

`Material` intentionally exposes very few public methods.

Most workflow operations belong to collections rather than individual
scientific objects.

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
project.materials.export(
    material,
    destination,
)
```

This method never modifies the Material.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise scientific summary suitable for interactive use.

Typical information includes:

- composition,
- crystal system,
- space group,
- lattice parameters.

---

# Immutability

A Material is immutable.

The following properties cannot be modified after creation:

- structure,
- composition,
- lattice,
- symmetry,
- scientific identity.

Changes to these properties produce a new Material rather than modifying
the existing one.

Administrative metadata may be updated where appropriate.

---

# Equality

Two Materials are equal if they represent the same persisted scientific
object.

Example:

```python
lif1 == lif2
```

evaluates scientific identity rather than object identity in memory.

---

# Scientific Questions

A Material enables users to answer questions such as:

- What bulk material am I studying?
- What is its composition?
- What is its crystal symmetry?
- Which surfaces have been generated?
- Has this material already been imported?

---

# Examples

## Retrieve a Material

```python
lif = project.materials.get(
    "LiF",
)
```

---

## Access crystallographic information

```python
print(lif.composition)

print(lif.space_group)

print(lif.crystal_system)
```

---

## Retrieve generated surfaces

```python
surfaces = lif.surfaces
```

---

## Export

```python
lif.export(
    "LiF.vasp",
)
```

---

# Design Notes

`Material` is intentionally lightweight.

It represents a persisted scientific object rather than an active
workflow manager.

Workflow operations such as importing, querying, or deleting Materials
belong to the `MaterialsCollection`.

Derived workflow stages consume Materials but never modify them.

This preserves scientific provenance and reinforces the project-centered
object lifecycle defined by the CALM Basic API.
