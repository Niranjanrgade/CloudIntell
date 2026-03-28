/**
 * StartEndNode — Rounded pill node for workflow start and end points.
 *
 * Used for two nodes:
 * - **Start** (blue): "User Query (AWS/Azure)" — entry point of the workflow.
 *   Only has a source handle (bottom) since nothing connects into it.
 * - **End** (emerald green): "Architect Solution Response" — final output.
 *   Only has a target handle (top) since nothing connects out of it.
 *
 * The `data.type` field ("start" or "end") controls the color scheme and
 * which handles are rendered.
 */
import { Handle, Position } from '@xyflow/react';

export function StartEndNode({ data }: { data: any }) {
  // Determine if this is the start or end node based on data.type.
  // Start nodes have data.type='start', end nodes have data.type='end'.
  const isStart = data.type === 'start';
  return (
    // Pill-shaped container with a thick border.
    // Start nodes use blue theming, end nodes use emerald green theming.
    <div className={`px-6 py-2 shadow-sm rounded-full border-2 min-w-[120px] text-center transition-all ${isStart ? 'bg-blue-50 border-blue-200 hover:border-blue-400' : 'bg-emerald-50 border-emerald-200 hover:border-emerald-400'}`}>
      {/* End nodes have a top target handle to receive the "Yes" edge from the decision node.
          Start nodes don't need a target handle since nothing connects into them. */}
      {!isStart && <Handle type="target" position={Position.Top} className={`w-2 h-2 ${isStart ? 'bg-blue-500' : 'bg-emerald-500'}`} />}
      {/* Node label — supports multi-line text (e.g. "User Query\n(AWS)") */}
      <div className={`text-sm font-bold whitespace-pre-line ${isStart ? 'text-blue-900' : 'text-emerald-900'}`}>{data.label}</div>
      {/* Start nodes have a bottom source handle for the edge to the architect supervisor.
          End nodes don't need a source handle since nothing connects out of them. */}
      {isStart && <Handle type="source" position={Position.Bottom} className={`w-2 h-2 ${isStart ? 'bg-blue-500' : 'bg-emerald-500'}`} />}
    </div>
  );
}
