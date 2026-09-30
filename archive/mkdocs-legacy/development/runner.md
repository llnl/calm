# Runner examples (test fixture)

This document contains runnable examples used by tests to validate the runner
public API surface. Keep examples minimal and stable.

```python
from pathlib import Path
from calm.project import open_workspace

# Use the current working directory so the example creates a local SQLite file
root = Path(".")
ws = open_workspace(root=root)

print("created", (root / "calm.sqlite").exists())
```
