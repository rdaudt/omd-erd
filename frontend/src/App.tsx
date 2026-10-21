import { useEffect, useState } from 'react';
import { catalogApi, type CatalogApi } from './api/client';
import type { GraphResponse } from './api/types';
import { CatalogSelector, type CatalogSelection } from './components/CatalogSelector';
import { StatusBanner } from './components/StatusBanner';

export type AppProps = { api?: CatalogApi };

export function App({ api = catalogApi }: AppProps) {
  const [selection, setSelection] = useState<CatalogSelection>({ service: null, database: null, schema: null });
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const schemaId = selection.schema?.id;

  useEffect(() => {
    if (!schemaId) {
      setLoading(false);
      setError(null);
      return;
    }

    const request = new AbortController();
    setLoading(true);
    setError(null);
    api.getGraph(schemaId, false, request.signal)
      .then((result) => {
        if (!request.signal.aborted) setGraph(result);
      })
      .catch((cause: unknown) => {
        if (!request.signal.aborted) setError(cause instanceof Error ? cause.message : 'Unable to load diagram');
      })
      .finally(() => {
        if (!request.signal.aborted) setLoading(false);
      });

    return () => request.abort();
  }, [api, schemaId]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p>OpenMetadata</p>
          <h1>Schema explorer</h1>
        </div>
        <CatalogSelector api={api} onSelectionChange={setSelection} />
      </header>
      <StatusBanner loading={loading} error={error} source={graph?.source ?? null} warnings={graph?.warnings ?? []} />
      <main className="app-content">
        <section className="diagram-shell" aria-label="Diagram">
          {graph ? (
            <>
              <h2>{graph.schema.name} diagram</h2>
              <p>{graph.tables.length} tables · {graph.relationships.length} relationships</p>
              {graph.tables.length === 0 && <p>No tables in this schema.</p>}
            </>
          ) : (
            <p>Select a service, database, and schema to view its diagram.</p>
          )}
        </section>
      </main>
    </div>
  );
}
