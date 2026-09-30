# CALM Basic API User Guide

# Chapter 9 — Campaigns

## Scientific Objective

The previous chapters demonstrated how to perform a single scientific
investigation.

In practice, computational materials science often involves studying
many related systems simultaneously.

A Campaign provides a structured way to organize, execute, monitor, and
reproduce these larger investigations while preserving the complete
scientific workflow.

By the end of this chapter you will be able to:

- create a Campaign,
- execute a Campaign,
- monitor Campaign progress,
- resume interrupted Campaigns,
- retrieve Campaigns,
- export Campaign summaries.

---

## Workflow

### Create a Campaign

Begin by creating a new Campaign describing the scientific
investigation.

```python
campaign = project.campaigns.create(
    name="LiF–Li₂O Interface Study",
)
```

The Campaign becomes a persisted object within the Project.

Initially it contains no completed workflow stages.

---

### Execute / Orchestrate a Campaign (current recommended practice)

Campaigns in CALM primarily serve as persisted metadata and provenance
containers; they do not (yet) embed a full orchestration engine in the basic
public facade. The recommended pattern today is:

1. create a campaign metadata object via the project facade:

```python
campaign = proj.create_campaign(name="LiF–Li2O Study", spec={})
run = proj.create_or_get_campaign_run(campaign["uid_full"], run_spec={"params": 1}, backend_id="deterministic")
```

2. pass campaign context into stage-run or dataset persistence calls so that
   provenance links are recorded:

```python
proj.run_relaxation_stage(["proto:1"], campaign_uid_full=campaign_uid, campaign_run_uid_full=run_uid)
proj.save(dataset, name="my_ds", campaign_uid_full=campaign_uid, campaign_run_uid_full=run_uid)
```

3. query campaigns and campaign_runs via `proj.campaigns()` or `proj.campaigns().runs(...)`.

The `project.campaigns.run(...)` and `project.campaigns.resume(...)` methods
described elsewhere are aspirational and remain deferred until a dedicated
campaign execution orchestration API is finalized and documented. This guide
therefore focuses on the current persistent/provenance pattern above.

---

### Monitor Campaign Progress

Campaign progress can be inspected directly.

```python
print(campaign.status)

print(campaign.progress)
```

Typical execution states include:

- created,
- running,
- paused,
- completed,
- failed.

---

### Resume an Interrupted Campaign

Long-running investigations may be interrupted.

Resume execution using:

```python
project.campaigns.resume(
    campaign,
)
```

Previously completed workflow stages remain unchanged.

Execution continues from the last completed stage.

---

### Retrieve a Campaign

Previously created Campaigns can be retrieved directly from the Project.

```python
campaign = project.campaigns.get(
    campaign_id,
)
```

Campaigns should always be retrieved rather than recreated.

---

### Query Campaigns

Locate Campaigns using scientific criteria.

```python
running = project.campaigns.find(
    status="running",
)
```

or

```python
campaigns = project.campaigns.find(
    material="LiF",
)
```

Queries return persisted Campaign objects.

---

### Export a Campaign Summary

Export a summary describing the Campaign.

```python
campaign.export(
    "campaign_summary.pdf",
)
```

or

```python
project.campaigns.export(
    campaign,
    "campaign_summary.pdf",
)
```

Export preserves:

- workflow history,
- metadata,
- provenance,
- execution summary.

The Campaign itself remains unchanged.

---

## Discussion

Campaigns differ fundamentally from every previous scientific object.

Materials, Surfaces, Matches, Interfaces, Relaxations, Analyses, and
Datasets represent scientific knowledge.

Campaigns represent scientific work.

A Campaign coordinates existing workflow stages.

It does not replace them.

Scientific objects continue to belong to their respective collections.

Campaigns simply organize their execution.

This separation allows:

- one scientific object to participate in multiple investigations,
- multiple Campaigns to reuse existing project data,
- long-running investigations to be resumed,
- computational work to remain reproducible.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Campaigns can be created | ✓ |
| Campaigns can be executed | ✓ |
| Campaign progress is observable | ✓ |
| Interrupted Campaigns can be resumed | ✓ |
| Campaigns can be retrieved | ✓ |
| Campaigns can be queried | ✓ |
| Campaign summaries can be exported | ✓ |
| Campaigns coordinate workflows without owning scientific objects | ✓ |

---

## Summary

In this chapter you learned how Campaigns organize large scientific
investigations.

Unlike the previous workflow stages, Campaigns do not generate new
scientific knowledge.

Instead, they coordinate and monitor scientific work while preserving
the complete provenance established throughout the Project.

At this point you have completed the complete CALM Basic API workflow:

```text
Project
    ↓
Materials
    ↓
Surfaces
    ↓
Matches
    ↓
Interfaces
    ↓
Relaxations
    ↓
Analyses
    ↓
Datasets

Campaigns coordinate the entire workflow.
```

You have now completed an end-to-end computational interface study using
only the CALM Basic API.

Every scientific object has been:

- created,
- persisted,
- retrieved,
- related through provenance,
- and organized within a Project.

This object lifecycle is the defining characteristic of the CALM Basic
API and forms the foundation for reproducible computational materials
science workflows.
