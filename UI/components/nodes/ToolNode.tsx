/**
 * ToolNode — Custom React Flow node for tool integrations (web search, RAG).
 *
 * Rendered as a rounded pill shape with a dashed border to visually
 * distinguish tools from agent nodes.  Domain architects connect to the
 * web_search tool node, and domain validators connect to the RAG tool node.
 * These connections are shown as dashed, animated edges in the graph.
 */
import { Handle, Position } from '@xyflow/react';

export function ToolNode({ data }: { data: any }) {
  return (
    // Pill-shaped node with a dashed border to visually distinguish tools from agents.
    // The dashed border communicates that these are external tool integrations rather
    // than AI agents owned by the system.
    <div className="px-4 py-2 shadow-sm rounded-full bg-white border-2 border-dashed border-gray-300 min-w-[140px] text-center transition-all hover:border-gray-500">
      {/* Top handle — receives dashed/animated edges from domain agents that call this tool */}
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-gray-400" />
      {/* Tool label — e.g. "Web search" or "RAG: AWS\nDocumentation" */}
      <div className="text-xs font-medium text-gray-600 whitespace-pre-line">{data.label}</div>
      {/* Bottom handle — source for outgoing connections (not actively used in the current layout
          but included for potential future edge routing) */}
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 bg-gray-400" />
    </div>
  );
}
