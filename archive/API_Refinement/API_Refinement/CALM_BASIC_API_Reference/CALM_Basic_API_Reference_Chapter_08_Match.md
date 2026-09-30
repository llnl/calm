# CALM Basic API Reference

# Chapter 8 — Match

## Overview

`Match` represents a persisted crystallographic interface match between
two previously generated `Surface` objects.

A Match records the crystallographic relationship between a film surface
and a substrate surface. It is the result of an interface matching
search and serves as the parent object for subsequent interface
construction.

A Match is **not** an atomistic interface structure.

It is a scientific description of a crystallographic relationship.

Match objects are created by the `MatchesCollection` and retrieved from
the Project rather than instantiated directly by users.

---

# Construction

Match objects are not constructed directly.

They are created by the Matches Collection.

Example:

```python
results = project.matches.search(
    film=film,
    substrate=substrate,
)

match = results.best()
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

## `film`

Type

```python
Surface
```

Film surface participating in the match.

Read-only.

---

## `substrate`

Type

```python
Surface
```

Substrate surface participating in the match.

Read-only.

---

## `strain`

Type

```python
float
```

Lattice strain associated with the match.

Read-only.

---

## `interface_area`

Type

```python
float
```

Area of the interface supercell.

Read-only.

---

## `orientation_relationship`

Type

```python
OrientationRelationship
```

Crystallographic orientation relationship.

Read-only.

---

## `transformation`

Type

```python
Transformation
```

Transformation relating the film and substrate lattices.

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

## `interfaces`

Type

```python
list[Interface]
```

Every Interface constructed from this Match.

Read-only.

---

## `film`

Type

```python
Surface
```

Film Surface.

Read-only.

---

## `substrate`

Type

```python
Surface
```

Substrate Surface.

Read-only.

---

# Methods

Match intentionally exposes very few methods.

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
project.matches.export(
    self,
    destination,
)
```

Export never modifies the Match.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise scientific summary.

Typical information includes:

- film material,
- substrate material,
- lattice strain,
- interface area,
- orientation relationship.

---

# Immutability

Match objects are immutable.

The following properties cannot change:

- parent surfaces,
- lattice relationship,
- orientation relationship,
- interface area,
- scientific identity.

A different crystallographic relationship is represented by a different
Match.

---

# Equality

Two Match objects are equal if they represent the same persisted
scientific object.

Example:

```python
match_a == match_b
```

evaluates scientific identity.

---

# Scientific Questions

A Match enables users to answer questions such as:

- Which surfaces participate in this match?
- What lattice strain is required?
- What is the interface area?
- What is the crystallographic orientation relationship?
- Has an Interface already been constructed from this Match?

---

# Examples

## Retrieve a Match

```python
match = project.matches.get(
    match_id,
)
```

---

## Inspect matching properties

```python
print(match.film)

print(match.substrate)

print(match.strain)

print(match.interface_area)
```

---

## Retrieve constructed Interfaces

```python
interfaces = match.interfaces
```

---

## Export

```python
match.export(
    "match.json",
)
```

---

# Design Notes

A Match is intentionally separated from an Interface.

A Match describes **how two surfaces may be combined**.

An Interface represents **one explicit atomistic realization** of that
relationship.

This separation allows:

- multiple Interfaces to be generated from one Match,
- exploration of construction parameters,
- preservation of crystallographic provenance,
- reproducible interface construction.

The Match object is therefore the bridge between crystallographic search
and atomistic interface construction.

---

# See Also

- `Project`
- `Surface`
- `MatchesCollection`
- `Interface`
- `InterfacesCollection`
