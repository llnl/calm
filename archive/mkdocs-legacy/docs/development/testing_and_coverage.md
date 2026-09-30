# Testing and Coverage

Guide to running tests and measuring test coverage for CALM development.

---

## Quick Start

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_public_api.py

# Run tests matching pattern
pytest -k "test_workspace"
```

### Run Tests with Coverage

```bash
# Terminal report
pytest --cov=calm --cov-report=term

# HTML report (recommended)
pytest --cov=calm --cov-report=html
open htmlcov/index.html  # View in browser

# Both terminal and HTML
pytest --cov=calm --cov-report=term --cov-report=html

# Use the convenience script
./run_coverage.sh
```

---

## Coverage Reports

### Terminal Report

Shows coverage summary in the terminal:

```bash
pytest --cov=calm --cov-report=term-missing
```

Output example:
```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
calm/__init__.py                       18      3 83.33%   23, 25, 41
calm/api.py                            43     16 62.79%   57-63, 177-178
...
-----------------------------------------------------------------
TOTAL                              12712  11732  7.71%
```

**Columns:**
- **Stmts**: Number of executable statements
- **Miss**: Number of statements not covered by tests
- **Cover**: Percentage covered
- **Missing**: Line numbers not covered

### HTML Report

Interactive HTML report with line-by-line coverage:

```bash
pytest --cov=calm --cov-report=html
open htmlcov/index.html
```

**Features:**
- Browse files with color-coded coverage
- Click files to see line-by-line coverage
- Green = covered, red = not covered
- Filter by module, package, or filename
- Sort by coverage percentage

### XML Report (CI/CD)

For GitLab CI or other tools:

```bash
pytest --cov=calm --cov-report=xml
```

Generates `coverage.xml` for CI/CD badge integration.

---

## Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["calm"]
omit = [
  "*/tests/*",
  "*/test_*.py",
  "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
  "pragma: no cover",
  "def __repr__",
  "raise NotImplementedError",
  "if __name__ == .__main__.:",
  "if TYPE_CHECKING:",
]
precision = 2
show_missing = true
```

### Excluding Code from Coverage

Use `# pragma: no cover` to exclude lines:

```python
def debug_function():  # pragma: no cover
    """This function is not tested"""
    print("Debug output")
```

---

## Running Specific Test Suites

### By Test Markers

CALM tests use pytest markers:

```bash
# Run smoke tests only (fast)
pytest -m smoke

# Run Workspace tests
pytest -m v2

# Run architecture boundary tests
pytest -m arch

# Exclude legacy tests
pytest -m "not legacy"
```

**Available markers:**
- `smoke`: Fast smoke tests for examples
- `legacy`: Legacy test suite
- `arch`: Architecture boundary tests
- `v2`: Workspace tests

### By Directory

```bash
# Run only public API tests
pytest tests/test_public_api.py

# Run all interface tests
pytest tests/test_interface*.py

# Run all tests in subdirectory
pytest tests/unit/
```

---

## Coverage Goals

### Current Status

Run `pytest --cov=calm --cov-report=term` to see current coverage.

### Target Coverage by Module

**High priority (aim for >80%):**
- `calm/api.py` - Public API
- `calm/project/` - Workspace and domain models
- `calm/interface/matching.py` - Core matching algorithm
- `calm/slab/` - Slab generation

**Medium priority (aim for >60%):**
- `calm/math2d/` - Mathematical utilities
- `calm/symmetry/` - Symmetry operations
- `calm/calculators/` - Calculator abstractions

**Lower priority:**
- `calm/viz/` - Visualization (optional dependency)
- `calm/extras/` - Experimental features
- `calm/project/ux/notebook.py` - Notebook helpers

---

## Continuous Integration

### GitLab CI Coverage

Add to `.gitlab-ci.yml`:

```yaml
test:coverage:
  stage: test
  tags:
    - dane
    - shell
  script:
    - pytest --cov=calm --cov-report=xml --cov-report=term
  coverage: '/TOTAL.*\s+(\d+\.\d+)%/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

This enables:
- Coverage percentage in merge requests
- Coverage badge in README
- Coverage trend tracking

---

## Coverage Badge

Add to README.md:

```markdown
[![Coverage](https://czgitlab.llnl.gov/weitzner/calm/badges/main/coverage.svg)](https://czgitlab.llnl.gov/weitzner/calm)
```

---

## Best Practices

### Writing Testable Code

1. **Keep functions small and focused**
   ```python
# Good - easy to test
def compute_strain(G_A, G_B):
 return log_strain(G_A, G_B)

# Bad - hard to test, does too much
def compute_and_save_strain(file_path, material_A, material_B):
 G_A = load_gram(file_path, material_A)
 G_B = load_gram(file_path, material_B)
 strain = log_strain(G_A, G_B)
 save_strain(file_path, strain)
 return strain
```

2. **Avoid side effects**
   - Pure functions are easier to test
   - Separate I/O from computation

3. **Use dependency injection**
   ```python
# Good - calculator can be mocked
def relax_structure(atoms, calculator):
 atoms.calc = calculator
 return optimize(atoms)

# Bad - hard to test without real calculator
def relax_structure(atoms):
 from calm.calculators import make_calculator
 atoms.calc = make_calculator("grace")
 return optimize(atoms)
```

### Writing Good Tests

1. **Test behavior, not implementation**
   ```python
# Good
def test_prototype_search_finds_matches():
    results = search_prototypes(slab_A, slab_B, k_max=5)
    assert len(results) > 0
    assert all(r.strain < 0.15 for r in results)

# Bad - tests internal implementation
def test_prototype_search_calls_hnf_enumerate():
    with mock.patch('calm.keys.hnf.enumerate_hnfs') as mock_hnf:
        search_prototypes(slab_A, slab_B)
        assert mock_hnf.called
```

2. **Use fixtures for common setup**
   ```python
import pytest

@pytest.fixture
def al_fcc():
    return bulk("Al", crystalstructure="fcc", a=4.05)

def test_slab_generation(al_fcc):
    slab = generate_slab(al_fcc, (1,1,1), layers=4)
    assert len(slab) == 4
```

3. **Test edge cases**
   - Zero/empty inputs
   - Large values
   - Invalid inputs
   - Boundary conditions

---

## Troubleshooting

### Coverage Not Updating

```bash
# Clear coverage data
rm .coverage coverage.xml
rm -rf htmlcov/

# Run fresh
pytest --cov=calm --cov-report=html
```

### Tests Failing Only in Coverage

Some tests may behave differently with coverage enabled:

```bash
# Run without coverage first
pytest tests/test_failing.py

# Then with coverage
pytest --cov=calm tests/test_failing.py
```

### Slow Coverage Runs

```bash
# Run coverage on subset
pytest --cov=calm tests/test_public_api.py

# Or exclude slow tests
pytest --cov=calm -m "not slow"
```

---

## Additional Resources

- **pytest documentation**: https://docs.pytest.org/
- **pytest-cov documentation**: https://pytest-cov.readthedocs.io/
- **Coverage.py documentation**: https://coverage.readthedocs.io/

---

## Summary Commands

```bash
# Quick test run
pytest

# Full coverage report
./run_coverage.sh

# Coverage with specific tests
pytest --cov=calm tests/test_public_api.py --cov-report=term

# HTML coverage report
pytest --cov=calm --cov-report=html && open htmlcov/index.html

# CI-ready coverage
pytest --cov=calm --cov-report=xml --cov-report=term
```
