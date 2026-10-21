import { BaseEdge, getSmoothStepPath, useInternalNode, type EdgeProps } from '@xyflow/react';
import type { RelationshipFlowEdge, TableFlowNode } from '../graph/layout';

export function RelationshipEdge(props: EdgeProps<RelationshipFlowEdge>) {
  if (props.source === props.target) return <SelfRelationshipEdge {...props} />;
  const [path, labelX, labelY] = getSmoothStepPath({ ...props, borderRadius: 8 });
  return <RelationshipPath {...props} path={path} labelX={labelX} labelY={labelY} />;
}

function SelfRelationshipEdge(props: EdgeProps<RelationshipFlowEdge>) {
  const node = useInternalNode<TableFlowNode>(props.source);
  if (!node) return null;
  const { sourceX, sourceY, targetX, targetY } = props;
  const clearance = 32;
  const top = node.internals.positionAbsolute.y - clearance;
  const right = Math.max(sourceX, targetX) + clearance;
  const left = Math.min(sourceX, targetX) - clearance;
  // Exit each side before crossing above the header, including when both
  // collapsed handles share the same vertical coordinate.
  const path = `M ${sourceX} ${sourceY} L ${right} ${sourceY} L ${right} ${top} L ${left} ${top} L ${left} ${targetY} L ${targetX} ${targetY}`;
  return <RelationshipPath {...props} path={path} labelX={(left + right) / 2} labelY={top} />;
}

function RelationshipPath({ id, data, markerEnd, style, path, labelX, labelY }: EdgeProps<RelationshipFlowEdge> & { path: string; labelX: number; labelY: number }) {
  return <g role="img" aria-label={data?.label}>
    <title>{data?.label}</title>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} interactionWidth={20} />
    {data && <text x={labelX} y={labelY - 7} textAnchor="middle" fontSize={10}
      fill="var(--text, #eeeaf6)" stroke="var(--canvas-bg, #131316)" strokeWidth={3} paintOrder="stroke"
      style={{ opacity: style?.opacity }}>{data.sourceColumn} → {data.targetColumn}</text>}
  </g>;
}
