# CALM Basic API Specification

# Chapter 18 — API Governance and Evolution

## Purpose

This chapter defines the long-term governance of the CALM Basic API.

The objective is to ensure that the Basic API evolves in a deliberate,
predictable, and scientifically consistent manner.

The Basic API is intended to become the primary public interface for
CALM. As the project grows, new functionality should strengthen the
existing API rather than fragment it.

---

# 1. Scope of the Basic API

The Basic API is intended to support the complete scientific workflows
defined in the CALM Basic API Design Handbook.

It shall provide a coherent interface for the majority of CALM users.

More specialized workflows may require advanced interfaces, but common
scientific investigations should remain entirely within the Basic API.

---

# 2. API Stability

The Basic API represents the long-term public contract of CALM.

Public behavior should evolve cautiously.

Changes that alter public semantics should occur only when they provide
clear scientific or usability benefits.

Internal implementation may evolve independently provided that public
behavior remains consistent with this specification.

---

# 3. Criteria for Adding New Functionality

New public functionality should satisfy the following criteria.

## Scientific Motivation

The functionality should correspond to a meaningful scientific concept
or workflow.

The Basic API should not expose implementation utilities.

---

## Consistency

The functionality should integrate naturally into the existing object
model and collection architecture.

Whenever possible, existing vocabulary should be reused.

---

## Discoverability

A scientist should be able to discover the new functionality by
reasoning about the scientific workflow.

If the correct collection or operation is not obvious, the proposed API
should be reconsidered.

---

## Workflow Integration

New functionality should extend existing workflows rather than introduce
parallel workflows.

Whenever possible, new capabilities should consume and produce persisted
scientific objects already defined by the specification.

---

# 4. Evaluating Proposed API Changes

Every proposed addition to the Basic API should answer the following
questions.

## Does it introduce a new scientific object?

If yes, should that object become first-class?

---

## Does it belong to an existing collection?

If yes, extending an existing collection is generally preferred over
creating a new one.

---

## Does it introduce a genuinely new scientific operation?

If yes, the operation should use terminology consistent with the Basic
API vocabulary.

---

## Does it preserve the object lifecycle?

New functionality should integrate with the established provenance graph.

---

# 5. Backward Compatibility

The Basic API should evolve conservatively.

When public behavior changes:

- migration paths should be provided where practical;
- deprecated behavior should remain available for an appropriate
  transition period;
- documentation should clearly identify changes.

Scientific reproducibility should always take precedence over API
convenience.

---

# 6. Relationship to Advanced APIs

The Basic API does not attempt to expose every capability of CALM.

Advanced interfaces may provide:

- lower-level control,
- experimental functionality,
- performance optimizations,
- specialized workflows.

However, advanced APIs should complement—not replace—the Basic API.

Whenever a capability becomes part of common scientific practice, it
should be evaluated for inclusion in the Basic API.

---

# 7. Relationship to the Handbook

The CALM Basic API Design Handbook and this specification are
complementary.

The handbook answers:

> "How do scientists perform scientific investigations using CALM?"

The specification answers:

> "What public API supports those investigations?"

The handbook motivates the specification.

The specification defines the public contract.

Both documents should evolve together.

---

# 8. Specification Maintenance

Future revisions of the specification should:

- preserve the object model;
- preserve collection consistency;
- preserve workflow semantics;
- preserve provenance;
- preserve scientific readability.

Changes should strengthen the overall coherence of the Basic API rather
than addressing isolated implementation concerns.

---

# 9. Guiding Principle

The Basic API should continue to evolve toward a single objective:

> A scientist should be able to understand, discover, and perform an
> entire computational materials science workflow by reasoning about the
> scientific problem rather than the software implementation.

Every future API decision should reinforce this objective.

---

# Summary

This chapter establishes the governance model for the CALM Basic API.

Together with the preceding chapters, it defines not only the current
public interface, but also the principles by which that interface should
continue to evolve.

The CALM Basic API Specification therefore serves as the long-term
architectural contract for the public API, while the CALM Basic API
Design Handbook provides the corresponding scientific workflow guide.

Together, these documents define a coherent, discoverable, and
scientifically meaningful public interface for CALM.
