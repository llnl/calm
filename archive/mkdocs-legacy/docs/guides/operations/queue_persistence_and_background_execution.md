# Queue Persistence and Background Execution

Complete guide to persistent queue execution and background workers in CALM.

Note: For the current runnable worker and monitor scripts and other example
workflows, see the Example Scripts guide at `docs/guides/examples/index.md`.

---

## Overview

CALM's job queue system provides **persistent job storage** and **flexible execution** options:

- **Jobs persist across Python sessions** - queue jobs in one script, execute in another
- **Multiple execution modes** - in-process, background thread, persistent worker process
- **Query from anywhere** - monitor queue status from any script or process
- **Dependency tracking** - child jobs wait for parent jobs to complete

---

## Key Concepts

### Job Persistence

Jobs are **stored in the workspace database**, not in memory. This means:

✓ Jobs survive Python process termination
✓ Multiple scripts can access the same queue
✓ Workers can run independently of the queueing script
✓ Queue state is persistent and can be inspected at any time

### Execution Options

You have three ways to execute queued jobs:

1. **Manual execution** - Call `ws.execute_queue()` or `ws.execute_next_job()` in your script
2. **In-process worker** - Start a background thread via `ws.start_queue_worker()`
3. **Persistent worker** - Run `queue_worker.py` as a separate process

---

## Quick Start

### 1. Queue Jobs

```python
from calm.project import open_workspace

ws = open_workspace("my_workspace.calm")

# Queue multiple jobs
job1 = ws.queue_prototype_search("s_001", "s_002", priority=10)
job2 = ws.queue_prototype_search("s_003", "s_004", priority=5)
job3 = ws.queue_registry_search(["p_001", "p_002"], priority=1)

print(f"Queued {len([job1, job2, job3])} jobs")
```

**At this point:**
- Jobs are stored in the database
- Jobs are NOT executing yet
- You can exit Python and jobs remain queued

### 2. Execute Jobs

Choose one of three execution methods:

#### Option A: Manual Execution

```python
# In same script or a different script
from calm.project import open_workspace

ws = open_workspace("my_workspace.calm")

# Execute all ready jobs
completed = ws.execute_queue()
print(f"Executed {len(completed)} jobs")
```

#### Option B: In-Process Worker

```python
# Start background thread
ws.start_queue_worker(poll_interval=5.0)

# Jobs execute automatically in background
# You can continue doing other work...

# When done, stop the worker
ws.stop_queue_worker()
```

**Note:** In-process worker runs as a daemon thread and **does not persist** after the Python process exits.

#### Option C: Persistent Worker Process

```bash
    # Start persistent worker (runs until manually stopped)
    # The repository does not ship a generic `queue_worker.py` script. Create a
    # small project-specific wrapper that opens the workspace and calls
    # `ws.execute_next_job()` in a loop, or use `ws.execute_queue()` for batch
    # execution.

    # Example (project-specific wrapper):
    # from calm.project import open_workspace
    # ws = open_workspace("my_workspace.calm")
    # while ws.execute_next_job() is not None:
    #     pass
```

**This is the recommended approach for long-running workflows** because:
- Worker persists across Python sessions
- Can run on remote machine or in screen/tmux session
- Separate from job submission scripts
- Can restart if it crashes

### 3. Monitor Queue

#### From Python

```python
from calm.project import open_workspace

ws = open_workspace("my_workspace.calm")

# Get summary
summary = ws.get_queue_summary()
print(f"Total: {summary['total']}")
print(f"Queued: {summary['by_status'].get('queued', 0)}")
print(f"Running: {summary['by_status'].get('running', 0)}")
print(f"Done: {summary['by_status'].get('done', 0)}")

# List all jobs
all_jobs = ws.list_all_jobs()
for job in all_jobs:
    print(f"{job.id_short}: {job.status} - {job.job_type}")

# Get specific job
job = ws.get_job("j_abc123")
print(f"Status: {job.status}")
```

#### From Command Line

