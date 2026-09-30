# Tutorial 09: Task Queue and Workflow Automation

Learn how to use CALM's task queue system to organize complex workflows, execute jobs in batch mode, and monitor long-running calculations.

---

## What You'll Learn

- Queue jobs for deferred execution
- Execute jobs manually or via background worker
- Build multi-stage workflows with dependencies
- Monitor queue status and progress
- Use persistent workers for long-running workflows

---

## Prerequisites

- Completed [Tutorial 03: Prototype Search](03_prototype_search.md)
- Completed [Tutorial 04: Follow-up Analyses](04_followups.md)
- Basic understanding of workflow automation

---

## Why Use the Task Queue?

Traditional CALM workflows execute tasks immediately:

```python
# Immediate execution
run = ws.start_prototype_search(slab_a, slab_b)  # Runs now
scan = ws.start_strain_partition_scan([proto_id])  # Runs now
```

**Challenges:**
- Must wait for each step to complete
- Script must stay running
- Hard to organize complex multi-step workflows
- Difficult to run on HPC/remote systems

**Task Queue Solution:**
- Queue all jobs upfront
- Execute in batch (or background)
- Script can exit after queuing
- Monitor from separate terminal/machine
- Automatic dependency management

---

## Basic Workflow: Queue and Execute

### Step 1: Setup

```python
from ase.build import bulk
from calm.project import open_workspace

# Create workspace
ws = open_workspace("queue_tutorial.calm")

# Add materials
al = bulk("Al", "fcc", a=4.05)
cu = bulk("Cu", "fcc", a=3.61)

bulk_al = ws.add_bulk(structure=al, label="Al FCC")
bulk_cu = ws.add_bulk(structure=cu, label="Cu FCC")

# Generate slabs
slabs_al = ws.build_slabs(bulk_al.id_short, millers=[(1,1,1)])
slabs_cu = ws.build_slabs(bulk_cu.id_short, millers=[(1,1,1)])
```

### Step 2: Queue Jobs (Don't Execute Yet)

```python
# Queue prototype searches
job1 = ws.queue_prototype_search(
    slabs_al[0].id_short,
    slabs_cu[0].id_short,
    k_max=5,
    strain_max=0.10,
    priority=10,  # High priority
)

job2 = ws.queue_prototype_search(
    slabs_al[0].id_short,
    slabs_cu[0].id_short,
    k_max=3,
    strain_max=0.15,
    priority=5,  # Medium priority
)

print(f"Queued jobs: {job1.id_short}, {job2.id_short}")
print(f"Status: {job1.status}")  # "queued"
```

**Key Points:**
- `queue_prototype_search()` doesn't execute - just stores the job
- Jobs are persisted in database (survive script exit)
- Returns a `Job` object with status="queued"

### Step 3: Execute Queue

#### Option A: Manual Execution

```python
# Execute all queued jobs
completed = ws.execute_queue()
print(f"Executed {len(completed)} jobs")

# Check results
for job in completed:
    print(f"{job.id_short}: {job.status}")  # "done"
    if job.run_uid_full:
        # Job created a run, can query results
        prototypes = ws.list_prototypes(job.run_uid_full)
        print(f"  Found {len(prototypes)} prototypes")
```

#### Option B: Execute One at a Time

```python
# Execute next ready job
job = ws.execute_next_job()
if job:
    print(f"Executed: {job.id_short}")
```

### Step 4: Monitor Queue

```python
# Get queue summary
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
print(f"Priority: {job.priority}")
print(f"Created: {job.created_at}")
```

---

## Multi-Stage Workflows with Dependencies

Build complex workflows where later stages depend on earlier stages completing.

### Example: Search → Scan → Registry

```python
# Stage 1: Prototype search (high priority)
search_job = ws.queue_prototype_search(
    slabs_al[0].id_short,
    slabs_cu[0].id_short,
    k_max=5,
    priority=10,
)

# Stage 2: Strain scan (depends on search)
scan_job = ws.queue_strain_partition_scan(
    prototypes=[],  # Will be filled from search results
    n_alpha=11,
    priority=5,
    parent_job=search_job.id_short,  # Dependency!
)

# Stage 3: Registry search (depends on scan)
registry_job = ws.queue_registry_search(
    prototypes=[],  # Will be filled from scan results
    n_steps=50,
    priority=1,
    parent_job=scan_job.id_short,  # Dependency!
)

# Execute queue - respects dependencies
completed = ws.execute_queue()

# Execution order:
# 1. search_job (ready immediately)
# 2. scan_job (becomes ready after search_job completes)
# 3. registry_job (becomes ready after scan_job completes)
```

