import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { CatalogApi } from './api/client';
import type { CatalogItem, GraphResponse } from './api/types';
import { App } from './App';
import type { ErdCanvasProps } from './components/ErdCanvas';

// Isolate App-owned selection from canvas effects so graph replacement is
// verified even when an empty graph unmounts the canvas.
vi.mock('./components/ErdCanvas', () => ({
  ErdCanvas: ({ graph, onSelectedTableChange }: ErdCanvasProps) => <button onClick={() => onSelectedTableChange(graph.tables[0])}>Select first table</button>,
}));

const service: CatalogItem = { id: 'service', name: 'MSSQL Desktop', fullyQualifiedName: 'MSSQL Desktop' };
const database: CatalogItem = { id: 'database', name: 'AdventureWorks2019', fullyQualifiedName: 'MSSQL Desktop.AdventureWorks2019' };
const schemaOne: CatalogItem = { id: 'one', name: 'Person', fullyQualifiedName: 'MSSQL Desktop.AdventureWorks2019.Person' };
const schemaTwo: CatalogItem = { id: 'two', name: 'Sales', fullyQualifiedName: 'MSSQL Desktop.AdventureWorks2019.Sales' };

function graph(schema: CatalogItem, source: 'live' | 'sample' = 'live'): GraphResponse {
  return { source, schema, tables: [], relationships: [], warnings: [] };
}

function api(getGraph: CatalogApi['getGraph']): CatalogApi {
  return {
    listServices: vi.fn(async () => [service]),
    listDatabases: vi.fn(async () => [database]),
    listSchemas: vi.fn(async () => [schemaOne, schemaTwo]),
    getGraph,
  };
}

async function selectSchema(user: ReturnType<typeof userEvent.setup>, schema: CatalogItem) {
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Service' }), service.id);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Database' }), database.id);
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Schema' }), schema.id);
}

describe('App graph loading', () => {
  it('loads only after schema selection and keeps the last graph during a replacement request', async () => {
    const user = userEvent.setup();
    let resolveSecond: (value: GraphResponse) => void = () => undefined;
    const pendingSecond = new Promise<GraphResponse>((resolve) => { resolveSecond = resolve; });
    const getGraph = vi.fn((schemaId: string) => schemaId === schemaOne.id ? Promise.resolve(graph(schemaOne)) : pendingSecond);
    render(<App api={api(getGraph)} />);

    await selectSchema(user, schemaOne);
    expect(getGraph).toHaveBeenCalledTimes(1);
    expect(getGraph).toHaveBeenCalledWith(schemaOne.id, false, expect.any(AbortSignal));
    expect(await screen.findByText('Person diagram')).toBeInTheDocument();

    await user.selectOptions(screen.getByRole('combobox', { name: 'Schema' }), schemaTwo.id);
    expect(getGraph).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Person diagram')).toBeInTheDocument();
    expect(screen.getByText('Loading diagram…')).toBeInTheDocument();

    resolveSecond(graph(schemaTwo));
    expect(await screen.findByText('Sales diagram')).toBeInTheDocument();
  });

  it('aborts a previous graph request and ignores its late response', async () => {
    const user = userEvent.setup();
    let resolveFirst: (value: GraphResponse) => void = () => undefined;
    const pendingFirst = new Promise<GraphResponse>((resolve) => { resolveFirst = resolve; });
    const getGraph = vi.fn((schemaId: string, _refresh: boolean, _signal: AbortSignal) =>
      schemaId === schemaOne.id ? pendingFirst : Promise.resolve(graph(schemaTwo)));
    render(<App api={api(getGraph)} />);

    await selectSchema(user, schemaOne);
    const previousSignal = getGraph.mock.calls[0][2];
    await user.selectOptions(screen.getByRole('combobox', { name: 'Schema' }), schemaTwo.id);
    expect(await screen.findByText('Sales diagram')).toBeInTheDocument();
    expect(previousSignal.aborted).toBe(true);

    await act(async () => { resolveFirst(graph(schemaOne)); });
    expect(screen.queryByText('Person diagram')).not.toBeInTheDocument();
  });

  it('labels fallback sample data and shows graph warnings', async () => {
    const user = userEvent.setup();
    const sample = { ...graph(schemaOne, 'sample'), warnings: ['One relationship was skipped'] };
    render(<App api={api(vi.fn(async () => sample))} />);

    await selectSchema(user, schemaOne);
    expect(await screen.findByText('Sample data — OpenMetadata unavailable')).toBeInTheDocument();
    expect(screen.getByText('One relationship was skipped')).toBeInTheDocument();
  });

  it('shows a failed graph request without discarding the previous diagram', async () => {
    const user = userEvent.setup();
    const getGraph = vi.fn((schemaId: string) => schemaId === schemaOne.id
      ? Promise.resolve(graph(schemaOne))
      : Promise.reject(new Error('Unable to load Sales')));
    render(<App api={api(getGraph)} />);

    await selectSchema(user, schemaOne);
    expect(await screen.findByText('Person diagram')).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Schema' }), schemaTwo.id);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load Sales');
    expect(screen.getByText('Person diagram')).toBeInTheDocument();
  });

  it('clears the selected table when the same schema is refreshed with zero tables', async () => {
    const user = userEvent.setup();
    const table = { id: 'orders', name: 'Orders', fullyQualifiedName: 'Person.Orders', description: null, owner: null, tags: [], tier: null, columns: [] };
    const initial = { ...graph(schemaOne), tables: [table] };
    const initialApi = api(vi.fn(async () => initial));
    const { rerender } = render(<App api={initialApi} />);
    await selectSchema(user, schemaOne);
    await user.click(await screen.findByRole('button', { name: 'Select first table' }));
    expect(screen.getByRole('complementary', { name: 'Selected table' })).toHaveTextContent('Orders');

    rerender(<App api={{ ...initialApi, getGraph: vi.fn(async () => graph(schemaOne)) }} />);
    await screen.findByText('No tables in this schema.');
    expect(screen.queryByRole('complementary', { name: 'Selected table' })).not.toBeInTheDocument();
  });

  it('refreshes the App selected table object when the same schema retains that table', async () => {
    const user = userEvent.setup();
    const table = { id: 'orders', name: 'Orders', fullyQualifiedName: 'Person.Orders', description: null, owner: null, tags: [], tier: null, columns: [] };
    const initial = { ...graph(schemaOne), tables: [table] };
    const initialApi = api(vi.fn(async () => initial));
    const { rerender } = render(<App api={initialApi} />);
    await selectSchema(user, schemaOne);
    await user.click(await screen.findByRole('button', { name: 'Select first table' }));
    const updated = { ...table, name: 'Orders updated', description: 'Current description' };
    rerender(<App api={{ ...initialApi, getGraph: vi.fn(async () => ({ ...initial, tables: [updated] })) }} />);
    expect(await screen.findByRole('heading', { name: 'Orders updated' })).toBeInTheDocument();
  });
});
