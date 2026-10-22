import { useEffect, useRef, useState } from 'react';
import type { CatalogApi } from '../api/client';
import type { CatalogItem } from '../api/types';

export type CatalogSelection = {
  service: CatalogItem | null;
  database: CatalogItem | null;
  schema: CatalogItem | null;
};

export type CatalogSelectorProps = {
  api: CatalogApi;
  onSelectionChange: (selection: CatalogSelection) => void;
};

export function CatalogSelector({ api, onSelectionChange }: CatalogSelectorProps) {
  const [services, setServices] = useState<CatalogItem[]>([]);
  const [databases, setDatabases] = useState<CatalogItem[]>([]);
  const [schemas, setSchemas] = useState<CatalogItem[]>([]);
  const [selection, setSelection] = useState<CatalogSelection>({ service: null, database: null, schema: null });
  const [loading, setLoading] = useState<'services' | 'databases' | 'schemas' | null>('services');
  const [error, setError] = useState<string | null>(null);
  const serviceRequest = useRef<AbortController | null>(null);
  const databaseRequest = useRef<AbortController | null>(null);
  const schemaRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const request = new AbortController();
    serviceRequest.current = request;
    setLoading('services');
    setError(null);
    api.listServices(request.signal)
      .then((items) => {
        if (!request.signal.aborted) setServices(items);
      })
      .catch((cause: unknown) => {
        if (!request.signal.aborted) setError(messageFor(cause));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(null);
      });
    return () => {
      request.abort();
      databaseRequest.current?.abort();
      schemaRequest.current?.abort();
    };
  }, [api]);

  function selectService(id: string) {
    databaseRequest.current?.abort();
    schemaRequest.current?.abort();
    const service = services.find((item) => item.id === id) ?? null;
    const nextSelection = { service, database: null, schema: null };
    setSelection(nextSelection);
    onSelectionChange(nextSelection);
    setDatabases([]);
    setSchemas([]);
    setError(null);
    setLoading(null);
    if (!service) return;

    const request = new AbortController();
    databaseRequest.current = request;
    setLoading('databases');
    api.listDatabases(service.id, request.signal)
      .then((items) => {
        if (!request.signal.aborted) setDatabases(items);
      })
      .catch((cause: unknown) => {
        if (!request.signal.aborted) setError(messageFor(cause));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(null);
      });
  }

  function selectDatabase(id: string) {
    schemaRequest.current?.abort();
    const database = databases.find((item) => item.id === id) ?? null;
    const nextSelection = { service: selection.service, database, schema: null };
    setSelection(nextSelection);
    onSelectionChange(nextSelection);
    setSchemas([]);
    setError(null);
    setLoading(null);
    if (!database) return;

    const request = new AbortController();
    schemaRequest.current = request;
    setLoading('schemas');
    api.listSchemas(database.id, request.signal)
      .then((items) => {
        if (!request.signal.aborted) setSchemas(items);
      })
      .catch((cause: unknown) => {
        if (!request.signal.aborted) setError(messageFor(cause));
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(null);
      });
  }

  function selectSchema(id: string) {
    const schema = schemas.find((item) => item.id === id) ?? null;
    const nextSelection = { ...selection, schema };
    setSelection(nextSelection);
    onSelectionChange(nextSelection);
  }

  return (
    <div className="catalog-selector" aria-label="Catalog selection">
      <label>
        Database service
        <select value={selection.service?.id ?? ''} onChange={(event) => selectService(event.target.value)} disabled={loading === 'services'}>
          <option value="">Select a service</option>
          {services.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label>
        Database
        <select value={selection.database?.id ?? ''} onChange={(event) => selectDatabase(event.target.value)} disabled={!selection.service || loading === 'databases' || databases.length === 0}>
          <option value="">Select a database</option>
          {databases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label>
        Schema
        <select value={selection.schema?.id ?? ''} onChange={(event) => selectSchema(event.target.value)} disabled={!selection.database || loading === 'schemas' || schemas.length === 0}>
          <option value="">Select a schema</option>
          {schemas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      {loading && <span role="status">Loading {loading}…</span>}
      {error && <span role="alert">{error}</span>}
    </div>
  );
}

function messageFor(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Catalog request failed';
}
