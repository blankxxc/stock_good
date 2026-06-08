# ADR-002: Point-in-Time Time Semantics

Status: accepted

Decision: All formal data contracts include event_time/publish_time/ingest_time/available_time where applicable. Model features must satisfy available_time <= prediction_time. Historical RAG answers default to as_of retrieval.

Reason: Avoid future function, announcement-time leakage, full-sample normalization, and retrospective citation contamination.
