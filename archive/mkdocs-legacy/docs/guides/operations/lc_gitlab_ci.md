# Using CALM with LLNL LC GitLab CI

This guide covers how to run CALM's CI/CD pipelines on LLNL's Livermore Computing (LC) GitLab using Jacamar runners.

## Overview

LLNL's LC GitLab (https://lc.llnl.gov/gitlab) uses **Jacamar runners** which execute jobs on CZ cluster login nodes or via SLURM batch jobs. This is different from standard GitLab CI which uses Docker containers.

**Key differences:**
- ❌ No Docker containers - Jobs run directly on LC systems
- ✅ Python from LC modules - Use `module load python/3.11`
- ✅ Shell or batch executor - Choose based on resource needs
- ✅ Virtualenv for isolation - Create `.venv` for clean dependencies

## Prerequisites

### 1. SSH Access to LC GitLab

**One-time setup from an LC machine (quartz, pascal, etc.):**

```bash
# Generate SSH key
cd $HOME/.ssh
ssh-keygen -t rsa -b 4096
# Press Enter for default filename and empty passphrase

# Display public key
cat id_rsa.pub
```

**Add to LC GitLab:**
1. Log in to https://lc.llnl.gov/gitlab
2. Go to: User menu → Edit profile → SSH Keys
3. Paste your $id_rsa.pub$ contents
4. Click "Add key"

**Test connection:**
```bash
ssh -p7999 git@czgitlab.llnl.gov
```

You should see:
```
PTY allocation request failed on channel 0
Welcome to GitLab, @<yourname>!
Connection to czgitlab closed.
```

### 2. Clone Repository on LC

```bash
# On quartz or other LC machine
cd /p/lustre1/<username>/  # Or your preferred location
git clone ssh://git@czgitlab.llnl.gov:7999/weitzner/calm.git
cd calm
```

## CI Configuration

### Current Setup

CALM's `.gitlab-ci.yml` is configured for LC's Jacamar runners:

```yaml
.lc_shell_template: &lc_shell_template
  tags:
    - quartz      # Use quartz cluster
    - shell       # Use shell executor (runs on login node)
  before_script:
    # Load Python module from LC software stack
    - module load python/3.11.8 || module load python/3.11 || module load python/3

    # Create and activate virtualenv
    - python3 -m venv .venv
    - source .venv/bin/activate

    # Upgrade pip
    - python -m pip install --upgrade pip
```

**Jobs:**
1. **pytest:py311** - Run test suite (15 min timeout)
2. **docs:mkdocs** - Build documentation (10 min timeout)
3. **build:dist** - Build Python packages (10 min timeout)
4. **pages** - Deploy docs to GitLab Pages (main branch only)
5. **dist:release** - Build release packages (tags only)

### Executor Types

#### Shell Executor (Current Setup)

**Pros:**
- ✅ Fast startup (no SLURM queue wait)
- ✅ Adequate for CI tasks (test, build, docs)
- ✅ Runs on login nodes
- ✅ Simpler configuration

**Cons:**
- ❌ Limited resources (login node constraints)
- ❌ Not suitable for large compute jobs

**When to use:** Standard CI tasks like testing, documentation building, package building

#### Batch Executor (Alternative)

**Pros:**
- ✅ Full compute node resources
- ✅ Isolated execution environment
- ✅ No login node load concerns

**Cons:**
- ❌ SLURM queue wait time
- ❌ Slower pipeline start
- ❌ More complex configuration

**When to use:** Compute-intensive CI tasks, performance testing, large-scale validation

**Example batch configuration:**

```yaml
.lc_batch_template: &lc_batch_template
  tags:
    - quartz
    - batch
  variables:
    LLNL_SLURM_SCHEDULER_PARAMETERS: "--nodes=1 -p pdebug --exclusive -t 10:00"
  before_script:
    - module load python/3.11
    - python3 -m venv .venv
    - source .venv/bin/activate
    - pip install --upgrade pip
```

## Typical CI Workflow

### 1. Push Code Changes

```bash
# Make changes
git add file.py
git commit -m "fix: update interface builder"
git push
```

### 2. Monitor Pipeline

