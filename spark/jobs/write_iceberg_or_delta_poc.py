from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "lakehouse" / "delta" / "day2_delta_poc_manifest.json"


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        import delta  # type: ignore  # noqa: F401
        # The package alone is not enough; Spark still needs Delta jars in the local session.
        # Keep the branch explicit for future upgrade, but use the fallback unless the connector is fully wired.
        raise RuntimeError("delta-spark connector jars are not bundled in this local Day2 runtime")
    except Exception as exc:
        import duckdb

        source = ROOT / "data" / "silver" / "dwd_stock_daily_bar"
        fallback_dir = ROOT / "lakehouse" / "delta" / "fallback_parquet" / "day2_delta_like_table" / "schema_version=v2"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(database=":memory:")
        df = con.execute("select * from read_parquet(?, hive_partitioning=false)", [str(source / "**" / "*.parquet")]).fetch_df()
        df = df.copy()
        df["schema_evolution_note"] = "v2_added_column_for_delta_fallback"
        out_file = fallback_dir / "part-000.parquet"
        df.to_parquet(out_file, index=False)
        read_back = con.execute("select * from read_parquet(?, hive_partitioning=false)", [str(fallback_dir / "*.parquet")]).fetch_df()
        report = {
            "status": "blocked_with_fallback",
            "table_format": "delta",
            "runtime": "spark-local-planned",
            "blocked_reason": str(exc),
            "fallback_parquet_manifest": {
                "status": "ok",
                "path": str(fallback_dir),
                "read_back_row_count": int(len(read_back)),
                "schema_evolution_checked": "schema_evolution_note" in read_back.columns,
                "format": "parquet",
            },
        }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
