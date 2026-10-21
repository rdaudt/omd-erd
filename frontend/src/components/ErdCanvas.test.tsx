import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ReactFlowInstance, ReactFlowProps } from '@xyflow/react';
import type { GraphResponse } from '../api/types';
import type { RelationshipFlowEdge, TableFlowNode } from '../graph/layout';
import { ErdCanvas } from './ErdCanvas';
import { App } from '../App';

const { fitView, updateNodeInternals } = vi.hoisted(() => ({ fitView: vi.fn(async () => true), updateNodeInternals: vi.fn() }));

// jsdom has no measurable viewport. Keep our custom nodes/edges and state real;
// replace only the React Flow viewport boundary with an event adapter.
vi.mock('@xyflow/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@xyflow/react')>();
  const { createElement, useEffect } = await import('react');
  return {
    ...actual,
    ReactFlow: ({ nodes = [], edges = [], nodeTypes, edgeTypes, onInit, onNodesChange, onNodeClick, nodesConnectable, children }: ReactFlowProps<TableFlowNode, RelationshipFlowEdge>) => {
      useEffect(() => { onInit?.({ fitView } as unknown as ReactFlowInstance<TableFlowNode, RelationshipFlowEdge>); }, [onInit]);
      return <div aria-label="Graph viewport" data-connectable={String(nodesConnectable)}>
        {nodes.map((node) => <div key={node.id} onClick={(event) => onNodeClick?.(event, node)}>
          {createElement(nodeTypes!.table, { ...node, selected: node.selected ?? false, dragging: false, isConnectable: false, zIndex: 0, draggable: true, selectable: true, deletable: false, positionAbsoluteX: node.position.x, positionAbsoluteY: node.position.y })}
          <output aria-label={`${node.id} position`}>{`${node.position.x},${node.position.y}`}</output>
          <button onClick={() => onNodesChange?.([{ id: node.id, type: 'position', position: { x: 777, y: 333 } }])}>Move {node.id}</button>
        </div>)}
        <svg>{edges.map((edge) => createElement(edgeTypes!.relationship, { ...edge, data: edge.data, type: edge.type, key: edge.id, sourceX: 280, sourceY: 50, targetX: 400, targetY: 50, sourcePosition: actual.Position.Right, targetPosition: actual.Position.Left, markerStart: undefined, markerEnd: undefined, selected: false, selectable: false, deletable: false }))}</svg>
        {children}
      </div>;
    },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Handle: () => <span />,
    Controls: () => <div aria-label="Zoom controls" />,
    Background: () => null,
    Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    useUpdateNodeInternals: () => updateNodeInternals,
  };
});

const graph: GraphResponse = {
  source: 'live', schema: { id: 'one', name: 'Sales', fullyQualifiedName: 'Sales' }, warnings: [],
  tables: ['Orders', 'Customer'].map((name) => ({
    id: name, name, fullyQualifiedName: name, description: null, owner: null, tags: [], tier: null,
    columns: [{ name: name === 'Orders' ? 'customer_id' : 'id', dataType: 'INT', nullable: false, primaryKey: name === 'Customer', foreignKey: name === 'Orders', description: null }],
  })),
  relationships: [{ id: 'fk', sourceTableId: 'Orders', sourceColumn: 'customer_id', targetTableId: 'Customer', targetColumn: 'id' }],
};