**In browser:**
1. Go to: https://lc.llnl.gov/gitlab/weitzner/calm
2. Navigate to: CI/CD → Pipelines
3. Click on the running pipeline
4. Click on individual jobs to see logs

**From command line:**

```bash
# Check latest pipeline status
git log -1 --pretty=format:"%H" | head -c 8
# Then visit: https://lc.llnl.gov/gitlab/weitzner/calm/-/pipelines
```

### 3. Typical Timeline

**Expected duration:**
- **pytest:py311**: 3-5 minutes
- **docs:mkdocs**: 2-3 minutes
- **build:dist**: 1-2 minutes
- **Total**: 6-10 minutes

**If longer:**
- Check job logs for issues
- Look for dependency installation problems
- Verify Python module loaded correctly

## Troubleshooting

### Job Stuck in Pending

**Symptom:** Job shows "pending" for >5 minutes

**Causes:**
1. No runners available with matching tags
2. All runners busy
3. Runner maintenance

**Solutions:**
```bash
# Check runner status in GitLab:
# Settings → CI/CD → Runners

# Verify tags in .gitlab-ci.yml match available runners
# Common tags: quartz, shell, batch
```

### Module Load Failures

**Symptom:** `module: command not found` or $ModuleCmd_Load.c(244):ERROR$

**Causes:**
- Module environment not initialized
- Python module not available on cluster

**Solutions:**

```yaml
before_script:
  # Initialize module environment
  - source /etc/profile.d/00-modulepath.sh || true
  - source /usr/share/lmod/lmod/init/bash || true

  # Try multiple Python versions
  - module load python/3.11.8 || module load python/3.11 || module load python/3
```

### Pip Installation Timeouts

**Symptom:** `pip install` hangs or times out

**Causes:**
- Network connectivity issues
- Building packages from source (numpy, scipy)
- Insufficient /tmp space

**Solutions:**

```yaml
script:
  # Use pip cache
  - export PIP_CACHE_DIR="$CI_PROJECT_DIR/.cache/pip"

  # Prefer binary wheels
  - pip install --prefer-binary -e ".[dev]"

  # Set custom temp directory
  - export TMPDIR="$CI_PROJECT_DIR/.tmp"
  - mkdir -p $TMPDIR
```

### Virtualenv Creation Fails

**Symptom:** `Error: Command '...' returned non-zero exit status`

**Causes:**
- Insufficient disk space
- Permissions issues
- Corrupted cache

**Solutions:**

```bash
# Clean up old virtualenvs
rm -rf .venv/

# Clean pip cache
rm -rf .cache/pip/

# Push to trigger new pipeline
git commit --allow-empty -m "ci: retry pipeline"
git push
```

### Test Failures

**Symptom:** pytest fails with errors

**Diagnosis:**

```bash
# Run tests locally on LC machine
ssh quartz
cd /path/to/calm
module load python/3.11
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

**Common issues:**
1. Missing dependencies (spglib, ase)
2. Import errors (PYTHONPATH issues)
3. Test timeouts (use `--timeout=300`)

## Advanced Configuration

### Using Containers with Podman

If you need containers (e.g., for DFT calculators):

```yaml
container_job:
  stage: build
  tags:
    - quartz
    - batch
  variables:
    LLNL_SLURM_SCHEDULER_PARAMETERS: "--nodes=1 -p pdebug --exclusive"
  script:
    # Enable Podman on LC
    - /collab/usr/gapps/lcweg/containers/scripts/enable-podman.sh

    # Build container
    - podman build -t calm:latest .

    # Run tests in container
    - podman run --rm calm:latest pytest
```

**Documentation:** https://hpc.llnl.gov/services/cloud/containers/using-containers-ci-pipelines

### Multiple Python Versions

To test against multiple Python versions:

```yaml
.pytest_template: &pytest_template
  stage: test
  tags:
    - quartz
    - shell
  timeout: 15m
  script:
    - module load ${PYTHON_MODULE}
    - python3 -m venv .venv
    - source .venv/bin/activate
    - pip install -e ".[dev]"
    - pytest -q --junitxml=junit.xml

pytest:py310:
  <<: *pytest_template
  variables:
    PYTHON_MODULE: "python/3.10"

