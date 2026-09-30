# CALM Basic API Specification

# Chapter 1 --- Object Model and Collection Architecture

## Purpose

This specification defines the public object model for the CALM Basic
API. It establishes the scientific objects, their ownership, and the
collection architecture that supports the workflow defined in the *CALM
Basic API Design Handbook*. This specification describes the public API
only and intentionally avoids implementation details.

------------------------------------------------------------------------

# 1. Design Goals

The Basic API shall:

-   expose scientific concepts rather than implementation concepts;
-   support the complete scientific workflow described in the handbook;
-   treat the project as the canonical source of scientific objects;
-   provide a consistent, discoverable interface;
-   minimize boilerplate for common scientific workflows.

------------------------------------------------------------------------

# 2. Scientific Object Model

The Basic API shall expose the following first-class scientific objects:

-   Project
-   Material
-   Surface
-   Match
-   Interface
-   Relaxation
-   Analysis
-   Dataset
-   Campaign

These are the primary concepts a scientist works with. Internal helper
objects and persistence mechanisms are not part of the Basic API.

------------------------------------------------------------------------

# 3. Collection Architecture

Every persisted scientific object shall belong to exactly one collection
owned by a project.

``` python
project.materials
project.surfaces
project.matches
project.interfaces
project.relaxations
project.analyses
project.datasets
project.campaigns
```

Collections are the primary entry points for discovering, creating,
retrieving, and managing scientific objects.

------------------------------------------------------------------------

# 4. Collection Responsibilities

  Collection    Consumes                Produces
  ------------- ----------------------- ------------
  materials     External structures     Material
  surfaces      Material                Surface
  matches       Surface + Surface       Match
  interfaces    Match                   Interface
  relaxations   Interface               Relaxation
  analyses      Relaxation, Interface   Analysis
  datasets      Project objects         Dataset
  campaigns     Project configuration   Campaign

Each collection owns the lifecycle of the objects it produces.

------------------------------------------------------------------------

# 5. Common Collection Vocabulary

Where applicable, collections should expose a consistent vocabulary.

  Method          Purpose
  --------------- ------------------------------
  import(...)     Import external data
  create(...)     Create directly
  generate(...)   Produce derived objects
  list(...)       Enumerate stored objects
  get(...)        Retrieve a single object
  find(...)       Query by scientific criteria
  export(...)     Write external artifacts
  delete(...)     Remove persisted objects

Not every collection requires every operation, but identical operations
should use identical names.

------------------------------------------------------------------------

# 6. Object Relationships

Objects should expose their scientific provenance through navigable
relationships.

Examples:

``` python
surface.material

match.film
match.substrate

interface.match

relaxation.interface
```

These relationships allow users to navigate the workflow naturally
without reconstructing objects.

------------------------------------------------------------------------

# 7. Persistence Rule

Once a scientific object has been persisted, downstream workflow stages
shall retrieve that object from the project rather than reconstructing
it in memory.

This rule underpins the object lifecycle presented throughout the
handbook and is the primary organizing principle of the Basic API.

------------------------------------------------------------------------

# Summary

This chapter defines the public object model and collection architecture
for the CALM Basic API. Subsequent chapters of the specification will
build on this foundation by defining the public behavior of each
collection and the workflow operations it supports.
