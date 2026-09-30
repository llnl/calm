# CALM conda recipe

This is CALM's **internal local-source qualification recipe** for stable version
`1.0.0`. It is not a public conda-forge recipe and it is not a release-source
recipe.

## Package policy

The conda artifact mirrors the import-light Python base package:

```text
python >=3.10,<3.13
numpy >=1.26,<3
sqlalchemy >=2.0,<3
```

Science dependencies are not bundled. Install ASE, SciPy, and spglib separately
for atomistic and crystallographic workflows, using a qualified CALM environment
or an equivalent reviewed environment.

`meta.yaml` is the sole build authority. It installs with:

```text
python -m pip install . -vv --no-deps --no-build-isolation
```

The removed `build.sh` and `bld.bat` files must not return.

## Static validation

From the repository root:

```bash
python engineering/qualification/check_conda_recipe.py --show-current
```

The checker derives the package version, Python range, build requirements, and
base runtime dependencies from `pyproject.toml`; verifies the MIT expression
and the exact `LICENSE` and `NOTICE` files; and rejects additional or competing
recipe files.

## Qualified local build

A local `source.path` recipe copies the working tree, including uncommitted
changes. Qualification evidence therefore requires an exact clean commit.
Before building:

```bash
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

`git status --short` must produce no output. Then build without upload and keep
repository-local output under the ignored `build/` tree:

```bash
rm -rf build/qualification/conda-channel
conda build conda-recipe \
  --no-anaconda-upload \
  --output-folder "$PWD/build/qualification/conda-channel"
```

Conda-build automatically executes `conda-recipe/run_test.py` in a fresh test
environment after the build. The test verifies the package version, public
`calm.open_project` entrypoint, noarch package record, base dependency closure,
and installed package-file boundary.

Inspect the expected artifact path with:

```bash
conda build conda-recipe --output
```

## Publication boundary

A future publication recipe must be created separately from an immutable source
archive with a recorded SHA-256 digest. Do not convert this local-path recipe by
adding commented URL placeholders or by treating a dirty local build as release
evidence.

The local package is licensed under the MIT License. `meta.yaml` publishes the
`MIT` expression and packages both the repository `LICENSE` and `NOTICE` files.
This resolves license metadata only; a public conda recipe still requires the
separate immutable-source and digest policy described above.

## Related documentation

- [Repository README](../README.md)
- [Installation guide](../docs/install.md)
- [Environment overview](../environments/README.md)
