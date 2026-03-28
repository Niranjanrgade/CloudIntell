/**
 * WorkflowGraph — React Flow visualization of the LangGraph agent workflow.
 *
 * Renders the full architecture generation pipeline as an interactive directed
 * graph with custom node types:
 * - **AgentNode** (purple): Supervisor, architect, validator, and synthesizer agents.
 * - **ToolNode** (dashed): Web search and RAG tools used by domain agents.
 * - **DecisionNode** (diamond): The validation success decision point.
 * - **StartEndNode** (rounded): User query start and solution response end.
 *
 * Node positions and edge definitions are driven by `lib/graph.config.ts`.
 * Node statuses (idle/active/completed) are updated in real time via the
 * `activeNodes` and `completedNodes` sets from `useRunOrchestration`.
 *
 * The `FarRightEdge` custom edge type handles the "No" iteration loop that
 * routes from the decision node back to the architect supervisor along the
 * far right side of the graph to avoid crossing other edges.
 */
'use client';

import { useMemo, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { AgentNode } from './nodes/AgentNode';
import { ToolNode } from './nodes/ToolNode';
import { DecisionNode } from './nodes/DecisionNode';
import { StartEndNode } from './nodes/StartEndNode';
import { FarRightEdge } from './edges/FarRightEdge';
import { WORKFLOW_EDGES, buildNodes } from '@/lib/graph.config';

import type { RunStatus } from '@/lib/types';

// ── Custom node type registry ────────────────────────────────────────────────
// Maps the `type` field in each React Flow node descriptor (from graph.config.ts)
// to its corresponding custom React component.  React Flow uses this mapping
// when rendering nodes — if a node has type:'agent', it renders <AgentNode>.
const nodeTypes = {
  agent: AgentNode,      // Supervisor, architect, validator, and synthesizer agents
  tool: ToolNode,        // Web search and RAG tool integrations
  decision: DecisionNode, // Diamond-shaped validation success decision point
  startEnd: StartEndNode, // Rounded pill for start (user query) and end (solution response)
};

// ── Custom edge type registry ────────────────────────────────────────────────
// The 'farRight' edge type is used for the validation failure loop that routes
// from the decision node back to the architect supervisor along the far right
// side of the canvas, avoiding overlap with the central agent grid.
const edgeTypes = {
  farRight: FarRightEdge,
};

interface WorkflowGraphProps {
  /** The active cloud provider — used to populate {provider} placeholders in node labels. */
  provider: 'AWS' | 'Azure';
  /** Set of UI node IDs that are currently executing (shown with pulse animation). */
  activeNodes?: Set<string>;
  /** Set of UI node IDs that have finished executing (shown in green). */
  completedNodes?: Set<string>;
  /** Overall run status — used to auto-mark the 'start' node as completed when running. */
  runStatus?: RunStatus;
}

export function WorkflowGraph({ provider, activeNodes, completedNodes, runStatus }: WorkflowGraphProps) {
  // Build the React Flow node objects from the static descriptors defined in
  // graph.config.ts.  The buildNodes() function substitutes {provider} in labels
  // and computes each node's status (idle/active/completed) from the active/completed sets.
  // Re-computed whenever the provider, node status sets, or run status change.
  const initialNodes = useMemo(
    () => buildNodes(provider, activeNodes, completedNodes, runStatus),
    [provider, activeNodes, completedNodes, runStatus],
  );

  // React Flow's controlled state for nodes and edges.
  // useNodesState / useEdgesState return [items, setItems, onItemsChange] tuples
  // that integrate with React Flow's internal change tracking (drag, selection, etc.).
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(WORKFLOW_EDGES);

  // Sync the controlled node state whenever the memo'd initialNodes change.
  // This ensures real-time status updates (active/completed) propagate to the canvas.
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  // Handler for user-initiated edge connections (drag from handle to handle).
  // In practice, users don't manually connect nodes in this read-only visualization,
  // but the callback satisfies React Flow's required prop for controlled edges.
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    // Outer wrapper — fills the parent container and provides the slate background
    <div className="w-full h-full bg-slate-50">
      {/* ReactFlow canvas — renders the directed graph with all nodes and edges.
          `fitView` automatically zooms/pans to show all nodes on mount.
          `fitViewOptions.padding` adds breathing room around the graph edges. */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        className="bg-slate-50"
      >
        {/* Background — subtle dot grid pattern for visual depth */}
        <Background color="#cbd5e1" gap={16} />

        {/* Controls — zoom in/out and fit-view buttons (bottom-left by default) */}
        <Controls className="bg-white shadow-md border border-slate-200 rounded-md" />

        {/* MiniMap — small overview of the full graph (bottom-right by default).
            nodeColor callback assigns distinct colors per node type so users
            can quickly identify agent (purple), tool (slate), decision (amber),
            and start/end (blue) nodes in the minimap. */}
        <MiniMap 
          nodeColor={(n) => {
            if (n.type === 'agent') return '#d8b4fe';   // Purple for agents
            if (n.type === 'tool') return '#f1f5f9';     // Light slate for tools
            if (n.type === 'decision') return '#fde68a'; // Amber for decision
            return '#bfdbfe';                             // Blue for start/end
          }}
          className="bg-white shadow-md border border-slate-200 rounded-md"
        />
      </ReactFlow>
    </div>
  );
}
