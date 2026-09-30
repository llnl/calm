# CALM Basic API Reference

# Chapter 14 — Analysis

## Overview

`Analysis` represents a persisted scientific interpretation derived from
one or more previously generated scientific objects.

Unlike structural objects such as `Material`, `Surface`, or
`Interface`, an Analysis contains scientific conclusions rather than
atomic structures.

An Analysis is the canonical representation of a computed scientific
quantity within a Project.

Analysis objects are created by the `AnalysesCollection` and retrieved
from the Project rather than instantiated directly by users.

---

# Construction

Analysis objects are not constructed directly.

They are created through the Analyses Collection.

Examples:

```python
analysis = project.analyses.run(
    interface_energy,
    relaxation,
)

comparison = project.analyses.compare(
    relaxation_a,
    relaxation_b,
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

## `type`

Type

```python
AnalysisType
```

The scientific analysis represented by this object.

Examples include:

- `interface_energy`
- `adhesion_energy`
- `strain_analysis`
- `bonding_analysis`
- `charge_analysis`
- `comparison`

Read-only.

---

## `inputs`

Type

```python
tuple[ScientificObject, ...]
```

The persisted scientific objects consumed by the analysis.

Read-only.

---

## `results`

Type

```python
AnalysisResults
```

The computed scientific results.

Read-only.

---

## `parameters`

Type

```python
AnalysisParameters
```

Parameters controlling the computation.

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

Analysis objects may reference one or more parent scientific objects.

Typical parents include:

```python
analysis.inputs
```

Examples:

- Relaxation
- Interface
- Match
- Surface
- Material

The specific input types depend upon the analysis.

---

# Methods

Analysis intentionally exposes very few methods.

Scientific computation belongs to the
`AnalysesCollection`.

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
project.analyses.export(
    self,
    destination,
)
```

Export never modifies the Analysis.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise summary of the scientific analysis.

Typical information includes:

- analysis type,
- parent objects,
- principal scientific results,
- computational parameters.

---

# Immutability

Analysis objects are immutable.

The following properties cannot change:

- analysis type,
- parent objects,
- computed results,
- computational parameters,
- scientific identity.

If an analysis is recomputed using different parameters or different
parent objects, a new Analysis object shall be created.

---

# Equality

Two Analysis objects are equal if they represent the same persisted
scientific object.

Example:

```python
analysis_a == analysis_b
```

evaluates scientific identity.

---

# Scientific Questions

An Analysis enables users to answer questions such as:

- What scientific quantity was computed?
- Which objects were analyzed?
- Which computational parameters were used?
- What were the resulting values?
- Has this scientific question already been answered?

---

# Examples

## Retrieve an Analysis

```python
analysis = project.analyses.get(
    analysis_id,
)
```

---

## Inspect results

```python
print(analysis.type)

print(analysis.results)

print(analysis.inputs)
```

---

## Export results

```python
analysis.export(
    "analysis.csv",
)
```

---

# Design Notes

An Analysis is the final scientific product of a computational workflow.

Unlike previous scientific objects, an Analysis contains interpretation
rather than structure.

Representing analyses as persisted first-class objects provides several
advantages:

- reproducibility,
- provenance,
- comparison,
- searchability,
- reuse,
- dataset construction.

An Analysis never modifies its parent scientific objects.

Instead, it records a reproducible scientific interpretation of those
objects.

---

# See Also

- `Project`
- `AnalysesCollection`
- `Relaxation`
- `Interface`
- `Dataset`
```