**How Dependencies Work:**
- Child jobs wait for parent to complete
- `parent_job` parameter sets dependency
- Priority matters only among ready jobs
- Failed parents block children (unless retries succeed)

---

## Priority-Based Scheduling

Control execution order with priorities (higher = runs first).

```python
# Queue with different priorities
ws.queue_prototype_search(slab_a, slab_b, priority=10)  # Runs 1st
ws.queue_prototype_search(slab_c, slab_d, priority=5)   # Runs 2nd
ws.queue_prototype_search(slab_e, slab_f, priority=0)   # Runs 3rd (default)

# Execute in priority order
ws.execute_queue()
```

**Priority Guidelines:**
- **10**: Critical, time-sensitive jobs
- **5**: Normal workflow jobs
- **1**: Low-priority, background analysis
- **0**: Default priority

---

## Background Execution

### In-Process Worker (Daemon Thread)

For simple automation in a single script:

```python
# Start background worker
ws.start_queue_worker(poll_interval=5.0)

# Queue jobs - they execute automatically in background
ws.queue_prototype_search(slab_a, slab_b)
ws.queue_prototype_search(slab_c, slab_d)

# Do other work while jobs execute...
import time
time.sleep(30)

# Check progress
summary = ws.get_queue_summary()
print(f"Done: {summary['by_status'].get('done', 0)}")

# Stop worker when done
ws.stop_queue_worker()
```

**Note:** Worker is a daemon thread - exits when script exits!

### Persistent Worker (Separate Process)

For production workflows that outlive the script:

```bash
# Terminal 1: Queue jobs
python my_workflow.py
# (script exits, jobs remain queued)

    # Terminal 2: Start persistent worker
    # Note: The repository does not ship a generic worker/monitor script. For
    # persistent execution, create a small project-specific wrapper that opens
    # the workspace and runs jobs in a loop. Example worker (project-local):
    # from calm.project import open_workspace
    # ws = open_workspace("workspace.calm")
    # while ws.execute_next_job() is not None:
    #     pass

    # Terminal 3: Monitor progress (project-local wrapper or use ws.list_queued_jobs())
```

**Key Difference:**
- In-process worker: Dies with script
- Persistent worker: Separate process, outlives script

---

## Monitoring and Inspection

### Python API

```python
# Queue summary
summary = ws.get_queue_summary()
# Returns: {'total': 10, 'by_status': {...}, 'by_job_type': {...}, 'ready': 3}

# List jobs by status
queued = ws.list_queued_jobs(status="queued")
running = ws.list_queued_jobs(status="running")
done = ws.list_queued_jobs(status="done")
failed = ws.list_queued_jobs(status="failed")

# Get specific job
job = ws.get_job("j_abc123")
if job.status == "done" and job.run_uid_full:
    # Query results from the run
    prototypes = ws.list_prototypes(job.run_uid_full)
```

### Command-Line Monitor

```bash
# Show summary
python examples/queue_monitor.py workspace.calm

# Watch mode (refresh every 5 seconds)
python examples/queue_monitor.py workspace.calm --watch 5

# Filter by status
python examples/queue_monitor.py workspace.calm --status running

# Get specific job
python examples/queue_monitor.py workspace.calm --job j_abc123

# Export as JSON
python examples/queue_monitor.py workspace.calm --json > status.json
```

---

## Error Handling and Retries

### Automatic Retries

```python
# Queue with retry on failure
job = ws.queue_prototype_search(
    slab_a, slab_b,
    max_retries=3,  # Retry up to 3 times
)

# If job fails, it will be retried automatically
ws.execute_queue()

# Check if job failed
job = ws.get_job(job.id_short)
if job.status == "failed":
    print(f"Failed after {job.retry_count} attempts")
    print(f"Error: {job.error}")
```

### Manual Inspection

```python
# Find all failed jobs
failed = ws.list_queued_jobs(status="failed")
for job in failed:
    print(f"{job.id_short}: {job.error['type']}")
    print(f"  Message: {job.error['error']}")
    print(f"  Retries: {job.retry_count}/{job.max_retries}")
```

---

## Complete Example: Multi-Material Workflow

