# Development Documentation

Internal development guides and references for CALM contributors.

## Contents

### [Testing and Coverage](testing_and_coverage.md)
Complete guide to running tests and measuring code coverage locally:
- Running pytest with various options
- Generating coverage reports (terminal, HTML, XML)
- Coverage configuration and goals
- Best practices for writing tests

### [CI/CD Coverage Integration](ci_coverage.md)
How coverage is integrated with GitLab CI:
- Automatic coverage tracking on every commit
- Coverage badge in README
- Coverage reports in merge requests
- Downloadable HTML reports from artifacts
- Troubleshooting coverage issues

### [Conda Local Build Guide](conda_local_build.md)
Building and installing CALM as a conda package:
- Building conda packages locally
- Installing from local builds
- Creating conda environments with CALM
- Internal distribution within LLNL
- Local conda channels for team sharing

### Project Structure

**Public-facing docs:**
- `docs/tutorials/` - Step-by-step learning guides
- `docs/guides/workflows/` - Task-oriented recipes
- `docs/mathematics/algorithms/` - Mathematical foundations
- `docs/concepts/` - Background knowledge
- `docs/reference/` - API reference

**Development docs (this directory):**
- Internal development practices
- Testing and coverage guides
- Architecture notes
- LLNL-specific deployment guides

---

## Quick Links

**Testing:**
```bash
# Run all tests
pytest

# Run with coverage
./run_coverage.sh

# View HTML coverage report
open htmlcov/index.html
```

**Development install:**
```bash
pip install -e ".[dev]"
```

**Documentation build:**
```bash
pip install -e ".[docs]"
mkdocs serve
```

---

## Contributing

See [Contributing Guide](../contributing.md) for general contribution guidelines.
