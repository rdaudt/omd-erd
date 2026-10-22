import type { EntityDisplayMode, GraphResponse } from '../api/types';

export function filterGraph(graph: GraphResponse, mode: EntityDisplayMode): GraphResponse {
  if (mode === 'both') return graph;
  const entityType = mode === 'tables' ? 'table' : 'view';
  const tables = graph.tables.filter((table) => table.entityType === entityType);
  const includedIds = new Set(tables.map((table) => table.id));
  return {
    ...graph,
    tables,
    relationships: graph.relationships.filter(
      (edge) => includedIds.has(edge.sourceTableId) && includedIds.has(edge.targetTableId),
    ),
  };
}

export function entityCounts(graph: GraphResponse): { tables: number; views: number } {
  return {
    tables: graph.tables.filter((entity) => entity.entityType === 'table').length,
    views: graph.tables.filter((entity) => entity.entityType === 'view').length,
  };
}

export function emptyMessage(mode: EntityDisplayMode): string {
  if (mode === 'tables') return 'No tables in this schema.';
  if (mode === 'views') return 'No views in this schema.';
  return 'No tables or views in this schema.';
}
