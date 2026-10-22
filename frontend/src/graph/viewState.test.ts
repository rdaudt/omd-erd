import { describe, expect, it } from 'vitest';
import type { GraphResponse, TableModel } from '../api/types';
import { relatedIds, resetViewState, visibleGraph } from './viewState';

const table = (id: string): TableModel => ({ id, name: id, fullyQualifiedName: id, entityType: 'table', description: null, owner: null, tags: [], tier: null, columns: [] });
const graph: GraphResponse = {
  source: 'live', schema: { id: 'schema', name: 'schema', fullyQualifiedName: 'schema' }, notices: [], warnings: [],
  tables: ['a', 'b', 'c', 'd'].map(table),
  relationships: [
    { id: 'ab', sourceTableId: 'a', sourceColumn: 'id', targetTableId: 'b', targetColumn: 'id' },
    { id: 'bc', sourceTableId: 'b', sourceColumn: 'id', targetTableId: 'c', targetColumn: 'id' },
  ],
};

describe('graph view state', () => {
  it('removes hidden tables and all incident edges without mutating input', () => {
    const visible = visibleGraph(graph, new Set(['b']));
    expect(visible.tables.map(({ id }) => id)).toEqual(['a', 'c', 'd']);
    expect(visible.relationships).toEqual([]);
    expect(graph.tables).toHaveLength(4);
    expect(visible.tables).not.toBe(graph.tables);
  });
  it('finds only direct neighbors in both directions', () => {
    expect(relatedIds(graph, 'a')).toEqual(new Set(['b']));
    expect(relatedIds(graph, 'b')).toEqual(new Set(['a', 'c']));
    expect(relatedIds(graph, null)).toEqual(new Set());
    expect(relatedIds(graph, 'missing')).toEqual(new Set());
  });
  it('resets selection and returns fresh empty sets', () => {
    const state = resetViewState();
    expect(state).toEqual({ hiddenIds: new Set(), collapsedIds: new Set(), selectedId: null });
    expect(state.hiddenIds).not.toBe(resetViewState().hiddenIds);
    expect(state.collapsedIds).not.toBe(resetViewState().collapsedIds);
  });
});
