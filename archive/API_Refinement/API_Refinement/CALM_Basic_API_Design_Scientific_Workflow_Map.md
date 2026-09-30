# CALM Basic API Design Handbook

# Chapter 00 --- Scientific Workflow Map

## Purpose

Before reviewing or redesigning the CALM basic API, we first
establish the scientific questions that users come to CALM to answer.
These questions define the desired workflow and therefore should drive
the public API. The tutorial and API review in subsequent chapters will
be organized around these tasks rather than around implementation
details.

------------------------------------------------------------------------

# Level 0 --- Project Setup

## Scientific Goal

Establish a reproducible scientific investigation.

### Questions

-   How do I start a new CALM project?
-   How do I reopen an existing project?
-   Which MLIP foundation model should I use?
-   What metadata should be recorded?
-   How do I make this workflow reproducible?

------------------------------------------------------------------------

# Level 1 --- Materials

## Scientific Question

**What materials am I studying?**

### Tasks

-   Import crystal structures.
-   List stored materials.
-   Retrieve a specific material.
-   Inspect composition, symmetry, and lattice parameters.
-   Export structures.

### Questions

-   Which polymorphs are available?
-   What is the space group?
-   Is the structure primitive or conventional?
-   How many materials are in the project?

------------------------------------------------------------------------

# Level 2 --- Surface Models

## Scientific Question

**What surfaces should I study?**

### Tasks

-   Generate surface primitive cells.
-   Generate slabs.
-   Generate multiple Miller orientations.
-   Enumerate terminations.
-   Store and retrieve surfaces.
-   Export surface models.

### Questions

-   Which orientations exist?
-   Which terminations are stoichiometric?
-   Which surfaces are polar?
-   Which surfaces are symmetry equivalent?
-   Which surfaces minimize surface cell size?

------------------------------------------------------------------------

# Level 3 --- Interface Matching

## Scientific Question

**Can these materials form coherent interfaces?**

### Tasks

-   Select two surfaces.
-   Perform lattice matching.
-   Store interface matches.
-   List and filter matches.
-   Export summary tables.
-   Generate Pareto plots.

### Questions

-   Which interfaces minimize strain?
-   Which minimize interface area?
-   Which are Pareto optimal?
-   Which orientation relationship is preferred?

------------------------------------------------------------------------

# Level 4 --- Interface Construction

## Scientific Question

**What does the interface actually look like?**

### Tasks

-   Generate candidate interface structures.
-   Apply strain partitioning.
-   Enumerate stacking registries.
-   Store and retrieve interface models.
-   Export structures.

### Questions

-   How should strain be partitioned?
-   Which registries are physically meaningful?
-   Which interface is smallest?
-   Which is most representative?

------------------------------------------------------------------------

# Level 5 --- Registry Optimization

## Scientific Question

**What is the optimal lateral registry?**

### Tasks

-   Perform Monte Carlo registry optimization.
-   Compare candidate registries.
-   Store optimized interfaces.

### Questions

-   Which registry minimizes energy?
-   Is the optimum unique?
-   How sensitive is the interface to translation?

------------------------------------------------------------------------

# Level 6 --- Structural Relaxation

## Scientific Question

**What is the relaxed atomic structure?**

### Tasks

-   Run structural relaxations.
-   Monitor convergence.
-   Restart interrupted calculations.
-   Compare relaxed structures.

### Questions

-   Did relaxation converge?
-   How much did atoms move?
-   Did reconstruction occur?

------------------------------------------------------------------------

# Level 7 --- Energetics

## Scientific Question

**Is the interface thermodynamically favorable?**

### Tasks

-   Compute interface energies.
-   Compute adhesion energies.
-   Compute work of separation.
-   Store calculated properties.
-   Compare interfaces.

### Questions

-   Which interface is most stable?
-   Which orientation is preferred?
-   How much energy is recovered through reconstruction?

------------------------------------------------------------------------

# Level 8 --- Analysis

## Scientific Question

**Why is this interface favorable?**

### Tasks

-   Analyze strain.
-   Analyze bonding.
-   Analyze coordination.
-   Analyze charge redistribution.
-   Analyze structural changes.

### Questions

-   Where is strain localized?
-   Which atoms reconstruct?
-   Which bonds form?
-   What stabilizes the interface?

------------------------------------------------------------------------

# Level 9 --- Dataset Generation

## Scientific Question

**How do I build a reusable dataset?**

### Tasks

-   Export structures.
-   Export metadata.
-   Export descriptors.
-   Export calculated properties.
-   Export provenance.

### Questions

-   Is the dataset reproducible?
-   Is the metadata complete?
-   Is it suitable for machine learning?

------------------------------------------------------------------------

# Level 10 --- Campaigns

## Scientific Question

**How do I study many interfaces efficiently?**

### Tasks

-   Execute parameter sweeps.
-   Process many material pairs.
-   Resume interrupted workflows.
-   Aggregate campaign results.

### Questions

-   Which material combinations are most promising?
-   What trends emerge?
-   Which systems warrant further study?

------------------------------------------------------------------------

# Cross-Cutting Themes

## Provenance

-   Where did this object originate?
-   Which workflow generated it?
-   Which parameters were used?

## Persistence

-   Has this object already been generated?
-   Can it be retrieved?
-   Should it be regenerated?

## Reproducibility

-   Can another scientist reproduce this workflow?
-   Are all parameters stored with the project?

## Querying

Examples include:

-   Show all surfaces for a material.
-   Show all interfaces involving a material.
-   Show all relaxed interfaces.
-   Show failed calculations.

## Comparison

-   Compare interfaces.
-   Compare relaxations.
-   Compare MLIPs.
-   Compare surface terminations.

------------------------------------------------------------------------

# Design Principle

The basic API should be organized around answering scientific
questions rather than exposing computational primitives. Each tutorial
chapter will therefore begin with a scientific objective, demonstrate
the corresponding workflow using the current public API, evaluate that
experience, and then propose an improved basic API that better
supports the same scientific investigation.
