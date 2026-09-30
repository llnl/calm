# Workspace layout and UX

This document describes the on-disk layout created by a CALM workspace.

A workspace is opened with:

```python
from pathlib import Path

from calm.project import open_workspace

ws = open_workspace(root=Path("."))
```

## Workspace layout

When you open a workspace rooted at `root/`, CALM stores two kinds of state:

- **Workspace database** (SQLite): `root/calm.sqlite` by default.
- **Artifacts / outputs**: `root/out/` by default.

A typical workspace directory looks like:

```
<root>/
  calm.sqlite
  out/
    runs/
      <run_id>/
        logs/
        plots/
        structures/
```

Notes:

- The `out/` directory is intended to be human-browsable.
- Use the `Workspace` facade rather than assuming internal database layout.
- For the authoritative database schema, see `docs/reference/workspace_database_schema.md`.

## UX goals

The workspace UX aims to keep the common loop straightforward:

1. Create (or reopen) a workspace.
2. Add bulks / build slabs.
3. Start runs (prototype search, follow-ups, etc.).
4. Query results.
5. Save plots/logs/structures as artifacts under `out/`.

For API details, see the workspace reference page.