```bash
# Show summary
python examples/queue_monitor.py my_workspace.calm

# Show verbose details
python examples/queue_monitor.py my_workspace.calm --verbose

# Filter by status
python examples/queue_monitor.py my_workspace.calm --status running

# Watch mode (refresh every 5 seconds)
python examples/queue_monitor.py my_workspace.calm --watch 5

# Get specific job
python examples/queue_monitor.py my_workspace.calm --job j_abc123

# Export as JSON
python examples/queue_monitor.py my_workspace.calm --json > status.json
```

---

## Complete Workflow Example

This example shows the full workflow: bulks → slabs → prototypes → strain scan → registry search.

### Step 1: Queue All Jobs

```python
#!/usr/bin/env python
"""queue_workflow.py - Queue a complete interface design workflow"""

from ase.build import bulk
from calm.project import open_workspace

# Setup workspace
ws = open_workspace("interface_workflow.calm")

# Add bulk materials
al_atoms = bulk("Al", "fcc", a=4.05)
cu_atoms = bulk("Cu", "fcc", a=3.61)
bulk_a = ws.add_bulk(structure=al_atoms, label="Al FCC")
bulk_b = ws.add_bulk(structure=cu_atoms, label="Cu FCC")

# Generate slabs
slabs_a = ws.build_slabs(bulk_a.id_short, millers=[(1,1,1), (1,0,0)])
slabs_b = ws.build_slabs(bulk_b.id_short, millers=[(1,1,1), (1,0,0)])

# Queue prototype searches (high priority)
prototype_jobs = []
for slab_a in slabs_a:
    for slab_b in slabs_b:
        job = ws.queue_prototype_search(
            slab_a.id_short,
            slab_b.id_short,
            k_max=5,
            strain_max=0.10,
            priority=10  # High priority
        )
        prototype_jobs.append(job)

print(f"Queued {len(prototype_jobs)} prototype search jobs")

# Queue strain scans (depends on prototype searches)
strain_jobs = []
for proto_job in prototype_jobs[:2]:  # First 2 for demo
    job = ws.queue_strain_partition_scan(
        prototypes=[],  # Will be filled from search results
        n_alpha=11,
        priority=5,  # Medium priority
        parent_job=proto_job.id_short  # Dependency
    )
    strain_jobs.append(job)

print(f"Queued {len(strain_jobs)} strain scan jobs")

# Queue registry searches (depends on strain scans)
registry_jobs = []
for strain_job in strain_jobs:
    job = ws.queue_registry_search(
        prototypes=[],  # Will be filled from strain results
        n_steps=50,
        priority=1,  # Low priority (runs last)
        parent_job=strain_job.id_short  # Dependency
    )
    registry_jobs.append(job)

print(f"Queued {len(registry_jobs)} registry search jobs")

# Show queue summary
summary = ws.get_queue_summary()
print(f"\nTotal jobs queued: {summary['total']}")
print(f"Jobs ready to run: {summary['ready']}")
print("\nRun one of:")
print("  Run a project-local worker/monitor wrapper that uses the workspace queue API.")
```

### Step 2: Execute in Background

```text
For persistent execution, create a small project-local worker that opens the
workspace and repeatedly calls `ws.execute_next_job()` or uses `ws.execute_queue()`
to drive queued jobs. The repository does not ship a generic `queue_worker.py`.
```

### Step 3: Monitor from Another Terminal

```text
Create a simple project-local monitor that queries the workspace API
and prints a readable status summary. There is no shipped generic monitor
script in the repository.
```

---

## Execution Mode Comparison

| Feature | Manual | In-Process Worker | Persistent Worker |
|---------|--------|-------------------|-------------------|
| **Persistence** | No (must call explicitly) | No (exits with script) | Yes (separate process) |
| **Use Case** | Interactive, notebooks | Simple automation | Production, long workflows |
| **Setup** | `ws.execute_queue()` | `ws.start_queue_worker()` | `python queue_worker.py` |
| **Monitoring** | Same script | Same script | Separate script/terminal |
| **Failure Handling** | Script must handle | Thread dies with script | Can restart separately |
| **Background** | No | Yes (daemon thread) | Yes (separate process) |

