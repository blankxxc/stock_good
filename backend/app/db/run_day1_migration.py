from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_PATH = ROOT / "warehouse_schema" / "migrations" / "0001_day1_metadata.sql"
DB_PATH = ROOT / "data" / "snapshots" / "day1_metadata.sqlite"


def run() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    sql = SQL_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql)
        conn.execute("insert into schema_registry (schema_name, schema_version, layer, contract_path, created_at) values (?, ?, ?, ?, datetime('now'))", ("day1_metadata", "v0.1.0", "metadata", str(SQL_PATH)))
        conn.commit()
    return DB_PATH


if __name__ == "__main__":
    print(run())
