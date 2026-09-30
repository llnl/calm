# CALM Basic API Specification

# Chapter 3 --- Object Lifecycle and Workflow Semantics

## Purpose

This chapter defines how scientific objects move through the CALM Basic
API. It establishes the lifecycle rules that govern relationships
between objects, the responsibilities of collections, and the semantics
of workflow operations.

The goal is to ensure that every workflow follows a consistent,
project-centered model.

------------------------------------------------------------------------

# 1. Scientific Object Lifecycle

The Basic API shall support the following lifecycle:

``` text
Material
    ↓ generate
Surface
    ↓ search
Match
    ↓ build
Interface
    ↓ optimize
Optimized Interface
    ↓ relax
Relaxation
    ↓ analyze
Analysis
    ↓ export
Dataset
```

Each workflow stage consumes persisted objects and produces new
persisted objects.

------------------------------------------------------------------------

# 2. Parent--Child Relationships

Every derived object shall retain references to the objects from which
it was created.

  Object       Parent Objects
  ------------ ---------------------------------
  Surface      Material
  Match        Film Surface, Substrate Surface
  Interface    Match
  Relaxation   Interface
  Analysis     Relaxation and/or Interface
  Dataset      Project Objects

These relationships define scientific provenance.

------------------------------------------------------------------------

# 3. Workflow Rules

## Rule 1

Generation operations shall never modify their input objects.

They shall create new persisted objects.

## Rule 2

Downstream workflow stages shall consume persisted project objects
rather than reconstructing equivalent objects in memory.

## Rule 3

Collections own the creation of the objects they produce.

For example:

-   Materials create `Material`.
-   Surfaces generate `Surface`.
-   Matches generate `Match`.
-   Interfaces build `Interface`.

------------------------------------------------------------------------

# 4. Persistence Semantics

The project is the canonical source of scientific state.

Once an object has been persisted:

-   later workflow stages should retrieve it,
-   provenance should remain intact,
-   duplicate reconstruction should be avoided.

------------------------------------------------------------------------

# 5. Workflow Composition

Workflow stages compose through persisted objects.

Examples:

``` python
material = project.materials.get("LiF")

surface = project.surfaces.generate(material=material)

match = project.matches.generate(
    film=surface,
    substrate=other_surface,
)

interface = project.interfaces.generate(match=match)
```

Each operation advances the scientific workflow while preserving
provenance.

------------------------------------------------------------------------

# 6. Lifecycle Consistency

Collections shall not bypass the lifecycle.

For example, if a `Match` is defined as the result of matching two
persisted surfaces, the Basic API should not require users to
reconstruct surfaces or construct matches from unrelated transient
objects during the normal workflow.

------------------------------------------------------------------------

# Summary

This chapter defines the semantic rules governing scientific object
lifecycles within the CALM Basic API. Together with the object model and
collection contract, these rules establish a consistent workflow in
which persisted scientific objects flow naturally from one stage of an
investigation to the next.