pytest:py311:
  <<: *pytest_template
  variables:
    PYTHON_MODULE: "python/3.11"

pytest:py312:
  <<: *pytest_template
  variables:
    PYTHON_MODULE: "python/3.12"
```

### Artifact Persistence

CI artifacts are stored for 1 week by default:

```yaml
build:dist:
  artifacts:
    paths:
      - dist/
    expire_in: 1 week  # or: 4 weeks, 30 days, never
```

**Download artifacts:**
1. Go to pipeline page
2. Click job name
3. Click "Download" button on right side

### Performance Optimization

**Use pip cache:**

```yaml
cache:
  key: "$CI_JOB_NAME"
  paths:
    - .cache/pip/
    - .venv/  # Cache entire virtualenv (faster than pip install)
```

**Parallel jobs:**

```yaml
# Run tests in parallel
pytest:unit:
  script: pytest tests/unit/ --timeout=300

pytest:integration:
  script: pytest tests/integration/ --timeout=600
```

## Best Practices

### 1. Test Locally First

Before pushing, test on an LC machine:

```bash
ssh quartz
cd /path/to/calm
module load python/3.11
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### 2. Use Timeouts

Always set job timeouts to prevent hung pipelines:

```yaml
pytest:py311:
  timeout: 15m  # Job-level timeout
  script:
    - pytest --timeout=300  # Per-test timeout (5 min)
```

### 3. Cache Dependencies

Cache virtualenv and pip to speed up subsequent runs:

```yaml
cache:
  key: "$CI_JOB_NAME-$CI_COMMIT_REF_SLUG"
  paths:
    - .cache/pip/
    - .venv/
```

### 4. Use Specific Python Versions

Specify exact Python module versions for reproducibility:

```yaml
before_script:
  - module load python/3.11.8  # Specific version
  # Fallback to minor version if needed
  # - module load python/3.11.8 || module load python/3.11
```

### 5. Clean Up Artifacts

Set appropriate expiration times:

```yaml
artifacts:
  expire_in: 1 week  # Test reports
  # expire_in: 4 weeks  # Release builds
  # expire_in: never  # Important releases
```

## Common Issues

### "No runners available"

**Check:**
1. Settings → CI/CD → Runners
2. Verify shared Jacamar runners are listed
3. Check job tags match available runners

### "Module command not found"

**Fix:**
```yaml
before_script:
  - source /etc/profile.d/00-modulepath.sh || true
  - module load python/3.11
```

### "Disk quota exceeded"

**Fix:**
```bash
# Clean up old CI artifacts on LC
cd /p/lustre1/<username>/calm
rm -rf .cache/ .venv/ .tmp/
```

### "Job timeout"

**Fix:**
```yaml
# Increase timeout
pytest:py311:
  timeout: 30m  # Default is 1 hour, but set explicitly
```

## Resources

**LLNL Documentation:**
- [LC GitLab Getting Started](https://hpc.llnl.gov/services/cloud/gitlab/getting-started-lc-gitlab)
- [LC GitLab CI/CD](https://hpc.llnl.gov/services/cloud/gitlab/using-cicd-lc-gitlab)
- [Containers in CI](https://hpc.llnl.gov/services/cloud/containers/using-containers-ci-pipelines)
- [Technical Bulletins](https://hpc.llnl.gov/updates-events/technical-bulletins-catalog)

**GitLab CI/CD:**
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [.gitlab-ci.yml Reference](https://docs.gitlab.com/ee/ci/yaml/)

**CALM Documentation:**
- <!-- [CALM README](../../README.md) (see repo root) -->
- <!-- [Contributing Guide](../../CONTRIBUTING.md) (see repo root) -->
- <!-- [CI Troubleshooting](../../CI_STALL_DIAGNOSIS.md) (see repo root) -->

## Contact

**LC GitLab Support:**
- Email: lc-hotline@llnl.gov
- Phone: (925) 422-4531
- Hours: M-F 8am-5pm Pacific

**CALM Project:**
- Issues: https://lc.llnl.gov/gitlab/weitzner/calm/-/issues
- Email: weitzner1@llnl.gov
