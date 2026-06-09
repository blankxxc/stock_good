# RAG Evidence

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## Claim-level schema

每条证据记录 claim_id、chunk_id、citation_span、license_id、event_time、publish_time、available_time、valid_from/valid_to、evidence_direction、evidence_strength、status、index_version。

## 检索模式

- as_of：强制 available_time <= prediction_time。
- present：当前知识检索。
- retrospective_review：事后复盘，必须显式标注。

## 输出约束

无引用拒答；回答必须区分事实、推断、假设、支持证据、反对证据和适用条件。
