# CALM Basic API Reference

# Chapter 11 — RelaxationsCollection

## Overview

`RelaxationsCollection` is the public interface for executing,
managing, retrieving, querying, exporting, and deleting atomistic
structural relaxations.

It owns every persisted `Relaxation` object.

Relaxations are performed on previously constructed `Interface`
objects and represent the transition from constructed atomistic models
to physically equilibrated structures.

`RelaxationsCollection` is accessed through:

```python
project.relaxations
```

---

# Purpose

The Relaxations Collection is responsible for executing atomistic
structural optimization workflows.

It supports:

- structural relaxation,
- restart,
- retrieval,
- querying,
- export,
- lifecycle management.

It does **not** perform:

- interface construction,
- scientific analysis,
- energetic interpretation.

---

# Methods

## `run`

### Signature

```python
run(
    interface,
    *,
    calculator=None,
    optimizer=None,
    fmax=None,
    smax=None,
    max_steps=None,
    metadata=None,
) -> Relaxation
```

### Description

Executes a structural relaxation beginning from a persisted Interface.

The parent Interface is never modified.

---

### Parameters

#### `interface`

Type

```python
Interface
```

The Interface to relax.

---

#### `calculator`

Type

```python
Calculator | None
```

Calculator used for the relaxation.

If omitted, the Project default is used.

---

#### `optimizer`

Type

```python
Optimizer | None
```

Structural optimization algorithm.

---

#### `fmax`

Type

```python
float | None
```

Maximum residual force.

---

#### `smax`

Type

```python
float | None
```

Maximum residual stress.

---

#### `max_steps`

Type

```python
int | None
```

Maximum optimization iterations.

---

#### `metadata`

Optional user-defined metadata.

---

### Returns

```python
Relaxation
```

The newly created persisted Relaxation.

---

### Side Effects

Creates one persisted Relaxation.

Updates project provenance.

---

### Raises

- `ObjectNotFoundError`
- `CalculationError`
- `InvalidInterfaceError`

---

## Example

```python
relaxation = project.relaxations.run(
    interface,
)
```

---

## `restart`

### Signature

```python
restart(
    relaxation,
) -> Relaxation
```

### Description

Restarts an incomplete Relaxation.

The Relaxation identity is preserved.

---

## Example

```python
project.relaxations.restart(
    relaxation,
)
```

---

## `list`

### Signature

```python
list() -> list[Relaxation]
```

Returns every persisted Relaxation.

---

## `get`

### Signature

```python
get(
    identifier,
) -> Relaxation
```

Retrieves one persisted Relaxation.

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Relaxation]
```

Returns Relaxations satisfying scientific criteria.

Supported criteria include:

- interface,
- convergence,
- calculator,
- optimizer,
- completion status.

---

## Example

```python
converged = project.relaxations.find(
    converged=True,
)
```

---

## `export`

### Signature

```python
export(
    relaxation,
    destination,
    *,
    format=None,
)
```

Exports one Relaxation.

Typical outputs include:

- relaxed structures,
- trajectories,
- calculator outputs.

Export never modifies the Relaxation.

---

## Example

```python
project.relaxations.export(
    relaxation,
    "relaxed_interface.vasp",
)
```

---

## `delete`

### Signature

```python
delete(
    relaxation,
)
```

Removes one persisted Relaxation.

Deletion follows the dependency rules defined by the Basic API.

---

# Collection Properties

`RelaxationsCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Run a relaxation

```python
relaxation = project.relaxations.run(
    interface,
)
```

---

## Restart a failed relaxation

```python
project.relaxations.restart(
    relaxation,
)
```

---

## Retrieve a Relaxation

```python
relaxation = project.relaxations.get(
    relaxation_id,
)
```

---

## Query converged Relaxations

```python
relaxations = project.relaxations.find(
    converged=True,
)
```

---

## Export a relaxed structure

```python
project.relaxations.export(
    relaxation,
    "relaxed_interface.vasp",
)
```

---

# Design Notes

Unlike previous collections, the primary operation is a long-running
scientific calculation rather than immediate object generation.

A Relaxation records both:

- the computational process,
- the resulting relaxed structure.

The parent Interface remains unchanged.

This preserves complete scientific provenance while allowing multiple
Relaxations to be performed from the same Interface using different
computational settings.

---

# See Also

- `Project`
- `Interface`
- `Relaxation`
- `InterfacesCollection`
- `AnalysesCollection`
```
