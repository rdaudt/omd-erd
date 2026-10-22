/// <reference types="vite/client" />
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Background, ReactFlow, ReactFlowProvider, applyNodeChanges, useNodesInitialized, type NodeChange, type ReactFlowInstance } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { GraphResponse, TableModel } from '../api/types';
import { layoutGraph, type RelationshipFlowEdge, type TableFlowNode } from '../graph/layout';
import { relatedIds, resetViewState, visibleGraph } from '../graph/viewState';
import { CanvasControls } from './CanvasControls';
import { RelationshipEdge } from './RelationshipEdge';
import { TableNode } from './TableNode';

export type CanvasDisplayState = {
  hiddenEntityIds: ReadonlySet<string>;
  disabled: boolean;
  onRestoreTable: (id: string) => void;
  onRestoreAll: () => void;
  onCollapseAll: () => void;
  onExpandAll: () => void;
  onRelayout: () => void;
};
export type ErdCanvasProps = {
  graph: GraphResponse;
  onSelectedTableChange: (table: TableModel | null) => void;
  onDisplayStateChange?: (state: CanvasDisplayState | null) => void;
};
const nodeTypes = { table: TableNode };
const edgeTypes = { relationship: RelationshipEdge };

// Remount only on schema identity changes, so schema view state cannot leak.
export function ErdCanvas(props: ErdCanvasProps) {
  return <ReactFlowProvider key={props.graph.schema.id}><Canvas {...props} /></ReactFlowProvider>;
}

