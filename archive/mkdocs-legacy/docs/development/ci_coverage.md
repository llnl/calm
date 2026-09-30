# CI/CD Coverage Integration

How test coverage is integrated with GitLab CI for CALM.

---

## Overview

Coverage is automatically measured on every commit and displayed as:
- **Coverage badge** in README.md
- **Coverage percentage** in merge requests
- **Coverage trends** over time
- **Downloadable HTML reports** from CI artifacts

---

## GitLab CI Configuration

### Coverage Job

The `pytest:py311` job in `.gitlab-ci.yml` includes coverage:

```yaml
pytest:py311:
  stage: test
  script:
    - pip install -e ".[dev]"
    - pytest -q --junitxml=junit.xml --timeout=300 \
        --cov=calm \
        --cov-report=term \
        --cov-report=xml \
        --cov-report=html
  coverage: '/TOTAL.*\s+(\d+)%/'  # Regex to extract coverage %
  artifacts:
    reports:
      junit: junit.xml               # Test results
      coverage_report:
        coverage_format: cobertura   # GitLab coverage format
        path: coverage.xml
    paths:
      - htmlcov/                     # HTML coverage report
```

### Key Components

**1. Coverage flags:**
- `--cov=calm` - Measure coverage for the calm package
- `--cov-report=term` - Display in terminal (for logs)
- `--cov-report=xml` - Generate coverage.xml (for GitLab)
- `--cov-report=html` - Generate htmlcov/ (for download)

**2. Coverage regex:**
```yaml
coverage: '/TOTAL.*\s+(\d+)%/'
```
This regex extracts the coverage percentage from pytest output:
```
TOTAL                              12712   8234  35%
                                                ^^
```

**3. Artifacts:**
- `junit.xml` - Test results for GitLab test reports
- `coverage.xml` - Coverage data in Cobertura format
- `htmlcov/` - Interactive HTML coverage report

---

## Coverage Badge

Badge in README.md:
```markdown
[![Coverage](https://czgitlab.llnl.gov/weitzner/calm/badges/main/coverage.svg)](...)
```

**Badge URL format:**
```
https://czgitlab.llnl.gov/<username>/<project>/badges/<branch>/coverage.svg
```

The badge automatically updates after each successful pipeline run on the main branch.

---

## Viewing Coverage Reports

### 1. GitLab UI

**Coverage percentage:**
- Navigate to: **CI/CD → Pipelines**
- Click on a pipeline
- Look for coverage percentage next to test job

**Coverage trends:**
- Navigate to: **Analytics → Repository Analytics**
- View coverage graph over time

### 2. Merge Requests

Coverage is displayed in merge requests:
- Overall coverage change (+/- %)
- Coverage per file
- Lines added/removed that are covered/uncovered

### 3. Downloadable HTML Report

From any pipeline:
1. Go to **CI/CD → Pipelines**
2. Click on the pipeline
3. Click **pytest:py311** job
4. Click **Browse** (top right) or **Download artifacts**
5. Navigate to `htmlcov/index.html`

---

## Coverage Requirements

### Minimum Coverage

Currently no minimum coverage threshold enforced, but consider adding:

```yaml
pytest:py311:
  script:
    - pytest --cov=calm --cov-report=term --cov-fail-under=80
```

This will fail the pipeline if coverage drops below 80%.

### Coverage Goals

See [testing_and_coverage.md](testing_and_coverage.md) for module-specific coverage goals.

**Suggested thresholds:**
- Overall: 75%+
- Core algorithms: 85%+
- Public API: 90%+
- Visualization: 60%+ (optional dependency)

---

## Interpreting Coverage Reports

### GitLab Coverage Report

After a pipeline runs, GitLab shows:
- **Changed files** with coverage data
- **New lines** and their coverage
- **Diff view** with coverage highlights

**Colors:**
- 🟢 **Green**: Line is covered by tests
- 🔴 **Red**: Line is not covered
- ⚪ **Gray**: Non-executable line (comments, blank)

### HTML Coverage Report

Download and open `htmlcov/index.html`:

**Main page:**
- List of all modules
- Coverage percentage per module
- Sort by name or coverage
- Filter by package

**File view:**
- Line-by-line coverage
- Green = covered, red = not covered
- Click line numbers to see which tests cover that line
- Branch coverage shows if/else paths

---

## Troubleshooting

### Coverage Not Showing in GitLab

**Check regex pattern:**
```bash
# Run pytest locally and check output format
pytest --cov=calm --cov-report=term
# Look for line like: TOTAL  12712  8234  35%
```

If format changed, update regex in `.gitlab-ci.yml`.

**Verify coverage.xml generated:**
```yaml
artifacts:
  reports:
    coverage_report:
      coverage_format: cobertura
      path: coverage.xml
```

### Badge Not Updating

1. Ensure pipeline ran successfully on `main` branch
2. Check that coverage regex matched (look at job logs)
3. Clear browser cache
4. Badge updates after pipeline completes (may take 1-2 minutes)

### Coverage Dropped Unexpectedly

**Possible causes:**
1. New code added without tests
2. Tests skipped on CI but run locally
3. Different Python version on CI
4. Missing test dependencies

**Debug:**
```bash
# Compare local vs CI coverage
pytest --cov=calm --cov-report=term  # Local

# Check which tests ran on CI
# (view CI job logs for list of tests)
```

---

## Coverage in Development Workflow

### Before Committing

```bash
# Check coverage locally
./run_coverage.sh

# Or specific tests
pytest tests/test_mymodule.py --cov=calm --cov-report=term
```

### In Merge Requests

1. Push commits
2. Wait for CI pipeline
3. Check coverage change in MR
4. Add tests if coverage dropped significantly
5. Review uncovered lines in diff view

### Coverage-Driven Development

1. Write failing test
2. Implement feature
3. Check coverage: `pytest --cov=calm`
4. Add tests for uncovered branches
5. Commit when coverage is acceptable

---

## Advanced Configuration

### Parallel Coverage

Run tests in parallel and combine coverage:

```yaml
pytest:py311:parallel:
  parallel: 4
  script:
    - pytest --cov=calm --cov-report=xml --cov-context=test -n auto
  after_script:
    - coverage combine
    - coverage xml
```

### Per-Module Coverage

Track coverage per module:

```yaml
pytest:core:
  script:
    - pytest tests/test_interface*.py --cov=calm.interface

pytest:slab:
  script:
    - pytest tests/test_slab*.py --cov=calm.slab
```

### Coverage Diff

Show only coverage for changed lines:

```bash
# In CI or locally
diff-cover coverage.xml --compare-branch=main
```

Requires `pip install diff-cover`.

---

## Related Documentation

- [Testing and Coverage Guide](testing_and_coverage.md) - Local coverage usage
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/yaml/)
- [GitLab Test Coverage](https://docs.gitlab.com/ee/ci/testing/test_coverage_visualization.html)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)

---

## Summary

**Coverage is automatically tracked in CI:**
- ✅ Badge in README
- ✅ Coverage percentage in pipelines
- ✅ Coverage change in merge requests
- ✅ Downloadable HTML reports
- ✅ Historical trends

**To view coverage:**
- **Badge**: See README
- **Percentage**: CI/CD → Pipelines
- **Trends**: Analytics → Repository Analytics
- **Details**: Download htmlcov/ artifacts
- **MR Diff**: Coverage tab in merge requests

**Coverage regex:** `/TOTAL.*\s+(\d+)%/`
