from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATHS_TO_SCAN = (
    ROOT / "calm",
    ROOT / "docs",
    ROOT / "tests",
    ROOT / "public_api.md",
    ROOT / "README.md",
    ROOT / "examples",
)

FORBIDDEN_QUEUE_PATTERNS = (
    "JobQueueService",
    "QueueWorker",
    "JobRepository",
    "SqlAlchemyJobRepository",
    "queue_prototype_search",
    "queue_registry_search",
    "queue_strain_partition_scan",
    "list_queued_jobs",
    "list_all_jobs",
    "get_queue_summary",
    "execute_queue",
    "execute_next_job",
    "start_queue_worker",
    "stop_queue_worker",
    "is_queue_worker_running",
    "calm.project.runner",
    "run_until_empty",
    "run_worker_loop",
    "execute_claimed_run",
    "default_run_handlers",
    "examples/queue_worker.py",
    "examples/queue_monitor.py",
    "examples/task_queue_demo.py",
    "CREATE TABLE IF NOT EXISTS jobs",
    "ix_jobs_",
    "Job = object",
    "self.jobs",
    "test_job_queue",
)

ALLOWED_FILES = {"tests/architecture/test_no_task_queue_surface.py"}


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for root in PATHS_TO_SCAN:
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
                continue
            if path.suffix not in {".py", ".md", ".txt", ".yml", ".yaml"}:
                continue
            files.append(path)
    return files


def test_removed_task_queue_surface_is_not_reintroduced() -> None:
    offenders: list[str] = []
    for path in _iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_QUEUE_PATTERNS:
            if pattern in text:
                offenders.append(f"{rel}: contains removed queue pattern {pattern!r}")
    assert offenders == [], "Removed task/job queue surface was reintroduced:\n" + "\n".join(sorted(set(offenders)))


def test_workspace_domain_model_imports_do_not_fall_back_to_object() -> None:
    path = ROOT / "calm" / "project" / "runtime" / "workspace.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    imported_from_models: set[str] = set()
    object_assignments: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "domain.models":
            imported_from_models.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module == "..domain.models":
            imported_from_models.update(alias.name for alias in node.names)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id == "object":
            object_assignments.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )

    assert "Job" not in imported_from_models
    assert "Job" not in object_assignments
    assert not ({"Bulk", "DerivedInterface", "Run"} & object_assignments)


def test_unit_of_work_does_not_expose_removed_jobs_attribute() -> None:
    path = ROOT / "calm" / "project" / "infrastructure" / "db" / "uow.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "jobs"
    ]
    assert offenders == []
