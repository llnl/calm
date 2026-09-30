# Building and Installing CALM with Conda (Local)

How to build and install CALM as a conda package locally without publishing to conda-forge or anaconda.org.

---

## Overview

You can build CALM as a conda package and install it locally. This is useful for:
- **Testing** the conda recipe before publishing
- **Internal distribution** within LLNL (share the built package)
- **Conda environment management** with all dependencies handled by conda
- **Reproducible environments** across different systems

---

## Prerequisites

### Install conda-build

```bash
# If using conda
conda install conda-build

# If using mamba (faster)
mamba install conda-build
```

---

## Building the Package Locally

### 1. Navigate to Repository Root

```bash
cd /path/to/calm
```

### 2. Build the Conda Package

```bash
# Build for your current platform
conda build conda-recipe

# Or with mamba (faster)
mamba build conda-recipe
```

**Build output:**
```
BUILD START: ['calm-0.1.0-py_0.tar.bz2']
...
TEST START: calm-0.1.0-py_0
...
TEST END: calm-0.1.0-py_0
...
# Automatic uploading is disabled
# If you want to upload package(s) to anaconda.org later, type:

anaconda upload /path/to/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
```

The built package is saved to:
```
~/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
```

Or on some systems:
```
~/miniforge3/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
~/miniconda3/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
```

---

## Installing the Local Package

### Option 1: Install Directly from Local Build

```bash
# Install from local build directory
conda install -c local calm

# Or with mamba
mamba install -c local calm
```

### Option 2: Install from Specific File

```bash
# Find the built package
conda build conda-recipe --output

# Install it
conda install /path/to/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2

# Or with mamba
mamba install /path/to/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
```

### Option 3: Create Environment with CALM

```bash
# Create new environment with CALM
conda create -n calm-env python=3.11 -c local calm

# Or with mamba
mamba create -n calm-env python=3.11 -c local calm

# Activate and use
conda activate calm-env
python -c "from calm import open_workspace; print('Success!')"
```

---

## Verifying Installation

```bash
# Activate environment
conda activate calm-env

# Check CALM is installed
conda list calm

# Test import
python -c "from calm import open_workspace; print('CALM installed via conda!')"

# Check version
python -c "import calm; print(calm.__version__ if hasattr(calm, '__version__') else 'version not set')"
```

---

## Sharing Built Packages Internally

### Copy Built Package to Shared Location

```bash
# Find the built package
PACKAGE=$(conda build conda-recipe --output)
echo $PACKAGE

# Copy to shared network drive (example)
cp $PACKAGE /shared/llnl/conda-packages/

# Or create a local channel
mkdir -p /shared/llnl/conda-channel/noarch
cp $PACKAGE /shared/llnl/conda-channel/noarch/
conda index /shared/llnl/conda-channel
```

### Install from Shared Location

```bash
# Method 1: Direct install
conda install /shared/llnl/conda-packages/calm-0.1.0-py_0.tar.bz2

# Method 2: Add as channel
conda install -c file:///shared/llnl/conda-channel calm

# Method 3: Add channel to conda config
conda config --add channels file:///shared/llnl/conda-channel
conda install calm
```

---

## Building for Multiple Python Versions

```bash
# Build for Python 3.10
conda build conda-recipe --python=3.10

# Build for Python 3.11
conda build conda-recipe --python=3.11

# Build for Python 3.12
conda build conda-recipe --python=3.12

# Build for all supported versions
conda build conda-recipe --python=3.10 --python=3.11 --python=3.12
```

**Note:** Since CALM uses `noarch: python`, one build works for all Python versions ≥3.10.

---

## Updating the Package

When you make changes to CALM:

### 1. Update Version Number

Edit `pyproject.toml`:
```toml
version = "0.1.1"  # Increment version
```

Edit `conda-recipe/meta.yaml`:
```yaml
{% set version = "0.1.1" %}
```

### 2. Rebuild Package

```bash
conda build conda-recipe
```

### 3. Reinstall in Environment

```bash
# Update from local channel
conda update -c local calm

# Or remove and reinstall
conda remove calm
conda install -c local calm
```

---

## Troubleshooting

### Build Fails with Missing Dependencies

**Issue:** Build can't find dependencies

