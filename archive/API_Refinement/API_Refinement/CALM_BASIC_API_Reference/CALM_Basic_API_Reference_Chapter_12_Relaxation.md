# CALM Basic API Reference

# Chapter 12 — Relaxation

## Overview

`Relaxation` represents a persisted structural optimization performed on
a previously constructed `Interface`.

A Relaxation records both the computational procedure and the resulting
relaxed atomic structure.

Unlike an `Interface`, which represents a constructed structural model,
a `Relaxation` represents the outcome of an atomistic simulation.

Relaxation objects are created by the `RelaxationsCollection` and
retrieved from the Project rather than instantiated directly by users.

---

# Construction

Relaxation objects are represented in the project persistence layer, but the
canonical public entrypoint for creating persisted relaxations is the
project-backed stage API. A dedicated `RelaxationsCollection` object model is
documented as an aspirational interface in the API refinement materials and is
deferred until the project-backed contract is stabilized.

Examples:

Project-backed (recommended for persisted runs):

```python
# Persisted relaxation via project stage API
proj.run_relaxation_stage(["proto:1"], max_steps=200, backend="deterministic")
```

Single-interface convenience (non-orchestration / ephemeral):

```python
relaxed = interface.relax(calculator=my_calc, fmax=0.05)
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

## `interface`

Type

```python
Interface
```

Parent Interface.

Read-only.

---

## `structure`

Type

```python
Structure
```

Final relaxed atomic structure.

Read-only.

---

## `trajectory`

Type

```python
Trajectory
```

Complete structural relaxation trajectory.

Read-only.

---

## `calculator`

Type

```python
CalculatorSpecification
```

Calculator used for the relaxation.

Read-only.

---

## `optimizer`

Type

```python
OptimizerSpecification
```

Optimizer used during structural relaxation.

Read-only.

---

## `converged`

Type

```python
bool
```

Indicates whether the relaxation satisfied the requested convergence
criteria.

Read-only.

---

## `steps`

Type

```python
int
```

Number of optimization steps performed.

Read-only.

---

## `energy`

Type

```python
float
```

Final total energy.

Read-only.

---

## `forces`

Type

```python
Forces
```

Final atomic forces.

Read-only.

---

## `stress`

Type

```python
StressTensor
```

Final stress tensor.

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

## `analyses`

Type

```python
list[Analysis]
```

Every Analysis derived from this Relaxation.

Read-only.

---

## `interface`

Type

```python
Interface
```

Parent Interface.

Read-only.

---

# Methods

Relaxation intentionally exposes very few public methods.

Simulation execution belongs to the `RelaxationsCollection`.

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
project.relaxations.export(
    self,
    destination,
)
```

Export never modifies the Relaxation.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise scientific summary.

Typical information includes:

- convergence status,
- total energy,
- number of optimization steps,
- calculator,
- optimizer.

---

# Immutability

Relaxation objects are immutable.

A completed Relaxation represents a permanent scientific record of a
specific structural optimization.

Properties that cannot change include:

- parent Interface,
- relaxed structure,
- convergence history,
- computational provenance,
- scientific identity.

If a new relaxation is performed using different computational
parameters, a new Relaxation object shall be created.

---

# Equality

Two Relaxation objects are equal if they represent the same persisted
scientific object.

Example:

```python
relaxation_a == relaxation_b
```

evaluates scientific identity.

---

# Scientific Questions

A Relaxation enables users to answer questions such as:

- Did the calculation converge?
- What is the relaxed structure?
- Which calculator was used?
- Which optimizer was used?
- How many optimization steps were required?
- Has this Relaxation already been analyzed?

---

# Examples

## Retrieve a Relaxation

```python
relaxation = project.relaxations.get(
    relaxation_id,
)
```

---

## Inspect convergence

```python
print(relaxation.converged)

print(relaxation.energy)

print(relaxation.steps)
```

---

## Retrieve Analyses

```python
analyses = relaxation.analyses
```

---

## Export the relaxed structure

```python
relaxation.export(
    "relaxed_interface.vasp",
)
```

---

# Design Notes

A Relaxation is a scientific record of a completed atomistic
optimization.

Unlike the Interface from which it was derived, the Relaxation contains
both the computational history and the resulting relaxed atomic
configuration.

Multiple Relaxations may legitimately exist for the same Interface
using different:

- MLIPs,
- optimizers,
- convergence criteria,
- computational settings.

This enables reproducible comparison of computational methodologies
while preserving complete scientific provenance.

---

# See Also

- `Project`
- `Interface`
- `RelaxationsCollection`
- `Analysis`
- `AnalysesCollection`
```