```python
#!/usr/bin/env python
"""Queue a complete multi-material interface workflow."""

from ase.build import bulk
from calm.project import open_workspace

# Setup
ws = open_workspace("multi_material.calm")

# Materials
materials = [
    ("Al", "fcc", 4.05),
    ("Cu", "fcc", 3.61),
    ("Ni", "fcc", 3.52),
]

# Add bulks and generate slabs
slabs_by_material = {}
for name, structure, a in materials:
    atoms = bulk(name, structure, a=a)
    bulk_obj = ws.add_bulk(structure=atoms, label=f"{name} {structure.upper()}")
    slabs = ws.build_slabs(bulk_obj.id_short, millers=[(1,1,1), (1,0,0)])
    slabs_by_material[name] = slabs

# Queue all pairwise prototype searches
search_jobs = []
for mat_a in materials:
    for mat_b in materials:
        if mat_a[0] >= mat_b[0]:  # Avoid duplicates
            continue

        name_a, name_b = mat_a[0], mat_b[0]
        for slab_a in slabs_by_material[name_a]:
            for slab_b in slabs_by_material[name_b]:
                job = ws.queue_prototype_search(
                    slab_a.id_short,
                    slab_b.id_short,
                    k_max=5,
                    priority=10,
                )
                search_jobs.append(job)

print(f"Queued {len(search_jobs)} prototype searches")

# Queue strain scans for first 3 searches
for search_job in search_jobs[:3]:
    scan_job = ws.queue_strain_partition_scan(
        prototypes=[],
        n_alpha=11,
        priority=5,
        parent_job=search_job.id_short,
    )

# Show queue summary
summary = ws.get_queue_summary()
print(f"\nQueue summary:")
print(f"  Total jobs: {summary['total']}")
print(f"  Ready to run: {summary['ready']}")
print(f"  By type: {summary['by_job_type']}")

# Execute all jobs
print("\nExecuting queue...")
completed = ws.execute_queue()
print(f"Completed {len(completed)} jobs")
```

---

## Best Practices

### 1. Structure Workflows with Dependencies

```python
# Good: Clear dependency chain
search = ws.queue_prototype_search(..., priority=10)
scan = ws.queue_strain_partition_scan(..., parent_job=search.id_short, priority=5)
registry = ws.queue_registry_search(..., parent_job=scan.id_short, priority=1)
```

### 2. Use Priorities Wisely

- Don't over-use high priorities (everything can't be urgent)
- Reserve priority 10 for truly critical jobs
- Use default priority (0) for most jobs

### 3. Monitor Long-Running Workflows

```bash
# Start worker in screen/tmux
screen -S calm_worker
python examples/queue_worker.py workspace.calm

# Detach: Ctrl+A, then D

# Monitor from laptop
python examples/queue_monitor.py workspace.calm --watch 10
```

### 4. Handle Failures Gracefully

```python
# Always set max_retries for flaky operations
job = ws.queue_prototype_search(..., max_retries=3)

# Check for failures after execution
failed = ws.list_queued_jobs(status="failed")
if failed:
    print(f"Warning: {len(failed)} jobs failed")
    for job in failed:
        print(f"  {job.id_short}: {job.error['type']}")
```

---

## Summary

**Key Concepts:**
- `queue_*()` methods add jobs without executing
- Jobs persist in database (survive script exit)
- `execute_queue()` or `execute_next_job()` runs jobs
- Dependencies via `parent_job` parameter
- Priorities control execution order (higher = first)
- Background workers enable true async execution

**Execution Modes:**
1. **Manual**: `ws.execute_queue()` - Simple, synchronous
2. **In-process worker**: `ws.start_queue_worker()` - Background thread
3. **Persistent worker**: `python queue_worker.py` - Separate process

**When to Use Queue:**
- Complex multi-step workflows
- Batch processing of many similar jobs
- HPC/remote execution
- Long-running calculations
- When you want to "set it and forget it"

---

## Next Steps

- **[Background Execution Guide](../guides/operations/queue_persistence_and_background_execution.md)** - Persistent workers, monitoring
- **[Task Queue API](../guides/operations/task_queue.md)** - Complete API reference
- **[Calculator Integration](08_calculators.md)** - Use ML potentials in queued jobs

---

## Further Reading

See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md` for current worker and monitor scripts.
- [Task Queue Implementation](../development/task_queue_implementation.md) - Technical details
