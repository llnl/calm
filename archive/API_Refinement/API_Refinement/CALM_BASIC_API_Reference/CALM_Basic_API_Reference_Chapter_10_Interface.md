# CALM Basic API Reference

# Chapter 10 — Interface

## Overview

`Interface` represents a persisted atomistic interface structure within a
CALM Project.

An Interface is derived from exactly one persisted `Match` and represents
a physically realizable atomistic model suitable for simulation.

Unlike a `Match`, which describes a crystallographic relationship,
an `Interface` contains explicit atomic coordinates and geometric
construction parameters.

Interface objects are created by the `InterfacesCollection` and
retrieved from the Project rather than instantiated directly by users.

---

# Construction

Interface objects are not constructed directly.

They are created by the Interfaces Collection.

Example:

```python
interface = project.interfaces.build(
    match,
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

Read-only.

---

## `match`

Type

```python
Match
```

Parent Match.

Read-only.

---

## `film`

Type

```python
Surface
```

Film Surface participating in the Interface.

Read-only.

---

## `substrate`

Type

```python
Surface
```

Substrate Surface participating in the Interface.

Read-only.

---

## `structure`

Type

```python
Structure
```

Complete atomistic interface structure.

Read-only.

---

## `strain`

Type

```python
StrainState
```

Current strain partitioning.

Read-only.

---

## `registry`

Type

```python
RegistryState
```

Current lateral registry.

Read-only.

---

## `interface_area`

Type

```python
float
```

Area of the constructed interface.

Read-only.

---

## `separation`

Type

```python
float
```

Current interface separation.

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

## `relaxations`

Type

```python
list[Relaxation]
```

Every Relaxation derived from this Interface.

Read-only.

---

## `match`

Type

```python
Match
```

Parent Match.

Read-only.

---

# Methods

Interface intentionally exposes very few public methods.

Construction and refinement belong to the
`InterfacesCollection`.

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
project.interfaces.export(
    self,
    destination,
)
```

Export never modifies the Interface.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise scientific summary.

Typical information includes:

- parent Match,
- constituent materials,
- interface area,
- strain partitioning,
- registry state,
- separation.

---

# Immutability

Interface identity is immutable.

Construction operations create the Interface.

Subsequent refinement operations such as:

- strain partitioning,
- registry optimization,

modify the geometry of the Interface while preserving its scientific
identity.

Properties that define scientific identity cannot change:

- parent Match,
- constituent surfaces,
- persistent identity.

---

# Equality

Two Interface objects are equal if they represent the same persisted
scientific object.

Example:

```python
interface_a == interface_b
```

evaluates scientific identity.

---

# Scientific Questions

An Interface enables users to answer questions such as:

- Which Match produced this Interface?
- What is the current interface geometry?
- How is strain partitioned?
- What registry has been selected?
- Has this Interface already been relaxed?

---

# Examples

## Retrieve an Interface

```python
interface = project.interfaces.get(
    interface_id,
)
```

---

## Inspect Interface properties

```python
print(interface.match)

print(interface.interface_area)

print(interface.strain)

print(interface.registry)
```

---

## Retrieve Relaxations

```python
relaxations = interface.relaxations
```

---

## Export

```python
interface.export(
    "interface.vasp",
)
```

---

# Design Notes

The Interface is the central structural object of the CALM scientific
workflow.

Unlike a Match, which represents a crystallographic relationship,
an Interface represents one explicit atomistic realization of that
relationship.

Interface refinement operations intentionally preserve Interface
identity because they improve the representation of the same scientific
object rather than creating a fundamentally new one.

All workflow operations involving construction or refinement belong to
the `InterfacesCollection`.

---

# See Also

- `Project`
- `Match`
- `InterfacesCollection`
- `Relaxation`
- `RelaxationsCollection`
