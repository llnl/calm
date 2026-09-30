# Runner

CALM v2 is centered around the workspace facade.

Many workspace operations (for example, the various `start_*` helpers) run to completion immediately in-process.
For workflows that *enqueue* work (for example, creating runs with `status="queued"`), you can either:

- handle the work synchronously in your own code (recommended for small scripts), or
- use the optional runner helpers (`calm.project.runner`) to claim and execute queued runs.

## Minimal workspace workflow

```python
from pathlib import Path

from calm.project import open_workspace

# Create (or reopen) a workspace rooted at the current directory.
ws = open_workspace(Path("."))

# Create a run record and attach a log artifact.
run = ws.create_run(run_type="unit_test", spec={"x": 1})
_ = ws.put_log(run.id_short, text="hello\n", filename="hello.txt")

print(run.id_short, run.status)
```

## Runner helpers

The runner helpers are intentionally small and may not be required for typical interactive usage.

```python
# Optional: claim/execute queued runs until the queue is empty.
# (Example only; in many workflows you can call the workspace "start_*" methods directly.)
from calm.project.runner import run_until_empty  # noqa: F401
```

## Structures and ASE export

The runner is orthogonal to structure IO. For a worked example that shows how
to attach ASE ``Atoms`` payloads to bulks/slabs, write POSCAR files using
``ase.io.write``, and compute in-plane strain tensors/eigenvalues for an
interface, see:

See the canonical Example Scripts listing at `docs/guides/examples/index.md` for the current runnable scripts. Do not rely on historical filenames in this page.
