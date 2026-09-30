from __future__ import annotations

import ast
import configparser
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTEST_CONFIG = REPOSITORY_ROOT / "pytest.ini"
BENCHMARK_ROOT = REPOSITORY_ROOT / "benchmarks"
BENCHMARK_TEST_ROOT = REPOSITORY_ROOT / "tests" / "unit" / "benchmarks"


def test_pytest_config_owns_repository_import_path() -> None:
    parser = configparser.ConfigParser()
    parser.read(PYTEST_CONFIG, encoding="utf-8")

    configured = parser.get("pytest", "pythonpath").split()
    assert configured == ["."]


def test_benchmark_tools_are_an_explicit_repository_package() -> None:
    initializer = BENCHMARK_ROOT / "__init__.py"
    assert initializer.is_file()
    assert "intentionally excluded" in initializer.read_text(encoding="utf-8")


def test_benchmark_tests_do_not_repair_sys_path_locally() -> None:
    for path in sorted(BENCHMARK_TEST_ROOT.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not isinstance(function, ast.Attribute):
                continue
            if function.attr not in {"append", "insert"}:
                continue
            owner = function.value
            assert not (
                isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "sys"
                and owner.attr == "path"
            ), f"local sys.path repair in {path.relative_to(REPOSITORY_ROOT)}"
