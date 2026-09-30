# CALM Basic API Reference

# Chapter 3 — MaterialsCollection

## Overview

`MaterialsCollection` is the public interface for managing bulk crystal
structures within a Project.

It owns every persisted `Material` and provides the complete API for
creating, retrieving, querying, exporting, and deleting materials.

`MaterialsCollection` is accessed through:

```python
project.materials
```

---

# Purpose

The Materials Collection is the entry point for every workflow that
begins with bulk crystal structures.

Every material imported into CALM becomes a persisted `Material`
contained within this collection.

---

# Methods

## `import`

### Signature

```python
import(
    source,
    *,
    name=None,
    primitive=False,
    metadata=None,
    overwrite=False,
) -> Material
```

### Description

Imports a bulk crystal structure into the Project.

The imported structure is immediately persisted as a `Material`.

---

### Parameters

#### `source`

The source of the structure.

Accepted values include:

- POSCAR
- CIF
- ASE `Atoms`
- other supported structure representations

---

#### `name`

Optional display name.

If omitted, CALM derives a default name.

---

#### `primitive`

If `True`, convert the structure to its primitive cell before
persistence.

---

#### `metadata`

Optional user-defined metadata.

---

#### `overwrite`

If `True`, replace an existing material with the same identity where
permitted.

---

### Returns

```python
Material
```

The newly persisted Material.

---

### Side Effects

Creates one persisted Material.

Updates project provenance.

---

### Raises

- `DuplicateObjectError`
- `InvalidStructureError`
- `ImportError`

---

## Example

```python
lif = project.materials.import(
    "LiF.vasp",
)
```

---

## `create`

### Signature

```python
create(
    structure,
    *,
    name=None,
    metadata=None,
) -> Material
```

### Description

Creates a persisted Material from an existing in-memory structure.

---

## Returns

```python
Material
```

---

## Example

```python
lif = project.materials.create(
    atoms,
    name="LiF",
)
```

---

## `list`

### Signature

```python
list() -> list[Material]
```

### Description

Returns every persisted Material contained within the Project.

---

## Example

```python
materials = project.materials.list()
```

---

## `get`

### Signature

```python
get(
    identifier,
) -> Material
```

### Description

Retrieves exactly one persisted Material.

---

### Parameters

`identifier`

Any supported Material identifier.

Examples include:

- persistent identity,
- unique scientific name.

---

### Returns

```python
Material
```

---

### Raises

- `ObjectNotFoundError`

---

## Example

```python
lif = project.materials.get("LiF")
```

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Material]
```

### Description

Returns every Material satisfying the specified scientific criteria.

---

### Supported Criteria

Examples include:

- composition,
- space group,
- crystal system,
- labels,
- tags.

---

## Example

```python
fluorides = project.materials.find(
    composition="LiF",
)
```

---

## `export`

### Signature

```python
export(
    material,
    destination,
    *,
    format=None,
)
```

### Description

Exports one persisted Material.

Export never modifies the Material.

---

## Example

```python
project.materials.export(
    lif,
    "LiF.vasp",
)
```

---

## `delete`

### Signature

```python
delete(
    material,
)
```

### Description

Removes one persisted Material from the Project.

Deletion follows the dependency rules defined by the Basic API.

---

## Example

```python
project.materials.delete(
    lif,
)
```

---

# Collection Properties

`MaterialsCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Import a material

```python
lif = project.materials.import(
    "LiF.vasp",
)
```

---

## Retrieve a material

```python
lif = project.materials.get(
    "LiF",
)
```

---

## List all materials

```python
materials = project.materials.list()
```

---

## Export a material

```python
project.materials.export(
    lif,
    "LiF.vasp",
)
```

---

# See Also

- `Project`
- `Material`
- `SurfacesCollection`
