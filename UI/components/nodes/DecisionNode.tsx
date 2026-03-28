/**
 * DecisionNode — Diamond-shaped decision node for validation routing.
 *
 * Represents the "Validation Success?" decision point in the workflow graph.
 * Rendered as a rotated square (diamond shape) with:
 * - Top handle (target): Receives edge from the validation reducer.
 * - Bottom handle ("yes"): Green, routes to the end node when validation passes.
 * - Right handle ("no"): Red, routes back to architect supervisor for re-iteration.
 */
import { Handle, Position } from '@xyflow/react';

export function DecisionNode({ data }: { data: any }) {
  return (
    // Outer container sized as a 24x24 box; the diamond shape is created
    // by rotating the inner div 45 degrees.
    <div className="w-24 h-24 relative flex items-center justify-center group">
      {/* Diamond background — a square rotated 45° to form a diamond shape.
          The amber color scheme distinguishes this from agent and tool nodes. */}
      <div className="absolute inset-0 bg-amber-50 border-2 border-amber-300 transform rotate-45 rounded-sm transition-all group-hover:border-amber-500 shadow-sm"></div>
      {/* Label text — positioned with z-10 so it appears above the rotated diamond.
          Uses very small text (10px) to fit inside the diamond shape. */}
      <div className="relative z-10 text-[10px] font-bold text-amber-900 text-center px-2 leading-tight">{data.label}</div>
      {/* Top handle — receives the edge from the validation reducer */}
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-amber-500" />
      {/* Bottom handle (id='yes') — green, routes to the end node on validation success */}
      <Handle type="source" position={Position.Bottom} id="yes" className="w-2 h-2 bg-green-500" />
      {/* Right handle (id='no') — red, routes back to architect supervisor for re-iteration */}
      <Handle type="source" position={Position.Right} id="no" className="w-2 h-2 bg-red-500" />
    </div>
  );
}
