import sqlite3
from pathlib import Path
from .schema import SCHEMA_SQL


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def recreate_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = connect(path)
    connection.executescript(SCHEMA_SQL)
    return connection

