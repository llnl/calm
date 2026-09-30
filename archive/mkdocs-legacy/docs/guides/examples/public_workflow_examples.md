# Public workflow examples and recommended beginner patterns

This short guide shows the recommended beginner-friendly pattern for continuing
work after you have run an interface search. It describes the canonical
"persisted-search" workflow that the numbered examples use: inspect a named
search, check readiness, build selected candidates, and run follow-up
refinements. The goal is to present a concise, scientist-focused recipe that
avoids low-level maintenance idioms.

Key principle: use the persisted-search facade for follow-up workflows.
Persisted search objects expose readable summaries and guarded build/refine
helpers that are suitable for scripts and tutorials. Advanced inspection and
infrastructure orchestration APIs still exist, but they are intended for
methods developers and workspace operators rather than basic examples.

Recommended beginner pattern (named search follow-up):

```python
from calm import open_project

project = open_project("/path/to/project.calm")

# Resolve a named persisted search (created by search_interfaces(..., name=...))
persisted = project.search("LiF_Li2O_100_interface_match")

# Non-throwing readiness/buildability summary
summary = persisted.buildability_summary()
print(summary.summary())

# Candidate collection for exploration and export
candidates = persisted.candidates()
candidates.to_table(title="Candidates").display()
```

Build interface structures from the persisted search
--------------------------------------------------

After confirming readiness with `buildability_summary()`, use the persisted
search's authoritative builder to construct interface models. Beginners should
prefer `persisted.build_top(...)` which provides a simple, discoverable entry
point for building the top candidates.

```python
from calm import BuildSettings

# Build the top 3 Pareto candidates into persisted interfaces
settings = BuildSettings(strain_partition="both", alpha=0.5, gap=1.5, vacuum=15.0)
interfaces = persisted.build_top(3, settings=settings, name_prefix="built_interface")
interfaces.write_structures("outputs/", format="vasp")
```

Refinement follow-ups (strain partitioning + registry search)
------------------------------------------------------------

Use `persisted.refine_interfaces(...)` to run strain-partition scans, derive
best-alpha interfaces, and (optionally) run registry Monte Carlo searches
seeded from derived interfaces. This high-level helper encapsulates the
follow-up workflow used by Example 06.

```python
from calm import RegistrySettings

refinement = persisted.refine_interfaces(top=2, pareto=True, alphas=[0.0,0.25,0.5,0.75,1.0], registry_settings=RegistrySettings(steps=32), label_prefix="example")
print(refinement.summary())
refinement.write_outputs("outputs/")
```

Advanced note (developer/infrastructure APIs)
--------------------------------------------

For workspace operators and methods developers, the repository includes lower-level
diagnostic and orchestration APIs, such as `classify_candidates(persist=False)`
and `Project.run_build_stage(...)`. These are intended for infrastructure and
diagnostic workflows and are not the recommended path for beginner tutorials. If
you need to run large-scale, queued orchestration or to script low-level run
control, consult the advanced docs and the workspace API reference.

Further reading:
- Examples: `examples/03_match_interfaces.py`, `examples/05_build_interfaces.py`, `examples/06_strain_partition_and_registry_search.py`
- Concepts and architecture notes: docs/engineering/architecture-redesign/active-roadmap.md
"""
