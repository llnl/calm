# Persistent project query and reporting

CALM can be used as a high-level workflow layer around a persistent `.calm`
project directory. The public project facade stores lightweight reporting rows
for searches, candidates, built interfaces, datasets, and energy records so that
users can reopen a project and recover tables and plots without interacting with
internal database tables.

The companion script is:

```bash
See runnable examples in the Example Scripts guide: `docs/guides/examples/index.md`.
```

## Workflow outline

```python
from calm import SearchSettings, Surface, open_project

project = open_project("LiF_Li2O_public_project.calm")

surface_a = Surface("LiF.poscar", miller=(1, 1, 1), thickness=10.0, material="LiF")
surface_b = Surface("Li2O.poscar", miller=(1, 1, 1), thickness=10.0, material="Li2O")

result = project.search_interfaces(
    surface_a,
    surface_b,
    name="LiF_Li2O_111_screen",
    settings=SearchSettings(max_candidates=8, max_principal_strain=0.10),
)
```

The search result is persisted through the public project facade. Candidate rows
can then be queried and exported:

```python
candidates = project.candidates().search("LiF_Li2O_111_screen").materials("LiF", "Li2O")
rows = candidates.to_rows(view="all")
candidates.write_table("tables/candidates.csv", view="all")
candidates.plot_pareto(save="plots/candidate_pareto.png")
```

## Build and persist interfaces

Live search candidates can be built into atomistic interface models. Saving those
models makes built-interface rows available through `project.interfaces()`:

```python
selection = result.select(pareto=True, n=2)
dataset = selection.build_dataset(name="LiF_Li2O_top2", gap=1.5, vacuum=12.0)

for i, interface in enumerate(dataset.interfaces):
    project.save(interface, name=f"interface_{i:04d}")

project.interfaces().write_table("tables/interfaces.csv", view="all")
project.interfaces().plot_build_summary(save="plots/interface_build_summary.png")
```

## Dataset and manifest reporting

Saving an `InterfaceDataset` records dataset summary rows and per-structure
manifest rows:

```python
project.save(dataset, name="LiF_Li2O_top2")
project.datasets().write_table("tables/datasets.csv", view="all")
project.datasets().write_manifest("tables/dataset_manifest.csv")
```

## Energy reporting rows

Energy calculations can be stored as public energy rows. The example uses
synthetic energy rows so it does not require a calculator backend in the default
example suite.

```python
project.save(
    {
        "energy_uid": "energy:example:0000",
        "build_uid": "build:example:0000",
        "calc_uid": "calc:synthetic:demo",
        "status": "succeeded",
        "gamma_eV_per_A2": 0.025,
        "gamma_J_per_m2": 0.4005,
    },
    name="synthetic_energy_0000",
)

project.energies().calculator("synthetic").write_table("tables/energies.csv", view="all")
project.energies().plot_distribution(save="plots/energy_distribution.png")
```

## Reopen and recover reports

A `.calm` project can be reopened later and queried through the same public
collections:

```python
from calm import open_project

reopened = open_project("LiF_Li2O_public_project.calm")
reopened.candidates().search("LiF_Li2O_111_screen").write_table("tables/reopened_candidates.csv")
reopened.interfaces().search("LiF_Li2O_111_screen").write_table("tables/reopened_interfaces.csv")
reopened.datasets().write_table("tables/reopened_datasets.csv")
reopened.energies().calculator("synthetic").write_table("tables/reopened_energies.csv")
```

## Current limitations

The public query layer stores JSON-native reporting rows. These rows are intended
for inspection, filtering, table export, and plotting. Rebuilding atomistic
interfaces from a reopened lightweight candidate row still requires the live
candidate objects or future archived prototype payloads.
