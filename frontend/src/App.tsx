import { useEffect, useMemo, useState } from 'react';
import { catalogApi, type CatalogApi } from './api/client';
import type { EntityDisplayMode, GraphResponse, TableModel } from './api/types';
import { emptyMessage, entityCounts, filterGraph } from './graph/entityFilter';
import { ErdCanvas, type CanvasDisplayState } from './components/ErdCanvas';
import { InspectorPanel } from './components/InspectorPanel';
import { CatalogSelector, type CatalogSelection } from './components/CatalogSelector';
import { StatusBanner } from './components/StatusBanner';
import { ThemeControl } from './components/ThemeControl';
import './styles.css';

export type AppProps = { api?: CatalogApi };
const emptyDisplayState: CanvasDisplayState = {
  hiddenEntityIds: new Set<string>(), disabled: true,
  onRestoreTable: () => undefined, onRestoreAll: () => undefined,
  onCollapseAll: () => undefined, onExpandAll: () => undefined, onRelayout: () => undefined,
};

export function App({ api = catalogApi }: AppProps) {
  const [selection, setSelection] = useState<CatalogSelection>({ service: null, database: null, schema: null });
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loadedSchemaId, setLoadedSchemaId] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<TableModel | null>(null);
  const [displayState, setDisplayState] = useState<CanvasDisplayState | null>(null);
  const [displayMode, setDisplayMode] = useState<EntityDisplayMode>('tables');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const schemaId = selection.schema?.id;
  const renderedGraph = useMemo(() => graph ? filterGraph(graph, displayMode) : null, [graph, displayMode]);
  const inspectedTable = renderedGraph?.tables.find((table) => table.id === selectedTable?.id) ?? null;
  const counts = graph ? entityCounts(graph) : { tables: 0, views: 0 };

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
      setDisplayMode('tables');
      return;
    }

    const request = new AbortController();
    setLoading(true);
    setError(null);
    api.getGraph(schemaId, false, request.signal)
      .then((result) => {
        if (!request.signal.aborted) {
          if (loadedSchemaId !== schemaId) {
            setSelectedTable(null);
            setDisplayState(null);
          }
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

  function changeDisplayMode(mode: EntityDisplayMode) {
    setSelectedTable(null);
    setDisplayState(null);
    setDisplayMode(mode);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">OpenMetadata</p>
          <h1>Schema explorer</h1>
        </div>
        <div className="header-controls">
          <CatalogSelector api={api} onSelectionChange={setSelection} />
          <ThemeControl />
        </div>
      </header>
      <StatusBanner loading={loading} error={error} source={graph?.source ?? null} notices={graph?.notices ?? []} warnings={graph?.warnings ?? []} />
      <main className="app-content">
        <section className="diagram-shell" aria-label="Diagram">
          {graph ? (
            <>
              <div className="diagram-heading"><h2>{graph.schema.name} diagram</h2>
                <p>{counts.tables} tables · {counts.views} views · {renderedGraph?.relationships.length ?? 0} relationships</p></div>
              {renderedGraph?.tables.length === 0 && <div className="empty-state"><p>{emptyMessage(displayMode)}</p></div>}
              {renderedGraph && renderedGraph.tables.length > 0 && <ErdCanvas key={`${loadedSchemaId ?? graph.schema.id}:${displayMode}`} graph={renderedGraph} onSelectedTableChange={setSelectedTable} onDisplayStateChange={setDisplayState} />}
            </>
          ) : (
            <div className="empty-state"><p className="eyebrow">Explore your catalog</p><h2>Every relationship, in view.</h2><p>Select a service, database, and schema to view its diagram.</p></div>
          )}
        </section>
        <InspectorPanel graph={graph} selectedTable={inspectedTable} displayMode={displayMode} onDisplayModeChange={changeDisplayMode} {...(displayState ?? emptyDisplayState)} />
      </main>
    </div>
  );
}
