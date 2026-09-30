# CALM Basic API Specification

# Chapter 12 — Object Identity

## Purpose

This chapter defines how scientific objects are uniquely identified,
referenced, and compared within the CALM Basic API.

The objective is to provide a consistent identity model that supports
scientific workflows while minimizing the user's need to reason about
internal persistence mechanisms.

Object identity is fundamental to every workflow because persisted
scientific objects are retrieved repeatedly throughout an investigation.

---

# 1. Design Goals

Object identity shall:

- uniquely identify every persisted scientific object;
- remain stable for the lifetime of the object;
- support reproducible scientific workflows;
- avoid exposing persistence implementation details;
- provide a consistent retrieval experience across every collection.

---

# 2. Scientific Identity

Every persisted scientific object possesses a unique scientific identity.

Scientific identity is distinct from:

- object labels,
- human-readable names,
- file names,
- exported artifacts.

Scientific identity exists solely to distinguish one persisted object
from another.

---

# 3. Object References

The Basic API shall support two forms of object reference.

## Direct Object Reference

Whenever a scientific object is already available, downstream workflow
stages should accept the object directly.

Example:

```python
material = project.materials.get("LiF")

project.surfaces.generate(
    material=material,
)
```

Passing scientific objects directly is the preferred workflow because it
reinforces the object lifecycle.

---

## Identity-Based Reference

Objects may also be retrieved using their persistent identity.

Example:

```python
material = project.materials.get(material_id)
```

The Basic API shall support this workflow whenever direct object
references are unavailable.

---

# 4. Human-Readable Names

Many scientific objects possess names or labels.

Examples include:

- "LiF"
- "Li₂O"
- "LiF (100)"
- "LiF–Li₂O Match 17"

These names improve readability but are **not** guaranteed to be unique.

Consequently:

- names improve usability,
- identities guarantee correctness.

---

# 5. Object Equality

Scientific object equality is determined by persistent identity.

For example:

```python
surface_a == surface_b
```

shall evaluate whether both objects represent the same persisted
scientific object.

Scientific equality is independent of:

- object names,
- exported files,
- memory location.

---

# 6. Parent Relationships

Every derived object shall retain references to its parent objects.

Examples include:

```text
Surface
    └── Material

Match
    ├── Film Surface
    └── Substrate Surface

Interface
    └── Match

Relaxation
    └── Interface

Analysis
    └── Parent Scientific Objects
```

These references are part of the object's identity and provenance.

---

# 7. Identity Preservation

Scientific identity shall remain stable.

Operations such as:

- export,
- query,
- visualization,
- analysis,

shall never change an object's identity.

Likewise, downstream workflow stages shall preserve references to the
original parent objects.

---

# 8. Derived Objects

Derived objects always receive new identities.

For example:

```text
Material
      ↓
Surface
```

The Surface is not the Material.

Likewise:

```text
Surface
      ↓
Match
```

The Match is not either parent Surface.

Every workflow stage produces a distinct scientific object with its own
identity.

---

# 9. Refinement Operations

Some workflow operations refine an existing scientific object rather
than producing a new one.

Examples include:

- strain partitioning,
- registry optimization.

These operations preserve the identity of the Interface because they are
considered refinements of the same scientific object.

The distinction between refinement and derivation shall be clearly
defined for every collection.

---

# 10. Object Retrieval

Collections shall retrieve objects using a consistent interface.

Examples:

```python
material = project.materials.get(...)

surface = project.surfaces.get(...)

match = project.matches.get(...)

interface = project.interfaces.get(...)
```

The retrieval mechanism shall not depend upon collection type.

---

# 11. Scientific Questions

The object identity model enables users to answer questions such as:

- Have I already generated this object?
- Which object produced this result?
- Which workflow created this interface?
- Which surface produced this match?
- Can I retrieve this object later?

---

# 12. Design Rationale

The Basic API intentionally separates:

- scientific identity,
- human-readable naming,
- persistence implementation.

Scientists should primarily interact with scientific objects.

Persistent identities exist to support reproducibility, provenance, and
workflow continuity without exposing implementation details.

This design reinforces the project-centered object lifecycle while
keeping the public API intuitive and consistent.

---

# Summary

Every persisted scientific object possesses a stable identity that
supports retrieval, provenance, and workflow continuity.

Derived objects receive new identities, refinement operations preserve
existing identities, and every collection exposes a uniform retrieval
interface.

The next chapter specifies **Metadata and Provenance**, defining the
scientific information that every persisted object shall record
throughout its lifetime.
