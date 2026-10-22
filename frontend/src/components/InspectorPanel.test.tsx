import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { GraphResponse } from '../api/types';
import { InspectorPanel, type InspectorPanelProps } from './InspectorPanel';

const graph: GraphResponse = {
  source: 'live', schema: { id: 'sales', name: 'Sales', fullyQualifiedName: 'Warehouse.Sales' }, warnings: [],
  tables: [
    { id: 'orders', name: 'Orders', fullyQualifiedName: 'Sales.Orders', description: 'Customer purchases', owner: 'Commerce team', tier: 'Tier1', tags: ['PII.Sensitive', 'Domain.Commerce'], columns: [
      { name: 'id', dataType: 'BIGINT', nullable: false, primaryKey: true, foreignKey: false, description: 'Order identifier' },
      { name: 'customer_id', dataType: 'INT', nullable: true, primaryKey: false, foreignKey: true, description: null },
    ] },
    { id: 'customers', name: 'Customers', fullyQualifiedName: 'Sales.Customers', description: null, owner: null, tier: null, tags: [], columns: [] },
    { id: 'lines', name: 'OrderLines', fullyQualifiedName: 'Sales.OrderLines', description: null, owner: null, tier: null, tags: [], columns: [] },
  ],
  relationships: [
    { id: 'outgoing', sourceTableId: 'orders', sourceColumn: 'customer_id', targetTableId: 'customers', targetColumn: 'id' },
    { id: 'incoming', sourceTableId: 'lines', sourceColumn: 'order_id', targetTableId: 'orders', targetColumn: 'id' },
  ],
};

function props(overrides: Partial<InspectorPanelProps> = {}): InspectorPanelProps {
  return { graph, selectedTable: null, hiddenTableIds: new Set(['lines']), disabled: false,
    onRestoreTable: vi.fn(), onRestoreAll: vi.fn(), onCollapseAll: vi.fn(), onExpandAll: vi.fn(), onRelayout: vi.fn(), ...overrides };
}

describe('InspectorPanel', () => {
  it('shows diagram counts and named hidden-table restore controls by default', async () => {
    const user = userEvent.setup();
    const actions = props();
    render(<InspectorPanel {...actions} />);
    const panel = screen.getByRole('complementary', { name: 'Diagram inspector' });
    expect(within(panel).getByText('3 tables')).toBeInTheDocument();
    expect(within(panel).getByText('2 relationships')).toBeInTheDocument();
    expect(within(panel).getByText('2 visible')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Restore OrderLines' }));
    expect(actions.onRestoreTable).toHaveBeenCalledWith('lines');
    for (const [name, action] of [
      ['Restore all hidden tables', actions.onRestoreAll], ['Collapse all tables', actions.onCollapseAll],
      ['Expand all tables', actions.onExpandAll], ['Relayout diagram', actions.onRelayout],
    ] as const) {
      await user.click(within(panel).getByRole('button', { name }));
      expect(action).toHaveBeenCalledOnce();
    }
  });

  it('shows selected OMD metadata, columns, keys, and both relationship directions', () => {
    render(<InspectorPanel {...props({ selectedTable: graph.tables[0] })} />);
    const panel = screen.getByRole('complementary', { name: 'Selected table' });
    expect(within(panel).getByRole('heading', { name: 'Orders' })).toBeInTheDocument();
    for (const value of ['Sales.Orders', 'Customer purchases', 'Commerce team', 'Tier1', 'PII.Sensitive', 'Domain.Commerce', 'Order identifier', 'BIGINT', 'INT', 'NULL', 'NOT NULL']) {
      expect(within(panel).getByText(value)).toBeInTheDocument();
    }
    expect(within(panel).getByLabelText('Primary key')).toBeInTheDocument();
    expect(within(panel).getByLabelText('Foreign key')).toBeInTheDocument();
    expect(within(panel).getByRole('region', { name: 'Incoming references' })).toHaveTextContent('OrderLines.order_id → Orders.id');
    expect(within(panel).getByRole('region', { name: 'Outgoing references' })).toHaveTextContent('Orders.customer_id → Customers.id');
  });

  it('uses explicit fallbacks for optional metadata and empty relationships', () => {
    render(<InspectorPanel {...props({ selectedTable: graph.tables[1], graph: { ...graph, relationships: [] } })} />);
    expect(screen.getAllByText('Not assigned')).toHaveLength(4);
    expect(screen.getByRole('region', { name: 'Incoming references' })).toHaveTextContent('None');
    expect(screen.getByRole('region', { name: 'Outgoing references' })).toHaveTextContent('None');
  });

  it('keeps the same panel mounted as selection changes and disables unavailable actions', () => {
    const { rerender } = render(<InspectorPanel {...props({ graph: null, hiddenTableIds: new Set(), disabled: true })} />);
    const panel = screen.getByRole('complementary', { name: 'Diagram inspector' });
    expect(within(panel).getByRole('button', { name: 'Relayout diagram' })).toBeDisabled();
    expect(within(panel).getByRole('button', { name: 'Restore all hidden tables' })).toBeDisabled();
    rerender(<InspectorPanel {...props({ selectedTable: graph.tables[0] })} />);
    expect(screen.getByRole('complementary', { name: 'Selected table' })).toBe(panel);
  });
});
