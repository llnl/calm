#!/usr/bin/env python3
"""Run the ten numbered examples in isolated processes for one or more passes."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EXAMPLES = REPO_ROOT / "examples"
SCRIPTS = tuple(f"{index:02d}_{name}.py" for index, name in (
    (1, "optimize_materials"),
    (2, "generate_surfaces"),
    (3, "search_interfaces"),
    (4, "compare_interface_searches"),
    (5, "build_interfaces"),
    (6, "refine_interfaces"),
    (7, "relax_interfaces"),
    (8, "evaluate_interface_energetics"),
    (9, "build_interface_dataset"),
    (10, "run_interface_campaign"),
))


def _stage(work_root: Path) -> Path:
    if work_root.exists():
        shutil.rmtree(work_root)
    staged = work_root / "examples"
    staged.mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy2(SOURCE_EXAMPLES / name, staged / name)
    shutil.copytree(SOURCE_EXAMPLES / "Structures", staged / "Structures")
    return staged


def _run(script: Path, *, cwd: Path, timeout: int) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT), environment.get("PYTHONPATH", "")) if part
    )
    environment.setdefault("MPLBACKEND", "Agg")
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    print(f"[{completed.returncode}] {script.name}")
    if completed.stdout:
        print(completed.stdout)
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise RuntimeError(f"numbered example failed: {script.name}")


def _verify(staged: Path) -> None:
    project = staged / "example_project.calm"
    manifest = project / "calm-reproducibility-manifest.json"
    if not project.is_dir():
        raise RuntimeError("numbered examples did not create the shared project")
    if not (staged / "outputs").is_dir():
        raise RuntimeError(
            "numbered examples did not create the shared outputs directory"
        )
    if not manifest.is_file():
        raise RuntimeError("Example 10 did not write the reproducibility manifest")
    code = (
        "import calm; "
        f"project=calm.open_project({str(project)!r}); "
        "report=project.verify_reproducibility_manifest(); "
        "report.raise_for_errors(); print(report.summary())"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=staged.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout)
    if completed.returncode != 0:
        print(completed.stderr, file=sys.stderr)
        raise RuntimeError("reproducibility manifest verification failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    if args.passes < 1:
        parser.error("--passes must be at least 1")

    staged = _stage(args.work_root.resolve())
    for pass_number in range(1, args.passes + 1):
        print(f"=== numbered example pass {pass_number}/{args.passes} ===")
        for name in SCRIPTS:
            _run(staged / name, cwd=staged.parent, timeout=args.timeout)
        _verify(staged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
