# MASTER Day9 adapter

Status: small_sample_trained / candidate, not approved.

Repository reference: SJTU-DMTai/MASTER
Paper/reference: AAAI 2024 MASTER: Market-Guided Stock Transformer for Stock Price Forecasting

This directory contains the project-local small-sample adapter required by Day 9:

- adapter.py: exposes build_adapter(seed) and the unified fit/predict/evaluate/register_model_artifact/explain_feature_dependency interface through Day9AdvancedModelAdapter.
- run_small_sample.py: runs this model through the common Day9 pipeline.
- environment.lock: Python, package, CPU/GPU and dependency snapshot.

Input dependency: market information: market_breadth, market_ret_*, market_vol_20d, ex_ante_regime_feature

Research boundary: research_signals_only_not_investment_advice. The adapter output is a research candidate only; it is not a trading instruction and must not be promoted to approved without later walk-forward, risk, simulation and review gates.
