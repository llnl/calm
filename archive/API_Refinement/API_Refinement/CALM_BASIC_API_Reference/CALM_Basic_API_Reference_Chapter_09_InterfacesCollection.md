# CALM Basic API Reference

# Chapter 9 — InterfacesCollection

## Overview

`InterfacesCollection` is the public interface for constructing,
retrieving, refining, querying, exporting, and deleting persisted
atomistic interface structures.

It owns every persisted `Interface` object.

Interface structures are constructed from previously generated
`Match` objects and represent explicit atomistic realizations of
crystallographic interface relationships.

`InterfacesCollection` is accessed through:

```python
project.interfaces
```

---

# Purpose

The Interfaces Collection is responsible for constructing physically
meaningful interface structures.

It supports:

- interface construction,
- strain partitioning,
- registry optimization,
- retrieval,
- querying,
- export,
- lifecycle management.

It does **not** perform:

- interface matching,
- atomistic relaxation,
- scientific analysis.

---

# Methods

## `build`

### Signature

```python
build(
    match,
    *,
    separation=None,
    slab_thickness=None,
    vacuum_thickness=None,
    metadata=None,
) -> Interface
```

### Description

Constructs a persisted Interface from a persisted Match.

The parent Match is never modified.

---

### Parameters

#### `match`

Type

```python
Match
```

The parent Match.

---

#### `separation`

Type

```python
float | None
```

Initial interface separation.

---

#### `slab_thickness`

Type

```python
float | None
```

Optional slab thickness override.

---

#### `vacuum_thickness`

Type

```python
float | None
```

Optional vacuum thickness.

---

#### `metadata`

Optional user metadata.

---

### Returns

```python
Interface
```

The newly persisted Interface.

---

### Side Effects

Creates one persisted Interface.

Updates project provenance.

---

### Raises

- `ObjectNotFoundError`
- `ConstructionError`
- `InvalidMatchError`

---

## Example

```python
interface = project.interfaces.build(
    match=match,
)
```

---

## `partition_strain`

### Signature

```python
partition_strain(
    interface,
    *,
    strategy="balanced",
) -> Interface
```

### Description

Optimizes strain partitioning within an existing Interface.

The Interface identity is preserved.

---

### Parameters

#### `interface`

Type

```python
Interface
```

Interface to optimize.

---

#### `strategy`

Type

```python
str
```

Strain partitioning strategy.

Examples include:

- `"balanced"`
- `"film"`
- `"substrate"`

---

### Returns

```python
Interface
```

The updated Interface.

---

## Example

```python
project.interfaces.partition_strain(
    interface,
)
```

---

## `optimize_registry`

### Signature

```python
optimize_registry(
    interface,
    *,
    method="monte_carlo",
    max_steps=None,
) -> Interface
```

### Description

Optimizes the lateral atomic registry.

Registry optimization modifies the Interface geometry while preserving
its scientific identity.

---

### Parameters

#### `interface`

Type

```python
Interface
```

Interface to optimize.

---

#### `method`

Type

```python
str
```

Optimization algorithm.

Examples include:

- `"monte_carlo"`
- `"grid"`
- `"deterministic"`

---

#### `max_steps`

Optional iteration limit.

---

### Returns

```python
Interface
```

The optimized Interface.

---

## Example

```python
project.interfaces.optimize_registry(
    interface,
)
```

---

## `list`

### Signature

```python
list() -> list[Interface]
```

Returns every persisted Interface.

---

## `get`

### Signature

```python
get(
    identifier,
) -> Interface
```

Retrieves one persisted Interface.

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Interface]
```

Returns Interfaces satisfying scientific criteria.

Supported criteria include:

- parent Match,
- materials,
- interface area,
- strain,
- registry,
- optimization state.

---

## Example

```python
interfaces = project.interfaces.find(
    optimized=True,
)
```

---

## `export`

### Signature

```python
export(
    interface,
    destination,
    *,
    format=None,
)
```

Exports one Interface.

Export never modifies the Interface.

---

## Example

```python
project.interfaces.export(
    interface,
    "interface.vasp",
)
```

---

## `delete`

### Signature

```python
delete(
    interface,
)
```

Removes one persisted Interface.

Deletion follows the dependency rules defined by the Basic API.

---

# Collection Properties

`InterfacesCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Construct an Interface

```python
interface = project.interfaces.build(
    match,
)
```

---

## Optimize strain partitioning

```python
project.interfaces.partition_strain(
    interface,
)
```

---

## Optimize registry

```python
project.interfaces.optimize_registry(
    interface,
)
```

---

## Retrieve an Interface

```python
interface = project.interfaces.get(
    interface_id,
)
```

---

## Export an Interface

```python
project.interfaces.export(
    interface,
    "interface.vasp",
)
```

---

# Design Notes

Unlike previous collections, the Interfaces Collection contains both
construction and refinement operations.

These operations intentionally preserve Interface identity because they
represent progressive refinement of the same scientific object rather
than creation of new scientific objects.

This collection forms the bridge between crystallographic matching and
atomistic simulation.

---

# See Also

- `Project`
- `Match`
- `Interface`
- `MatchesCollection`
- `RelaxationsCollection`
```
