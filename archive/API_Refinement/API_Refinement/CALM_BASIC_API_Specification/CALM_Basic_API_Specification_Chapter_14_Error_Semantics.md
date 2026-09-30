# CALM Basic API Specification

# Chapter 14 — Error Semantics

## Purpose

This chapter defines the expected public behavior of the CALM Basic API
when scientific operations cannot be completed.

The objective is to ensure that errors are:

- scientifically meaningful,
- predictable,
- consistent across collections,
- independent of implementation details.

This chapter specifies **public API behavior**, not implementation
exceptions.

---

# 1. Design Goals

The Basic API shall:

- report errors in scientific language;
- distinguish user errors from computational failures;
- preserve project integrity;
- never leave persisted scientific objects in an inconsistent state;
- provide sufficient information for corrective action.

---

# 2. Error Categories

The Basic API recognizes five categories of errors.

## Object Errors

Errors involving persisted scientific objects.

Examples include:

- object not found,
- duplicate object,
- object already exists,
- deleted object,
- inaccessible object.

---

## Workflow Errors

Errors arising from an invalid scientific workflow.

Examples include:

- attempting to generate surfaces from a missing material,
- attempting to build an interface without a match,
- attempting to relax an interface that does not exist,
- attempting to analyze an unfinished relaxation.

---

## Scientific Errors

Errors arising because the requested scientific operation cannot be
performed.

Examples include:

- no valid interface matches found,
- surface generation failed,
- incompatible lattices,
- unsupported crystal symmetry,
- invalid Miller orientation.

These are legitimate scientific outcomes rather than software failures.

---

## Computational Errors

Errors arising during numerical execution.

Examples include:

- structural relaxation failed to converge,
- optimizer failure,
- calculator failure,
- external program failure,
- insufficient computational resources.

These errors represent unsuccessful calculations rather than invalid
workflows.

---

## Project Errors

Errors involving project state.

Examples include:

- project cannot be opened,
- missing project,
- incompatible project version,
- corrupted project,
- write failure.

---

# 3. Error Principles

## Rule 1

Errors shall never expose internal persistence implementation.

Users should not need to understand:

- SQL,
- database schemas,
- internal identifiers,
- storage layout.

---

## Rule 2

Errors shall describe the failed scientific operation.

For example:

> Material "LiF" could not be found.

rather than

> Primary key lookup failed.

---

## Rule 3

Errors shall preserve project consistency.

Failed operations shall not partially create scientific objects.

---

## Rule 4

Errors shall preserve provenance.

Partial scientific workflows shall never corrupt existing project data.

---

# 4. Missing Objects

When an object cannot be retrieved:

```python
project.materials.get("LiF")
```

the API shall report that the requested scientific object does not
exist.

Collections shall behave consistently.

---

# 5. Empty Queries

Scientific queries may legitimately return no results.

Example:

```python
project.matches.find(
    max_strain=0.01,
)
```

An empty result is **not** an error.

It represents a valid scientific outcome.

---

# 6. Scientific Search Failures

Some scientific operations may produce no valid solutions.

Examples include:

- interface matching,
- registry optimization,
- surface generation.

These outcomes shall be reported as valid scientific results rather than
software failures whenever appropriate.

---

# 7. Computational Failures

Numerical calculations may fail.

Examples include:

- relaxation did not converge,
- optimizer exceeded iteration limit,
- calculator terminated unexpectedly.

The resulting scientific object should preserve sufficient information
to understand the failure.

Whenever practical, unsuccessful calculations should remain available
for inspection rather than being discarded.

---

# 8. Recoverability

The Basic API should distinguish between recoverable and unrecoverable
errors.

Examples of recoverable situations include:

- restarting a relaxation,
- modifying convergence criteria,
- relaxing a different interface.

Examples of unrecoverable situations include:

- deleted parent objects,
- incompatible project versions,
- corrupted project state.

---

# 9. Collection Consistency

Equivalent operations shall behave consistently across all collections.

Examples:

```python
project.materials.get(...)

project.surfaces.get(...)

project.matches.get(...)
```

shall report missing objects in a consistent manner.

Likewise:

```python
list(...)

find(...)

export(...)
```

shall exhibit consistent public behavior.

---

# 10. Scientific Questions

The error model enables users to distinguish between questions such as:

- Did I perform an invalid workflow?
- Does this scientific object exist?
- Did the calculation fail?
- Did the scientific search legitimately find no solutions?
- Can this workflow be resumed?

---

# 11. Design Rationale

Scientific software frequently encounters situations where the absence
of a result is itself scientifically meaningful.

Examples include:

- no interface match exists,
- no stable registry exists,
- relaxation does not converge.

The Basic API therefore distinguishes between:

- scientific outcomes,
- workflow errors,
- computational failures.

This distinction allows users to interpret unsuccessful workflows
correctly while maintaining a consistent public interface.

---

# Summary

The CALM Basic API defines a consistent public error model centered on
scientific workflows rather than implementation details.

Errors describe failed scientific operations, preserve project
consistency, maintain provenance, and distinguish between invalid
workflows, legitimate scientific outcomes, and computational failures.

The next chapter specifies **Project Semantics**, defining the behavior,
responsibilities, and lifecycle of the Project itself as the root object
of the Basic API.
