import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react';
import type { RelationshipFlowEdge } from '../graph/layout';

export function RelationshipEdge({ id, data, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd, style }: EdgeProps<RelationshipFlowEdge>) {
  const [path] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 8 });
  return <g role="img" aria-label={data?.label}>
    <title>{data?.label}</title>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} interactionWidth={20} />
  </g>;
}
