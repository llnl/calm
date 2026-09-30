Relaxation stage examples
=========================

This page shows small examples for using the stage-oriented relaxation APIs.

Open a workspace (default backend is deterministic):

```py
from calm import open_project

# Default project/workspace: open_project returns a Project facade backed by a Workspace
proj = open_project("/path/to/project")

# Use the Project-level facade to run relaxation stages
ws = proj._workspace  # advanced users may use the underlying Workspace when needed
```

Run a deterministic (CI-safe) relaxation:

```py
results = proj.run_relaxation_stage(["proto:..."], max_steps=50)
for r in results:
    print(r["target_uid"], r["status"], r.get("relaxed_interface_uid"))
```

Run using the real/ASE backend (opt-in). This will raise a clear error if
the runtime is missing ASE or calculator provenance.

```py
try:
    results = proj.run_relaxation_stage(["proto:..."], max_steps=200, backend="real")
except RuntimeError as e:
    print("Real backend failed or missing dependencies:", e)
    # Fall back to deterministic for exploratory runs
    results = proj.run_relaxation_stage(["proto:..."], max_steps=50)
```

Partial-resume: continue incomplete run targets only

```py
# Compute a long run, simulate interruption, then resume only missing targets
results = proj.run_relaxation_stage(["proto:..."], max_steps=500)
# Later, resume and compute only missing targets
results = proj.run_relaxation_stage(["proto:..."], max_steps=500, partial_resume=True, resume=True)
```

Artifact access and followup queries

```py
# List followup rows for a run

run = results[0].get("run_uid")
followups = proj.list_followup_results(run=run)
for f in followups:
    print(f.uid_full, f.payload)

# List artifacts for a run
artifacts = proj._workspace.list_artifacts(run)
for a in artifacts:
    print(a.uid_full, a.uri)
```

Notes
-----
- The workspace default relaxation backend may be configured at composition
  time via open_workspace(...). By default the workspace uses the
  deterministic test backend. To use the real backend by default, pass
  default_relaxation_backend="real" to the composition helper (see
  calm.project.bootstrap.open_workspace).
- Backend selection is encoded in the run specification to ensure deterministic
  run identity and safe resume semantics.
