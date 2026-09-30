# CALM Basic API Specification

# Chapter 08 — Relaxations Collection

## Purpose

The Relaxations Collection is the public interface for performing,
managing, retrieving, querying, and exporting atomistic structural
relaxations.

It is the canonical owner of every persisted `Relaxation` object and
represents the transition from atomistic interface models to physically
relaxed structures.

The Relaxations Collection is responsible for executing structural
optimization workflows while recording the complete computational
provenance of every relaxation.

The Relaxations Collection is **not** responsible for constructing
interface structures or performing scientific analysis.

---

# 1. Scientific Object

The Relaxations Collection owns the following public scientific object.

```text
Relaxation
```

A `Relaxation` represents a complete structural optimization performed
on a persisted `Interface`.

A Relaxation records:

- the input Interface,
- computational parameters,
- relaxation trajectory,
- convergence information,
- final relaxed structure,
- computational provenance.

---

# 2. Collection Ownership

The Relaxations Collection is accessed through the project.

```python
project.relaxations
```

Every persisted `Relaxation` belongs to exactly one project.

Every Relaxation has exactly one parent `Interface`.

---

# 3. Lifecycle Responsibilities

The Relaxations Collection is responsible for:

- executing structural relaxations,
- monitoring relaxation progress,
- restarting interrupted relaxations,
- retrieving persisted relaxations,
- querying relaxations,
- exporting relaxed structures,
- deleting relaxations.

The Relaxations Collection does **not**:

- construct interface structures,
- compute interface energies,
- perform scientific interpretation.

Those responsibilities belong to downstream collections.

---

# 4. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Relaxations are generated computationally. |
| `create(...)` | ✗ | Relaxations are executed from Interfaces. |
| `generate(...)` | ✗ | Relaxation is an explicit simulation. |
| `run(...)` | ✓ | Execute a structural relaxation. |
| `restart(...)` | ✓ | Resume an interrupted relaxation. |
| `list(...)` | ✓ | Enumerate persisted relaxations. |
| `get(...)` | ✓ | Retrieve one persisted relaxation. |
| `find(...)` | ✓ | Query relaxations. |
| `export(...)` | ✓ | Export relaxed structures and trajectories. |
| `delete(...)` | ✓ | Remove persisted relaxations. |

---

# 5. Behavioral Contract

## `run(...)`

Executes a structural relaxation beginning from a persisted Interface.

Inputs typically include:

- Interface,
- calculator,
- convergence criteria,
- optimizer,
- force tolerance,
- stress tolerance,
- maximum iterations.

Execution produces one persisted Relaxation object.

The parent Interface shall never be modified.

---

## `restart(...)`

Continues a previously interrupted Relaxation.

The restart operation preserves the existing Relaxation identity and
extends its computational history.

---

## `list(...)`

Returns all persisted Relaxation objects.

---

## `get(...)`

Returns one persisted Relaxation.

---

## `find(...)`

Returns Relaxations satisfying scientific criteria.

Typical criteria include:

- parent Interface,
- convergence status,
- optimizer,
- calculator,
- completion state.

---

## `export(...)`

Exports relaxed structures, trajectories, or computational outputs.

Export shall never modify persisted Relaxation objects.

---

## `delete(...)`

Removes persisted Relaxation objects while preserving project
provenance rules.

---

# 6. Scientific Transformations

A Relaxation represents a physical transformation of an Interface.

Unlike geometry refinement operations performed within the Interfaces
Collection, structural relaxation changes atomic coordinates through
atomistic simulation.

The original Interface remains unchanged.

The Relaxation stores both:

- the initial Interface,
- the relaxed structure.

This preserves complete scientific provenance.

---

# 7. Object Relationships

Every Relaxation is derived from exactly one Interface.

```text
Material
      ↓
Surface
      ↓
Match
      ↓
Interface
      ↓
Relaxation
```

Scientific analyses consume Relaxations.

```text
Relaxation
      ↓
Analysis
```

---

# 8. Scientific Questions

The Relaxations Collection enables users to answer questions such as:

- Did the structure converge?
- How much did the atoms move?
- Did reconstruction occur?
- What is the relaxed interface geometry?
- Which relaxation should be analyzed?

---

# 9. Example Workflow

```python
project = Project.open("lif_li2o")

interface = project.interfaces.get(interface_id)

relaxation = project.relaxations.run(
    interface=interface,
)

if not relaxation.converged:

    relaxation = project.relaxations.restart(
        relaxation,
    )

project.relaxations.export(
    relaxation,
    "relaxed_interface.vasp",
)
```

---

# 10. Design Rationale

Structural relaxation represents the transition from constructed
interface models to physically equilibrated atomic structures.

The Relaxations Collection groups all simulation-oriented operations
into a single public interface while separating them from geometry
construction and scientific analysis.

This organization mirrors the scientific workflow while preserving a
clear separation of responsibilities between collections.

---

# Summary

The Relaxations Collection owns every persisted `Relaxation` object and
provides the public interface for executing and managing structural
optimization workflows.

It bridges atomistic interface construction and scientific analysis by
producing physically relaxed structures together with complete
computational provenance.

The next chapter specifies the **Analyses Collection**, which consumes
persisted Relaxation objects to compute derived scientific quantities
and interpret simulation results.