**Solution:** Ensure all dependencies are available in conda:
```bash
# Check if dependencies exist
conda search numpy scipy ase spglib sqlalchemy

# Some packages might need conda-forge channel
conda build conda-recipe -c conda-forge
```

### Package Not Found After Building

**Issue:** `conda install -c local calm` fails

**Solution:**
```bash
# Find where conda-bld is located
conda info

# Look for "package cache" path
# The package should be in: <conda_root>/conda-bld/noarch/

# If not in local channel, install directly
conda install ~/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2
```

### Import Test Fails During Build

**Issue:** Test imports fail during `conda build`

**Solution:** Check that all imports in `meta.yaml` test section work:
```yaml
test:
  imports:
    - calm
    - calm.api  # If this fails, check module exists
```

### Wrong Python Version

**Issue:** Built for wrong Python version

**Solution:**
```bash
# Specify Python version explicitly
conda build conda-recipe --python=3.11

# Or use variant config file (advanced)
```

---

## Development Workflow with Conda

### 1. Development Environment

```bash
# Create dev environment with editable install
conda create -n calm-dev python=3.11 numpy scipy ase spglib sqlalchemy
conda activate calm-dev
cd /path/to/calm
pip install -e ".[dev]"
```

### 2. Testing Conda Build

```bash
# Build package locally
conda build conda-recipe

# Test in fresh environment
conda create -n calm-test python=3.11 -c local calm
conda activate calm-test
pytest /path/to/calm/tests
```

### 3. Internal Distribution

```bash
# Build and copy to shared location
conda build conda-recipe
cp ~/conda-bld/noarch/calm-*.tar.bz2 /shared/calm-releases/
```

---

## Creating a Local Conda Channel

For easy internal distribution:

### 1. Create Channel Directory

```bash
mkdir -p /shared/llnl/conda-channel/noarch
```

### 2. Copy Packages

```bash
cp ~/conda-bld/noarch/calm-0.1.0-py_0.tar.bz2 /shared/llnl/conda-channel/noarch/
```

### 3. Index Channel

```bash
conda index /shared/llnl/conda-channel
```

### 4. Add to Conda Config

```bash
# Add channel (persistent)
conda config --add channels file:///shared/llnl/conda-channel

# Or use in command
conda install -c file:///shared/llnl/conda-channel calm
```

---

## Alternative: Building Without conda-build

If you don't want to use `conda-build`, you can still use conda for dependencies:

```bash
# Create environment with dependencies
conda create -n calm python=3.11 numpy scipy ase spglib sqlalchemy

# Install CALM with pip
conda activate calm
pip install -e /path/to/calm
```

This gives you conda dependency management without building a conda package.

---

## Comparison: conda vs pip

| Feature | conda install | pip install |
|---------|---------------|-------------|
| **Dependency resolution** | Binary, all dependencies | Python-only |
| **Non-Python deps** | Yes (e.g., compilers, libraries) | No |
| **Environment isolation** | Excellent | Good (virtualenv) |
| **Speed** | Slower install, faster imports | Faster install |
| **Scientific packages** | Optimized binaries | May need compilation |
| **Distribution** | .tar.bz2 packages | .whl or .tar.gz |

**For CALM:**
- Use conda if you want complete environment management
- Use pip if you only need Python packages
- Both work equally well since CALM is pure Python

---

## Next Steps

### For Internal LLNL Use

1. Build package locally: `conda build conda-recipe`
2. Copy to shared drive
3. Share installation instructions with colleagues

### For Future Public Release

When ready to publish to conda-forge:
1. Create conda-forge feedstock (separate repo)
2. Update `meta.yaml` source URL to GitHub/GitLab release
3. Submit PR to conda-forge
4. See: [conda-forge documentation](https://conda-forge.org/docs/maintainer/adding_pkgs.html)

---

## Summary Commands

```bash
# Build locally
conda build conda-recipe

# Install from local build
conda install -c local calm

# Create new environment with CALM
conda create -n myenv python=3.11 -c local calm

# Verify installation
conda activate myenv
python -c "from calm import open_workspace; print('Success!')"

# Update after rebuilding
conda update -c local calm
```

---

## Related Documentation

- [Conda Build Documentation](https://docs.conda.io/projects/conda-build/)
- [Conda User Guide](https://docs.conda.io/projects/conda/)
- [Conda-Forge Contributing Guide](https://conda-forge.org/docs/maintainer/)
