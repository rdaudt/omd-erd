import { describe, expect, it, vi } from 'vitest';
import { ApiError, createCatalogApi } from './client';

describe('catalog API client', () => {
  it('uses the four read-only routes and forwards request cancellation', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response('[]', { status: 200 }));
    const api = createCatalogApi(fetcher);
    const signal = new AbortController().signal;

    await api.listServices(signal);
    await api.listDatabases('service/id', signal);
    await api.listSchemas('database id', signal);
    fetcher.mockResolvedValueOnce(new Response('{"source":"live","schema":{"id":"x","name":"x","fullyQualifiedName":"x"},"tables":[],"relationships":[],"warnings":[]}', { status: 200 }));
    await api.getGraph('schema/id', true, signal);

    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      '/api/services',
      '/api/databases?serviceId=service%2Fid',
      '/api/schemas?databaseId=database+id',
      '/api/schemas/schema%2Fid/graph?refresh=true',
    ]);
    expect(fetcher.mock.calls.every(([, init]) => init?.signal === signal && init?.method === 'GET')).toBe(true);
  });

  it('throws an ApiError with status and safe detail', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response('{"detail":"Catalog parent was not found"}', { status: 404 }));
    const api = createCatalogApi(fetcher);

    await expect(api.listDatabases('missing', new AbortController().signal)).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'Catalog parent was not found',
    } satisfies Partial<ApiError>);
  });
});
