# Task Queue and Monitoring — Guides

These guides are task-focused references for practical CALM workflows. Use
them when you already know what you want to do and want a concise recipe for
getting the job done.

For step-by-step learning, start with the [Tutorials](../tutorials/index.md).
For background explanations, see [Concepts](../concepts/overview.md). For the
API and exact signatures, consult the [Reference](../reference/index.md).

## Workflow guides

These pages cover common workflow patterns and practical recipes:

- [Workspace: prototype search](workflows/project_prototype_search.md)
- [Workspace: interface optimization workflow](workflows/project_interface_optimization.md)
- [One-off: build and score an interface (no DB)](workflows/one_off_interface.md)
- [Scripted workflow](workflows/scripted_workflow.md)

## Task queue and monitoring

These pages cover queue-backed execution, monitoring, and runtime checks:

 - [Task Queue](operations/task_queue.md) — queue jobs for batch execution and orchestration
 - [Background Execution & Monitoring](operations/queue_persistence_and_background_execution.md) — persistent workers, monitoring, and resume semantics
 - [Calculator Availability Checks](operations/calculator_availability_checks.md) — verify backend availability and fail-fast patterns

## Operations and advanced topics

- [Rollback an authoritative migration](operations/migration_rollback.md)
- [GitLab CI on Livermore Computing](operations/lc_gitlab_ci.md)

## Examples

These example-oriented pages show common operational patterns:

 - [Public workflow examples](examples/public_workflow_examples.md)
 - [Relaxation examples](examples/relaxation_examples.md)
 
## Notes

These example pages are now surfaced under the Guides section of the documentation site. For larger runnable scripts and demos see the top-level `examples/` directory; the Guides examples are short walkthroughs and may link to the runnable scripts in `examples/`.
## When to use what

- Tutorials: guided learning path for new users
- Guides: immediate, task-focused recipes (this collection)
- Concepts: background and rationale
- Reference: exact APIs and conventions

## Next steps

- New to CALM? Start with the [Quickstart](../getting-started/quickstart.md).
- Want to automate many runs? Read the [Task Queue](operations/task_queue.md) guide.
