# CALM Basic API Reference

# Chapter 18 — Campaign

## Overview

`Campaign` represents a persisted scientific investigation that
coordinates one or more computational workflows within a CALM Project.

Unlike scientific objects such as `Material`, `Surface`, or
`Relaxation`, a Campaign does not represent a scientific result.

Instead, it records the execution of a coordinated computational study.

Campaign objects are created by the `CampaignsCollection` and retrieved
from the Project rather than instantiated directly by users.

---

# Construction

Campaign objects are not constructed directly.

They are created through the Campaigns Collection.

Example:

```python
campaign = project.campaigns.create(
    name="LiF–Li₂O Screening",
)
```

---

# Properties

## `id`

Type

```python
ObjectId
```

Persistent scientific identity.

Read-only.

---

## `name`

Type

```python
str
```

Human-readable campaign name.

Read-only.

---

## `description`

Type

```python
str | None
```

Optional campaign description.

Read-only.

---

## `status`

Type

```python
CampaignStatus
```

Current execution status.

Typical values include:

- `"created"`
- `"running"`
- `"paused"`
- `"completed"`
- `"failed"`

Read-only.

---

## `created`

Type

```python
datetime
```

Campaign creation timestamp.

Read-only.

---

## `started`

Type

```python
datetime | None
```

Execution start time.

Read-only.

---

## `completed`

Type

```python
datetime | None
```

Execution completion time.

Read-only.

---

## `progress`

Type

```python
Progress
```

Current execution progress.

Typical information includes:

- completed tasks,
- remaining tasks,
- percentage complete.

Read-only.

---

## `metadata`

Type

```python
Metadata
```

Campaign metadata.

Examples include:

- authors,
- tags,
- computational resources,
- scheduling information,
- notes.

Read-only.

---

## `project`

Type

```python
Project
```

Owning Project.

Read-only.

---

# Relationships

Campaigns coordinate scientific workflows.

They may reference:

```python
campaign.materials

campaign.interfaces

campaign.relaxations

campaign.datasets
```

These relationships represent work coordinated by the Campaign rather
than ownership of scientific objects.

All relationships are read-only.

---

# Methods

Campaign intentionally exposes very few public methods.

Execution belongs to the `CampaignsCollection`.

---

## `export`

### Signature

```python
export(
    destination,
    *,
    format=None,
)
```

### Description

Convenience wrapper for

```python
project.campaigns.export(
    self,
    destination,
)
```

Export never modifies the Campaign.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise summary of the Campaign.

Typical information includes:

- name,
- status,
- progress,
- number of workflow stages,
- execution history.

---

# Immutability

Campaign identity is immutable.

Execution state may evolve as the Campaign progresses.

Examples include:

- status,
- progress,
- completion time.

These changes do not alter the Campaign's scientific identity.

---

# Equality

Two Campaign objects are equal if they represent the same persisted
Campaign.

Example:

```python
campaign_a == campaign_b
```

evaluates scientific identity.

---

# Scientific Questions

A Campaign enables users to answer questions such as:

- What investigation is currently running?
- Which workflow stages have completed?
- Which calculations remain?
- Has this Campaign finished?
- Which datasets were produced?

---

# Examples

## Retrieve a Campaign

```python
campaign = project.campaigns.get(
    campaign_id,
)
```

---

## Inspect status

```python
print(campaign.status)

print(campaign.progress)
```

---

## Export a report

```python
campaign.export(
    "campaign_report.pdf",
)
```

---

# Design Notes

Campaigns intentionally represent scientific work rather than scientific
results.

This distinction allows the same scientific objects to participate in
multiple investigations while preserving a complete record of how those
investigations were executed.

Campaigns therefore complement the provenance model without becoming
part of the scientific object hierarchy itself.

---

# See Also

- `Project`
- `CampaignsCollection`
- `Dataset`
- `DatasetsCollection`
- `Analysis`
