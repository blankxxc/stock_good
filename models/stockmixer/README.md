# StockMixer advanced_models adapter

Status: small_sample_trained / candidate, not approved.

Repository reference: SJTU-DMTai/StockMixer
Paper/reference: AAAI 2024 StockMixer: A Simple yet Strong MLP-based Architecture for Stock Price Forecasting

This directory contains the project-local small-sample adapter required by advanced_models:

- adapter.py: exposes build_adapter(seed) and the unified fit/predict/evaluate/register_model_artifact/explain_feature_dependency interface through advanced_modelsAdvancedModelAdapter.
- run_small_sample.py: runs this model through the common advanced_models pipeline.
- environment.lock: Python, package, CPU/GPU and dependency snapshot.

Input dependency: indicator/temporal/stock mixing tensors from relation_graph feature matrix

Research boundary: research_signals_only_not_investment_advice. The adapter output is a research candidate only; it is not a trading instruction and must not be promoted to approved without later walk-forward, risk, simulation and review gates.
