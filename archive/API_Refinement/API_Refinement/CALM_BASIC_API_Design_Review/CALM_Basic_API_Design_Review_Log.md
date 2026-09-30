# CALM Basic API Design Review Log

## Purpose

This document records the formal architectural review of the CALM Basic
API.

Its objective is to determine whether the Basic API is sufficiently
complete, consistent, discoverable, and scientifically meaningful to
serve as the stable public interface for CALM before implementation
begins.

Unlike the User Guide, Architecture Specification, and Reference
Specification, this document is a living engineering artifact that
records the evolution of the API during formal review.

---

# Review Objectives

The review evaluates whether the Basic API satisfies the original design
goals:

- Scientific workflows are intuitive.
- The Project is the canonical source of scientific state.
- Scientific objects are retrieved rather than reconstructed.
- Persistence and provenance are preserved.
- Implementation details remain hidden.
- The public interface is discoverable and internally consistent.

---

# Review Methodology

Each public type is evaluated using three complementary perspectives.

## Level 1 — Internal Consistency

Questions include:

- Is the purpose clearly defined?
- Are all public methods specified?
- Are public properties complete?
- Are object relationships defined?
- Are mutability rules clear?
- Are examples sufficient?

---

## Level 2 — Cross-Document Consistency

Questions include:

- Does the Architecture Specification define the concept?
- Does the Reference Specification define the public interface?
- Does the User Guide use the interface exactly as specified?

---

## Level 3 — Workflow Sufficiency

Questions include:

- Can a scientist complete the intended workflow?
- Is the workflow discoverable?
- Does the workflow preserve persistence?
- Does the workflow preserve provenance?
- Does it avoid exposing implementation details?

---

# Recommendation Criteria

Recommendations are recorded only when they:

1. materially improve the user experience,
2. improve consistency,
3. directly support the original project goals.

Pure stylistic preferences are intentionally excluded.

---

# Review Status

| Component | Status | Confidence |
|-----------|--------|------------|
| Project | Complete | High |
| MaterialsCollection | Complete | High |
| Material | Complete | High |
| SurfacesCollection | Complete | High |
| Surface | Pending | — |
| MatchesCollection | Complete | Medium–High |
| Match | Pending | — |
| InterfacesCollection | Complete | High |
| Interface | Complete | High |
| RelaxationsCollection | Complete | Very High |
| Relaxation | Complete | Very High |
| AnalysesCollection | Complete | Very High |
| Analysis | Complete | Very High |
| DatasetsCollection | Complete | Very High |
| Dataset | Complete | Very High |
| CampaignsCollection | Complete | Medium–High |
| Campaign | Complete | Medium–High |

---

# Overall Assessment

## Components Reviewed

- Project
- MaterialsCollection
- Material
- SurfacesCollection
- MatchesCollection
- InterfacesCollection
- Interface
- RelaxationsCollection
- Relaxation
- AnalysesCollection
- Analysis
- DatasetsCollection
- Dataset
- CampaignsCollection
- Campaign

---

## Recommendation Summary

| Priority | Count |
|----------|------:|
| Critical | 0 |
| High | 3 |
| Medium | 8 |
| Low | 0 |

No architectural redesign has been required.

The review has consistently strengthened confidence in the object model,
collection architecture, and workflow semantics.

Most recommendations clarify public semantics rather than altering the
overall architecture.

---

# Validated Architectural Principles

---

## V-001 — Collections Own Scientific Operations

Scientific objects expose:

- scientific state,
- provenance,
- relationships.

Collections own:

- creation,
- retrieval,
- querying,
- scientific workflows.

**Status**

Accepted.

---

## V-002 — Persisted Objects Are Retrieved

Once persisted, scientific objects are retrieved from the Project rather
than reconstructed.

**Status**

Accepted.

---

## V-003 — Parent Relationships Are Intrinsic

Relationships such as

```python
surface.material

interface.match

relaxation.interface
```

represent intrinsic scientific provenance.

They belong on scientific objects.

**Status**

Accepted.

---

## V-004 — Search Results Belong to Collections

Search results are not intrinsic object relationships.

Scientific searches remain collection responsibilities.

**Status**

Accepted.

---

## V-005 — Scientific Objects Should Remain Small

Scientific objects primarily expose:

- properties,
- provenance,
- relationships.

Collections perform work.

**Status**

Accepted.

---

## V-006 — Construction Operations Preserve Identity

