'use client';

import { PointerEvent, WheelEvent, useEffect, useMemo, useRef, useState } from 'react';

export type RelationNode = {
  symbol: string;
  name: string;
  community_id: number;
  community_assignments?: Record<string, number>;
  centrality_score: number;
  degree: number;
};

export type RelationEdge = {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  weight: number;
  confidence: number;
  directed: boolean;
};

export type RelationNetwork = {
  as_of_date?: string | null;
  nodes: RelationNode[];
  edges: RelationEdge[];
  available_node_counts?: number[];
  available_community_counts?: number[];
  default_node_count?: number;
  default_community_count?: number;
};

type Position = { x: number; y: number };
type ViewState = { x: number; y: number; scale: number };
type DragState =
  | { kind: 'pan'; pointerId: number; clientX: number; clientY: number; originX: number; originY: number }
  | { kind: 'node'; pointerId: number; symbol: string; clientX: number; clientY: number; originX: number; originY: number };

const DESKTOP_WIDTH = 1200;
const DESKTOP_HEIGHT = 700;
const MOBILE_WIDTH = 700;
const MOBILE_HEIGHT = 1000;
const MIN_SCALE = 0.68;
const MAX_SCALE = 2.4;
const SHOW_ALL_EDGE_CAP = 1200;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

export const relationLabels: Record<string, string> = {
  industry_same: '同行业',
  concept_same: '同概念',
  index_member_same: '同指数成分',
  price_corr: '价格联动',
  lead_lag: '领先滞后',
  news_co_mention: '新闻共现',
  supply_chain_upstream: '上游关系',
  supply_chain_downstream: '下游关系',
};

const relationColors: Record<string, string> = {
  industry_same: '#38bdf8',
  concept_same: '#a78bfa',
  index_member_same: '#f5c84c',
  price_corr: '#2dd4bf',
  lead_lag: '#fb7185',
  news_co_mention: '#60a5fa',
  supply_chain_upstream: '#f59e0b',
  supply_chain_downstream: '#4ade80',
};

// Fixed community colors are deliberately separate from relation-type edge colors.
const communityPalette = [
  { light: '#67e8f9', dark: '#0e7490' },
  { light: '#c4b5fd', dark: '#6d28d9' },
  { light: '#86efac', dark: '#15803d' },
  { light: '#fda4af', dark: '#be123c' },
  { light: '#fde68a', dark: '#a16207' },
  { light: '#93c5fd', dark: '#1d4ed8' },
  { light: '#fdba74', dark: '#c2410c' },
  { light: '#f0abfc', dark: '#a21caf' },
  { light: '#5eead4', dark: '#0f766e' },
  { light: '#cbd5e1', dark: '#475569' },
] as const;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function compareNodes(a: RelationNode, b: RelationNode) {
  return b.centrality_score - a.centrality_score
    || b.degree - a.degree
    || a.symbol.localeCompare(b.symbol, 'en');
}

function communityFor(node: RelationNode, communityCount: number) {
  const assigned = node.community_assignments?.[String(communityCount)];
  const community = typeof assigned === 'number' && Number.isFinite(assigned)
    ? assigned
    : node.community_id;
  return Math.max(0, Math.floor(Number.isFinite(community) ? community : 0));
}

function uniquePositiveCounts(values: number[] | undefined, maximum?: number) {
  return Array.from(new Set((values ?? [])
    .filter((value) => Number.isInteger(value) && value > 0 && (maximum === undefined || value <= maximum))))
    .sort((a, b) => a - b);
}

function getNodeCountOptions(network: RelationNetwork) {
  const configured = uniquePositiveCounts(network.available_node_counts, network.nodes.length);
  if (!configured.length) return [Math.min(20, network.nodes.length)];
  if (!configured.includes(network.nodes.length)) configured.push(network.nodes.length);
  return configured.sort((a, b) => a - b);
}

function getCommunityCountOptions(network: RelationNetwork) {
  const configured = uniquePositiveCounts(network.available_community_counts, 10);
  if (configured.length) return configured;
  const fallbackCount = new Set(network.nodes.map((node) => Math.max(0, node.community_id))).size || 2;
  const assignmentCounts = uniquePositiveCounts(network.nodes.flatMap((node) => Object.keys(node.community_assignments ?? {})
    .map((key) => Number(key))), 10);
  if (assignmentCounts.length) return Array.from(new Set([fallbackCount, ...assignmentCounts])).sort((a, b) => a - b);
  return [fallbackCount];
}

