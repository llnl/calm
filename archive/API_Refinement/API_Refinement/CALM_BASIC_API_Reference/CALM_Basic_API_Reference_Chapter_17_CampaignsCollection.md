# CALM Basic API Reference

# Chapter 17 — CampaignsCollection

## Overview

`CampaignsCollection` is the public interface for creating, executing,
monitoring, retrieving, querying, exporting, and deleting scientific
campaigns.

It owns every persisted `Campaign` object.

A Campaign coordinates multiple scientific workflows performed within a
Project. Unlike scientific collections such as Materials or Interfaces,
Campaigns organize computational work rather than scientific objects.

`CampaignsCollection` is accessed through:

```python
project.campaigns
```

---

# Purpose

The Campaigns Collection is responsible for coordinating scientific
investigations that span many calculations.

It supports:

- campaign creation,
- campaign execution,
- campaign monitoring,
- workflow resumption,
- querying,
- export,
- lifecycle management.

It does **not** perform scientific calculations itself.

Scientific work continues to be delegated to the appropriate
collections.

---

# Methods

## `create`

### Signature

```python
create(
    *,
    name,
    description=None,
    metadata=None,
) -> Campaign
```

### Description

Creates a new Campaign.

A newly created Campaign contains no completed workflow stages.

---

### Parameters

#### `name`

Human-readable campaign name.

---

#### `description`

Optional campaign description.

---

#### `metadata`

Optional user-defined metadata.

---

### Returns

```python
Campaign
```

The newly created Campaign.

---

### Side Effects

Creates one persisted Campaign.

Updates project provenance.

---

### Raises

- `DuplicateObjectError`
- `CampaignCreationError`

---

## Example

```python
campaign = project.campaigns.create(
    name="LiF–Li₂O Screening",
)
```

---

## Execution and orchestration

Campaigns primarily function as metadata and provenance containers in the
current public contract. At present, the canonical way to execute or attach
work to a campaign is to create a campaign and a deterministic campaign run via
the Project facade and then pass the resulting campaign identifiers into the
existing downstream stage-run helpers and dataset persistence calls. For
example:

```python
camp = proj.create_campaign(name="LiF Study", spec={})
cr = proj.create_or_get_campaign_run(camp["uid_full"], run_spec={"a":1}, backend_id="deterministic")
proj.run_energy_stage(["proto:1"], campaign_uid_full=camp["uid_full"], campaign_run_uid_full=cr["uid_full"])
proj.save(dataset, name="ds", campaign_uid_full=camp["uid_full"], campaign_run_uid_full=cr["uid_full"])
```

The `CampaignsCollection` in the public facade is therefore primarily a
query/reporting surface (`project.campaigns()`) and a place to retrieve
campaign metadata and associated runs. A self-contained campaign-run
execution/resume orchestration API (`CampaignsCollection.run` /
`CampaignsCollection.resume`) is aspirational and deferred until a dedicated
campaign-execution model is stabilized and implemented.

---

## Example

```python
project.campaigns.run(
    campaign,
)
```

---

## `resume`

### Signature

```python
resume(
    campaign,
)
```

### Description

Resumes an interrupted Campaign.

Previously completed workflow stages are preserved.

---

## Example

```python
project.campaigns.resume(
    campaign,
)
```

---

## `list`

### Signature

```python
list() -> list[Campaign]
```

Returns every persisted Campaign.

---

## `get`

### Signature

```python
get(
    identifier,
) -> Campaign
```

Retrieves one persisted Campaign.

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Campaign]
```

Returns Campaigns satisfying scientific criteria.

Supported criteria include:

- name,
- status,
- creation date,
- completion date,
- material system,
- tags.

---

## Example

```python
campaigns = project.campaigns.find(
    status="running",
)
```

---

## `export`

### Signature

```python
export(
    campaign,
    destination,
    *,
    format=None,
)
```

### Description

Exports a Campaign summary.

Typical outputs include:

- workflow reports,
- provenance summaries,
- execution summaries,
- publication supplements.

---

## Example

```python
project.campaigns.export(
    campaign,
    "campaign_report.pdf",
)
```

---

## `delete`

### Signature

```python
delete(
    campaign,
)
```

### Description

Removes one persisted Campaign.

Deleting a Campaign does not delete scientific objects generated during
the Campaign.

---

# Collection Properties

`CampaignsCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Create a Campaign

```python
campaign = project.campaigns.create(
    name="High-Throughput Screening",
)
```

---

## Execute a Campaign

```python
project.campaigns.run(
    campaign,
)
```

---

## Resume a Campaign

```python
project.campaigns.resume(
    campaign,
)
```

---

## Query Campaigns

```python
running = project.campaigns.find(
    status="running",
)
```

---

## Export a Campaign Report

```python
project.campaigns.export(
    campaign,
    "campaign.pdf",
)
```

---

# Design Notes

Campaigns coordinate scientific work.

They do not own the scientific objects produced during that work.

Instead, they record:

- workflow intent,
- execution state,
- scheduling information,
- computational provenance.

This separation allows scientific objects to remain reusable while
Campaigns provide higher-level organization of large computational
studies.

---

# See Also

- `Project`
- `Campaign`
- `DatasetsCollection`
- `Dataset`
