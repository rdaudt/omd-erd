import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { CatalogApi } from '../api/client';
import type { CatalogItem } from '../api/types';
import { CatalogSelector } from './CatalogSelector';

const service = { id: 'service-1', name: 'MSSQL Desktop', fullyQualifiedName: 'MSSQL Desktop' };
const database = { id: 'database-1', name: 'AdventureWorks2019', fullyQualifiedName: 'MSSQL Desktop.AdventureWorks2019' };
const schema = { id: 'schema-1', name: 'Person', fullyQualifiedName: 'MSSQL Desktop.AdventureWorks2019.Person' };

function catalogApi(overrides: Partial<CatalogApi> = {}): CatalogApi {
  return {
    listServices: vi.fn(async (): Promise<CatalogItem[]> => [service, { id: 'service-2', name: 'Other', fullyQualifiedName: 'Other' }]),
    listDatabases: vi.fn(async (): Promise<CatalogItem[]> => [database]),
    listSchemas: vi.fn(async (): Promise<CatalogItem[]> => [schema]),
    getGraph: vi.fn(),
    ...overrides,
  };
}

describe('CatalogSelector', () => {
  it('loads databases and schemas in order and resets children when service changes', async () => {
    const user = userEvent.setup();
    const api = catalogApi();
    const onSelectionChange = vi.fn();
    render(<CatalogSelector api={api} onSelectionChange={onSelectionChange} />);

    const serviceSelect = await screen.findByRole('combobox', { name: 'Service' });
    const databaseSelect = screen.getByRole('combobox', { name: 'Database' });
    const schemaSelect = screen.getByRole('combobox', { name: 'Schema' });
    expect(databaseSelect).toBeDisabled();
    expect(schemaSelect).toBeDisabled();

    await user.selectOptions(serviceSelect, service.id);
    expect(await screen.findByRole('option', { name: 'AdventureWorks2019' })).toBeInTheDocument();
    expect(databaseSelect).toBeEnabled();
    expect(schemaSelect).toBeDisabled();
    expect(api.listDatabases).toHaveBeenCalledWith(service.id, expect.any(AbortSignal));

    await user.selectOptions(databaseSelect, database.id);
    expect(await screen.findByRole('option', { name: 'Person' })).toBeInTheDocument();
    expect(schemaSelect).toBeEnabled();
    expect(api.listSchemas).toHaveBeenCalledWith(database.id, expect.any(AbortSignal));

    await user.selectOptions(schemaSelect, schema.id);
    expect(onSelectionChange).toHaveBeenLastCalledWith({ service, database, schema });

    await user.selectOptions(serviceSelect, 'service-2');
    expect(databaseSelect).toHaveValue('');
    expect(schemaSelect).toHaveValue('');
    expect(schemaSelect).toBeDisabled();
    expect(onSelectionChange).toHaveBeenLastCalledWith({ service: { id: 'service-2', name: 'Other', fullyQualifiedName: 'Other' }, database: null, schema: null });
  });

  it('aborts a previous database request and ignores its late response', async () => {
    const user = userEvent.setup();
    let resolveFirst: (items: CatalogItem[]) => void = () => undefined;
    const firstResult = new Promise<CatalogItem[]>((resolve) => { resolveFirst = resolve; });
    const listDatabases = vi.fn((serviceId: string, _signal: AbortSignal) => serviceId === service.id ? firstResult : Promise.resolve([
      { id: 'database-2', name: 'Current database', fullyQualifiedName: 'Other.Current database' },
    ]));
    const api = catalogApi({ listDatabases });
    render(<CatalogSelector api={api} onSelectionChange={vi.fn()} />);

    const serviceSelect = await screen.findByRole('combobox', { name: 'Service' });
    await user.selectOptions(serviceSelect, service.id);
    const previousSignal = listDatabases.mock.calls[0]?.[1] as AbortSignal;
    await user.selectOptions(serviceSelect, 'service-2');
    expect(await screen.findByRole('option', { name: 'Current database' })).toBeInTheDocument();
    expect(previousSignal.aborted).toBe(true);

    resolveFirst([database]);
    expect(screen.queryByRole('option', { name: 'AdventureWorks2019' })).not.toBeInTheDocument();
  });
});