function getDefaultCount(configured: number | undefined, options: number[], fallback: number) {
  if (typeof configured === 'number' && options.includes(configured)) return configured;
  if (options.includes(fallback)) return fallback;
  return options[0] ?? fallback;
}

function selectCommunityBalancedNodes(nodes: RelationNode[], requestedCount: number, communityCount: number) {
  const targetCount = requestedCount === 300
    ? nodes.length
    : Math.min(Math.max(0, requestedCount), nodes.length);
  if (targetCount >= nodes.length) {
    return [...nodes]
      .sort(compareNodes)
      .map((node) => ({ ...node, community_id: communityFor(node, communityCount) }));
  }

  const groups = new Map<number, RelationNode[]>();
  nodes.forEach((node) => {
    const community = communityFor(node, communityCount);
    groups.set(community, [...(groups.get(community) ?? []), node]);
  });
  const communityIds = Array.from(groups.keys()).sort((a, b) => a - b);
  communityIds.forEach((community) => groups.get(community)?.sort(compareNodes));

  const selected: RelationNode[] = [];
  const offsets = new Map<number, number>();
  // Every non-empty community receives one slot before remaining slots are shared round-robin.
  communityIds.slice(0, targetCount).forEach((community) => {
    const node = groups.get(community)?.[0];
    if (node) selected.push({ ...node, community_id: community });
    offsets.set(community, node ? 1 : 0);
  });

  while (selected.length < targetCount) {
    let addedThisPass = false;
    communityIds.forEach((community) => {
      if (selected.length >= targetCount) return;
      const offset = offsets.get(community) ?? 0;
      const node = groups.get(community)?.[offset];
      if (!node) return;
      selected.push({ ...node, community_id: community });
      offsets.set(community, offset + 1);
      addedThisPass = true;
    });
    if (!addedThisPass) break;
  }
  return selected;
}

function communityCenters(communityIds: number[], compact: boolean) {
  const width = compact ? MOBILE_WIDTH : DESKTOP_WIDTH;
  const height = compact ? MOBILE_HEIGHT : DESKTOP_HEIGHT;
  const center = { x: width / 2, y: height / 2 };
  const centers = new Map<number, Position>();
  const count = communityIds.length;
  if (count === 1) {
    centers.set(communityIds[0], center);
    return centers;
  }
  if (count === 2) {
    communityIds.forEach((community, index) => centers.set(community, compact
      ? { x: center.x, y: center.y + (index === 0 ? -245 : 245) }
      : { x: center.x + (index === 0 ? -285 : 285), y: center.y }));
    return centers;
  }

  const placeRing = (ids: number[], radiusX: number, radiusY: number, phase: number) => {
    ids.forEach((community, index) => {
      const angle = phase + index / ids.length * Math.PI * 2;
      centers.set(community, {
        x: center.x + Math.cos(angle) * radiusX,
        y: center.y + Math.sin(angle) * radiusY,
      });
    });
  };

  if (count <= 4) {
    placeRing(communityIds, compact ? 205 : 315, compact ? 315 : 190, -Math.PI / 2);
  } else {
    const innerCount = count <= 7 ? 2 : 3;
    placeRing(communityIds.slice(0, innerCount), compact ? 92 : 150, compact ? 145 : 100, -Math.PI / 2);
    placeRing(communityIds.slice(innerCount), compact ? 250 : 455, compact ? 390 : 270, -Math.PI / 2);
  }
  return centers;
}

function communitySpread(communityCount: number, compact: boolean) {
  if (communityCount <= 2) return compact ? 165 : 180;
  if (communityCount <= 4) return compact ? 112 : 128;
  if (communityCount <= 7) return compact ? 76 : 88;
  return compact ? 62 : 72;
}

