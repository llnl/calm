# How-to guides

These guides are task-focused walkthroughs. They are intentionally more detailed than the [Quickstart](../../getting-started/quickstart.md) and are written to match the shipped examples.

## Guides

### Core Workflows

- [Workspace: prototype search](project_prototype_search.md)
- [Workspace: interface optimization workflow](project_interface_optimization.md)
- [One-off: build and score an interface (no DB)](one_off_interface.md)

### Task Queue System

- [Task Queue Basics](../operations/task_queue.md) - Queue jobs for batch execution
- [Background Execution & Monitoring](../operations/queue_persistence_and_background_execution.md) - Persistent workers and queue monitoring
 
### Advanced Topics

- [Calculator Availability Checks](../operations/calculator_availability_checks.md) - Check ML potential dependencies
- [Rollback an authoritative migration](../operations/migration_rollback.md) - Revert an authoritative migration using the migration_log_uid

If you are looking for background concepts (UIDs, records, calculators), start at [Concepts](../../concepts/overview.md).
