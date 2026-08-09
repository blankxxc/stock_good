from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import duckdb
import networkx as nx
import numpy as np
import pandas as pd

AVAILABLE_NODE_COUNTS = [20, 50, 100, 200, 300]
AVAILABLE_COMMUNITY_COUNTS = [2, 4, 6, 8, 10]
DEFAULT_NODE_COUNT = 50
DEFAULT_COMMUNITY_COUNT = 4
PRICE_NEIGHBORS = 4
LEAD_LAG_NEIGHBORS = 2
INDUSTRY_NEIGHBORS = 3
INDEX_NEIGHBORS = 2

DatasetSignature = tuple[tuple[str, int, int], ...]


def _edge_key(source: str, target: str, relation_type: str, directed: bool) -> tuple[str, str, str]:
    if not directed and source > target:
        source, target = target, source
    return source, target, relation_type


def _put_edge(
    store: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    relation_type: str,
    weight: float,
    confidence: float,
    directed: bool,
) -> None:
    source = str(source)
    target = str(target)
    if not source or not target or source == target:
        return
    source, target, relation_type = _edge_key(source, target, str(relation_type), directed)
    safe_weight = float(np.clip(abs(float(weight)), 0.0, 1.0))
    safe_confidence = float(np.clip(float(confidence), 0.0, 1.0))
    if not np.isfinite(safe_weight) or safe_weight <= 0.0:
        return
    key = source, target, relation_type
    candidate = {
        "id": f"{source}::{target}::{relation_type}",
        "source": source,
        "target": target,
        "relation_type": relation_type,
        "weight": round(safe_weight, 6),
        "confidence": round(safe_confidence, 6),
        "directed": bool(directed),
    }
    previous = store.get(key)
    if previous is None or candidate["weight"] > previous["weight"]:
        store[key] = candidate


def _add_ring_edges(
    store: dict[tuple[str, str, str], dict[str, Any]],
    symbols: list[str],
    relation_type: str,
    neighbor_count: int,
    weight: float,
    confidence: float,
) -> None:
    if len(symbols) < 2:
        return
    ordered = sorted(symbols)
    for index, source in enumerate(ordered):
        for offset in range(1, min(neighbor_count, len(ordered) - 1) + 1):
            target = ordered[(index + offset) % len(ordered)]
            _put_edge(store, source, target, relation_type, weight, confidence, False)


def _duckdb_source(paths: list[Path]) -> str | list[str]:
    resolved = [str(path.resolve()) for path in paths]
    return resolved[0] if len(resolved) == 1 else resolved


def _recent_daily(connection: duckdb.DuckDBPyConnection, daily_paths: list[Path]) -> pd.DataFrame:
    source = _duckdb_source(daily_paths)
    return connection.execute(
        """
        SELECT
            CAST(trade_date AS VARCHAR) AS trade_date,
            CAST(symbol AS VARCHAR) AS symbol,
                COALESCE(NULLIF(CAST(stock_name AS VARCHAR), ''), CAST(symbol AS VARCHAR)) AS stock_name,
            COALESCE(NULLIF(CAST(industry_name AS VARCHAR), ''), '未知行业') AS industry_name,
            CAST(close AS DOUBLE) AS close
        FROM read_parquet(?)
        WHERE symbol IS NOT NULL
          AND close IS NOT NULL
          AND trade_date IN (
              SELECT trade_date
              FROM (
                  SELECT DISTINCT trade_date
                  FROM read_parquet(?)
                  ORDER BY trade_date DESC
                  LIMIT 121
              )
          )
        ORDER BY trade_date, symbol
        """,
        [source, source],
    ).df()