function buildLayout(nodes: RelationNode[], compact: boolean): Record<string, Position> {
  const groups = new Map<number, RelationNode[]>();
  nodes.forEach((node) => groups.set(node.community_id, [...(groups.get(node.community_id) ?? []), node]));
  const communityIds = Array.from(groups.keys()).sort((a, b) => a - b);
  const centers = communityCenters(communityIds, compact);
  const spread = communitySpread(communityIds.length, compact);
  const positions: Record<string, Position> = {};

  communityIds.forEach((community) => {
    const center = centers.get(community);
    const group = [...(groups.get(community) ?? [])].sort(compareNodes);
    if (!center) return;
    group.forEach((node, index) => {
      if (index === 0) {
        positions[node.symbol] = center;
        return;
      }
      const radius = spread * Math.sqrt(index / Math.max(group.length - 1, 1));
      const angle = index * GOLDEN_ANGLE;
      positions[node.symbol] = {
        x: center.x + Math.cos(angle) * radius,
        y: center.y + Math.sin(angle) * radius,
      };
    });
  });
  return positions;
}

function compareEdges(a: RelationEdge, b: RelationEdge, selectedSymbol: string | null) {
  const aSelected = selectedSymbol !== null && (a.source === selectedSymbol || a.target === selectedSymbol) ? 1 : 0;
  const bSelected = selectedSymbol !== null && (b.source === selectedSymbol || b.target === selectedSymbol) ? 1 : 0;
  return bSelected - aSelected
    || b.weight - a.weight
    || b.confidence - a.confidence
    || a.id.localeCompare(b.id, 'en');
}

function edgeQuota(nodeCount: number, activeTypeCount: number) {
  const scaled = nodeCount <= 50 ? nodeCount * 1.6
    : nodeCount <= 100 ? nodeCount * 1.4
      : nodeCount <= 200 ? nodeCount * 1.2
        : nodeCount * 1.08;
  return Math.round(Math.max(activeTypeCount * 6, scaled));
}

function selectBalancedEdges(
  edges: RelationEdge[],
  activeTypes: Set<string>,
  minStrength: number,
  showAll: boolean,
  selectedSymbol: string | null,
  nodeCount: number,
) {
  const byType = new Map<string, RelationEdge[]>();
  Array.from(activeTypes).sort().forEach((type) => byType.set(type, []));
  edges.forEach((edge) => {
    if (!activeTypes.has(edge.relation_type) || edge.weight < minStrength) return;
    byType.get(edge.relation_type)?.push(edge);
  });
  byType.forEach((typeEdges) => typeEdges.sort((a, b) => compareEdges(a, b, selectedSymbol)));

  const cap = showAll ? SHOW_ALL_EDGE_CAP : edgeQuota(nodeCount, byType.size);
  const selected: RelationEdge[] = [];
  const selectedIds = new Set<string>();
  const offsets = new Map<string, number>();
  const types = Array.from(byType.keys());
  if (selectedSymbol) {
    // Reserve the first pass for the selected node's one-hop context, still round-robin by type.
    const incidentByType = new Map(types.map((type) => [type, (byType.get(type) ?? [])
      .filter((edge) => edge.source === selectedSymbol || edge.target === selectedSymbol)]));
    const incidentOffsets = new Map<string, number>();
    const incidentCap = showAll ? cap : Math.max(12, Math.floor(cap * .55));
    while (selected.length < incidentCap) {
      let addedThisPass = false;
      types.forEach((type) => {
        if (selected.length >= incidentCap) return;
        const offset = incidentOffsets.get(type) ?? 0;
        const edge = incidentByType.get(type)?.[offset];
        if (!edge) return;
        selected.push(edge);
        selectedIds.add(edge.id);
        incidentOffsets.set(type, offset + 1);
        addedThisPass = true;
      });
      if (!addedThisPass) break;
    }
  }
  while (selected.length < cap) {
    let addedThisPass = false;
    types.forEach((type) => {
      if (selected.length >= cap) return;
      let offset = offsets.get(type) ?? 0;
      const typeEdges = byType.get(type) ?? [];
      while (typeEdges[offset] && selectedIds.has(typeEdges[offset].id)) offset += 1;
      offsets.set(type, offset);
      const edge = typeEdges[offset];
      if (!edge) return;
      selected.push(edge);
      selectedIds.add(edge.id);
      offsets.set(type, offset + 1);
      addedThisPass = true;
    });
    if (!addedThisPass) break;
  }
  return selected;
}

