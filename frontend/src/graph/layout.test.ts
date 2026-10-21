import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ElkNode } from 'elkjs/lib/elk-api';
import type { GraphResponse } from '../api/types';
import { COLUMN_HEIGHT, HEADER_HEIGHT, layoutGraph, TABLE_WIDTH } from './layout';

const { layout } = vi.hoisted(() => ({ layout: vi.fn(async (graph: ElkNode) => ({
  ...graph, children: graph.children?.map((node, index) => ({ ...node, x: index * 400, y: 80 })),
})) }));
vi.mock('elkjs/lib/elk.bundled.js', () => ({ default: class { layout = layout; } }));

const graph: GraphResponse = {
  source: 'live', schema: { id: 'schema', name: 'schema', fullyQualifiedName: 'schema' }, warnings: [],
  tables: ['Orders', 'Customer'].map((name) => ({
    id: name, name, fullyQualifiedName: name, description: null, owner: null, tags: [], tier: null,
    columns: ['id', 'customer_id'].map((column) => ({ name: column, dataType: 'INT', nullable: false, primaryKey: column === 'id', foreignKey: column === 'customer_id', description: null })),
  })),
  relationships: [{ id: 'fk', sourceTableId: 'Orders', sourceColumn: 'customer_id', targetTableId: 'Customer', targetColumn: 'id' }],
};

describe('ELK layout adapter', () => {
  beforeEach(() => { layout.mockClear(); });
  it('uses stable dimensions, RIGHT layered layout, orthogonal routing, and column ports', async () => {
    const result = await layoutGraph(graph, new Set(['Customer']));
    const input = layout.mock.calls[0][0];
    expect(input.layoutOptions).toMatchObject({ 'elk.algorithm': 'layered', 'elk.direction': 'RIGHT', 'elk.edgeRouting': 'ORTHOGONAL' });
    expect(input.children?.[0]).toMatchObject({ id: 'Orders', width: TABLE_WIDTH, height: HEADER_HEIGHT + 2 * COLUMN_HEIGHT });
    expect(input.children?.[1]?.height).toBe(HEADER_HEIGHT);
    const edge = input.edges![0];
    expect(input.children?.[0].ports?.map(({ id }) => id)).toContain(edge.sources[0]);
    expect(input.children?.[1].ports?.map(({ id }) => id)).toContain(edge.targets[0]);
    expect(result.nodes[1].position).toEqual({ x: 400, y: 80 });
    expect(result.edges[0]).toMatchObject({ id: 'fk', source: 'Orders', target: 'Customer', data: { sourceColumn: 'customer_id', targetColumn: 'id', label: 'Orders.customer_id references Customer.id' } });
    expect(result.edges[0].sourceHandle).toBe(edge.sources[0]);
    expect(result.edges[0].targetHandle).toBe(edge.targets[0]);
    expect(result.edges[0].markerEnd).toMatchObject({ type: 'arrowclosed' });
  });
  it('returns empty graph without invoking ELK', async () => {
    expect(await layoutGraph({ ...graph, tables: [], relationships: [] }, new Set())).toEqual({ nodes: [], edges: [] });
    expect(layout).not.toHaveBeenCalled();
  });
});
