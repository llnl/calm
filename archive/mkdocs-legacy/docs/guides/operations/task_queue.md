# Task Queue System

The CALM task queue system allows you to plan and execute computational workflows by queueing tasks for deferred or batch execution.

## Overview

The task queue system provides:

- **Deferred Execution**: Queue tasks without executing them immediately
- **Batch Execution**: Execute multiple tasks at once
- **Dependencies**: Chain tasks where one must complete before another starts
- **Priorities**: Control execution order with priority values
- **Retry Logic**: Automatically retry failed tasks
- **Background Execution**: Optional background worker for automatic execution

## Basic Usage

### Queueing Tasks

Queue tasks for later execution:

```python
from calm.project import open_workspace

ws = open_workspace("path/to/workspace")

# Queue prototype searches
job1 = ws.queue_prototype_search("s_001", "s_002")
job2 = ws.queue_prototype_search("s_003", "s_004")
job3 = ws.queue_prototype_search("s_005", "s_006")

print(f"Queued {job1.id_short}, {job2.id_short}, {job3.id_short}")
```

### Executing the Queue

Execute all queued tasks:

```python
# Execute all ready jobs
completed = ws.execute_queue()
print(f"Executed {len(completed)} jobs")

# Or execute one at a time
job = ws.execute_next_job()
if job:
    print(f"Executed {job.id_short}")
```

### Inspecting the Queue

View queued tasks:

```python
# List all queued jobs
queued = ws.list_queued_jobs()
for job in queued:
    print(f"{job.id_short}: {job.job_type} (priority={job.priority})")

# List jobs by status
failed = ws.list_queued_jobs(status="failed")
done = ws.list_queued_jobs(status="done")
```

## Job Types

The queue supports three job types:

### 1. Prototype Search

Search for interface prototypes between two slabs:

```python
job = ws.queue_prototype_search(
    "s_001", "s_002",
    n_candidates=20,
    k_max=10,
    priority=5
)
```

### 2. Registry Search

Optimize interface registry configurations:

```python
job = ws.queue_registry_search(
    prototypes=["p_001", "p_002"],
    n_steps=100,
    priority=3
)
```

### 3. Strain Partition Scan

Scan strain partition parameters:

```python
job = ws.queue_strain_partition_scan(
    prototypes=["p_001"],
    n_alpha=21,
    priority=1
)
```

## Advanced Features

### Task Dependencies

Chain tasks where a child job waits for a parent to complete:

```python
# Queue parent job
parent = ws.queue_prototype_search("s_001", "s_002", priority=10)

# Queue child jobs that depend on parent
child1 = ws.queue_registry_search(
    ["p_001"],  # Will be created by parent
    parent_job=parent.id_short,
    priority=5
)

child2 = ws.queue_strain_partition_scan(
    ["p_001"],
    parent_job=parent.id_short,
    priority=5
)

# Execute queue - parent runs first, then children
completed = ws.execute_queue()
```

### Priority Control

Higher priority jobs execute first:

```python
# Low priority (default = 0)
ws.queue_prototype_search("s_001", "s_002", priority=0)

# Medium priority
ws.queue_prototype_search("s_003", "s_004", priority=5)

# High priority (executes first)
ws.queue_prototype_search("s_005", "s_006", priority=10)

# Execute - highest priority runs first
job = ws.execute_next_job()
print(f"Executed: {job.id_short} (priority={job.priority})")
```

### Retry Logic

Automatically retry failed tasks:

```python
job = ws.queue_prototype_search(
    "s_001", "s_002",
    max_retries=3  # Retry up to 3 times on failure
)

# If execution fails, the job will be re-queued automatically
# up to max_retries times
```

### Canceling Jobs

Cancel queued jobs before they execute:

```python
job = ws.queue_prototype_search("s_001", "s_002")

# Cancel before execution
cancelled = ws.cancel_job(job.id_short)
print(f"Status: {cancelled.status}")  # "cancelled"
```

Note: Only queued or failed jobs can be cancelled. Running or completed jobs cannot be cancelled.

## Background Worker

Use the background worker for automatic execution:

```python
# Start background worker (polls every 5 seconds)
ws.start_queue_worker(poll_interval=5.0)

# Queue jobs - they execute automatically in background
ws.queue_prototype_search("s_001", "s_002")
ws.queue_prototype_search("s_003", "s_004")

# Do other work while jobs execute...

# Check status
queued = ws.list_queued_jobs()
print(f"Still queued: {len(queued)}")

done = ws.list_queued_jobs(status="done")
print(f"Completed: {len(done)}")

# Stop worker when done
ws.stop_queue_worker()
```

