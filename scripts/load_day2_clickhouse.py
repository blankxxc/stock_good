from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLICKHOUSE_CONTAINER = os.environ.get("CLICKHOUSE_CONTAINER", "stock-good-day1-clickhouse-1")
REPORT = ROOT / "reports" / "day2" / "clickhouse_load_report.json"

TABLE_GLOBS = {
    "ads_dashboard_summary": "data/ads/ads_dashboard_summary/*.parquet",
    "ads_score_latest": "data/ads/ads_score_latest/*.parquet",
    "ads_backtest_summary": "data/ads/ads_backtest_summary/*.parquet",
}


def _query(sql: str, data: bytes | None = None) -> str:
    """Run ClickHouse SQL through docker exec.

    The ClickHouse image used by the local Compose stack disables network access
    for default when no explicit password is set. Using the in-container client
    avoids creating or printing credentials while still exercising the live DB.
    """
    cmd = [
        "docker",
        "exec",
        "-i" if data is not None else "",
        CLICKHOUSE_CONTAINER,
        "clickhouse-client",
        "--query",
        sql,
    ]
    cmd = [part for part in cmd if part]
    proc = subprocess.run(
        cmd,
        input=data,
        capture_output=True,
        cwd=ROOT,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ClickHouse query failed rc={proc.returncode}: {proc.stderr.decode('utf-8', errors='replace')}"
        )
    return proc.stdout.decode("utf-8", errors="replace")


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _json_each_row(df: pd.DataFrame) -> bytes:
    lines = []
    for row in df.to_dict(orient="records"):
        lines.append(json.dumps({k: _clean_value(v) for k, v in row.items()}, ensure_ascii=False))
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    sql_path = ROOT / "deploy" / "clickhouse" / "day2_ads_tables.sql"
    ddl = sql_path.read_text(encoding="utf-8")
    for statement in [part.strip() for part in ddl.split(";") if part.strip()]:
        _query(statement)

    con = duckdb.connect(database=":memory:")
    inserted: dict[str, int] = {}
    for table, glob in TABLE_GLOBS.items():
        _query(f"TRUNCATE TABLE IF EXISTS {table}")
        df = con.execute("select * from read_parquet(?)", [str(ROOT / glob)]).fetch_df()
        if len(df):
            _query(f"INSERT INTO {table} FORMAT JSONEachRow", _json_each_row(df))
        count = int(_query(f"SELECT count() FROM {table}").strip() or "0")
        inserted[table] = count

    report = {"status": "ok", "clickhouse_container": CLICKHOUSE_CONTAINER, "inserted": inserted}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
