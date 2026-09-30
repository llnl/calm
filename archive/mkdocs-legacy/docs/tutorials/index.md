# Tutorials

Learn CALM through step-by-step tutorials that cover the complete workflow from loading crystal structures to optimizing interface configurations.

## Getting Started

New to CALM? Start here:

1. **[Workspace Basics](01_workspace_basics.md)** - Create a workspace, load structures, and export files
2. **[Slab Generation](02_slab_generation.md)** - Generate surface slabs with automatic termination enumeration
3. **[Prototype Search](03_prototype_search.md)** - Find and rank interface candidates

## Advanced Workflows

Once you're comfortable with the basics:

4. **[Follow-up Analyses](04_followups.md)** - Optimize strain distribution and atomic alignment
5. **[Strain Analysis](05_strain_analysis.md)** - Comprehensive strain decomposition and visualization
6. **[Surface Terminations](06_terminations.md)** - Detect and enumerate polar surface terminations

## Specialized Topics

7. **[Thickness Control](07_thickness_control.md)** - Control slab thickness and track deformations
8. **[Calculator Integration](08_calculators.md)** - Use machine learning potentials for energy evaluation
9. **[Task Queue & Workflow Automation](09_task_queue.md)** - Queue jobs, build workflows, and run calculations in batch mode
10. **[Persistent Project Querying](10_public_project_query_reporting.md)** - Reopen `.calm` projects, query workflow stages, export tables, and create standard plots
12. **[Candidate Collections](12_candidate_collection_demo.md)** - Filter, rank, export, and build candidate collections

## Tutorial Philosophy

These tutorials are designed to:

- **Build on each other** - Each tutorial introduces new concepts while reinforcing previous ones
- **Use real examples** - All code examples are runnable scripts from `examples/`
- **Focus on the public API** - Only use stable, documented functions
- **Explain the why** - Not just how, but why you'd use each feature

## Prerequisites

- Python 3.10+
- CALM installed (`pip install .` from repository root)
- Basic familiarity with ASE (Atomic Simulation Environment)
- Basic understanding of crystallography (Miller indices, unit cells)

## Data Files

The tutorials use example crystal structures located in `examples/Structures/`:

- `LiF.poscar` - Rock salt structure (Fm-3m)
- `Li2O.poscar` - Anti-fluorite structure (Fm-3m)

These are chosen for:
- **Small unit cells** - Fast computation for tutorials
- **Cubic symmetry** - Easier to visualize and understand
- **Good lattice match** - Demonstrates CALM's capabilities

## Next Steps

After completing the tutorials:

- Explore [Guides](../guides/index.md) for specific tasks
- Read [Concepts](../concepts/overview.md) for deeper understanding
- Check the [API Reference](../reference/index.md) for detailed function documentation
- Review [Algorithm Details](../mathematics/algorithms/README.md) for mathematical background
