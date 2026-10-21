import type { CatalogItem, GraphResponse } from './types';

export interface CatalogApi {
  listServices(signal: AbortSignal): Promise<CatalogItem[]>;
  listDatabases(serviceId: string, signal: AbortSignal): Promise<CatalogItem[]>;
  listSchemas(databaseId: string, signal: AbortSignal): Promise<CatalogItem[]>;
  getGraph(schemaId: string, refresh: boolean, signal: AbortSignal): Promise<GraphResponse>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`Request failed (${status}): ${detail}`);
    this.name = 'ApiError';
  }
}

function safeDetail(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    const detail = body.detail.replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 300);
    if (detail) return detail;
  }
  return `HTTP ${status}`;
}

export async function getJson<T>(url: string, signal: AbortSignal, fetcher: typeof fetch = fetch): Promise<T> {
  const response = await fetcher(url, { method: 'GET', signal });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, safeDetail(body, response.status));
  }
  return (await response.json()) as T;
}

export function createCatalogApi(fetcher: typeof fetch = fetch): CatalogApi {
  return {
    listServices: (signal) => getJson<CatalogItem[]>('/api/services', signal, fetcher),
    listDatabases: (serviceId, signal) =>
      getJson<CatalogItem[]>(`/api/databases?${new URLSearchParams({ serviceId })}`, signal, fetcher),
    listSchemas: (databaseId, signal) =>
      getJson<CatalogItem[]>(`/api/schemas?${new URLSearchParams({ databaseId })}`, signal, fetcher),
    getGraph: (schemaId, refresh, signal) =>
      getJson<GraphResponse>(
        `/api/schemas/${encodeURIComponent(schemaId)}/graph${refresh ? '?refresh=true' : ''}`,
        signal,
        fetcher,
      ),
  };
}

export const catalogApi = createCatalogApi();
