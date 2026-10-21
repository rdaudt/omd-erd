import { MarkerType, type Edge, type Node } from '@xyflow/react';
import type { ElkNode } from 'elkjs/lib/elk-api';
import type { GraphResponse, TableModel } from '../api/types';

export const TABLE_WIDTH = 280;
export const HEADER_HEIGHT = 48;
export const COLUMN_HEIGHT = 28;

export type TableNodeData = {
  table: TableModel;
  collapsed: boolean;
  related?: boolean;
  onSelect?: (id: string) => void;
  onToggleCollapsed?: (id: string) => void;
  onHide?: (id: string) => void;
};
export type RelationshipEdgeData = { sourceColumn: string; targetColumn: string; label: string };
export type TableFlowNode = Node<TableNodeData, 'table'>;
export type RelationshipFlowEdge = Edge<RelationshipEdgeData, 'relationship'>;
export type LayoutResult = { nodes: TableFlowNode[]; edges: RelationshipFlowEdge[] };

export function columnPortId(tableId: string, column: string, side: 'source' | 'target'): string {
  return JSON.stringify([tableId, column, side]);
}

export function columnPortTop(index: number, collapsed: boolean): number {
  return collapsed ? HEADER_HEIGHT / 2 : HEADER_HEIGHT + (index + 0.5) * COLUMN_HEIGHT;
}

// Keep the layout engine out of the initial application download. The canvas
// already displays its layout status while this promise loads and runs ELK.
let elkPromise: Promise<import('elkjs/lib/elk-api').ELK> | undefined;

function loadElk() {
  elkPromise ??= import('elkjs/lib/elk.bundled.js').then(({ default: ELK }) => new ELK());
  return elkPromise;
}

export async function layoutGraph(graph: GraphResponse, collapsedIds: ReadonlySet<string>): Promise<LayoutResult> {
  if (graph.tables.length === 0) return { nodes: [], edges: [] };
  const tables = new Map(graph.tables.map((table) => [table.id, table]));
  const edges: RelationshipFlowEdge[] = graph.relationships
    .filter((edge) => tables.has(edge.sourceTableId) && tables.has(edge.targetTableId))
    .map((edge) => ({
      id: edge.id, type: 'relationship', source: edge.sourceTableId, target: edge.targetTableId,
      sourceHandle: columnPortId(edge.sourceTableId, edge.sourceColumn, 'source'),
      targetHandle: columnPortId(edge.targetTableId, edge.targetColumn, 'target'),
      data: {
        sourceColumn: edge.sourceColumn, targetColumn: edge.targetColumn,
        label: `${tables.get(edge.sourceTableId)!.name}.${edge.sourceColumn} references ${tables.get(edge.targetTableId)!.name}.${edge.targetColumn}`,
      },
      ariaLabel: `${tables.get(edge.sourceTableId)!.name}.${edge.sourceColumn} references ${tables.get(edge.targetTableId)!.name}.${edge.targetColumn}`,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#a69cc7', width: 18, height: 18 },
      deletable: false, reconnectable: false,
    }));
  const input: ElkNode = {
    id: graph.schema.id,
    layoutOptions: {
      'elk.algorithm': 'layered', 'elk.direction': 'RIGHT', 'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '60', 'elk.layered.spacing.nodeNodeBetweenLayers': '100',
    },
    children: graph.tables.map((table) => {
      const collapsed = collapsedIds.has(table.id);
      return {
        id: table.id, width: TABLE_WIDTH, height: HEADER_HEIGHT + (collapsed ? 0 : table.columns.length * COLUMN_HEIGHT),
        layoutOptions: { 'elk.portConstraints': 'FIXED_POS' },
        ports: table.columns.flatMap((column, index) => (['source', 'target'] as const).map((side) => ({
          id: columnPortId(table.id, column.name, side), width: 0, height: 0,
          x: side === 'source' ? TABLE_WIDTH : 0, y: columnPortTop(index, collapsed),
          layoutOptions: { 'elk.port.side': side === 'source' ? 'EAST' : 'WEST' },
        }))),
      };
    }),
    edges: edges.map((edge) => ({ id: edge.id, sources: [edge.sourceHandle!], targets: [edge.targetHandle!] })),
  };
  const elk = await loadElk();
  const result = await elk.layout(input);
  const positions = new Map(result.children?.map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]));
  return {
    nodes: graph.tables.map((table) => ({
      id: table.id, type: 'table', ariaLabel: `${table.name} table`, position: positions.get(table.id) ?? { x: 0, y: 0 },
      data: { table, collapsed: collapsedIds.has(table.id) },
      width: TABLE_WIDTH, dragHandle: '.table-node-header', deletable: false,
    })),
    edges,
  };
}
