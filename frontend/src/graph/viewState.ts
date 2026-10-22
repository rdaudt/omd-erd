import type { GraphResponse } from '../api/types';

export type ViewState = {
  hiddenIds: ReadonlySet<string>;
  collapsedIds: ReadonlySet<string>;
  selectedId: string | null;
};

export function visibleGraph(graph: GraphResponse, hiddenIds: ReadonlySet<string>): GraphResponse {
  return {
    ...graph,
    tables: graph.tables.filter((table) => !hiddenIds.has(table.id)),
    relationships: graph.relationships.filter((edge) => !hiddenIds.has(edge.sourceTableId) && !hiddenIds.has(edge.targetTableId)),
  };
}

export function relatedIds(graph: GraphResponse, selectedId: string | null): Set<string> {
  const related = new Set<string>();
  if (selectedId === null) return related;
  for (const edge of graph.relationships) {
    if (edge.sourceTableId === selectedId && edge.targetTableId !== selectedId) related.add(edge.targetTableId);
    if (edge.targetTableId === selectedId && edge.sourceTableId !== selectedId) related.add(edge.sourceTableId);
  }
  return related;
}

export function resetViewState(): ViewState {
  return { hiddenIds: new Set(), collapsedIds: new Set(), selectedId: null };
}
