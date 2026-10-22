import { Controls, Panel } from '@xyflow/react';

type CanvasControlsProps = {
  onRelayout: () => void;
  onCollapseAll: () => void;
  onExpandAll: () => void;
  onRestoreAll: () => void;
  hiddenCount: number;
  disabled?: boolean;
};

export function CanvasControls({ onRelayout, onCollapseAll, onExpandAll, onRestoreAll, hiddenCount, disabled }: CanvasControlsProps) {
  return <>
    <Controls showInteractive={false} />
    <Panel position="top-right">
      <div role="toolbar" aria-label="Diagram controls" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button disabled={disabled} onClick={onRelayout}>Relayout diagram</button>
        <button disabled={disabled} onClick={onCollapseAll}>Collapse all entities</button>
        <button disabled={disabled} onClick={onExpandAll}>Expand all entities</button>
        <button disabled={hiddenCount === 0} onClick={onRestoreAll}>Restore all entities</button>
        {hiddenCount > 0 && <span role="status">{hiddenCount} hidden</span>}
      </div>
    </Panel>
  </>;
}
