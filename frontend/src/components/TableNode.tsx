import { useEffect } from 'react';
import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import { COLUMN_HEIGHT, HEADER_HEIGHT, TABLE_WIDTH, columnPortId, columnPortTop, type TableFlowNode } from '../graph/layout';

export function TableNode({ id, data, selected }: NodeProps<TableFlowNode>) {
  const { table, collapsed, related, onSelect, onToggleCollapsed, onHide } = data;
  const entityLabel = table.entityType === 'view' ? 'view' : 'table';
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [id, collapsed, table.columns, updateNodeInternals]);

  return (
    <article className={`table-node${selected ? ' is-selected' : ''}${related ? ' is-related' : ''}`}
      aria-label={`${table.name} ${entityLabel}, ${collapsed ? 'collapsed' : 'expanded'}`}
      style={{ width: TABLE_WIDTH }}>
      <div className="table-node-header" style={{ height: HEADER_HEIGHT }}>
        <button className="nodrag table-name" aria-label={`Select ${table.name}`} aria-pressed={selected} onClick={(event) => { event.stopPropagation(); onSelect?.(id); }} title={table.fullyQualifiedName}>{table.name}</button>
        {table.entityType === 'view' && <span className="entity-type-badge">VIEW</span>}
        {collapsed && <span className="table-count">{table.columns.length} cols</span>}
        <button className="nodrag table-action" aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${table.name}`} aria-expanded={!collapsed} onClick={(event) => { event.stopPropagation(); onToggleCollapsed?.(id); }}>{collapsed ? '+' : '−'}</button>
        <button className="nodrag table-action" aria-label={`Hide ${table.name}`} onClick={(event) => { event.stopPropagation(); onHide?.(id); }}>×</button>
      </div>
      {!collapsed && <div role="list" aria-label={`${table.name} columns`}>
        {table.columns.map((column) => <div className="table-column" role="listitem" key={column.name} style={{ height: COLUMN_HEIGHT }}>
          {column.primaryKey && <span className="key-badge" role="img" aria-label="Primary key" title="Primary key">PK</span>}
          {column.foreignKey && <span className="key-badge foreign-key" role="img" aria-label="Foreign key" title="Foreign key">FK</span>}
          <span className="column-name" title={column.name}>{column.name}</span>
          <span className="column-type" title={column.dataType}>{column.dataType}</span><span className="column-nullability">{column.nullable ? 'NULL' : 'NOT NULL'}</span>
        </div>)}
      </div>}
      {table.columns.flatMap((column, index) => (['source', 'target'] as const).map((side) => (
        <Handle key={columnPortId(id, column.name, side)} id={columnPortId(id, column.name, side)} type={side}
          position={side === 'source' ? Position.Right : Position.Left} isConnectable={false}
          style={{ top: columnPortTop(index, collapsed), width: 5, height: 5, pointerEvents: 'none' }} />
      )))}
    </article>
  );
}
