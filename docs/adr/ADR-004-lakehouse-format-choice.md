# ADR-004: Lakehouse Format Choice

Status: proposed

Decision: Day 1 scaffolds Iceberg, Hudi, and Delta directories. Day 2 will choose at least one local PoC. Parquet + DuckDB/Polars remains the stable fallback for the two-week demo.

Reason: The project needs reproducible dataset snapshots now, while table-format time travel/schema evolution can be promoted only after local evidence.
