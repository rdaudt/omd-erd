import { describe, expect, it } from 'vitest';
import type { GraphResponse, TableModel } from '../api/types';
import { emptyMessage, entityCounts, filterGraph } from './entityFilter';

const entity = (id: string, entityType: TableModel['entityType']): TableModel => ({
  id, name: id, fullyQualifiedName: `Sales.${id}`, entityType,
  description: null, owner: null, tags: [], tier: null, columns: [],
});

const graph: GraphResponse = {
  source: 'live',
  schema: { id: 'sales', name: 'Sales', fullyQualifiedName: 'Sales' },
  tables: [entity('orders', 'table'), entity('customers', 'table'), entity('order-summary', 'view')],
  relationships: [
    { id: 'orders-customers', sourceTableId: 'orders', sourceColumn: 'customer_id', targetTableId: 'customers', targetColumn: 'id' },
    { id: 'summary-orders', sourceTableId: 'order-summary', sourceColumn: 'order_id', targetTableId: 'orders', targetColumn: 'id' },
  ],
  warnings: [],
};

describe('entity graph filtering', () => {
  it('keeps only tables and relationships whose endpoints remain', () => {
    const filtered = filterGraph(graph, 'tables');
    expect(filtered.tables.map(({ id }) => id)).toEqual(['orders', 'customers']);
    expect(filtered.relationships.map(({ id }) => id)).toEqual(['orders-customers']);
  });

  it('keeps only views and drops relationships to filtered tables', () => {
    const filtered = filterGraph(graph, 'views');
    expect(filtered.tables.map(({ id }) => id)).toEqual(['order-summary']);
    expect(filtered.relationships).toEqual([]);
  });

  it('returns the complete graph for both', () => {
    expect(filterGraph(graph, 'both')).toBe(graph);
  });

  it('reports complete graph counts and mode-specific empty messages', () => {
    expect(entityCounts(graph)).toEqual({ tables: 2, views: 1 });
    expect(emptyMessage('tables')).toBe('No tables in this schema.');
    expect(emptyMessage('views')).toBe('No views in this schema.');
    expect(emptyMessage('both')).toBe('No tables or views in this schema.');
  });
});
