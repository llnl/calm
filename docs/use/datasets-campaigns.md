# Datasets and campaigns

<p class="calm-lede">
Build provenance-aware learning datasets from completed interface workflows and use campaigns to run or compare repeated cases without making either feature a requirement for ordinary interface construction.
</p>

## Outcome

You can create a dataset with explicit features, targets, grouping, validation, and deterministic splits; export it with structures and a checksum manifest; and optionally define a campaign that applies a common workflow policy across named cases.

Datasets and campaigns are advanced study-management tools. A CALM study can be complete without either one.

## When to use it

Use a dataset when model development or statistical analysis requires a joined table of structures, workflow results, features, targets, and provenance.

Use a campaign when several named systems or policy variants should run through the same declared stages and be compared consistently.

Do not create a dataset simply to export one table, and do not create a campaign for a single interactive workflow that is already clear as ordinary project operations.

## Prerequisites

Dataset items must already exist in the project. For a supervised interfacial-energy dataset, that typically means completed relaxed structures, raw energies, and derived thermodynamic results.

```python
search = project.search("lif-li2o-100")
results = search.thermodynamic_results(
    status="completed",
    latest_run=True,
)
if not results:
    raise RuntimeError("No completed thermodynamic results are available")
```

Campaign prerequisites depend on the stages included. A campaign that starts at energy evaluation can reuse existing interfaces; one that starts at search requires exact surface inputs.

## Scientific decisions

### Define features and targets explicitly

Every feature and target should identify:

- its public data source;
- data type;
- units where applicable;
- whether it is required; and
- its scientific meaning.

A convenient column is not automatically a meaningful descriptor or target.

### Prevent information leakage

Related structures must not be split independently when they share a parent candidate, prototype, material pair, or other information that would make evaluation optimistic. `group_by` declares the lineage keys that must stay together.

### Define duplicate and failure policies

Choose whether repeated items should raise or be skipped and whether incomplete items invalidate the dataset. These are part of dataset identity and should not change silently during accumulation.

### Decide campaign stage ownership

A campaign case should state which existing search or surface pair it uses and which stages it runs. Avoid combining unrelated scientific systems only because they share a software configuration.

## Minimal procedure

### Create and validate a dataset

```python
from calm import (
    DatasetFeature,
    DatasetSettings,
    DatasetSplitSettings,
    DatasetTarget,
)

settings = DatasetSettings(
    schema_version="calm.interface_learning.v1",
    duplicate_policy="skip",
    failure_policy="error",
    require_complete_provenance=True,
    features=(
        DatasetFeature(
            name="interface_area_A2",
            source="thermodynamic.normalization_area_A2",
            units="angstrom^2",
        ),
        DatasetFeature(
            name="maximum_force_eV_per_A",
            source="relaxation.max_force_eV_per_A",
            units="eV/angstrom",
        ),
    ),
    targets=(
        DatasetTarget(
            name="work_of_adhesion_J_per_m2",
            source="thermodynamic.value_J_per_m2",
            units="J/m^2",
        ),
    ),
    group_by=("lineage.prototype",),
    split=DatasetSplitSettings(
        train_fraction=0.8,
        validation_fraction=0.1,
        test_fraction=0.1,
        seed=2026,
    ),
)

dataset = project.create_dataset(
    "lif-li2o-learning",
    results,
    settings=settings,
    description="Relaxed interface structures with explicit energy targets.",
    tags=["interface", "learning"],
)

validation = dataset.validate()
validation.raise_for_errors()
readiness = dataset.validate_ml()
readiness.raise_for_errors()
```

### Export the dataset

```python
exported = dataset.export(
    "exports/lif-li2o-learning",
    manifest_format="json",
    include_structures=True,
    structure_format="extxyz",
    overwrite=True,
)
print(exported.summary())
```

The export includes a machine-readable manifest and checksums. Preserve these with the exported structures and table.

### Define and run a campaign

