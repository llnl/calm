from __future__ import annotations

import sqlite3
from pathlib import Path

from calm.project.infrastructure.reproducibility import hash_sqlite_snapshot


def _seed_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE sample ("
            "sample_pk INTEGER PRIMARY KEY AUTOINCREMENT, "
            "label TEXT NOT NULL, "
            "value REAL NOT NULL, "
            "payload BLOB"
            ")"
        )
        connection.executemany(
            "INSERT INTO sample(label, value, payload) VALUES (?, ?, ?)",
            [
                ("alpha", -0.0, b"one"),
                ("beta", 2.5, b"two"),
                ("gamma", 3.75, None),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_sqlite_logical_snapshot_ignores_physical_rewrites(tmp_path: Path) -> None:
    database = tmp_path / "calm.sqlite"
    _seed_database(database)

    recorded = hash_sqlite_snapshot(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute("REINDEX")
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()

    assert hash_sqlite_snapshot(database) == recorded


def test_sqlite_logical_snapshot_detects_authoritative_row_changes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "calm.sqlite"
    _seed_database(database)
    recorded = hash_sqlite_snapshot(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE sample SET value = ? WHERE label = ?",
            (2.75, "beta"),
        )
        connection.commit()
    finally:
        connection.close()

    assert hash_sqlite_snapshot(database) != recorded


def test_sqlite_logical_snapshot_includes_autoincrement_state(tmp_path: Path) -> None:
    database = tmp_path / "calm.sqlite"
    _seed_database(database)
    recorded = hash_sqlite_snapshot(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO sample(label, value, payload) VALUES (?, ?, ?)",
            ("transient", 9.0, None),
        )
        connection.execute("DELETE FROM sample WHERE label = ?", ("transient",))
        connection.commit()
    finally:
        connection.close()

    assert hash_sqlite_snapshot(database) != recorded
