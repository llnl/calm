# Quickstart

This quickstart uses CALM's public scientific API. The default workflow is
in-memory: it does not create a project database and it does not require an
MLIP unless you ask for energy-based operations.

## 1) Define two generic surfaces

<!-- calm-docs: skip reason="requires example POSCAR files and ASE; illustrative unless those files present" -->
```python
from calm import Surface, SearchSettings, search_interfaces

surface_a = Surface(
    "examples/Structures/LiF.poscar",
    miller=(1, 1, 1),
    thickness=10.0,
    material="LiF",
    label="LiF(111)",
)

surface_b = Surface(
    "examples/Structures/Li2O.poscar",
    miller=(1, 1, 1),
    thickness=10.0,
    material="Li2O",
    label="Li2O(111)",
)
```

CALM intentionally uses `surface_a` and `surface_b`; neither side is assumed to
be a film or a substrate.

## 2) Search for interface candidates

<!-- calm-docs: skip reason="prototype search may be expensive and requires ASE/spglib; illustrative" -->
```python
result = search_interfaces(
    surface_a,
    surface_b,
    settings=SearchSettings(
        max_principal_strain=0.10,
        max_atoms=300,
        max_supercell_index=12,
        max_candidates=25,
    ),
)

print(result.to_dataframe())
print(result.summary())
```

The result is a sequence of interface candidates. Each candidate carries the
mismatch, size, strain diagnostics, and enough internal information to build an
atomistic interface.

## 3) Plot the Pareto front

```python
result.plot_pareto(
    x="atoms",
    y="mismatch",
    save="LiF_Li2O_111_pareto.png",
)
```

`atoms` and `mismatch` are user-friendly aliases for `n_atoms_estimate` and
`d_cell`. You can also use the formal CALM metrics directly:

```python
result.plot_pareto(x="d_size", y="d_cell")
```

## 4) Build and write one interface

```python
candidate = result.best
print(candidate.summary())

interface = candidate.build(
    strain_partition="both",
    alpha=0.5,
    gap=1.5,
    vacuum=15.0,
)

interface.write("LiF_Li2O_interface.POSCAR")
print(interface.summary())
```

## 5) Project-backed workflows

For persistent campaigns, open a project. Project methods store results by
default and expose scientific collections for recovery and filtering.

```python
from calm import open_project

project = open_project("LiF_Li2O_campaign.calm")

print(project.structures().to_dataframe())
print(project.candidates().materials("LiF", "Li2O").pareto(scope="global").to_dataframe())
```

Direct SQLite, repository, and artifact-store objects are advanced/internal
implementation details. Users should normally recover work through
`project.materials()`, `project.structures()`, `project.candidates()`, and
`project.interfaces()`.
