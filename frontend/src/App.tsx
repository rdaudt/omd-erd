import { useEffect, useState } from 'react';
import { catalogApi, type CatalogApi } from './api/client';
import type { GraphResponse, TableModel } from './api/types';
import { ErdCanvas, type CanvasDisplayState } from './components/ErdCanvas';
import { InspectorPanel } from './components/InspectorPanel';
import { CatalogSelector, type CatalogSelection } from './components/CatalogSelector';
import { StatusBanner } from './components/StatusBanner';
import './styles.css';

export type AppProps = { api?: CatalogApi };
const emptyDisplayState: CanvasDisplayState = {
  hiddenTableIds: new Set<string>(), disabled: true,
  onRestoreTable: () => undefined, onRestoreAll: () => undefined,
  onCollapseAll: () => undefined, onExpandAll: () => undefined, onRelayout: () => undefined,
};

export function App({ api = catalogApi }: AppProps) {
  const [selection, setSelection] = useState<CatalogSelection>({ service: null, database: null, schema: null });
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loadedSchemaId, setLoadedSchemaId] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<TableModel | null>(null);
  const [displayState, setDisplayState] = useState<CanvasDisplayState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const schemaId = selection.schema?.id;
  const inspectedTable = graph?.tables.find((table) => table.id === selectedTable?.id) ?? null;

  useEffect(() => {
    setSelectedTable((previous) => graph?.tables.find((table) => table.id === previous?.id) ?? null);
  }, [graph]);

  useEffect(() => {
    if (!schemaId) {
      setGraph(null);
      setLoadedSchemaId(null);
      setSelectedTable(null);
      setDisplayState(null);
      setLoading(false);
      setError(null);
      return;
    }

    const request = new AbortController();
    setLoading(true);
    setError(null);
    api.getGraph(schemaId, false, request.signal)
      .then((result) => {
        if (!request.signal.aborted) {
          setSelectedTable(null);
          setDisplayState(null);
          setGraph(result);
          setLoadedSchemaId(schemaId);
        }
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
          <p className="eyebrow">OpenMetadata</p>
          <h1>Schema explorer</h1>
        </div>
        <CatalogSelector api={api} onSelectionChange={setSelection} />
      </header>
      <StatusBanner loading={loading} error={error} source={graph?.source ?? null} warnings={graph?.warnings ?? []} />
      <main className="app-content">
        <section className="diagram-shell" aria-label="Diagram">
          {graph ? (
            <>
              <div className="diagram-heading"><h2>{graph.schema.name} diagram</h2>
                <p>{graph.tables.length} tables · {graph.relationships.length} relationships</p></div>
              {graph.tables.length === 0 && <div className="empty-state"><p>No tables in this schema.</p></div>}
              {graph.tables.length > 0 && <ErdCanvas key={loadedSchemaId ?? graph.schema.id} graph={graph} onSelectedTableChange={setSelectedTable} onDisplayStateChange={setDisplayState} />}
            </>
          ) : (
            <div className="empty-state"><p className="eyebrow">Explore your catalog</p><h2>Every relationship, in view.</h2><p>Select a service, database, and schema to view its diagram.</p></div>
          )}
        </section>
        <InspectorPanel graph={graph} selectedTable={inspectedTable} {...(displayState ?? emptyDisplayState)} />
      </main>
    </div>
  );
}
