import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ReactFlowInstance, ReactFlowProps } from '@xyflow/react';
import type { ElkNode } from 'elkjs/lib/elk-api';
import type { GraphResponse } from '../api/types';
import type { RelationshipFlowEdge, TableFlowNode } from '../graph/layout';
import { ErdCanvas } from './ErdCanvas';
import { App } from '../App';

const { fitView, updateNodeInternals, nodeMeasurement } = vi.hoisted(() => ({ fitView: vi.fn(async () => true), updateNodeInternals: vi.fn(), nodeMeasurement: { ready: true } }));

// Canvas tests exercise view state, not ELK's engine or its download latency.
// layout.test.ts verifies the adapter; the browser test uses the real engine.
vi.mock('elkjs/lib/elk.bundled.js', () => ({ default: class {
  async layout(input: ElkNode) {
    return { ...input, children: input.children?.map((node, index) => ({ ...node, x: index * 400, y: 80 })) };
  }
} }));

// jsdom has no measurable viewport. Keep our custom nodes/edges and state real;
// replace only the React Flow viewport boundary with an event adapter.
vi.mock('@xyflow/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@xyflow/react')>();
  const { createElement, useEffect } = await import('react');
  return {
    ...actual,
    ReactFlow: ({ nodes = [], edges = [], nodeTypes, edgeTypes, onInit, onNodesChange, onNodeClick, onPaneClick, nodesConnectable, children }: ReactFlowProps<TableFlowNode, RelationshipFlowEdge>) => {
      useEffect(() => { onInit?.({ fitView } as unknown as ReactFlowInstance<TableFlowNode, RelationshipFlowEdge>); }, [onInit]);
      return <div aria-label="Graph viewport" data-connectable={String(nodesConnectable)}>
        <button onClick={(event) => onPaneClick?.(event)}>Click empty canvas</button>
        {nodes.map((node) => <div key={node.id} style={node.style} onClick={(event) => onNodeClick?.(event, node)}>
          {createElement(nodeTypes!.table, { ...node, selected: node.selected ?? false, dragging: false, isConnectable: false, zIndex: 0, draggable: true, selectable: true, deletable: false, positionAbsoluteX: node.position.x, positionAbsoluteY: node.position.y })}
          <output aria-label={`${node.id} position`}>{`${node.position.x},${node.position.y}`}</output>
          <button onClick={() => onNodesChange?.([{ id: node.id, type: 'position', position: { x: 777, y: 333 } }])}>Move {node.id}</button>
          <button onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
            event.stopPropagation();
            if (event.key === 'Enter') onNodesChange?.([{ id: node.id, type: 'select', selected: !node.selected }]);
          }}>Native selection {node.id}</button>
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
    useNodesInitialized: () => nodeMeasurement.ready,
  };
});

const graph: GraphResponse = {
  source: 'live', schema: { id: 'one', name: 'Sales', fullyQualifiedName: 'Sales' }, notices: [], warnings: [],
  tables: ['Orders', 'Customer'].map((name) => ({
    id: name, name, fullyQualifiedName: name, entityType: 'table', description: null, owner: null, tags: [], tier: null,
    columns: [{ name: name === 'Orders' ? 'customer_id' : 'id', dataType: 'INT', nullable: false, primaryKey: name === 'Customer', foreignKey: name === 'Orders', description: null }],
  })),
  relationships: [{ id: 'fk', sourceTableId: 'Orders', sourceColumn: 'customer_id', targetTableId: 'Customer', targetColumn: 'id' }],
};

