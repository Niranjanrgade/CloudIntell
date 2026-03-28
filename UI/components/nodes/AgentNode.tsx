/**
 * AgentNode — Custom React Flow node for AI agents in the workflow graph.
 *
 * Displays a rounded rectangle with the agent's label and a visual status
 * indicator.  Three status states are supported:
 * - **idle** (purple): Default state before the agent has executed.
 * - **active** (purple with pulse animation): Agent is currently executing.
 * - **completed** (green with checkmark badge): Agent has finished successfully.
 *
 * Has handles on top (target), right (target, for iteration loop edge), and
 * bottom (source) to support the workflow graph's edge routing.
 */
import { Handle, Position } from '@xyflow/react';
import type { NodeStatus } from '@/lib/types';

export function AgentNode({ data }: { data: { label: string; status?: NodeStatus } }) {
  // Default to 'idle' if no status is provided (e.g. before a run starts)
  const status: NodeStatus = data.status || 'idle';

  // Common base classes shared across all statuses — rounded card with shadow
  const baseClasses =
    'px-4 py-3 shadow-md rounded-lg min-w-[160px] max-w-[180px] text-center transition-all hover:shadow-lg relative';

  // Status-specific visual styling:
  // idle     → light purple background, thin border
  // active   → deeper purple background, thick border, pulse animation
  // completed → light green background with green border
  const statusClasses: Record<NodeStatus, string> = {
    idle: 'bg-purple-50 border border-purple-200 hover:border-purple-400',
    active:
      'bg-purple-100 border-2 border-purple-500 shadow-purple-200 shadow-lg animate-pulse',
    completed:
      'bg-green-50 border border-green-300 hover:border-green-400',
  };

  // Text color varies by status for contrast and visual feedback
  const textClasses: Record<NodeStatus, string> = {
    idle: 'text-purple-900',
    active: 'text-purple-900',
    completed: 'text-green-900',
  };

  // Handle (connector dot) color matches the node's status theme
  const handleColor: Record<NodeStatus, string> = {
    idle: 'bg-purple-500',
    active: 'bg-purple-600',
    completed: 'bg-green-500',
  };

  return (
    <div className={`${baseClasses} ${statusClasses[status]}`}>
      {/* Top handle — incoming edges from parent nodes (e.g. supervisor → architect) */}
      <Handle type="target" position={Position.Top} className={`w-2 h-2 ${handleColor[status]}`} />
      {/* Right handle — target for the iteration loop edge (decision → architect_supervisor).
          Uses a named id='right' so the FarRightEdge can specifically target this handle. */}
      <Handle type="target" position={Position.Right} id="right" className={`w-2 h-2 ${handleColor[status]}`} />
      {/* Agent label — supports multi-line text via whitespace-pre-line (e.g. "AWS Compute\nGenerator Agent") */}
      <div className={`text-sm font-semibold whitespace-pre-line leading-tight ${textClasses[status]}`}>
        {data.label}
      </div>
      {/* Completion checkmark badge — small green circle with a white check SVG,
          positioned at the top-right corner of the node card */}
      {status === 'completed' && (
        <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}
      {/* Bottom handle — outgoing edges to child nodes */}
      <Handle type="source" position={Position.Bottom} className={`w-2 h-2 ${handleColor[status]}`} />
    </div>
  );
}