function labelLimits(nodeCount: number, scale: number) {
  if (nodeCount <= 50) return { symbols: nodeCount, names: nodeCount };
  if (nodeCount <= 100) {
    return scale >= 1.25
      ? { symbols: nodeCount, names: nodeCount }
      : { symbols: nodeCount, names: Math.ceil(nodeCount * .62) };
  }
  const zoomStep = scale >= 2 ? nodeCount : scale >= 1.6 ? 150 : scale >= 1.25 ? 85 : nodeCount <= 200 ? 36 : 42;
  return { symbols: Math.min(nodeCount, zoomStep), names: Math.min(nodeCount, Math.ceil(zoomStep * .58)) };
}

function nodeRadius(node: RelationNode, nodeCount: number, compact: boolean) {
  if (nodeCount <= 50) return compact
    ? clamp(18 + node.centrality_score * 90, 20, 30)
    : clamp(15 + node.centrality_score * 100, 16, 25);
  if (nodeCount <= 100) return clamp(11 + node.centrality_score * 64, 12, compact ? 20 : 18);
  if (nodeCount <= 200) return clamp(7 + node.centrality_score * 38, 8, 13);
  return clamp(5.5 + node.centrality_score * 30, 6.5, 11);
}

function formatMetric(value: number, digits = 3) {
  return Number.isFinite(value) ? value.toFixed(digits) : '—';
}

