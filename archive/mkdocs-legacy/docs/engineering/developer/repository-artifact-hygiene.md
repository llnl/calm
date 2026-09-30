# Repository artifact hygiene

CALM examples, documentation builds, test runs, and project workflows can produce many local artifacts. Those artifacts are useful for development, but they must not become source files or appear in clean handoff snapshots.

## Approved generated-output locations

Generated example outputs should go under:

```text
examples/outputs/<script-name>/
```

Temporary or local workspaces may be created under ignored paths such as:

```text
examples/workspace/
workspace/
*.calm/
```

Do not write generated artifacts directly into the repository root or directly into `examples/`.

## Ignored artifact classes

The repository should ignore at least these generated classes:

```text
site/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
__pycache__/
.coverage*
*.sqlite
*.db
*.calm/
examples/outputs/
examples/workspace/
examples/*_interface.POSCAR
examples/C*_interface.POSCAR
examples/*.png
examples/*.csv
examples/*.cif
```

Reference data and documentation assets can still be versioned when they live in an intentional source location, such as `examples/structures/` or a documented assets directory.

## Clean snapshot export

Use the clean snapshot exporter when preparing a repository archive for a new chat or handoff:

```bash
cd ~/Codes/calm
python scripts/export_clean_snapshot.py --output ~/Downloads/calm-clean-snapshot.zip
```

To inspect what would be included without writing a zip file:

```bash
python scripts/export_clean_snapshot.py --dry-run
```

The exporter uses Git to enumerate tracked files plus non-ignored source files, then excludes known generated-artifact patterns. It is intended for handoff snapshots, not for release packaging.

## Guardrail tests

The architecture hygiene tests enforce that:

- generated artifacts are not tracked by Git;
- `.gitignore` contains the core generated-artifact patterns;
- the clean snapshot exporter does not include generated artifacts in dry-run output.

Run the focused guardrail with:

```bash
pytest -q tests/arch/test_repository_artifact_hygiene.py
```

## Policy

If a workflow requires a generated file to be committed, put it in a clearly named source-data or documentation-assets directory and update this policy. Otherwise, generated files belong in ignored output directories.
