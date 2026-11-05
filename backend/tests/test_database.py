
import sqlite3

import pytest

from app import database


def test_readonly_query_timeout(monkeypatch, tmp_path):
    db_path = tmp_path / "timeout_test.db"

    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE numbers (value INTEGER)"
    )
    connection.executemany(
        "INSERT INTO numbers (value) VALUES (?)",
        [(i,) for i in range(100)],
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(
        database,
        "QUERY_TIMEOUT_SECONDS",
        0.001,
    )
    monkeypatch.setattr(
        database,
        "SQLITE_PROGRESS_OPCODES",
        1,
    )

    conn = database.get_connection(readonly=True)

    try:
        with pytest.raises(
            sqlite3.OperationalError,
            match="interrupted",
        ):
            conn.execute(
                """
                SELECT COUNT(*)
                FROM numbers AS a
                CROSS JOIN numbers AS b
                CROSS JOIN numbers AS c
                CROSS JOIN numbers AS d
                """
            ).fetchone()
    finally:
        conn.close()
