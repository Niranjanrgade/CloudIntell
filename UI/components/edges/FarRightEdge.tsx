/**
 * FarRightEdge — Custom edge routing for the iteration "No" loop.
 *
 * When validation fails, the workflow loops back from the decision node to
 * the architect supervisor.  This custom edge routes the connection along the
 * far right side of the graph (x=950) to avoid crossing through the grid of
 * domain agent nodes.  The path uses rounded corners (quadratic Bézier curves)
 * for a clean appearance.
 *
 * Styled with a red stroke and "No" label to clearly indicate the failure path.
 */
import { BaseEdge, EdgeProps } from '@xyflow/react';

export function FarRightEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  style = {},
  markerEnd,
  label,
}: EdgeProps) {
  // The X-coordinate where the edge routes along the far right of the graph.
  // Set to 950px which is to the right of all node positions (max node x is ~700).
  const farRightX = 950;
  // Radius for the quadratic Bézier curves at each corner of the path.
  const radius = 16;
  
  // Build an SVG path that:
  // 1. Starts at the source (decision node's right handle)
  // 2. Goes horizontally right to (farRightX - radius)
  // 3. Curves 90° to go upward using a quadratic Bézier (Q command)
  // 4. Goes vertically up to (targetY + radius)
  // 5. Curves 90° to go horizontally left toward the target
  // 6. Goes horizontally left to the target (architect supervisor's right handle)
  const path = `
    M ${sourceX} ${sourceY} 
    L ${farRightX - radius} ${sourceY} 
    Q ${farRightX} ${sourceY} ${farRightX} ${sourceY - radius} 
    L ${farRightX} ${targetY + radius} 
    Q ${farRightX} ${targetY} ${farRightX - radius} ${targetY} 
    L ${targetX} ${targetY}
  `;

  return (
    <>
      {/* Render the SVG path using React Flow's BaseEdge which handles
          stroke styling and the arrowhead marker at the end. */}
      <BaseEdge path={path} markerEnd={markerEnd} style={style} />
      {/* "No" label — positioned near the source handle (slightly right and above)
          to clearly indicate this is the validation-failure iteration path. */}
      {label && (
        <text
          x={sourceX + 20}
          y={sourceY - 10}
          fill="#ef4444"
          fontSize={12}
          fontWeight="bold"
        >
          {label}
        </text>
      )}
    </>
  );
}
