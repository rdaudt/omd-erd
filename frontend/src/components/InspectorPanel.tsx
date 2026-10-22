import type { EntityDisplayMode, GraphResponse, RelationshipModel, TableModel } from '../api/types';
import { entityCounts, filterGraph } from '../graph/entityFilter';

export type InspectorPanelProps = {
  graph: GraphResponse | null;
  selectedTable: TableModel | null;
  displayMode: EntityDisplayMode;
  onDisplayModeChange: (mode: EntityDisplayMode) => void;
  hiddenEntityIds: ReadonlySet<string>;
  disabled: boolean;
  onRestoreTable: (id: string) => void;
  onRestoreAll: () => void;
  onCollapseAll: () => void;
  onExpandAll: () => void;
  onRelayout: () => void;
};

const assigned = (value: string | null) => value?.trim() || 'Not assigned';

export function InspectorPanel({ graph, selectedTable, displayMode, onDisplayModeChange, hiddenEntityIds, disabled, onRestoreTable, onRestoreAll, onCollapseAll, onExpandAll, onRelayout }: InspectorPanelProps) {
  const tables = new Map(graph?.tables.map((table) => [table.id, table]) ?? []);
  const displayedGraph = graph ? filterGraph(graph, displayMode) : null;
  const hiddenEntities = displayedGraph?.tables.filter((table) => hiddenEntityIds.has(table.id)) ?? [];
  const counts = graph ? entityCounts(graph) : { tables: 0, views: 0 };
  const incoming = graph?.relationships.filter((edge) => edge.targetTableId === selectedTable?.id) ?? [];
  const outgoing = graph?.relationships.filter((edge) => edge.sourceTableId === selectedTable?.id) ?? [];

  function references(title: string, edges: RelationshipModel[]) {
    return <section className="inspector-section" aria-label={title}>
      <h3>{title} <span className="count-badge">{edges.length}</span></h3>
      {edges.length ? <ul className="reference-list">{edges.map((edge) => <li key={edge.id}>
        {tables.get(edge.sourceTableId)?.name ?? edge.sourceTableId}.{edge.sourceColumn} → {tables.get(edge.targetTableId)?.name ?? edge.targetTableId}.{edge.targetColumn}
      </li>)}</ul> : <p className="muted">None</p>}
    </section>;
  }

  return <aside className="inspector-panel" aria-label={selectedTable ? 'Selected table' : 'Diagram inspector'}>
    <div className="inspector-content" key={selectedTable?.id ?? 'overview'}>
      <p className="eyebrow">{selectedTable ? `${selectedTable.entityType === 'view' ? 'View' : 'Table'} details` : 'Workspace'}</p>
      <h2>{selectedTable?.name ?? 'Diagram overview'}</h2>
      <fieldset className="entity-mode" role="radiogroup" aria-label="Entities to display">
        <legend>Show</legend>
        {([['tables', 'Tables'], ['views', 'Views'], ['both', 'Both']] as const).map(([value, label]) => <label key={value}>
          <input type="radio" name="entity-display-mode" value={value} checked={displayMode === value} onChange={() => onDisplayModeChange(value)} />
          <span>{label}</span>
        </label>)}
      </fieldset>
      {selectedTable ? <>
        <p className="qualified-name">{selectedTable.fullyQualifiedName}</p>
        <section className="inspector-section" aria-label="Table metadata">
          <h3>Description</h3><p className="metadata-description">{assigned(selectedTable.description)}</p>
          <dl className="metadata-grid"><div><dt>Owner</dt><dd>{assigned(selectedTable.owner)}</dd></div><div><dt>Tier</dt><dd>{assigned(selectedTable.tier)}</dd></div></dl>
          <h3>Tags</h3>
          {selectedTable.tags.length ? <ul className="tag-list">{selectedTable.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul> : <p className="muted">Not assigned</p>}
        </section>
        <section className="inspector-section" aria-label="Columns">
          <h3>Columns <span className="count-badge">{selectedTable.columns.length}</span></h3>
          {selectedTable.columns.length ? <ul className="column-details">{selectedTable.columns.map((column) => <li key={column.name}>
            <div className="column-detail-heading"><strong>{column.name}</strong>
              {column.primaryKey && <span className="key-badge" role="img" aria-label="Primary key">PK</span>}
              {column.foreignKey && <span className="key-badge foreign-key" role="img" aria-label="Foreign key">FK</span>}
            </div>
            <div className="column-detail-type"><span>{column.dataType}</span><span>{column.nullable ? 'NULL' : 'NOT NULL'}</span></div>
            {column.tags?.length ? <ul className="tag-list column-tag-list" aria-label={`${column.name} tags`}>{column.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul> : null}
            <p className="muted">{assigned(column.description)}</p>
          </li>)}</ul> : <p className="muted">No columns</p>}
        </section>
        {references('Incoming references', incoming)}
        {references('Outgoing references', outgoing)}
      </> : <>
        <p className="muted">Select an entity to explore its metadata and foreign keys.</p>
        <section className="diagram-stats" aria-label="Diagram counts">
          <span>{counts.tables} {counts.tables === 1 ? 'table' : 'tables'}</span>
          <span>{counts.views} {counts.views === 1 ? 'view' : 'views'}</span>
          <span>{displayedGraph?.relationships.length ?? 0} relationships</span>
          <span>{(displayedGraph?.tables.length ?? 0) - hiddenEntities.length} visible</span>
        </section>
        <section className="inspector-section" aria-label="Display actions">
          <h3>Display</h3>
          <div className="inspector-actions">
            <button disabled={disabled} onClick={onCollapseAll}>Collapse all entities</button>
            <button disabled={disabled} onClick={onExpandAll}>Expand all entities</button>
            <button disabled={disabled} onClick={onRelayout}>Relayout diagram</button>
          </div>
        </section>
      </>}
      <section className="inspector-section" aria-label="Hidden entities">
        <h3>Hidden entities <span className="count-badge">{hiddenEntities.length}</span></h3>
        {hiddenEntities.length ? <ul className="hidden-table-list">{hiddenEntities.map((table) => <li key={table.id}><span>{table.name}</span><button aria-label={`Restore ${table.name}`} onClick={() => onRestoreTable(table.id)}>Restore</button></li>)}</ul> : <p className="muted">All entities are visible.</p>}
        <button className="restore-all" disabled={disabled || hiddenEntities.length === 0} onClick={onRestoreAll}>Restore all hidden entities</button>
      </section>
    </div>
  </aside>;
}
