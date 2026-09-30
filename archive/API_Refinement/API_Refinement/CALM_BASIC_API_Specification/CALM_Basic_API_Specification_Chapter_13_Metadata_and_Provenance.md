# CALM Basic API Specification

# Chapter 13 — Metadata and Provenance

## Purpose

This chapter defines the metadata and provenance model of the CALM Basic
API.

The objective is to ensure that every persisted scientific object
contains sufficient information to:

- understand its scientific meaning,
- reproduce its creation,
- trace its lineage,
- support downstream workflows,
- preserve long-term reproducibility.

Metadata and provenance are considered first-class components of every
scientific object.

---

# 1. Design Goals

The metadata model shall:

- preserve scientific provenance;
- support complete workflow reproducibility;
- remain independent of persistence implementation;
- expose scientifically meaningful information;
- minimize duplication across collections.

---

# 2. Metadata Categories

Every persisted scientific object shall expose metadata belonging to
four categories.

## Scientific Metadata

Describes the scientific meaning of the object.

Examples include:

- material composition,
- Miller orientation,
- interface area,
- lattice strain,
- convergence status,
- analysis type.

Scientific metadata is specific to each collection.

---

## Workflow Metadata

Describes how the object entered the workflow.

Examples include:

- parent scientific objects,
- workflow stage,
- creation method,
- generation parameters.

Workflow metadata defines scientific provenance.

---

## Computational Metadata

Describes computational choices used to generate the object.

Examples include:

- MLIP,
- calculator,
- optimizer,
- convergence criteria,
- software version,
- computational settings.

This information enables reproducibility.

---

## Administrative Metadata

Describes project management information.

Examples include:

- creation time,
- modification time,
- project,
- labels,
- user-defined tags,
- notes.

Administrative metadata improves organization without affecting
scientific meaning.

---

# 3. Provenance Model

Every derived scientific object shall record its immediate parent
objects.

Examples include:

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
      ↓
Analysis
```

The provenance graph shall remain traversable throughout the lifetime of
the project.

---

# 4. Provenance Rules

## Rule 1

Derived objects shall never lose references to their parents.

---

## Rule 2

Workflow stages shall preserve complete provenance.

---

## Rule 3

Export operations shall preserve provenance whenever the export format
supports it.

---

## Rule 4

Deleting a parent object shall respect project dependency rules.

---

# 5. Common Metadata

Every persisted scientific object shall expose common metadata.

Examples include:

- unique identity,
- project,
- creation timestamp,
- labels,
- user notes,
- parent references.

This common metadata provides a consistent experience across all
collections.

---

# 6. Collection-Specific Metadata

Collections extend the common metadata with scientific information.

Examples include:

## Materials

- composition,
- space group,
- lattice parameters,
- crystal system.

---

## Surfaces

- parent material,
- Miller index,
- termination,
- slab thickness,
- vacuum thickness.

---

## Matches

- film surface,
- substrate surface,
- lattice strain,
- interface area,
- orientation relationship.

---

## Interfaces

- parent match,
- strain partitioning,
- registry,
- construction parameters.

---

## Relaxations

- parent interface,
- optimizer,
- convergence status,
- relaxation trajectory,
- final structure.

---

## Analyses

- parent scientific objects,
- analysis type,
- derived quantities,
- analysis parameters.

---

# 7. Metadata Access

Metadata shall be accessed through scientific objects.

Examples:

```python
material.composition

surface.miller

match.strain

interface.registry

relaxation.converged

analysis.type
```

Users should not need to access metadata through separate database
interfaces.

---

# 8. Provenance Navigation

Scientific objects shall expose navigable provenance.

Examples:

```python
surface.material

match.film

match.substrate

interface.match

relaxation.interface

analysis.relaxation
```

Navigation should be intuitive and require no database knowledge.

---

# 9. Scientific Questions

The metadata model enables users to answer questions such as:

- Where did this object originate?
- Which workflow created it?
- Which parameters were used?
- Which MLIP generated this result?
- Which Interface produced this Relaxation?
- Which Surface produced this Match?
- Is this result reproducible?

---

# 10. Design Rationale

Scientific reproducibility depends upon preserving more than atomic
structures.

It also requires preserving:

- workflow history,
- computational settings,
- parent relationships,
- scientific intent.

By making metadata and provenance part of every scientific object, the
Basic API supports reproducible computational materials science while
remaining independent of persistence implementation.

---

# Summary

Every persisted scientific object in the CALM Basic API carries
scientific metadata, workflow metadata, computational metadata, and
administrative metadata.

Together, these define a complete provenance model that supports
scientific reproducibility, workflow continuity, and intuitive
navigation of project data.

The next chapter specifies **Error Semantics**, defining the expected
public behavior of the Basic API when workflows cannot be completed or
scientific operations fail.