describe('ERD canvas interactions', () => {
  it('labels view nodes visibly and accessibly', async () => {
    const view = { ...graph.tables[0], id: 'Summary', name: 'Summary', entityType: 'view' as const };
    render(<ErdCanvas graph={{ ...graph, tables: [view], relationships: [] }} onSelectedTableChange={vi.fn()} />);
    expect(await screen.findByRole('article', { name: 'Summary view, expanded' })).toBeInTheDocument();
    expect(screen.getByText('VIEW')).toBeInTheDocument();
  });

  it('waits for measured nodes before fitting and does not refit when tables are restored', async () => {
    fitView.mockClear();
    nodeMeasurement.ready = false;
    try {
      const { rerender } = render(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
      await screen.findByRole('button', { name: 'Select Orders' });
      expect(fitView).not.toHaveBeenCalled();
      nodeMeasurement.ready = true;
      rerender(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
      await waitFor(() => expect(fitView).toHaveBeenCalledWith({ padding: 0.15, duration: 350 }));
      nodeMeasurement.ready = false;
      rerender(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
      nodeMeasurement.ready = true;
      rerender(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
      expect(fitView).toHaveBeenCalledOnce();
    } finally { nodeMeasurement.ready = true; }
  });

  it('publishes display actions and hidden tables for the inspector without moving graph state', async () => {
    const user = userEvent.setup();
    const onDisplayStateChange = vi.fn();
    render(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} onDisplayStateChange={onDisplayStateChange} />);
    await user.click(await screen.findByRole('button', { name: 'Hide Orders' }));
    await waitFor(() => expect(onDisplayStateChange.mock.lastCall?.[0].hiddenEntityIds.has('Orders')).toBe(true));
    act(() => onDisplayStateChange.mock.lastCall?.[0].onRestoreTable('Orders'));
    expect(await screen.findByRole('button', { name: 'Select Orders' })).toBeInTheDocument();
    act(() => onDisplayStateChange.mock.lastCall?.[0].onCollapseAll());
    expect(screen.getByRole('article', { name: 'Orders table, collapsed' })).toBeInTheDocument();
    act(() => onDisplayStateChange.mock.lastCall?.[0].onExpandAll());
    expect(screen.getByRole('article', { name: 'Orders table, expanded' })).toBeInTheDocument();
  });

  it('restores a hidden table from the mounted App inspector', async () => {
    const user = userEvent.setup();
    const service = { id: 'service', name: 'Service', fullyQualifiedName: 'Service' };
    render(<App api={{ listServices: vi.fn(async () => [service]), listDatabases: vi.fn(async () => [service]), listSchemas: vi.fn(async () => [graph.schema]), getGraph: vi.fn(async () => graph) }} />);
    const panel = screen.getByRole('complementary', { name: 'Diagram inspector' });
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Database service' }), service.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Database' }), service.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Schema' }), graph.schema.id);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    expect(screen.getByRole('complementary', { name: 'Selected table' })).toBe(panel);
    await user.click(screen.getByRole('button', { name: 'Hide Orders' }));
    await user.click(within(panel).getByRole('button', { name: 'Restore Orders' }));
    expect(await screen.findByRole('button', { name: 'Select Orders' })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Diagram inspector' })).toBe(panel);
  });

  it('fits the viewport without animation when reduced motion is requested', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
    fitView.mockClear();
    try {
      render(<ErdCanvas graph={graph} onSelectedTableChange={vi.fn()} />);
      await waitFor(() => expect(fitView).toHaveBeenCalledWith({ padding: 0.15, duration: 0 }));
    } finally { vi.unstubAllGlobals(); }
  });

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
    await user.click(screen.getByRole('button', { name: 'Restore all entities' }));
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
    await user.click(screen.getByRole('button', { name: 'Collapse all entities' }));
    await user.click(screen.getByRole('button', { name: 'Expand all entities' }));
    await user.click(screen.getByRole('button', { name: 'Hide Orders' }));
    await user.click(screen.getByRole('button', { name: 'Restore all entities' }));
    rerender(<ErdCanvas graph={{ ...graph, warnings: ['Refreshed'] }} onSelectedTableChange={vi.fn()} />);
    expect(screen.getByLabelText('Orders position')).toHaveTextContent('777,333');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Relayout diagram' })).toBeEnabled());
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
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Database service' }), service.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Database' }), database.id);
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Schema' }), graph.schema.id);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    expect(screen.getByRole('complementary', { name: 'Selected table' })).toHaveTextContent('Orders');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Schema' }), emptySchema.id);
    await screen.findByText('No tables in this schema.');
    expect(screen.queryByRole('complementary', { name: 'Selected table' })).not.toBeInTheDocument();
  });

  it('clears selection and highlighting if the selected table disappears in the same schema', async () => {
    const user = userEvent.setup();
    const onSelectedTableChange = vi.fn();
    const isolated = { ...graph.tables[1], id: 'Audit', name: 'Audit' };
    const { rerender } = render(<ErdCanvas graph={{ ...graph, tables: [...graph.tables, isolated] }} onSelectedTableChange={onSelectedTableChange} />);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    expect(screen.getByRole('article', { name: 'Audit table, expanded' }).parentElement).toHaveStyle({ opacity: 0.35 });
    rerender(<ErdCanvas graph={{ ...graph, tables: [graph.tables[1], isolated], relationships: [] }} onSelectedTableChange={onSelectedTableChange} />);
    await waitFor(() => expect(onSelectedTableChange).toHaveBeenLastCalledWith(null));
    expect(screen.getByRole('article', { name: 'Audit table, expanded' }).parentElement).toHaveStyle({ opacity: 1 });
  });

  it('notifies the parent with current metadata when a selected table is refreshed', async () => {
    const user = userEvent.setup();
    const onSelectedTableChange = vi.fn();
    const { rerender } = render(<ErdCanvas graph={graph} onSelectedTableChange={onSelectedTableChange} />);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    const updated = { ...graph.tables[0], description: 'Current description', owner: 'New owner' };
    rerender(<ErdCanvas graph={{ ...graph, tables: [updated, graph.tables[1]] }} onSelectedTableChange={onSelectedTableChange} />);
    await waitFor(() => expect(onSelectedTableChange).toHaveBeenLastCalledWith(updated));
    expect(onSelectedTableChange.mock.lastCall?.[0]).toBe(updated);
    expect(screen.getByRole('button', { name: 'Select Orders' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('synchronizes pane deselection and native keyboard selection changes with the parent and highlighting', async () => {
    const user = userEvent.setup();
    const onSelectedTableChange = vi.fn();
    const isolated = { ...graph.tables[1], id: 'Audit', name: 'Audit' };
    render(<ErdCanvas graph={{ ...graph, tables: [...graph.tables, isolated] }} onSelectedTableChange={onSelectedTableChange} />);
    await user.click(await screen.findByRole('button', { name: 'Select Orders' }));
    await user.click(screen.getByRole('button', { name: 'Click empty canvas' }));
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole('button', { name: 'Select Orders' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('article', { name: 'Audit table, expanded' }).parentElement).toHaveStyle({ opacity: 1 });
    screen.getByRole('button', { name: 'Native selection Orders' }).focus();
    await user.keyboard('{Enter}');
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(graph.tables[0]);
    expect(screen.getByRole('button', { name: 'Select Orders' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('article', { name: 'Audit table, expanded' }).parentElement).toHaveStyle({ opacity: 0.35 });
    await user.keyboard('{Enter}');
    expect(onSelectedTableChange).toHaveBeenLastCalledWith(null);
    expect(screen.getByRole('button', { name: 'Select Orders' })).toHaveAttribute('aria-pressed', 'false');
  });
});