### When to Use Each

**Manual Execution:**
- Interactive exploration in Jupyter notebooks
- Simple, short workflows
- When you want full control over timing

**In-Process Worker:**
- Simple automation scripts
- When queue and execution happen in same session
- Quick prototyping

**Persistent Worker:**
- Production workflows
- Long-running calculations
- Remote execution (SSH session, screen/tmux)
- When queue submission and execution are separate concerns

---

## Background Worker Details

### Starting the Worker

```bash
# Basic usage
python examples/queue_worker.py workspace.calm

# Custom poll interval (check every 10 seconds)
python examples/queue_worker.py workspace.calm --interval 10

# Run N jobs then exit
python examples/queue_worker.py workspace.calm --max-jobs 50
```

### Running in Background (Unix/macOS)

```bash
# Run in background with output to log file
nohup python examples/queue_worker.py workspace.calm > worker.log 2>&1 &

# Get process ID
echo $!

# Check if running
ps aux | grep queue_worker.py

# Stop worker
kill <pid>

# Or use pkill
pkill -f queue_worker.py
```

### Running in Screen/Tmux

```bash
# Start screen session
screen -S calm_worker

# Start worker
python examples/queue_worker.py workspace.calm

# Detach: Ctrl+A, then D

# Reattach later
screen -r calm_worker

# List sessions
screen -ls
```

### Worker Behavior

The persistent worker:

✓ Polls queue every N seconds (default 5)
✓ Executes ready jobs in priority order
✓ Respects job dependencies
✓ Handles errors and retries
✓ Logs all activity
✓ Continues until manually stopped (Ctrl+C or kill)
✓ Gracefully shuts down on signals (SIGINT, SIGTERM)

---

## Querying the Queue

### Python API

```python
from calm.project import open_workspace

ws = open_workspace("workspace.calm")

# Summary statistics
summary = ws.get_queue_summary()
# Returns: {'total': 10, 'by_status': {...}, 'by_job_type': {...}, 'ready': 3}

# List all jobs
all_jobs = ws.list_all_jobs()

# Filter by status
queued = ws.list_queued_jobs(status="queued")
running = ws.list_queued_jobs(status="running")
done = ws.list_queued_jobs(status="done")
failed = ws.list_queued_jobs(status="failed")

# Get specific job
job = ws.get_job("j_abc123")
print(f"Status: {job.status}")
print(f"Job type: {job.job_type}")
print(f"Priority: {job.priority}")
print(f"Parent: {job.parent_job_uid}")
if job.error:
    print(f"Error: {job.error['type']}: {job.error['error']}")
```

### Command Line

```bash
# Summary
python examples/queue_monitor.py workspace.calm

# Verbose (shows all job details)
python examples/queue_monitor.py workspace.calm --verbose

# Filter by status
python examples/queue_monitor.py workspace.calm --status queued
python examples/queue_monitor.py workspace.calm --status running
python examples/queue_monitor.py workspace.calm --status done
python examples/queue_monitor.py workspace.calm --status failed

# Specific job
python examples/queue_monitor.py workspace.calm --job j_abc123

# Watch mode (live updates)
python examples/queue_monitor.py workspace.calm --watch 5

# JSON export
python examples/queue_monitor.py workspace.calm --json
```

---

## Dependencies and Execution Order

### How Dependencies Work

Jobs with `parent_job_uid` set will **not execute** until the parent job completes successfully.

```python
# Queue parent job
parent = ws.queue_prototype_search("s_001", "s_002", priority=10)

# Queue child job (depends on parent)
child = ws.queue_registry_search(
    ["p_001"],
    parent_job=parent.id_short,  # Dependency
    priority=5
)

# Execution order:
# 1. parent executes first (higher priority)
# 2. child waits until parent status == "done"
# 3. child becomes ready and executes
```

### Priority Within Ready Jobs

Among jobs that are ready to execute:

- **Priority**: Higher values execute first (priority DESC)
- **Age**: Older jobs execute first (created_at ASC)

