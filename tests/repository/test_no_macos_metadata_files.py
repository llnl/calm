from __future__ import annotations

from pathlib import Path
import subprocess


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {here}")


def _tracked_paths(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw]


def test_no_tracked_macos_metadata_files() -> None:
    """Reject tracked Finder, AppleDouble, and macOS archive metadata."""

    bad: list[Path] = []
    for path in _tracked_paths(_repo_root()):
        if ".DS_Store" in path.parts:
            bad.append(path)
        elif "__MACOSX" in path.parts:
            bad.append(path)
        elif any(part.startswith("._") for part in path.parts):
            bad.append(path)

    assert bad == [], "Tracked macOS metadata artifacts:\n" + "\n".join(
        f"- {path.as_posix()}" for path in sorted(bad)
    )
