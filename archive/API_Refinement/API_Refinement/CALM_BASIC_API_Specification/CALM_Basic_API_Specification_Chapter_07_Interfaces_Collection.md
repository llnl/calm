# CALM Basic API Specification

# Chapter 07 — Interfaces Collection

## Purpose

The Interfaces Collection is the public interface for constructing,
managing, retrieving, querying, optimizing, and exporting atomistic
interface structures.

It is the canonical owner of every persisted `Interface` object and
represents the transition from crystallographic interface relationships
to explicit atomistic interface models.

The Interfaces Collection is responsible for constructing physically
realizable interface structures from persisted interface matches. It is
also responsible for operations that modify interface geometry while
preserving the scientific identity of the interface.

The Interfaces Collection is **not** responsible for structural
relaxation or energetic analysis.

---

# 1. Scientific Object

The Interfaces Collection owns the following public scientific object.

```text
Interface
```

An `Interface` represents a complete atomistic structural model derived
from a persisted `Match`.

An Interface contains all information necessary to reproduce the
structure, including:

- film and substrate structures,
- crystallographic orientation relationship,
- interface geometry,
- strain partitioning,
- atomic registry,
- construction parameters.

---

# 2. Collection Ownership

The Interfaces Collection is accessed through the project.

```python
project.interfaces
```

Every persisted `Interface` belongs to exactly one project.

Every Interface has exactly one parent `Match`.

---

# 3. Lifecycle Responsibilities

The Interfaces Collection is responsible for:

- constructing interface structures,
- optimizing strain partitioning,
- optimizing atomic registry,
- retrieving persisted interfaces,
- querying interfaces,
- exporting interface structures,
- deleting interfaces.

The Interfaces Collection does **not**:

- perform atomistic relaxation,
- compute interface energies,
- perform scientific analysis.

Those responsibilities belong to downstream collections.

---

# 4. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Interfaces are derived scientific objects. |
| `create(...)` | ✗ | Interfaces are constructed from matches. |
| `generate(...)` | ✗ | Interface construction is expressed explicitly as a build operation. |
| `build(...)` | ✓ | Construct interface structures from persisted matches. |
| `list(...)` | ✓ | Enumerate persisted interfaces. |
| `get(...)` | ✓ | Retrieve one persisted interface. |
| `find(...)` | ✓ | Query interfaces using scientific criteria. |
| `export(...)` | ✓ | Export interface structures. |
| `delete(...)` | ✓ | Remove persisted interfaces. |

---

# 5. Behavioral Contract

## `build(...)`

Constructs one or more persisted Interface objects from a persisted
Match.

Typical construction parameters include:

- interface separation,
- vacuum thickness,
- slab thickness,
- supercell configuration,
- termination selection.

The parent Match shall never be modified.

---

## `partition_strain(...)`

Optimizes the distribution of lattice strain between the film and
substrate.

This operation updates the Interface geometry while preserving the
scientific identity of the Interface.

The optimization shall record all resulting strain information as part
of the Interface metadata.

---

## `optimize_registry(...)`

Optimizes the lateral atomic registry between the two slabs.

Typical optimization methods include:

- Monte Carlo,
- deterministic search,
- user-defined optimization algorithms.

The optimized registry remains part of the Interface object.

---

## `list(...)`

Returns all persisted Interface objects contained within the project.

---

## `get(...)`

Returns exactly one persisted Interface.

---

## `find(...)`

Returns Interface objects satisfying scientific criteria.

Typical criteria include:

- parent Match,
- constituent materials,
- Miller orientations,
- interface area,
- strain,
- registry state,
- optimization status.

---

## `export(...)`

Exports Interface structures to supported atomistic structure formats.

Export shall never modify the persisted Interface.

---

## `delete(...)`

Removes persisted Interface objects while preserving project provenance.

---

# 6. Scientific Transformations

Unlike previous collections, the Interfaces Collection contains
operations that modify Interface geometry while preserving the identity
of the scientific object.

Examples include:

- strain partitioning,
- registry optimization,
- interface reconstruction operations.

These transformations are considered refinements of an existing
Interface rather than creation of an entirely new scientific object.

---

# 7. Object Relationships

Every Interface is derived from exactly one Match.

```text
Material
      ↓
Surface
      ↓
Match
      ↓
Interface
```

Every Relaxation references exactly one Interface.

```text
Interface
      ↓
Relaxation
```

---

# 8. Scientific Questions

The Interfaces Collection enables users to answer questions such as:

- What does the interface actually look like?
- How should lattice strain be partitioned?
- Which atomic registry is most favorable?
- Which interface geometry should be relaxed?
- Which interface is physically representative?

---

# 9. Example Workflow

```python
project = Project.open("lif_li2o")

match = project.matches.get(match_id)

interface = project.interfaces.build(
    match=match,
)

project.interfaces.partition_strain(
    interface,
)

project.interfaces.optimize_registry(
    interface,
    method="monte_carlo",
)

project.interfaces.export(
    interface,
    "LiF_Li2O_interface.vasp",
)
```

---

# 10. Design Rationale

Interface construction represents the first workflow stage that creates
explicit atomistic interface structures.

Unlike the Matches Collection, whose primary activity is scientific
search, the Interfaces Collection focuses on scientific model
construction and refinement.

Interface construction, strain partitioning, and registry optimization
are grouped together because they all modify the geometry of the same
scientific object.

Keeping these operations within a single collection provides a coherent
user experience while preserving the project-centered object lifecycle.

---

# Summary

The Interfaces Collection owns every persisted `Interface` object and
provides the public interface for constructing and refining atomistic
interface structures.

It bridges crystallographic interface matching and atomistic simulation,
providing the final structural model that will subsequently undergo
structural relaxation.

The next chapter specifies the **Relaxations Collection**, which
consumes persisted Interface objects and performs atomistic structural
optimization.
```