def _existing_edges(
    connection: duckdb.DuckDBPyConnection,
    edge_paths: list[Path],
    latest_date: str,
    universe: set[str],
    store: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    if not edge_paths:
        return
    source = _duckdb_source(edge_paths)
    rows = connection.execute(
        """
        SELECT
            CAST(src_symbol AS VARCHAR),
            CAST(dst_symbol AS VARCHAR),
            CAST(relation_type AS VARCHAR),
            ABS(COALESCE(relation_weight, 0.0)),
            COALESCE(confidence, 0.0),
            COALESCE(direction, 'undirected') <> 'undirected'
        FROM read_parquet(?, union_by_name = true)
        WHERE src_symbol IS NOT NULL AND dst_symbol IS NOT NULL AND src_symbol <> dst_symbol
          AND (
              as_of_date IS NULL
              OR NULLIF(TRIM(CAST(as_of_date AS VARCHAR)), '') IS NULL
              OR TRY_CAST(as_of_date AS DATE) <= TRY_CAST(? AS DATE)
          )
          AND (
              available_time IS NULL
              OR NULLIF(TRIM(CAST(available_time AS VARCHAR)), '') IS NULL
              OR TRY_CAST(available_time AS DATE) <= TRY_CAST(? AS DATE)
          )
          AND (
              start_time IS NULL
              OR NULLIF(TRIM(CAST(start_time AS VARCHAR)), '') IS NULL
              OR TRY_CAST(start_time AS DATE) <= TRY_CAST(? AS DATE)
          )
          AND (
              end_time IS NULL
              OR NULLIF(TRIM(CAST(end_time AS VARCHAR)), '') IS NULL
              OR TRY_CAST(end_time AS DATE) >= TRY_CAST(? AS DATE)
          )
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY src_symbol, dst_symbol, relation_type, COALESCE(direction, 'undirected')
            ORDER BY
                COALESCE(
                    TRY_CAST(as_of_date AS TIMESTAMP),
                    TRY_CAST(start_time AS TIMESTAMP),
                    TRY_CAST(available_time AS TIMESTAMP)
                ) DESC NULLS LAST,
                TRY_CAST(available_time AS TIMESTAMP) DESC NULLS LAST
        ) = 1
        """,
        [source, latest_date, latest_date, latest_date, latest_date],
    ).fetchall()
    for source_symbol, target_symbol, relation_type, weight, confidence, directed in rows:
        if source_symbol in universe and target_symbol in universe:
            _put_edge(store, source_symbol, target_symbol, relation_type, weight, confidence, bool(directed))


def _correlation_edges(
    returns: pd.DataFrame,
    store: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    if returns.empty or returns.shape[1] < 2:
        return
    correlation = returns.corr(min_periods=max(20, len(returns) // 3)).fillna(0.0)
    symbols = list(correlation.columns)
    for source in symbols:
        candidates = correlation[source].drop(labels=[source], errors="ignore").abs().sort_values(ascending=False)
        for target, value in candidates.head(PRICE_NEIGHBORS).items():
            if float(value) >= 0.12:
                _put_edge(store, source, str(target), "price_corr", float(value) * 0.82, 0.82, False)

    values = returns.to_numpy(dtype=float)
    if values.shape[0] < 25:
        return
    valid_indices = np.flatnonzero(np.isfinite(values).sum(axis=0) >= 20)
    if len(valid_indices) < 2:
        return
    valid_symbols = [str(returns.columns[index]) for index in valid_indices]
    values = values[:, valid_indices]
    column_means = np.array([
        float(np.nanmean(values[:, index]))
        for index in range(values.shape[1])
    ])
    values = np.where(np.isfinite(values), values, column_means)
    earlier = values[:-1]
    later = values[1:]
    earlier_std = np.std(earlier, axis=0)
    later_std = np.std(later, axis=0)
    earlier = (earlier - np.mean(earlier, axis=0)) / np.where(earlier_std > 1e-12, earlier_std, 1.0)
    later = (later - np.mean(later, axis=0)) / np.where(later_std > 1e-12, later_std, 1.0)
    lagged = (earlier.T @ later) / max(earlier.shape[0] - 1, 1)
    np.fill_diagonal(lagged, 0.0)
    for source_index, source in enumerate(valid_symbols):
        order = np.argsort(np.abs(lagged[source_index]))[::-1]
        added = 0
        for target_index in order:
            value = float(abs(lagged[source_index, target_index]))
            if value < 0.12:
                break
            _put_edge(store, source, valid_symbols[target_index], "lead_lag", value * 0.78, 0.78, True)
            added += 1
            if added >= LEAD_LAG_NEIGHBORS:
                break


def _balanced_communities(symbols: list[str], target_count: int) -> list[set[str]]:
    ordered = sorted(symbols)
    return [set(ordered[index::target_count]) for index in range(target_count)]


def _supported_community_counts(symbol_count: int) -> list[int]:
    configured = [count for count in AVAILABLE_COMMUNITY_COUNTS if count <= symbol_count]
    if configured:
        return configured
    return [1] if symbol_count == 1 else []


def _community_assignments(symbols: list[str], edges: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    if not symbols:
        return {}

    graph = nx.Graph()
    graph.add_nodes_from(symbols)
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        weight = float(edge["weight"])
        previous = graph.get_edge_data(source, target, {}).get("weight", 0.0)
        graph.add_edge(source, target, weight=previous + weight)

    assignments = {symbol: {} for symbol in symbols}
    for target_count in _supported_community_counts(len(symbols)):
        if target_count == 1:
            communities = [set(symbols)]
        elif target_count == len(symbols) or graph.number_of_edges() == 0:
            communities = _balanced_communities(symbols, target_count)
        else:
            try:
                communities = list(
                    nx.algorithms.community.greedy_modularity_communities(
                        graph,
                        weight="weight",
                        cutoff=target_count,
                        best_n=target_count,
                    )
                )
            except (ValueError, ZeroDivisionError):
                communities = _balanced_communities(symbols, target_count)

        communities = [set(community) for community in communities if community]
        while len(communities) > target_count:
            communities.sort(key=lambda community: (len(community), min(community)))
            source_community = communities.pop(0)
            best_index = max(
                range(len(communities)),
                key=lambda index: (
                    sum(
                        float(graph.get_edge_data(left, right, {}).get("weight", 0.0))
                        for left in source_community
                        for right in communities[index]
                    ),
                    -len(communities[index]),
                    min(communities[index]),
                ),
            )
            communities[best_index].update(source_community)
        while len(communities) < target_count:
            splittable = [index for index, community in enumerate(communities) if len(community) > 1]
            if not splittable:
                communities = _balanced_communities(symbols, target_count)
                break
            largest_index = max(
                splittable,
                key=lambda index: (len(communities[index]), min(communities[index])),
            )
            largest = sorted(communities.pop(largest_index))
            split_at = max(1, len(largest) // 2)
            communities.extend([set(largest[:split_at]), set(largest[split_at:])])
        if len(communities) != target_count or any(not community for community in communities):
            communities = _balanced_communities(symbols, target_count)
        communities.sort(key=lambda community: min(community))
        for community_id, community in enumerate(communities):
            for symbol in community:
                assignments[symbol][str(target_count)] = community_id
    return assignments


def _dataset_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.parquet") if path.is_file())


def _dataset_signature(directory: Path) -> DatasetSignature:
    signature: list[tuple[str, int, int]] = []
    for path in _dataset_files(directory):
        relative_path = path.relative_to(directory).as_posix()
        try:
            stat = path.stat()
            signature.append((relative_path, stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append((relative_path, -1, -1))
    return tuple(signature)


def _snapshot_metadata(
    daily_signature: DatasetSignature,
    edge_signature: DatasetSignature,
    as_of_date: str | None,
) -> dict[str, Any]:
    fingerprint = hashlib.sha256(repr((daily_signature, edge_signature)).encode("utf-8")).hexdigest()[:16]
    return {
        "version": fingerprint,
        "as_of_date": as_of_date,
        "daily_file_count": len(daily_signature),
        "edge_file_count": len(edge_signature),
    }


def _empty_network(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": None,
        "snapshot": snapshot,
        "nodes": [],
        "edges": [],
        "available_node_counts": [],
        "available_community_counts": [],
        "default_node_count": 0,
        "default_community_count": 0,
    }


def _supported_node_counts(node_count: int) -> list[int]:
    configured = [count for count in AVAILABLE_NODE_COUNTS if count <= node_count]
    if configured:
        return configured
    return [node_count] if node_count else []


def relation_network_payload(root_value: str) -> dict[str, Any]:
    root = Path(root_value)
    daily_dir = root / "data" / "real" / "csi300_daily"
    edge_dir = root / "data" / "gold" / "stock_relation_edge"
    return _cached_relation_network_payload(
        root_value,
        _dataset_signature(daily_dir),
        _dataset_signature(edge_dir),
    )


@lru_cache(maxsize=2)
def _cached_relation_network_payload(
    root_value: str,
    daily_signature: DatasetSignature,
    edge_signature: DatasetSignature,
) -> dict[str, Any]:
    root = Path(root_value)
    daily_dir = root / "data" / "real" / "csi300_daily"
    edge_dir = root / "data" / "gold" / "stock_relation_edge"
    daily_paths = _dataset_files(daily_dir)
    edge_paths = _dataset_files(edge_dir)
    snapshot = _snapshot_metadata(daily_signature, edge_signature, None)
    if not daily_paths:
        return _empty_network(snapshot)

    connection = duckdb.connect(database=":memory:")
    try:
        daily = _recent_daily(connection, daily_paths)
        if daily.empty:
            return _empty_network(snapshot)
        latest_date = str(daily["trade_date"].max())
        snapshot["as_of_date"] = latest_date
        latest = daily[daily["trade_date"] == latest_date].drop_duplicates("symbol").sort_values("symbol")
        latest = latest.head(300).copy()
        symbols = latest["symbol"].astype(str).tolist()
        universe = set(symbols)
        names = dict(zip(latest["symbol"].astype(str), latest["stock_name"].astype(str)))
        industries = dict(zip(latest["symbol"].astype(str), latest["industry_name"].astype(str)))

        edge_store: dict[tuple[str, str, str], dict[str, Any]] = {}
        _existing_edges(connection, edge_paths, latest_date, universe, edge_store)

        industry_groups: dict[str, list[str]] = {}
        for symbol in symbols:
            industry_groups.setdefault(industries.get(symbol, "未知行业"), []).append(symbol)
        for group in industry_groups.values():
            _add_ring_edges(edge_store, group, "industry_same", INDUSTRY_NEIGHBORS, 0.779, 0.95)
        _add_ring_edges(edge_store, symbols, "index_member_same", INDEX_NEIGHBORS, 0.5984, 0.88)

        prices = daily[daily["symbol"].isin(symbols)].pivot(index="trade_date", columns="symbol", values="close").sort_index()
        returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        _correlation_edges(returns, edge_store)

        edges = sorted(edge_store.values(), key=lambda edge: (edge["relation_type"], edge["source"], edge["target"]))
        graph = nx.Graph()
        graph.add_nodes_from(symbols)
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            graph.add_edge(source, target, weight=graph.get_edge_data(source, target, {}).get("weight", 0.0) + float(edge["weight"]))
        degrees = {symbol: 0 for symbol in symbols}
        for edge in edges:
            degrees[edge["source"]] += 1
            degrees[edge["target"]] += 1
        weighted_degrees = dict(graph.degree(weight="weight"))
        maximum_weighted_degree = max(weighted_degrees.values(), default=1.0) or 1.0
        assignments = _community_assignments(symbols, edges)
        community_counts = _supported_community_counts(len(symbols))
        default_community_count = (
            DEFAULT_COMMUNITY_COUNT
            if DEFAULT_COMMUNITY_COUNT in community_counts
            else max(community_counts, default=0)
        )

        nodes = [
            {
                "symbol": symbol,
                "name": names.get(symbol) or symbol,
                "community_id": assignments[symbol][str(default_community_count)],
                "community_assignments": assignments[symbol],
                "centrality_score": round(float(weighted_degrees.get(symbol, 0.0)) / maximum_weighted_degree, 8),
                "degree": int(degrees.get(symbol, 0)),
            }
            for symbol in symbols
        ]
        return {
            "as_of_date": latest_date,
            "snapshot": snapshot,
            "nodes": nodes,
            "edges": edges,
            "available_node_counts": _supported_node_counts(len(nodes)),
            "available_community_counts": community_counts,
            "default_node_count": min(DEFAULT_NODE_COUNT, len(nodes)),
            "default_community_count": default_community_count,
        }
    finally:
        connection.close()
