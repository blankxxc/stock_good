# HIST Day9 adapter

Status: small_sample_trained / candidate, not approved.

Repository reference: Wentao-Xu/HIST
Paper/reference: HIST: Graph-based Framework for Stock Trend Forecasting via Mining Concept-Oriented Shared Information

This directory contains the project-local small-sample adapter required by Day 9:

- adapter.py: exposes build_adapter(seed) and the unified fit/predict/evaluate/register_model_artifact/explain_feature_dependency interface through Day9AdvancedModelAdapter.
- run_small_sample.py: runs this model through the common Day9 pipeline.
- environment.lock: Python, package, CPU/GPU and dependency snapshot.

Input dependency: concept_matrix + industry/concept/relation spillover features from Day8 graph adapter

Research boundary: research_signals_only_not_investment_advice. The adapter output is a research candidate only; it is not a trading instruction and must not be promoted to approved without later walk-forward, risk, simulation and review gates.