Construction operations refine an existing scientific object without
creating a fundamentally new scientific result.

Examples include:

- strain partitioning,
- registry optimization.

These operations preserve Interface identity.

**Status**

Accepted.

---

## V-007 — Derivation Operations Produce New Scientific Objects

Scientific workflow stages produce new persisted scientific objects.

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

Each derivation creates a new scientific identity.

**Status**

Accepted.

---

## V-008 — Failed Computations Are Scientific Results

A failed Relaxation remains a valid scientific object.

Failure is scientifically meaningful and must preserve:

- provenance,
- trajectory,
- computational history,
- diagnostic information.

Scientific objects are not discarded merely because a calculation failed.

**Status**

Accepted.

---

## V-009 — Scientific Results Are First-Class Objects

Derived scientific quantities are represented as persisted Analysis
objects rather than primitive values.

This preserves:

- provenance,
- discoverability,
- reproducibility,
- queryability.

**Status**

Accepted.

---

## V-010 — Scientific Deliverables Are First-Class Objects

Datasets represent scientific deliverables rather than export files.

They preserve:

- provenance,
- metadata,
- scientific relationships.

**Status**

Accepted.

---

## V-011 — Organizational Abstractions Remain Separate

Campaigns organize scientific work.

Datasets organize scientific results.

Neither alters the scientific object hierarchy.

**Status**

Accepted.

---

# Recommendations

## R-001

**Priority**

Medium

**Component**

Project

**Status**

Open

**Recommendation**

Remove `ProjectConfiguration` from the Basic API.

**Discussion**

Configuration is an implementation-support abstraction rather than a
scientific concept.

Expose only:

```python
project.configure(...)
```

---

## R-002

**Priority**

Medium

**Component**

Project

**Status**

Open

**Recommendation**

Specify automatic persistence explicitly.

Projects should not require explicit save operations.

---

## R-003

**Priority**

High

**Component**

MaterialsCollection

**Status**

Open

**Recommendation**

Clarify the semantics of `import()`.

The Basic API should explicitly define the supported import workflow and
optimize for one obvious workflow.

---

## R-004

**Priority**

Medium

**Component**

MaterialsCollection

**Status**

Open

**Recommendation**

Reconsider `create()`.

If one obvious creation workflow is sufficient, removing `create()`
would simplify the public interface.

---

## R-005

**Priority**

Medium

**Component**

Material

**Status**

Open

**Recommendation**

Clarify the scientific semantics of `material.structure`.

Avoid exposing implementation-specific crystallographic types.

---

## R-006

**Priority**

Medium

**Component**

SurfacesCollection

**Status**

Open

**Recommendation**

Clarify the semantics of `generate()`.

The specification should explicitly define the unit of generation.

---

## R-007

**Priority**

High

**Component**

Surface

**Status**

Accepted

**Recommendation**

Remove `surface.matches` from the Basic API.

Rationale
---------
Matches are the result of an exploratory search operation and belong to
the `MatchesCollection` rather than being an intrinsic property of a
persisted `Surface` object. Exposing `surface.matches` encourages
database-like navigation patterns and duplicates the canonical
collection-based retrieval model.

Retrieval of related matches should be performed via the collection API:

```python
project.matches.find(film=surface)
project.matches.find(substrate=surface)
```

This change improves conceptual orthogonality (objects vs searches) and
clarifies persistence ownership.

---

## R-008

**Priority**

High

**Component**

MatchesCollection

**Status**

Open

**Recommendation**

Reconsider the return type of `search()`.

Determine whether:

```python
list[Match]
```

is sufficient or whether a dedicated search result abstraction is
necessary.

---

## R-009

**Priority**

Medium

**Component**

MatchesCollection

**Status**

Open

**Recommendation**

Explicitly specify that searches persist Match objects.

Persistence behavior should be stated normatively.

---

## R-010

**Priority**

Medium

**Component**

Relaxation

**Status**

Open

**Recommendation**

Explicitly define failed Relaxations as valid scientific objects.

Failure should preserve:

- provenance,
- trajectory,
- diagnostics.

---

## R-011

**Priority**

Medium

**Component**

Analysis

**Status**

Open

**Recommendation**

Expose primary scientific quantities as first-class Analysis
properties where practical.

Prefer:

```python
analysis.energy
```

over deeply nested result containers.

---

## R-012

**Priority**

Medium

**Component**

Campaign

**Status**

Open

**Recommendation**