describe('ERD canvas interactions', () => {
  it('selects, collapses, hides, and restores tables and incident relationships', async () => {
    const user = userEvent.setup();
    const onSelectedTableChange = vi.fn();
    render(<ErdCanvas graph={graph} onSelectedTableChange={onSelectedTableChange} />);
    expect(await screen.findByRole('button', { name: 'Select Orders' })).toBeInTheDocument();
    expect(screen.getByLabelText('Graph viewport')).toHaveAttribute('data-connectable', 'false');
    expect(screen.getByLabelText('Orders.customer_id references Customer.id')).toBeInTheDocument();
    expect(screen.getByLabelText('Foreign key')).toBeInTheDocument();
    expect(screen.getByLabelText('Primary key')).toBeInTheDocument();
    expect(screen.getAllByText('NOT NULL')).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: 'Select Orders' }));
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(graph.tables[0]);
    await user.click(screen.getByRole('button', { name: 'Collapse Orders' }));
    expect(screen.getByRole('article', { name: 'Orders table, collapsed' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Hide Orders' }));
    expect(screen.queryByRole('button', { name: 'Select Orders' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Orders.customer_id references Customer.id')).not.toBeInTheDocument();
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(null);
    await user.click(screen.getByRole('button', { name: 'Restore all tables' }));
    expect(screen.getByRole('button', { name: 'Select Orders' })).toBeInTheDocument();
    expect(screen.getByLabelText('Orders.customer_id references Customer.id')).toBeInTheDocument();
    expect(fitView).toHaveBeenCalledWith({ padding: 0.15, duration: 350 });
  });

  it('preserves dragged positions across selection, collapse, hide, restore, and same-schema refresh', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
    await screen.findByRole('button', { name: 'Move Orders' });
    await user.click(screen.getByRole('button', { name: 'Move Orders' }));
    await user.click(screen.getByRole('button', { name: 'Select Orders' }));
    await user.click(screen.getByRole('button', { name: 'Collapse all tables' }));
    await user.click(screen.getByRole('button', { name: 'Expand all tables' }));
    await user.click(screen.getByRole('button', { name: 'Hide Orders' }));
    await user.click(screen.getByRole('button', { name: 'Restore all tables' }));
    rerender(<ErdCanvas graph={{ ...graph, warnings: ['Refreshed'] }} onSelectedTableChange={vi.fn()} />);
    expect(screen.getByLabelText('Orders position')).toHaveTextContent('777,333');
    await user.click(screen.getByRole('button', { name: 'Relayout diagram' }));
    await waitFor(() => expect(screen.getByLabelText('Orders position')).not.toHaveTextContent('777,333'));
  });

  it('resets hidden, collapsed, and selected state when schema identity changes', async () => {
    const user = userEvent.setup();
    const onSelectedTableChange = vi.fn();
    const { rerender } = render(<ErdCanvas graph={graph} onSelectedTableChange={onSelectedTableChange} />);
    await user.click(await screen.findByRole('button', { name: 'Collapse Customer' }));
    await user.click(screen.getByRole('button', { name: 'Select Customer' }));
    await user.click(screen.getByRole('button', { name: 'Hide Orders' }));
    await act(async () => rerender(<ErdCanvas graph={{ ...graph, schema: { ...graph.schema, id: 'two' } }} onSelectedTableChange={onSelectedTableChange} />));
    expect(await screen.findByRole('article', { name: 'Customer table, expanded' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Select Orders' })).toBeInTheDocument();
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(null);
  });

  it('clears the App selection when switching to a schema with no tables', async () => {
    const user = userEvent.setup();
    const emptySchema = { id: 'empty', name: 'Empty', fullyQualifiedName: 'Empty' };
    const service = { id: 'service', name: 'Service', fullyQualifiedName: 'Service' };
    const database = { id: 'database', name: 'Database', fullyQualifiedName: 'Database' };
    render(<App api={{
      listServices: vi.fn(async () => [service]),
      listDatabases: vi.fn(async () => [database]),
      listSchemas: vi.fn(async () => [graph.schema, emptySchema]),
      getGraph: vi.fn(async (schemaId) => schemaId === emptySchema.id ? { ...graph, schema: emptySchema, tables: [], relationships: [] } : graph),
    }} />);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Service' }), service.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Database' }), database.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Schema' }), graph.schema.id);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    expect(screen.getByRole('complementary', { name: 'Selected table' })).toHaveTextContent('Orders');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Schema' }), emptySchema.id);
    await screen.findByText('No tables in this schema.');
    expect(screen.queryByRole('complementary', { name: 'Selected table' })).not.toBeInTheDocument();
  });
});
