import { render, screen } from '@testing-library/react';
import { Position } from '@xyflow/react';
import { describe, expect, it, vi } from 'vitest';
import { RelationshipEdge } from './RelationshipEdge';

vi.mock('@xyflow/react', async (importOriginal) => ({
  ...await importOriginal<typeof import('@xyflow/react')>(),
  useInternalNode: () => ({ internals: { positionAbsolute: { x: 100, y: 75 } } }),
}));

describe('self-referencing relationship geometry', () => {
  it.each([
    { state: 'expanded', sourceY: 165, targetY: 137 },
    { state: 'collapsed', sourceY: 99, targetY: 99 },
  ])('routes outside the $state table, including its header', ({ sourceY, targetY }) => {
    const label = 'Employee.manager_id references Employee.id';
    render(<svg><RelationshipEdge id="self" source="Employee" target="Employee" sourceX={380} targetX={100}
      sourceY={sourceY} targetY={targetY} sourcePosition={Position.Right} targetPosition={Position.Left}
      data={{ sourceColumn: 'manager_id', targetColumn: 'id', label }} /></svg>);
    const path = screen.getByRole('img', { name: label }).querySelector('path.react-flow__edge-path')!.getAttribute('d')!;
    expect(screen.getByText('manager_id → id', { selector: 'text' })).toBeInTheDocument();
    const points = Array.from(path.matchAll(/[ML]\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/g), (match) => ({ x: Number(match[1]), y: Number(match[2]) }));
    expect(points[0]).toEqual({ x: 380, y: sourceY });
    expect(points.at(-1)).toEqual({ x: 100, y: targetY });
    expect(Math.min(...points.map(({ y }) => y))).toBeLessThan(75);
    expect(Math.min(...points.map(({ x }) => x))).toBeLessThan(100);
    expect(Math.max(...points.map(({ x }) => x))).toBeGreaterThan(380);
    for (let index = 1; index < points.length; index++) {
      const previous = points[index - 1];
      const point = points[index];
      // Each orthogonal segment stays outside the table interior.
      expect((previous.x === point.x && (point.x <= 100 || point.x >= 380)) ||
        (previous.y === point.y && (point.y < 75 || Math.max(previous.x, point.x) <= 100 || Math.min(previous.x, point.x) >= 380))).toBe(true);
    }
  });
});
