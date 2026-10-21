import { useEffect } from 'react';
import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import { COLUMN_HEIGHT, HEADER_HEIGHT, TABLE_WIDTH, columnPortId, columnPortTop, type TableFlowNode } from '../graph/layout';

export function TableNode({ id, data, selected }: NodeProps<TableFlowNode>) {
  const { table, collapsed, related, onSelect, onToggleCollapsed, onHide } = data;
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [id, collapsed, table.columns, updateNodeInternals]);

  return (
    <article className={`table-node${selected ? ' is-selected' : ''}${related ? ' is-related' : ''}`}
      aria-label={`${table.name} table, ${collapsed ? 'collapsed' : 'expanded'}`}
      style={{ width: TABLE_WIDTH, background: 'white', border: `1px solid ${selected ? '#2563eb' : related ? '#60a5fa' : '#94a3b8'}`, borderRadius: 6, boxSizing: 'border-box' }}>
      <div className="table-node-header" style={{ height: HEADER_HEIGHT, display: 'flex', alignItems: 'center', gap: 4, padding: '0 8px', boxSizing: 'border-box', cursor: 'grab' }}>
        <button className="nodrag" aria-label={`Select ${table.name}`} aria-pressed={selected} onClick={(event) => { event.stopPropagation(); onSelect?.(id); }} style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis' }} title={table.fullyQualifiedName}>{table.name}</button>
        <button className="nodrag" aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${table.name}`} aria-expanded={!collapsed} onClick={(event) => { event.stopPropagation(); onToggleCollapsed?.(id); }}>{collapsed ? '+' : '−'}</button>
        <button className="nodrag" aria-label={`Hide ${table.name}`} onClick={(event) => { event.stopPropagation(); onHide?.(id); }}>×</button>
      </div>
      {!collapsed && <div role="list" aria-label={`${table.name} columns`}>
        {table.columns.map((column) => <div role="listitem" key={column.name} style={{ height: COLUMN_HEIGHT, display: 'flex', alignItems: 'center', gap: 6, padding: '0 8px', fontSize: 12, boxSizing: 'border-box' }}>
          {column.primaryKey && <span role="img" aria-label="Primary key" title="Primary key">🔑</span>}
          {column.foreignKey && <span role="img" aria-label="Foreign key" title="Foreign key">↗</span>}
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={column.name}>{column.name}</span>
          <span>{column.dataType}</span><span>{column.nullable ? 'NULL' : 'NOT NULL'}</span>
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
