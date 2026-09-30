# CALM Basic API User Guide

# Chapter 5 — Interface Construction

## Scientific Objective

Once a promising crystallographic Match has been identified, the next
step is to construct an explicit atomistic Interface suitable for
simulation.

In this chapter you will retrieve a persisted Match from the Project,
construct an Interface, optimize its strain partitioning and atomic
registry, inspect the resulting structure, and export it for
visualization.

By the end of this chapter you will be able to:

- retrieve persisted Match objects,
- construct atomistic Interface structures,
- optimize strain partitioning,
- optimize atomic registry,
- inspect Interface properties,
- export Interface structures.

The resulting Interface becomes the input for atomistic structural
relaxation.

---

## Workflow

### Retrieve a Match

Interface construction begins by retrieving a previously generated Match
from the Project.

```python
match = project.matches.get(
    match_id,
)
```

The Match is retrieved from persistent storage.

No interface matching calculations are repeated.

---

### Construct an Interface

Construct an atomistic Interface from the selected Match.

```python
interface = project.interfaces.build(
    match,
)
```

The newly constructed Interface is immediately persisted within the
Project.

The parent Match remains unchanged.

---

### Optimize Strain Partitioning

Distribute lattice strain between the film and substrate.

```python
project.interfaces.partition_strain(
    interface,
)
```

This operation refines the Interface geometry while preserving the
scientific identity of the Interface.

---

### Optimize Atomic Registry

Optimize the lateral alignment between the two slabs.

```python
project.interfaces.optimize_registry(
    interface,
)
```

Registry optimization refines the existing Interface rather than
creating a new scientific object.

---

### Retrieve the Interface

Previously constructed Interfaces can be retrieved directly from the
Project.

```python
interface = project.interfaces.get(
    interface_id,
)
```

Retrieval is preferred over reconstructing the Interface.

---

### Query Existing Interfaces

Locate Interfaces using scientific criteria.

```python
interfaces = project.interfaces.find(
    match=match,
)
```

or

```python
interfaces = project.interfaces.find(
    optimized=True,
)
```

Queries always return persisted Interface objects.

---

### Inspect Interface Properties

Every Interface exposes the information required to understand the
constructed structure.

```python
print(interface.match)

print(interface.film)

print(interface.substrate)

print(interface.interface_area)

print(interface.strain)

print(interface.registry)
```

These properties describe the current state of the Interface.

---

### Retrieve Relaxations

At this stage no Relaxations have yet been performed.

Nevertheless, every Interface exposes the relationship to the
Relaxations that will later be generated from it.

```python
relaxations = interface.relaxations
```

Initially this collection is empty.

---

### Export an Interface

Export the Interface structure.

```python
interface.export(
    "lif_li2o_interface.vasp",
)
```

or

```python
project.interfaces.export(
    interface,
    "lif_li2o_interface.vasp",
)
```

Export never modifies the persisted Interface.

---

## Discussion

Interface construction transforms a crystallographic relationship into
an explicit atomistic structural model.

Unlike previous workflow stages, Interface construction is followed by
refinement operations that improve the geometry of the same scientific
object.

The Basic API therefore distinguishes between:

- construction,

and

- refinement.

Construction creates the Interface.

Subsequent operations such as:

- strain partitioning,
- registry optimization,

refine that Interface while preserving its scientific identity.

The object lifecycle therefore becomes:

```text
Match
    ↓
Interface
    ↓
Refinement
```

This allows scientists to progressively improve an Interface without
losing provenance or creating unnecessary duplicate objects.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Persisted Matches can be retrieved | ✓ |
| Interfaces can be constructed from Matches | ✓ |
| Constructed Interfaces become persisted scientific objects | ✓ |
| Strain partitioning refines an Interface | ✓ |
| Registry optimization refines an Interface | ✓ |
| Interfaces can be retrieved | ✓ |
| Interfaces can be queried | ✓ |
| Interface properties are directly accessible | ✓ |
| Interfaces can be exported | ✓ |
| Downstream workflows retrieve persisted Interfaces rather than reconstructing them | ✓ |

---

## Summary

In this chapter you constructed an explicit atomistic Interface from a
previously generated Match.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,
- Atomistic Interfaces,

with complete provenance linking every Interface to its parent Match.

The constructed Interface is now ready for atomistic structural
relaxation.

In the next chapter you will perform a structural relaxation on the
Interface and generate the relaxed atomic structure used for scientific
analysis.
