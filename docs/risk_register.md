# Day 1 Risk Register

| risk_id | title | severity | mitigation | owner | status |
|---|---|---:|---|---|---|
| R-001 | Docker Desktop/CLI installed, but Docker Linux engine cannot start because WSL is not installed/enabled and this shell is not elevated | High | Docker CLI and Compose now resolve from `C:\Program Files\Docker\Docker\resources\bin`; enable WSL/VirtualMachinePlatform from an Administrator terminal and reboot, then start Docker Desktop before full compose gate | platform | open |
| R-002 | PySpark parquet write on native Windows required HADOOP_HOME/winutils.exe | Medium | Installed `C:\Users\blankxxc\hadoop\bin\winutils.exe` and `hadoop.dll`; Spark smoke now writes Parquet successfully with `write_status=parquet_ok` | data-platform | mitigated |
| R-003 | Future data leakage through timestamps | High | Enforce event_time/publish_time/ingest_time/available_time in contracts and point-in-time joins | quant | open |
| R-004 | RAG answer without citations | High | claim_id/citation_span/evidence_strength required; no-citation answers marked evidence-insufficient | rag | open |
| R-005 | UI wording looks like recommendation | Medium | Product copy uses research candidate/rank/explanation language only | product | open |
