# TRSR advanced_models adapter

Status: small_sample_trained / candidate, not approved.

Repository reference: fulifeng/Temporal_Relational_Stock_Ranking
Paper/reference: Temporal Relational Ranking for Stock Prediction

This directory contains the project-local small-sample adapter required by advanced_models:

- adapter.py: exposes build_adapter(seed) and the unified fit/predict/evaluate/register_model_artifact/explain_feature_dependency interface through advanced_modelsAdvancedModelAdapter.
- run_small_sample.py: runs this model through the common advanced_models pipeline.
- environment.lock: Python, package, CPU/GPU and dependency snapshot.

Input dependency: relation_matrix + lead_lag / neighbor propagation features from relation_graph graph adapter

Research boundary: research_signals_only_not_investment_advice. The adapter output is a research candidate only; it is not a trading instruction and must not be promoted to approved without later walk-forward, risk, simulation and review gates.
