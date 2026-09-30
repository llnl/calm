# Repository resynchronization baseline

Patch generation must start from a trustworthy repository state.

## Baseline priority order

Use the first available source in this order:

1. A freshly uploaded repository archive from the user after a reported green run.
2. A repository archive whose patch state is explicitly described by the user.
3. A local working tree only when its provenance is clear and the user confirms it matches their checkout.

Do not generate a forward patch from an uncertain internal tree.

## Required baseline facts

Before producing a patch, record or infer:

- latest applied patch filename;
- latest green validation commands;
- current active milestone;
- whether the user reported local changes outside the patch series;
- next expected patch number.

## Standard user-side application path

Assume patches are downloaded to `~/Downloads` and applied from `~/Codes/calm`:

```bash
cd ~/Codes/calm
git apply --check ~/Downloads/NNNN-short-description.patch
git apply ~/Downloads/NNNN-short-description.patch
```

If the user reports a different checkout path, only the `cd` target changes. Patch paths should still use `~/Downloads` unless the user says otherwise.

## Failure handling

If `git apply --check` fails, stop. Do not ask the user to hand-edit the patch. Request the failure output and provide a corrective patch with a letter suffix, for example:

```text
0016a-fix-engineering-doc-baseline-conflict.patch
```
