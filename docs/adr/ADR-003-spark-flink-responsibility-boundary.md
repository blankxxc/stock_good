# ADR-003: Spark and Flink Responsibility Boundary

Status: accepted

Decision: Spark handles offline batch ETL, lakehouse materialization, batch factor computation, label construction, and training matrices. Flink handles event-time streaming, watermarking, window aggregation, late-data handling, and real-time factor streams.

Reason: Keeping batch and stream responsibilities separate avoids silently mixing close-time features into same-close predictions.