export function StockRelationNetwork({ network, relationTypes }: { network: RelationNetwork; relationTypes: string[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const nodeCountOptions = useMemo(() => getNodeCountOptions(network), [network]);
  const communityCountOptions = useMemo(() => getCommunityCountOptions(network), [network]);
  const defaultNodeCount = getDefaultCount(network.default_node_count, nodeCountOptions, network.nodes.length);
  const fallbackCommunityCount = new Set(network.nodes.map((node) => node.community_id)).size || 2;
  const defaultCommunityCount = getDefaultCount(network.default_community_count, communityCountOptions, fallbackCommunityCount);
  const [compact, setCompact] = useState(false);
  const [activeTypes, setActiveTypes] = useState(() => new Set(relationTypes));
  const [minStrength, setMinStrength] = useState(0.35);
  const [showAll, setShowAll] = useState(false);
  const [nodeCount, setNodeCount] = useState(defaultNodeCount);
  const [communityCount, setCommunityCount] = useState(defaultCommunityCount);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<RelationEdge | null>(null);
  const [query, setQuery] = useState('');
  const [view, setView] = useState<ViewState>({ x: 0, y: 0, scale: 1 });
  const [positionOverrides, setPositionOverrides] = useState<Record<string, Position>>({});

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 620px)');
    const update = () => {
      setCompact(mediaQuery.matches);
      setPositionOverrides({});
      setView({ x: 0, y: 0, scale: 1 });
    };
    update();
    mediaQuery.addEventListener('change', update);
    return () => mediaQuery.removeEventListener('change', update);
  }, []);

  const visibleNodes = useMemo(
    () => selectCommunityBalancedNodes(network.nodes, nodeCount, communityCount),
    [communityCount, network.nodes, nodeCount],
  );
  const visibleNodeSet = useMemo(() => new Set(visibleNodes.map((node) => node.symbol)), [visibleNodes]);
  const inducedEdges = useMemo(
    () => network.edges.filter((edge) => visibleNodeSet.has(edge.source) && visibleNodeSet.has(edge.target)),
    [network.edges, visibleNodeSet],
  );
  const canvasWidth = compact ? MOBILE_WIDTH : DESKTOP_WIDTH;
  const canvasHeight = compact ? MOBILE_HEIGHT : DESKTOP_HEIGHT;
  const basePositions = useMemo(() => buildLayout(visibleNodes, compact), [compact, visibleNodes]);
  const positions = useMemo(() => ({ ...basePositions, ...positionOverrides }), [basePositions, positionOverrides]);
  const nodeMap = useMemo(() => new Map(visibleNodes.map((node) => [node.symbol, node])), [visibleNodes]);
  const visibleEdges = useMemo(
    () => selectBalancedEdges(inducedEdges, activeTypes, minStrength, showAll, selectedSymbol, visibleNodes.length),
    [activeTypes, inducedEdges, minStrength, selectedSymbol, showAll, visibleNodes.length],
  );
  const selectedNode = selectedSymbol ? nodeMap.get(selectedSymbol) : undefined;
  const focusSymbol = hoveredSymbol ?? selectedSymbol;
  const connectedSymbols = useMemo(() => {
    const connected = new Set<string>();
    if (!focusSymbol) return connected;
    visibleEdges.forEach((edge) => {
      if (edge.source === focusSymbol) connected.add(edge.target);
      if (edge.target === focusSymbol) connected.add(edge.source);
    });
    return connected;
  }, [focusSymbol, visibleEdges]);
  const selectedConnections = useMemo(() => {
    if (!selectedSymbol) return [];
    return inducedEdges
      .filter((edge) => activeTypes.has(edge.relation_type) && edge.weight >= minStrength)
      .filter((edge) => edge.source === selectedSymbol || edge.target === selectedSymbol)
      .sort((a, b) => compareEdges(a, b, selectedSymbol))
      .map((edge) => ({ edge, neighbor: nodeMap.get(edge.source === selectedSymbol ? edge.target : edge.source) }))
      .filter((item) => item.neighbor)
      .slice(0, 12);
  }, [activeTypes, inducedEdges, minStrength, nodeMap, selectedSymbol]);
  const matches = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return [];
    return visibleNodes.filter((node) => `${node.symbol} ${node.name}`.toLowerCase().includes(keyword)).slice(0, 8);
  }, [query, visibleNodes]);
  const communityIds = useMemo(
    () => Array.from(new Set(visibleNodes.map((node) => node.community_id))).sort((a, b) => a - b),
    [visibleNodes],
  );
  const communityHaloRadius = communitySpread(communityIds.length, compact) + (visibleNodes.length <= 100 ? 30 : 18);
  const rankedSymbols = useMemo(() => new Map([...visibleNodes].sort(compareNodes).map((node, index) => [node.symbol, index])), [visibleNodes]);
  const limits = labelLimits(visibleNodes.length, view.scale);

  useEffect(() => {
    if (selectedSymbol && !nodeMap.has(selectedSymbol)) setSelectedSymbol(null);
    if (hoveredSymbol && !nodeMap.has(hoveredSymbol)) setHoveredSymbol(null);
  }, [hoveredSymbol, nodeMap, selectedSymbol]);

  function resetGraph() {
    setActiveTypes(new Set(relationTypes));
    setMinStrength(0.35);
    setShowAll(false);
    setNodeCount(defaultNodeCount);
    setCommunityCount(defaultCommunityCount);
    setSelectedSymbol(null);
    setHoveredSymbol(null);
    setHoveredEdge(null);
    setPositionOverrides({});
    setView({ x: 0, y: 0, scale: 1 });
    setQuery('');
  }

  function changeNodeCount(value: number) {
    setNodeCount(value);
    setHoveredSymbol(null);
    setHoveredEdge(null);
    setPositionOverrides({});
  }

  function changeCommunityCount(value: number) {
    setCommunityCount(value);
    setHoveredSymbol(null);
    setHoveredEdge(null);
    setPositionOverrides({});
  }

  function toggleType(type: string) {
    setActiveTypes((current) => {
      const next = new Set(current);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function zoomBy(factor: number) {
    setView((current) => ({ ...current, scale: clamp(current.scale * factor, MIN_SCALE, MAX_SCALE) }));
  }

  function selectStock(symbol: string) {
    setSelectedSymbol(symbol);
    setHoveredSymbol(null);
    setQuery('');
  }

  function handleWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? 0.9 : 1.1);
  }

  function startNodeDrag(event: PointerEvent<SVGGElement>, symbol: string) {
    event.stopPropagation();
    selectStock(symbol);
    const position = positions[symbol];
    if (!position) return;
    dragRef.current = {
      kind: 'node', pointerId: event.pointerId, symbol,
      clientX: event.clientX, clientY: event.clientY,
      originX: position.x, originY: position.y,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest('.relation-node')) return;
    dragRef.current = {
      kind: 'pan', pointerId: event.pointerId,
      clientX: event.clientX, clientY: event.clientY,
      originX: view.x, originY: view.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.classList.add('is-dragging');
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds) return;
    const dx = (event.clientX - drag.clientX) * (canvasWidth / bounds.width) / view.scale;
    const dy = (event.clientY - drag.clientY) * (canvasHeight / bounds.height) / view.scale;
    if (drag.kind === 'pan') {
      setView((current) => ({ ...current, x: drag.originX + dx, y: drag.originY + dy }));
    } else {
      setPositionOverrides((current) => ({
        ...current,
        [drag.symbol]: { x: drag.originX + dx, y: drag.originY + dy },
      }));
    }
  }

  function finishDrag(event: PointerEvent<SVGSVGElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    event.currentTarget.classList.remove('is-dragging');
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  if (!network.nodes.length) {
    return <div className="graph-empty" role="status">暂无可绘制的股票节点。</div>;
  }

  return (
    <section className="relation-network-panel" aria-labelledby="relation-network-title">
      <dl className="graph-stat-strip relation-dynamic-stats" aria-label="当前关系网络摘要">
        <div><dt>股票节点</dt><dd data-testid="graph-visible-node-count">{visibleNodes.length}</dd></div>
        <div><dt>可视关系</dt><dd data-testid="graph-visible-edge-count">{visibleEdges.length}</dd></div>
        <div><dt>关系类型</dt><dd>{activeTypes.size}</dd></div>
        <div><dt>关系社区</dt><dd data-testid="graph-visible-community-count">{communityIds.length}</dd></div>
        <div className="graph-stat-types"><dt>当前包含</dt><dd>{Array.from(activeTypes).map((type) => relationLabels[type] ?? '其他关系').join(' · ') || '未选择关系类型'}</dd></div>
      </dl>

      <div className="relation-network-toolbar">
        <div>
          <span className="relation-eyebrow">INTERACTIVE NETWORK</span>
          <h2 id="relation-network-title">股票关系网络</h2>
          <p>{visibleNodes.length} 个节点 · 当前显示 {visibleEdges.length} / {inducedEdges.length} 条子图关系</p>
        </div>
        <div className="relation-network-actions" aria-label="关系图控制">
          <button data-testid="graph-zoom-in" type="button" onClick={() => zoomBy(1.16)} aria-label="放大关系图">＋</button>
          <button type="button" onClick={() => zoomBy(0.86)} aria-label="缩小关系图">−</button>
          <button data-testid="graph-reset" type="button" className="relation-reset-button" onClick={resetGraph}>重置</button>
        </div>
      </div>

      <div className="relation-network-controls">
        <div className="relation-size-controls" aria-label="网络规模控制">
          <strong className="relation-size-controls-title">选择图谱规模</strong>
          <label>
            <span>节点数量</span>
            <select data-testid="graph-node-count-select" value={nodeCount} onChange={(event) => changeNodeCount(Number(event.target.value))}>
              {nodeCountOptions.map((count) => <option key={count} value={count}>{count === 300 ? '300（全部）' : count}</option>)}
            </select>
          </label>
          <label>
            <span>社区数量</span>
            <select data-testid="graph-community-count-select" value={communityCount} onChange={(event) => changeCommunityCount(Number(event.target.value))}>
              {communityCountOptions.map((count) => <option key={count} value={count}>{count} 个社区</option>)}
            </select>
          </label>
        </div>
        <div className="relation-filter-row" aria-label="关系类型筛选">
          {relationTypes.map((type) => (
            <button
              data-testid="graph-relation-filter"
              type="button"
              key={type}
              className={activeTypes.has(type) ? 'is-active' : undefined}
              onClick={() => toggleType(type)}
              aria-pressed={activeTypes.has(type)}
            >
              <i style={{ backgroundColor: relationColors[type] ?? '#94a3b8' }} />
              {relationLabels[type] ?? '其他关系'}
            </button>
          ))}
        </div>
        <label className="relation-strength-control">
          <span>最低强度 <b>{minStrength.toFixed(2)}</b></span>
          <input
            type="range" min="0.3" max="0.9" step="0.05" value={minStrength}
            onChange={(event) => setMinStrength(Number(event.target.value))}
          />
        </label>
        <label className="relation-show-all">
          <input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />
          显示全部关系（最多 {SHOW_ALL_EDGE_CAP} 条）
        </label>
      </div>

      <div className="relation-network-layout">
        <div className="relation-canvas-shell" data-testid="graph-stage">
          <label className="relation-search">
            <span className="sr-only">搜索当前子图股票节点</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索当前节点的名称或代码" autoComplete="off" />
            {matches.length ? (
              <span className="relation-search-results">
                {matches.map((node) => (
                  <button type="button" key={node.symbol} onClick={() => selectStock(node.symbol)}>
                    <b>{node.name}</b><small>{node.symbol} · 社区 {node.community_id + 1}</small>
                  </button>
                ))}
              </span>
            ) : null}
          </label>

          <svg
            ref={svgRef}
            className={`relation-network-svg${compact ? ' is-compact' : ''}`}
            viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
            role="img"
            aria-label={`股票关系网络，共 ${visibleNodes.length} 个股票节点、${visibleEdges.length} 条可见关系、${communityIds.length} 个社区`}
            onWheel={handleWheel}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={finishDrag}
            onPointerCancel={finishDrag}
          >
            <defs>
              {communityPalette.map((color, index) => (
                <radialGradient key={index} id={`relation-node-community-${index}`} cx="35%" cy="28%">
                  <stop offset="0" stopColor={color.light} /><stop offset="1" stopColor={color.dark} />
                </radialGradient>
              ))}
              <filter id="relation-node-glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
              {relationTypes.map((type) => (
                <marker key={type} id={`arrow-${type}`} viewBox="0 0 10 10" refX="10" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={relationColors[type] ?? '#94a3b8'} />
                </marker>
              ))}
            </defs>
            <g data-testid="graph-viewport" transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
              <g className="relation-community-layer" aria-hidden="true">
                {communityIds.map((communityId) => {
                  const group = visibleNodes.filter((node) => node.community_id === communityId);
                  if (!group.length) return null;
                  const centerX = group.reduce((sum, node) => sum + (positions[node.symbol]?.x ?? 0), 0) / group.length;
                  const centerY = group.reduce((sum, node) => sum + (positions[node.symbol]?.y ?? 0), 0) / group.length;
                  return <circle className={`is-community-${communityId % communityPalette.length}`} key={communityId} cx={centerX} cy={centerY} r={communityHaloRadius} />;
                })}
              </g>
              <g className="relation-edge-layer">
                {visibleEdges.map((edge) => {
                  const source = positions[edge.source];
                  const target = positions[edge.target];
                  if (!source || !target) return null;
                  const connected = !focusSymbol || edge.source === focusSymbol || edge.target === focusSymbol;
                  return (
                    <line
                      data-testid="graph-edge"
                      data-edge-id={edge.id}
                      key={edge.id}
                      className={connected ? 'is-connected' : 'is-muted'}
                      x1={source.x} y1={source.y} x2={target.x} y2={target.y}
                      stroke={relationColors[edge.relation_type] ?? '#94a3b8'}
                      strokeWidth={0.55 + edge.weight * (visibleNodes.length > 100 ? 1.4 : 2.1)}
                      markerEnd={edge.directed ? `url(#arrow-${edge.relation_type})` : undefined}
                      onMouseEnter={() => setHoveredEdge(edge)}
                      onMouseLeave={() => setHoveredEdge(null)}
                    ><title>{`${relationLabels[edge.relation_type] ?? '其他关系'} · 强度 ${edge.weight.toFixed(3)} · 置信度 ${edge.confidence.toFixed(2)}`}</title></line>
                  );
                })}
              </g>
              <g className="relation-node-layer">
                {visibleNodes.map((node) => {
                  const position = positions[node.symbol];
                  if (!position) return null;
                  const active = focusSymbol === node.symbol;
                  const nearby = connectedSymbols.has(node.symbol);
                  const emphasized = active || nearby || selectedSymbol === node.symbol || hoveredSymbol === node.symbol;
                  const muted = Boolean(focusSymbol && !active && !nearby);
                  const radius = nodeRadius(node, visibleNodes.length, compact);
                  const rank = rankedSymbols.get(node.symbol) ?? visibleNodes.length;
                  const showSymbol = emphasized || rank < limits.symbols;
                  const showName = emphasized || rank < limits.names;
                  const paletteIndex = node.community_id % communityPalette.length;
                  const symbolFontSize = visibleNodes.length > 200 ? 7 : visibleNodes.length > 100 ? 8 : undefined;
                  const nameFontSize = visibleNodes.length > 200 ? 6.5 : visibleNodes.length > 100 ? 7.5 : undefined;
                  return (
                    <g
                      data-testid="graph-node"
                      data-symbol={node.symbol}
                      data-community={node.community_id}
                      key={node.symbol}
                      className={`relation-node is-community-${paletteIndex}${active ? ' is-selected' : ''}${nearby ? ' is-nearby' : ''}${muted ? ' is-muted' : ''}`}
                      transform={`translate(${position.x} ${position.y})`}
                      role="button" tabIndex={0}
                      aria-label={`${node.name} ${node.symbol}，社区 ${node.community_id + 1}，中心度 ${formatMetric(node.centrality_score, 4)}`}
                      onPointerDown={(event) => startNodeDrag(event, node.symbol)}
                      onClick={() => selectStock(node.symbol)}
                      onMouseEnter={() => setHoveredSymbol(node.symbol)}
                      onMouseLeave={() => setHoveredSymbol(null)}
                      onFocus={() => setHoveredSymbol(node.symbol)}
                      onBlur={() => setHoveredSymbol(null)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault(); selectStock(node.symbol);
                        }
                      }}
                    >
                      <circle className="relation-node-halo" r={radius + (visibleNodes.length > 100 ? 5 : 10)} />
                      <circle className="relation-node-core" r={radius} />
                      {showSymbol ? <text className="relation-node-symbol" style={symbolFontSize ? { fontSize: symbolFontSize } : undefined} y="1">{node.symbol.slice(0, 6)}</text> : null}
                      {showName ? <text className="relation-node-name" style={nameFontSize ? { fontSize: nameFontSize } : undefined} y={radius + (visibleNodes.length > 100 ? 10 : 17)}>{node.name}</text> : null}
                    </g>
                  );
                })}
              </g>
            </g>
          </svg>

          <div className="relation-canvas-caption">
            {communityIds.map((communityId) => <span key={communityId}><i className={`is-community-${communityId % communityPalette.length}`} />社区 {communityId + 1}</span>)}
            <span>滚轮缩放 · 拖动画布 · 拖动节点</span>
          </div>
          {hoveredEdge ? (
            <div className="relation-edge-tooltip">
              {relationLabels[hoveredEdge.relation_type] ?? '其他关系'} · 强度 {hoveredEdge.weight.toFixed(3)} · 置信度 {hoveredEdge.confidence.toFixed(2)}
            </div>
          ) : null}
        </div>

        <aside className="relation-node-inspector" data-testid="graph-node-detail" aria-live="polite">
          {selectedNode ? (
            <>
              <span className="relation-eyebrow">SELECTED STOCK</span>
              <div className="relation-selected-heading"><div><h3>{selectedNode.name}</h3><span>{selectedNode.symbol}</span></div><strong>社区 {selectedNode.community_id + 1}</strong></div>
              <dl className="relation-selected-meta">
                <div><dt>中心度</dt><dd>{formatMetric(selectedNode.centrality_score, 4)}</dd></div>
                <div><dt>全部关系数</dt><dd>{selectedNode.degree}</dd></div>
                <div><dt>当前筛选连接</dt><dd>{selectedConnections.length}</dd></div>
              </dl>
              <div className="relation-neighbor-list">
                <span>关联股票</span>
                {selectedConnections.length ? selectedConnections.map(({ edge, neighbor }) => (
                  <button type="button" key={`${edge.id}-${neighbor!.symbol}`} onClick={() => selectStock(neighbor!.symbol)}>
                    <i style={{ backgroundColor: relationColors[edge.relation_type] ?? '#94a3b8' }} />
                    <span><b>{neighbor!.name}</b><small>{neighbor!.symbol} · {relationLabels[edge.relation_type] ?? '其他关系'}</small></span>
                    <em>{edge.weight.toFixed(3)}</em>
                  </button>
                )) : <small>当前筛选条件下没有关系。</small>}
              </div>
              <a className="relation-detail-link" href={`/stocks/${encodeURIComponent(selectedNode.symbol)}`}>查看个股详情 <span>→</span></a>
            </>
          ) : (
            <div className="relation-inspector-empty"><span className="relation-eyebrow">NODE DETAILS</span><h3>选择一个股票节点</h3><p>点击图中的股票，即可查看真实的一跳关联、关系类型、方向与强度。</p></div>
          )}
          <small className="relation-sample-note">图中关系来自当前本地关系边数据；默认按类型均衡降噪，可主动显示更多关系。</small>
        </aside>
      </div>
    </section>
  );
}