```python
from calm import CampaignCase, CampaignSettings, DatasetSettings

base = CampaignCase(
    name="LiF_Li2O_100",
    search_name="lif-li2o-100",
)

cases = CampaignCase.grid(
    base,
    axes={
        "dataset_policy": (
            CampaignCase.variant(
                "strict",
                dataset_settings=DatasetSettings(
                    schema_version="calm.raw_energy.v1",
                    duplicate_policy="error",
                    failure_policy="error",
                ),
            ),
            CampaignCase.variant(
                "resume-safe",
                dataset_settings=DatasetSettings(
                    schema_version="calm.raw_energy.v1",
                    duplicate_policy="skip",
                    failure_policy="error",
                ),
            ),
        )
    },
)

campaign = project.create_campaign(
    name="lif-li2o-energy-policies",
    cases=cases,
    settings=CampaignSettings(
        stages=("energy", "dataset"),
        energy_backend="real",
        dataset_name_template="{campaign}_{case}",
        on_error="raise",
    ),
)

result = campaign.run(
    resume=True,
    export_root="exports/campaign",
)
```

## Inspect the result

Inspect dataset membership and splits:

```python
dataset.to_table(view="learning").display()
print(dataset.groups())
print(dataset.split())
```

Project-level queries remain available:

```python
project.datasets().to_table().display()
project.dataset_items("lif-li2o-learning").to_table().display()
```

Inspect and compare a campaign:

```python
print(result.summary())
result.write_table("exports/campaign-results.csv")

comparison = result.comparison().rank_by("energy_raw_eV_mean")
comparison.write_table("exports/campaign-comparison.csv")
```

A campaign comparison is only meaningful when the compared cases share compatible quantities and protocols.

## Interpretation

A dataset is a declared scientific join, not merely a CSV file. Its meaning depends on feature and target sources, units, membership criteria, provenance completeness, grouping, and split policy.

A leakage-safe split prevents related groups from crossing train, validation, and test partitions. It does not guarantee that the dataset is representative, balanced, unbiased, or suitable for a particular model.

A campaign standardizes repeated execution and comparison. It does not turn unlike systems or unlike reference conventions into comparable scientific observations.

## Common variations

### Add items later

```python
project.add_dataset_items("lif-li2o-learning", additional_results)
report = project.validate_dataset("lif-li2o-learning")
report.raise_for_errors()
```

Dataset declarations remain fixed; appended items follow the saved duplicate and failure policies.

### Build an unsplit analysis dataset

Omit `split` when train/validation/test assignment is not required. Keep `group_by` if group identity remains scientifically important.

### Run only selected campaign stages

```python
CampaignSettings(stages=("search", "build"))
```

A case must provide the inputs required by its first stage. Later stages can reuse compatible saved work when `resume=True`.

### Reopen campaign results

```python
campaign = project.campaign("lif-li2o-energy-policies")
for run in campaign.runs():
    print(run.id_short, run.status)
```

## Common problems

### Dataset validation reports missing fields

Inspect the feature or target source, item stage, completed result type, and provenance requirements. Do not replace a required scientific value with a silent default.

### Related structures appear in different splits

Review `group_by` and confirm that the chosen lineage key identifies all related examples. Recreate the dataset declaration if the grouping policy was scientifically wrong.

### Dataset creation raises an identity conflict

The same name was used with a different declaration. Use a new name or restore the original schema, policies, features, targets, grouping, and split settings.

### A campaign case fails while others complete

Inspect `result.failures`, the case status, and the first failing stage. `on_error="record"` preserves failures for comparison; `on_error="raise"` stops immediately.

### Campaign rankings combine incompatible values

Verify quantity, units, calculator, reference convention, and normalization before ranking. Software-level availability does not establish scientific comparability.

## Exact API

- [`DatasetFeature`, `DatasetTarget`, dataset settings, and campaign declarations](../reference/api/inputs-settings.md)
- [`Project` dataset and campaign operations](../reference/api/project.md)
- [Dataset, campaign, validation, and export result objects](../reference/api/returned-objects.md)
