# Workspace

`Workspace` is the recommended high-level facade for CALM's layered architecture.

You open (or create) a workspace with `calm.project.open_workspace(...)`. The workspace persists
state in a SQLite database located under the workspace root and writes artifacts (logs, plots,
structures) under the `out/` directory.

## Create or open a workspace

<!-- calm-docs: execute name="workspace-basic" -->
```python
from pathlib import Path

from calm.project import Workspace, open_workspace

ws: Workspace = open_workspace(Path("my_workspace"))
print(ws)
```

## Persistence model

A default workspace stores structured state in:

```text
<workspace-root>/calm.sqlite
```

and generated artifacts under:

```text
<workspace-root>/out/
```

The current database schema is summarized in
[Workspace Database Schema](workspace_database_schema.md) and implemented in
`calm/project/infrastructure/db/tables.py`.

Use the `Workspace` facade for normal workflows. Direct SQL inspection is
mainly for debugging, migration work, or developer audits.

## Runs and artifacts

Runs are lightweight records that you can attach artifacts to (logs, plots, structures).

<!-- calm-docs: execute name="workspace-basic" -->
```python
from pathlib import Path

from calm.project import open_workspace

ws = open_workspace(Path("my_workspace"))

run = ws.create_run(run_type="unit_test", spec={"x": 1})
ws.put_log(run.id_short, text="hello\n", filename="hello.txt")
ws.put_plot(run.id_short, data=b"PNG", filename="plot.png")
ws.put_structure(run.id_short, text="STRUCT\n", filename="struct.xyz")
```

By default, artifacts are written under:

- `my_workspace/out/runs/<run_id>/logs/...`
- `my_workspace/out/runs/<run_id>/plots/...`
- `my_workspace/out/runs/<run_id>/structures/...`

## Bulk → slabs → prototype search

The workspace exposes a small, composable workflow:

1) Add a bulk record  
2) Generate slab candidates  
3) Run a prototype search

```python
from pathlib import Path

from calm.project import open_workspace

ws = open_workspace(Path("my_workspace"))

bulk = ws.add_bulk(label="A", payload={"source": "docs"})
slabs = ws.build_slabs(
    bulk.id_short,
    millers=[(1, 1, 1), (2, 0, 0)],
    payload={"note": "docs"},
)

run = ws.start_prototype_search(slabs[0].id_short, slabs[1].id_short, n_candidates=10)
protos = ws.list_prototypes(run=run.id_short)

# Optional: write a pareto plot artifact for the run.
_ = ws.pareto_plot(run.id_short, filename="pareto.png")
```

## Downstream stages (registry / relaxation / energy)

Workspace exposes higher-level orchestrators that operate on persisted prototypes
and produce normalized per-prototype result rows. Use the following helpers from
the workspace facade (or the Project facade) to run downstream stages:

- `run_registry_stage(prototypes, n_steps=..., campaign_uid_full=..., campaign_run_uid_full=...)`
- `run_relaxation_stage(prototypes, max_steps=..., backend=..., campaign_uid_full=..., campaign_run_uid_full=...)`
- `run_energy_stage(prototypes, calculation=..., backend=..., campaign_uid_full=..., campaign_run_uid_full=...)`

Each stage returns a list of dicts; minimally each dict contains `status`,
`prototype_uid`, and, when a run was created, `run_uid`.

These methods accept optional campaign context so runs and persisted datasets can
be associated with a campaign/campaign_run for provenance and resume semantics.

## Followups

Followups attach derived results to a run and can emit plot artifacts.

```python
from pathlib import Path

from calm.project import open_workspace

ws = open_workspace(Path("my_workspace"))

# Assume `protos` was obtained via `ws.list_prototypes(...)`.
# Select a few prototype ids for a scan.
proto_ids = [p.id_short for p in protos[:3]]

scan = ws.start_strain_partition_scan(
    proto_ids,
    alphas=[0.0, 0.5, 1.0],
    payload={"note": "docs"},
)

results = ws.list_followup_results(run=scan.id_short, kind="strain_partition_scan")

# Optional: write a plot artifact for the scan run.
_ = ws.strain_partition_plot(scan.id_short, filename="strain.png")
```

## Migration note

Use `open_workspace(...)` to create/open a workspace and interact with it via `Workspace`.
