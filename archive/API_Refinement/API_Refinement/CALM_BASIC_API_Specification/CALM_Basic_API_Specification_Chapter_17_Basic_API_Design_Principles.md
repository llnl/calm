# CALM Basic API Specification

# Chapter 17 — Basic API Design Principles

## Purpose

This chapter summarizes the architectural principles that govern the
CALM Basic API.

Unlike previous chapters, which specify public objects, collections, and
workflow behavior, this chapter specifies the design philosophy that
future Basic API development shall follow.

These principles provide the long-term contract against which future API
extensions should be evaluated.

---

# 1. Scientific Workflows Drive the API

The Basic API shall be organized around scientific investigations rather
than software implementation.

Scientists should interact with concepts such as:

- materials,
- surfaces,
- interface matches,
- interfaces,
- relaxations,
- analyses,

rather than implementation concepts such as:

- databases,
- records,
- identifiers,
- storage layers.

Scientific intent shall always take precedence over implementation
convenience.

---

# 2. The Project is the Canonical Scientific Context

Every scientific investigation begins with a Project.

The Project owns:

- every scientific object,
- every collection,
- every workflow,
- every provenance relationship.

The Project is the canonical source of scientific state.

---

# 3. Scientific Objects are First-Class Concepts

The Basic API shall expose only meaningful scientific objects.

Examples include:

- Material,
- Surface,
- Match,
- Interface,
- Relaxation,
- Analysis,
- Dataset,
- Campaign.

Internal implementation objects shall remain outside the Basic API.

---

# 4. Collections Own Scientific Objects

Every scientific object belongs to exactly one collection.

Collections are responsible for:

- creation,
- retrieval,
- querying,
- export,
- lifecycle management.

Ownership shall be unambiguous.

---

# 5. Scientific Workflows Consume Persisted Objects

Once a scientific object has been persisted, all downstream workflow
stages shall retrieve that object from the Project.

The Basic API shall discourage reconstruction of scientific objects that
already exist within the Project.

This principle preserves provenance and reinforces reproducibility.

---

# 6. Derived Objects Preserve Provenance

Every derived scientific object shall retain references to its parent
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

The provenance graph shall remain complete throughout the lifetime of
the Project.

---

# 7. Collections Shall Behave Consistently

Equivalent scientific operations shall use identical method names.

Examples include:

```python
get(...)

list(...)

find(...)

export(...)
```

Users who understand one collection should immediately understand every
other collection.

---

# 8. Method Names Reflect Scientific Meaning

Method names shall describe the scientific operation being performed.

Examples include:

- `import()` — import external scientific data,
- `generate()` — derive new scientific objects,
- `search()` — perform scientific searches,
- `build()` — construct scientific models,
- `run()` — execute scientific simulations,
- `export()` — produce external scientific artifacts.

The Basic API shall avoid multiple names for the same scientific action.

---

# 9. The Basic API Hides Implementation Details

Users should not need to understand:

- persistence layers,
- database schemas,
- storage formats,
- internal identifiers,
- internal helper objects.

Implementation details shall remain behind the public interface.

---

# 10. Discoverability is a Design Requirement

Scientific workflows should be discoverable through the public API
itself.

Users should not need to inspect implementation code in order to perform
common scientific tasks.

If a workflow cannot be discovered using the public interface, the Basic
API should be considered incomplete regardless of whether the underlying
implementation exists.

---

# 11. Reproducibility is Fundamental

Every workflow shall preserve sufficient information to reproduce the
scientific investigation.

This includes:

- parent relationships,
- computational settings,
- workflow parameters,
- scientific metadata,
- provenance.

Reproducibility is a property of the API, not merely of the
implementation.

---

# 12. The Basic API Optimizes for Scientific Readability

Code written using the Basic API should read like a scientific workflow.

For example:

```python
project.materials.import(...)

project.surfaces.generate(...)

project.matches.search(...)

project.interfaces.build(...)

project.relaxations.run(...)

project.analyses.run(...)
```

The sequence of operations should communicate the scientific
investigation without requiring explanation of implementation details.

---

# 13. Consistency Takes Precedence Over Convenience

New functionality should integrate into the existing object model and
collection vocabulary.

Introducing special cases or alternative interfaces should be avoided
unless they represent genuinely different scientific concepts.

Consistency across collections reduces cognitive load and improves
discoverability.

---

# 14. Scientific Results are Immutable

Scientific objects represent completed workflow stages.

Once created, they should be treated as immutable records of the
scientific investigation.

When a workflow produces a fundamentally new scientific result, it
should create a new persisted object rather than modifying an existing
one.

Refinement operations explicitly identified by the specification are the
only exceptions to this rule.

---

# 15. Workflow Stages Have Clear Responsibilities

Each workflow stage has a single responsibility.

Examples include:

- Materials own bulk structures.
- Surfaces own surface models.
- Matches own crystallographic relationships.
- Interfaces own atomistic interface structures.
- Relaxations own structural optimization.
- Analyses own scientific interpretation.

Responsibilities shall not overlap unnecessarily.

---

# 16. The Specification is the Public Contract

This specification defines the intended behavior of the CALM Basic API.

Implementation choices may evolve.

The public semantics defined here shall remain stable unless revised by
the specification itself.

Future API evolution should extend this specification rather than
circumvent it.

---

# Summary

The CALM Basic API is organized around scientific investigations rather
than software implementation.

Its design is governed by a small set of consistent principles:

- Projects own investigations.
- Collections own scientific objects.
- Scientific objects preserve provenance.
- Workflows consume persisted objects.
- Collections expose a uniform interface.
- Scientific concepts remain independent of implementation details.

Together with the preceding specification chapters, these principles
define the long-term public contract for the CALM Basic API.

Future development should be evaluated against these principles to
ensure that the API remains coherent, discoverable, reproducible, and
faithful to the scientific workflow it is intended to support.
