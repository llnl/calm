"""Tests for deterministic GitLab pytest file sharding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineering.ci.run_pytest_shard import (
    discover_test_files,
    select_shard,
    shard_number,
    write_manifest,
)


def test_three_shards_are_nonempty_disjoint_and_exhaustive() -> None:
    files = discover_test_files()
    shards = [
        select_shard(files, shard_index=index, shard_count=3)
        for index in range(1, 4)
    ]

    assert all(shards)
    assert sum(len(shard) for shard in shards) == len(files)
    assert set().union(*(set(shard) for shard in shards)) == set(files)
    for left_index, left in enumerate(shards):
        for right in shards[left_index + 1 :]:
            assert set(left).isdisjoint(right)


def test_assignment_is_stable_and_one_based() -> None:
    path = Path("tests/unit/test_example.py")

    observed = shard_number(path, shard_count=5)
    assert 1 <= observed <= 5
    assert shard_number(path, shard_count=5) == observed


def test_invalid_shard_selection_fails_closed() -> None:
    with pytest.raises(ValueError, match="between 1 and shard_count"):
        select_shard([], shard_index=0, shard_count=3)
    with pytest.raises(ValueError, match="positive"):
        shard_number(Path("tests/test_x.py"), shard_count=0)


def test_manifest_records_exact_file_inventory(tmp_path: Path) -> None:
    path = tmp_path / "shard.json"
    files = [Path("tests/test_a.py"), Path("tests/unit/test_b.py")]

    write_manifest(path, shard_index=2, shard_count=3, files=files)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload == {
        "schema": "calm.pytest_shard.v1",
        "shard_index": 2,
        "shard_count": 3,
        "file_count": 2,
        "files": ["tests/test_a.py", "tests/unit/test_b.py"],
    }
