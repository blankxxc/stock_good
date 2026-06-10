# ADR-005 Final Release Gates

## Status

Accepted for final acceptance local final acceptance.

## Context

final acceptance 不新增核心功能，目标是把 foundation-ops deployment 形成可演示、可验证、可审计的最终交付。

## Decision

最终 release gate 必须同时检查：pytest、final acceptance acceptance、frontend route/build、Docker Compose config、backup/restore smoke、no broker integration、license gate、RAG citation gate、point-in-time gate、manual review before real use。

## Consequences

- 允许 local PoC / partial 模块存在，但必须写明 maturity 和 blocked reason。
- 不允许把 replay realtime、advanced model adapter 或 simulation 输出宣传为正式交易能力。
- 报告导出必须保留 export_manifest、license result、redaction、watermark、audit_id。