**Worker behavior:**
- Runs in a daemon thread (won't prevent program exit)
- Polls queue every `poll_interval` seconds
- Executes one job at a time
- Continues running until explicitly stopped

## Complete Workflow Example

Here's a complete example showing a multi-stage workflow:

```python
from calm.project import open_workspace

ws = open_workspace("path/to/workspace")

# Stage 1: Search for prototypes (high priority)
print("Stage 1: Searching for prototypes...")
job_search = ws.queue_prototype_search(
    "slab_a", "slab_b",
    n_candidates=20,
    priority=10,
    max_retries=2
)

# Stage 2: Optimize best prototypes (medium priority, depends on search)
print("Stage 2: Registry optimization...")
job_registry = ws.queue_registry_search(
    ["p_001", "p_002"],  # Will be created by search
    n_steps=100,
    parent_job=job_search.id_short,
    priority=5,
    max_retries=1
)

# Stage 3: Scan strain partitions (low priority, depends on optimization)
print("Stage 3: Strain scanning...")
job_strain = ws.queue_strain_partition_scan(
    ["p_001"],
    n_alpha=21,
    parent_job=job_registry.id_short,
    priority=1
)

# Execute entire workflow
print("\nExecuting workflow...")
completed = ws.execute_queue()

print(f"\nCompleted {len(completed)} jobs:")
for i, job in enumerate(completed, 1):
    print(f"  {i}. {job.id_short}: {job.job_type}")
    if job.run_uid_full:
        print(f"     → Run: {job.run_uid_full[:12]}...")
```

## Job Status States

Jobs can be in one of five states:

- **queued**: Waiting to execute
- **running**: Currently executing
- **done**: Successfully completed
- **failed**: Execution failed (may retry if max_retries > 0)
- **cancelled**: Manually cancelled before execution

## Job Attributes

Each job has the following attributes:

```python
job = ws.queue_prototype_search("s_001", "s_002")

print(f"Job ID: {job.id_short}")           # Short ID (e.g., "j_a1b2c3d4")
print(f"Full UID: {job.uid_full}")         # Full UID (e.g., "job:a1b2c3d4...")
print(f"Type: {job.job_type}")             # "prototype_search", etc.
print(f"Status: {job.status}")             # "queued", "running", "done", etc.
print(f"Priority: {job.priority}")         # Integer (higher = first)
print(f"Spec: {job.spec}")                 # Job parameters
print(f"Parent: {job.parent_job_uid}")     # Parent job UID (if dependent)
print(f"Run: {job.run_uid_full}")          # Created run UID (after execution)
print(f"Retries: {job.retry_count}/{job.max_retries}")  # Retry info
print(f"Created: {job.created_at}")        # Timestamp
```

## Best Practices

### 1. Use Priorities Strategically

Assign priorities based on urgency and dependencies:

```python
# Critical path (high priority)
ws.queue_prototype_search("critical_a", "critical_b", priority=10)

# Normal workload (default priority)
ws.queue_prototype_search("normal_a", "normal_b", priority=0)

# Exploratory/optional (low priority)
ws.queue_prototype_search("explore_a", "explore_b", priority=-5)
```

### 2. Chain Related Tasks

Use dependencies for multi-stage workflows:

```python
# Generate → Optimize → Analyze
job1 = ws.queue_prototype_search("s_a", "s_b")
job2 = ws.queue_registry_search(["p_001"], parent_job=job1.id_short)
job3 = ws.queue_strain_partition_scan(["p_001"], parent_job=job2.id_short)
```

### 3. Add Retries for Unstable Operations

Use retries for operations that might fail transiently:

```python
ws.queue_prototype_search(
    "s_001", "s_002",
    max_retries=3  # Retry up to 3 times
)
```

### 4. Monitor Queue Status

Regularly check queue status, especially with background worker:

```python
# Check what's pending
queued = ws.list_queued_jobs()
print(f"Pending: {len(queued)}")

# Check for failures
failed = ws.list_queued_jobs(status="failed")
if failed:
    for job in failed:
        print(f"Failed: {job.id_short}, error: {job.error}")
```

### 5. Clean Up Completed Jobs

Jobs remain in the database after completion. You can query them:

```python
# View completed jobs
done = ws.list_queued_jobs(status="done")
for job in done:
    print(f"{job.id_short}: run={job.run_uid_full}")
```

## Comparison: Queue vs Direct Execution

### Direct Execution (Original)

```python
# Execute immediately
run = ws.start_prototype_search("s_001", "s_002")
# Blocks until complete
```

**Use when:**
- Running a single task interactively
- Need immediate results
- Simple one-off operations

### Queue Execution (New)

```python
# Queue for later
job = ws.queue_prototype_search("s_001", "s_002")
# Returns immediately, no execution yet

# Execute when ready
completed = ws.execute_queue()
```

**Use when:**
- Planning multiple related tasks
- Batch processing many tasks
- Complex workflows with dependencies
- Want to review planned work before execution
- Using background worker

## Troubleshooting

### Jobs Not Executing

Check if jobs are ready:

```python
summary = ws.get_queue_summary()
ready_count = summary.get("ready", 0)
if ready_count == 0:
    print("No jobs ready - check dependencies or queued job status")
```

### Background Worker Not Working

Verify worker is running:

```python
if not ws.is_queue_worker_running():
    print("Worker not running - start with ws.start_queue_worker()")
```

### Failed Jobs Not Retrying

Check retry configuration:

```python
failed = ws.list_queued_jobs(status="failed")
for job in failed:
    if job.retry_count >= job.max_retries:
        print(f"{job.id_short}: max retries exceeded")
```

## API Reference

See the workspace API documentation for complete details on:

- `ws.queue_prototype_search(...)`
- `ws.queue_registry_search(...)`
- `ws.queue_strain_partition_scan(...)`
- `ws.list_queued_jobs(...)`
- `ws.execute_queue()`
- `ws.execute_next_job()`
- `ws.cancel_job(...)`
- `ws.start_queue_worker(...)`
- `ws.stop_queue_worker()`
- `ws.is_queue_worker_running()`