Explicitly define Campaigns as optional orchestration objects.

The canonical scientific workflow should remain complete without
Campaigns.

Campaigns should be described as workflow coordinators rather than
required workflow stages.

---

# Final Assessment

After reviewing the complete public object model, collection
architecture, and scientific workflow, the Basic API demonstrates a
remarkably high degree of internal consistency.

The review identified no architectural flaws requiring redesign.

Instead, the remaining recommendations primarily strengthen:

- semantic clarity,
- discoverability,
- implementation guidance,
- consistency of public behavior.

The object lifecycle, persistence model, provenance model, and workflow
organization have all remained stable under review.

At the conclusion of this review, the Basic API appears to be
architecturally mature and approaching implementation readiness.

The remaining work consists primarily of resolving the outstanding
recommendations, updating the design documents accordingly, and
performing one final consistency pass before declaring a design freeze.

---

# Accepted Design Resolutions

The following recommendations were accepted during the formal design
review.

This section maps each accepted recommendation to the design documents
that require modification before the Basic API is declared frozen.

After the corresponding document updates have been completed, the
recommendation status should be changed from **Accepted** to
**Implemented**.

---

| ID | Resolution | Documents to Update |
|----|------------|---------------------|
| R-001 | Remove `ProjectConfiguration` from the Basic API. Retain `Project.configure(...)` as the sole public configuration interface. Implementation: delete the ProjectConfiguration reference chapter and update Project reference to document `project.configure(...)`. | Architecture Specification (Project), Reference Specification (Project), User Guide (Project Setup) |
| R-002 | Explicitly specify automatic persistence. Every create-like operation immediately persists its resulting scientific object. No explicit `save()` operation exists in the Basic API. | Architecture Specification (Project), Reference Specification (Project). |
| R-003 | Define `MaterialsCollection.import()` as importing exactly one scientific object and returning exactly one `Material`. Bulk import workflows belong to Campaigns or the Advanced API. | Reference Specification (MaterialsCollection). |
| R-006 | Explicitly define the semantics of `SurfacesCollection.generate()`. One invocation produces every scientifically valid Surface implied by the requested Miller orientations and generation parameters. | Reference Specification (SurfacesCollection). |
| R-009 | Explicitly specify that successful interface matching searches immediately persist every generated `Match`. | Reference Specification (MatchesCollection). |
| R-010 | Explicitly define that a failed Relaxation remains a valid persisted scientific object. `converged=False` describes the outcome of the calculation rather than the existence of the object. | Reference Specification (Relaxation), Architecture Specification (Relaxation semantics). |
| R-012 | Explicitly define Campaigns as optional workflow orchestration objects rather than required scientific workflow stages. | Architecture Specification (Campaigns), User Guide (Campaign chapter), Reference Specification (Campaigns). |

---

# Rejected Recommendations

The following recommendations were intentionally rejected after further
architectural review.

They are retained here to document the rationale behind the current
design.

| ID | Resolution |
|----|------------|
| R-004 | Retain `MaterialsCollection.create()`. It represents creation from an in-memory scientific structure, whereas `import()` represents creation from an external representation. These are distinct user workflows. |
| R-005 | Retain the current semantics of `material.structure`. The Basic API specifies the scientific meaning of the property rather than its concrete implementation type. |
| R-007 | Retain `surface.matches`. (Obsoleted) | 
| R-008 | Retain `MatchSearchResult` (or equivalent search abstraction). A matching search is itself a scientifically meaningful result rather than merely a list of `Match` objects. |
| R-011 | Retain `analysis.results` as the primary container for analysis-specific outputs. The generic `Analysis` object should not be specialized with properties that apply only to particular analysis types. |

---

# Design Freeze Checklist

Before declaring the Basic API frozen, verify that:

- [ ] Every accepted recommendation has been implemented.
- [ ] Every affected document has been updated.
- [ ] The User Guide remains consistent with the Reference Specification.
- [ ] The Reference Specification remains consistent with the Architecture Specification.
- [ ] Every public method used in the User Guide exists in the Reference Specification.
- [ ] Every public type described in the Reference Specification is introduced by the Architecture Specification.
- [ ] The Design Review Log contains no remaining open recommendations.

Completion of this checklist constitutes **Design Freeze v1** for the
CALM Basic API.

From this point onward, implementation should conform to the frozen
public API. Any future changes to the Basic API should begin by updating
the design documents before implementation.