```python
# These have no dependencies, so execution order is by priority
ws.queue_prototype_search("s_001", "s_002", priority=10)  # Executes 1st
ws.queue_prototype_search("s_003", "s_004", priority=5)   # Executes 2nd
ws.queue_prototype_search("s_005", "s_006", priority=0)   # Executes 3rd (default priority)
```

### Complex Workflows

You can build multi-stage workflows:

```python
# Stage 1: Prototype searches (priority 10)
search_jobs = []
for slab_pair in slab_pairs:
    job = ws.queue_prototype_search(*slab_pair, priority=10)
    search_jobs.append(job)

# Stage 2: Strain scans (priority 5, depends on searches)
strain_jobs = []
for search_job in search_jobs:
    job = ws.queue_strain_partition_scan(
        prototypes=[],
        priority=5,
        parent_job=search_job.id_short
    )
    strain_jobs.append(job)

# Stage 3: Registry searches (priority 1, depends on scans)
registry_jobs = []
for strain_job in strain_jobs:
    job = ws.queue_registry_search(
        prototypes=[],
        priority=1,
        parent_job=strain_job.id_short
    )
    registry_jobs.append(job)

# Execution order:
# 1. All search_jobs execute (ready immediately, priority 10)
# 2. strain_jobs execute as searches complete (priority 5)
# 3. registry_jobs execute as scans complete (priority 1)
```

---

## Best Practices

### 1. Structure Workflows with Dependencies

```python
# Good: Clear dependency chain
search = ws.queue_prototype_search("s_a", "s_b", priority=10)
scan = ws.queue_strain_partition_scan(..., parent_job=search.id_short, priority=5)
registry = ws.queue_registry_search(..., parent_job=scan.id_short, priority=1)
```

### 2. Use Priorities Wisely

- **Priority 10**: Critical, time-sensitive jobs
- **Priority 5**: Normal workflow jobs
- **Priority 1**: Low-priority, background analysis
- **Priority 0**: Default, no special handling

### 3. Monitor Long-Running Workflows

```bash
# Start worker in screen/tmux
screen -S workflow
python examples/queue_worker.py workspace.calm

# Detach and monitor from laptop
python examples/queue_monitor.py workspace.calm --watch 10
```

### 4. Handle Failures

```python
# Queue with retries
job = ws.queue_prototype_search(
    "s_001", "s_002",
    max_retries=3  # Retry up to 3 times on failure
)

# Check for failures
failed = ws.list_queued_jobs(status="failed")
for job in failed:
    print(f"{job.id_short}: {job.error}")
```

### 5. Use JSON Export for Reporting

```bash
# Export queue state
python examples/queue_monitor.py workspace.calm --json > status.json

# Process with jq
cat status.json | jq '.summary'
cat status.json | jq '.jobs[] | select(.status == "failed")'
```

---

## Summary

**Key Takeaways:**

✓ Jobs persist in database, not in memory
✓ Queue in one script, execute in another
✓ Three execution modes: manual, in-process, persistent worker
✓ Monitor from any script or terminal
✓ Dependencies ensure correct execution order
✓ Priorities control execution among ready jobs

**Typical Workflow:**

1. **Queue jobs** - `python queue_workflow.py`
2. **Start worker** - `nohup python examples/queue_worker.py workspace.calm &`
3. **Monitor** - `python examples/queue_monitor.py workspace.calm --watch 5`
4. **Query** - Use Python API or command-line monitor
5. **Stop worker** - `pkill -f queue_worker.py`

---

## See Also

- [Task Queue Guide](task_queue.md) - Complete queue API reference
- [Task Queue Implementation](../../development/task_queue_implementation.md) - Technical details
  - Note: The repository does not currently ship `examples/comprehensive_workflow_queue.py`,
    `examples/queue_worker.py`, or `examples/queue_monitor.py`. Use the workspace queue API
    (`ws.queue_*`, `ws.execute_queue()`, `ws.execute_next_job()`, `ws.list_queued_jobs()`) or
    create project-specific wrapper scripts as needed.