function Canvas({ graph, onSelectedTableChange, onDisplayStateChange }: ErdCanvasProps) {
  const [view, setView] = useState(resetViewState);
  const [baseNodes, setBaseNodes] = useState<TableFlowNode[]>([]);
  const [baseEdges, setBaseEdges] = useState<RelationshipFlowEdge[]>([]);
  const [revision, setRevision] = useState(0);
  const [fitRevision, setFitRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [instance, setInstance] = useState<ReactFlowInstance<TableFlowNode, RelationshipFlowEdge> | null>(null);
  const appliedRevision = useRef<number | null>(null);
  const appliedFitRevision = useRef(0);
  const nodesInitialized = useNodesInitialized();
  const viewRef = useRef(view);
  const selectedCallback = useRef(onSelectedTableChange);
  viewRef.current = view;
  selectedCallback.current = onSelectedTableChange;

  useEffect(() => { selectedCallback.current(null); }, []);

  useEffect(() => {
    const selectedId = viewRef.current.selectedId;
    if (selectedId === null) return;
    const table = graph.tables.find((item) => item.id === selectedId) ?? null;
    if (!table) {
      viewRef.current = { ...viewRef.current, selectedId: null };
      setView((previous) => ({ ...previous, selectedId: null }));
    }
    selectedCallback.current(table);
  }, [graph.tables]);

  useEffect(() => {
    let cancelled = false;
    const preservePositions = appliedRevision.current === revision;
    setLoading(true);
    setError(null);
    layoutGraph(graph, viewRef.current.collapsedIds).then((result) => {
      if (cancelled) return;
      setBaseNodes((previous) => {
        const positions = new Map(previous.map((node) => [node.id, node.position]));
        return result.nodes.map((node) => ({ ...node, position: preservePositions ? positions.get(node.id) ?? node.position : node.position }));
      });
      setBaseEdges(result.edges);
      appliedRevision.current = revision;
      if (!preservePositions) setFitRevision((value) => value + 1);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!cancelled) {
        setError(cause instanceof Error ? cause.message : 'Unable to lay out diagram');
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [graph, revision]);

  useEffect(() => {
    if (!instance || !nodesInitialized || fitRevision <= appliedFitRevision.current) return;
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    appliedFitRevision.current = fitRevision;
    void instance.fitView({ padding: 0.15, duration: reducedMotion ? 0 : 350 });
  }, [instance, fitRevision, nodesInitialized]);

  const onInit = useCallback((flow: ReactFlowInstance<TableFlowNode, RelationshipFlowEdge>) => { setInstance(flow); }, []);
  const select = useCallback((id: string | null) => {
    const table = graph.tables.find((item) => item.id === id && !viewRef.current.hiddenIds.has(item.id)) ?? null;
    const selectedId = table?.id ?? null;
    if (viewRef.current.selectedId === selectedId) return;
    viewRef.current = { ...viewRef.current, selectedId };
    setView((previous) => ({ ...previous, selectedId }));
    selectedCallback.current(table);
  }, [graph.tables]);
  const toggleCollapsed = useCallback((id: string) => {
    setView((previous) => {
      const collapsedIds = new Set(previous.collapsedIds);
      if (collapsedIds.has(id)) collapsedIds.delete(id); else collapsedIds.add(id);
      return { ...previous, collapsedIds };
    });
  }, []);
  const hide = useCallback((id: string) => {
    if (viewRef.current.selectedId === id) select(null);
    setView((previous) => ({ ...previous, hiddenIds: new Set([...previous.hiddenIds, id]) }));
  }, [select]);
  const restoreTable = useCallback((id: string) => {
    setView((previous) => {
      const hiddenIds = new Set(previous.hiddenIds);
      hiddenIds.delete(id);
      return { ...previous, hiddenIds };
    });
  }, []);
  const restoreAll = useCallback(() => setView((previous) => ({ ...previous, hiddenIds: new Set<string>() })), []);
  const collapseAll = useCallback(() => setView((previous) => ({ ...previous, collapsedIds: new Set(graph.tables.map((table) => table.id)) })), [graph.tables]);
  const expandAll = useCallback(() => setView((previous) => ({ ...previous, collapsedIds: new Set<string>() })), []);
  const relayout = useCallback(() => setRevision((value) => value + 1), []);
  const displayState = useMemo<CanvasDisplayState>(() => ({
    hiddenEntityIds: view.hiddenIds, disabled: loading || graph.tables.length === 0,
    onRestoreTable: restoreTable, onRestoreAll: restoreAll, onCollapseAll: collapseAll, onExpandAll: expandAll, onRelayout: relayout,
  }), [view.hiddenIds, loading, graph.tables.length, restoreTable, restoreAll, collapseAll, expandAll, relayout]);
  useEffect(() => { onDisplayStateChange?.(displayState); }, [onDisplayStateChange, displayState]);
  useEffect(() => () => { onDisplayStateChange?.(null); }, [onDisplayStateChange]);
  const onNodesChange = useCallback((changes: NodeChange<TableFlowNode>[]) => {
    setBaseNodes((previous) => applyNodeChanges(changes, previous));
    const selectionChanges = changes.filter((change) => change.type === 'select');
    const selected = selectionChanges.find((change) => change.selected);
    if (selected) select(selected.id);
    else if (selectionChanges.some((change) => change.id === viewRef.current.selectedId)) select(null);
  }, [select]);
  const visible = useMemo(() => visibleGraph(graph, view.hiddenIds), [graph, view.hiddenIds]);
  const neighbors = useMemo(() => relatedIds(graph, view.selectedId), [graph, view.selectedId]);
  const tables = new Map(visible.tables.map((table) => [table.id, table]));
  const nodes = baseNodes.filter((node) => tables.has(node.id)).map((node) => ({
    ...node, selected: node.id === view.selectedId,
    style: { opacity: view.selectedId && node.id !== view.selectedId && !neighbors.has(node.id) ? 0.35 : 1 },
    data: { table: tables.get(node.id)!, collapsed: view.collapsedIds.has(node.id), related: neighbors.has(node.id), onSelect: select, onToggleCollapsed: toggleCollapsed, onHide: hide },
  }));
  const relationshipIds = new Set(visible.relationships.map((edge) => edge.id));
  const edges = baseEdges.filter((edge) => relationshipIds.has(edge.id)).map((edge) => ({
    ...edge, style: { stroke: 'var(--edge-color, #a69cc7)', strokeWidth: 1.6, opacity: view.selectedId && edge.source !== view.selectedId && edge.target !== view.selectedId ? 0.25 : 1 },
  }));

  return <div className="erd-canvas" aria-label={`${graph.schema.name} ERD`}>
    {loading && <p className="canvas-notice" role="status">Laying out diagram…</p>}
    {error && <p className="canvas-notice is-error" role="alert">{error}</p>}
    <ReactFlow<TableFlowNode, RelationshipFlowEdge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
      onInit={onInit} onNodesChange={onNodesChange} onNodeClick={(_event, node) => select(node.id)}
      onPaneClick={() => select(null)} multiSelectionKeyCode={null}
      nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} minZoom={0.1} maxZoom={2} colorMode="dark">
      <Background gap={24} size={1} color="var(--grid-dot)" />
      <CanvasControls onRelayout={relayout}
        onCollapseAll={collapseAll}
        onExpandAll={expandAll}
        onRestoreAll={restoreAll}
        hiddenCount={view.hiddenIds.size} disabled={loading || graph.tables.length === 0} />
    </ReactFlow>
  </div>;
}
