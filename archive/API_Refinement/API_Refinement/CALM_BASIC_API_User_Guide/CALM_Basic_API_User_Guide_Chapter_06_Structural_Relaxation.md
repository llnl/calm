# CALM Basic API User Guide

# Chapter 6 — Structural Relaxation

## Scientific Objective

The atomistic Interface constructed in the previous chapter represents a
physically reasonable initial model.

The next step is to allow the atoms to relax toward their equilibrium
configuration.

In this chapter you will retrieve a persisted Interface, perform a
structural relaxation, monitor its progress, inspect the resulting
Relaxation, and export the relaxed structure.

By the end of this chapter you will be able to:

- retrieve persisted Interfaces,
- perform structural relaxations,
- restart interrupted calculations,
- inspect Relaxation objects,
- retrieve previously completed Relaxations,
- export relaxed structures.

The resulting Relaxation becomes the foundation for scientific analysis.

---

## Workflow

### Retrieve an Interface

Structural relaxation always begins with a previously constructed
Interface.

```python
interface = project.interfaces.get(
    interface_id,
)
```

The Interface is retrieved from the Project.

No interface construction is repeated.

---

### Run a Structural Relaxation (canonical public workflow)

Execute a structural optimization using the project-backed stage API or the
single-interface convenience method. The repository currently treats the
project-stage API as the canonical, durable public contract for persisted
simulations. A future `RelaxationsCollection` object model is documented as an
aspirational API but is deferred until the project-backed contract is stabilized.

Project-backed (recommended for persisted runs):

```python
# Run a persisted relaxation over a set of prototype ids / persisted objects
proj.run_relaxation_stage(["proto:1"], max_steps=200, backend="deterministic")
```

Single-interface convenience (non-orchestration / ephemeral):

```python
interface.relax(calculator=my_calc, fmax=0.05)
```

The project-backed entrypoint is the supported path to obtain persisted run
records and to ensure that reopen/resume semantics and provenance are recorded.
The `InterfaceModel.relax()` helper is useful for one-off local calls but does
not replace the project-backed persisted run semantics.

---

### Inspect Relaxation Status

Determine whether the calculation converged.

```python
print(relaxation.converged)

print(relaxation.steps)

print(relaxation.energy)
```

These properties describe the completed relaxation.

---

### Restart an Incomplete Relaxation

If necessary, continue a previously interrupted calculation.

```python
project.relaxations.restart(
    relaxation,
)
```

Restarting preserves the scientific identity of the Relaxation while
extending its computational history.

---

### Retrieve a Relaxation

Previously completed Relaxations can be retrieved directly from the
Project.

```python
relaxation = project.relaxations.get(
    relaxation_id,
)
```

Scientific workflows retrieve Relaxations from the Project rather than
rerunning calculations.

---

### Query Relaxations

Locate Relaxations using scientific criteria.

```python
completed = project.relaxations.find(
    converged=True,
)
```

or

```python
relaxations = project.relaxations.find(
    interface=interface,
)
```

Queries return persisted Relaxation objects.

---

### Inspect the Relaxed Structure

Every Relaxation records both the input Interface and the resulting
relaxed structure.

```python
print(relaxation.structure)

print(relaxation.calculator)

print(relaxation.optimizer)
```

The Relaxation represents a permanent scientific record of the
calculation.

---

### Retrieve Analyses

At this stage no scientific analyses have yet been performed.

Nevertheless, every Relaxation exposes the relationship to the Analysis
objects that will later be derived from it.

```python
analyses = relaxation.analyses
```

Initially this collection is empty.

---

### Export the Relaxed Structure

Export the relaxed atomic structure.

```python
relaxation.export(
    "relaxed_interface.vasp",
)
```

or

```python
project.relaxations.export(
    relaxation,
    "relaxed_interface.vasp",
)
```

Export never modifies the persisted Relaxation.

---

## Discussion

Structural relaxation represents the first computational simulation in
the CALM workflow.

Unlike interface construction, which builds a structural model,
relaxation performs a physical optimization of atomic coordinates.

The Basic API intentionally records the result as a new scientific
object:

```text
Interface
      ↓
Relaxation
```

The original Interface is preserved.

The Relaxation records:

- the input Interface,
- the computational procedure,
- the relaxation trajectory,
- the final relaxed structure.

This separation preserves complete scientific provenance and allows
multiple Relaxations to be performed on the same Interface using
different computational settings.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Persisted Interfaces can be retrieved | ✓ |
| Structural relaxations can be executed | ✓ |
| Relaxations become persisted scientific objects | ✓ |
| Relaxations can be restarted | ✓ |
| Relaxations can be retrieved | ✓ |
| Relaxations can be queried | ✓ |
| Relaxation properties are directly accessible | ✓ |
| Relaxed structures can be exported | ✓ |
| Downstream workflows retrieve persisted Relaxations rather than rerunning calculations | ✓ |

---

## Summary

In this chapter you performed a structural relaxation on a previously
constructed Interface.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,
- Atomistic Interfaces,
- Structural Relaxations,

with complete provenance linking every Relaxation to its parent
Interface.

The relaxed structure is now ready for scientific interpretation.

In the next chapter you will compute derived scientific quantities such
as interface energy, adhesion energy, and strain, transforming
simulation results into scientific understanding.
