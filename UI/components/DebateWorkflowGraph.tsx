/**
 * DebateWorkflowGraph — React Flow visualization of the debate agent workflow.
 *
 * Renders the debate pipeline as an interactive directed graph with:
 * - **Start/End nodes**: User problem input and final verdict output.
 * - **Agent nodes**: Debate setup, AWS/Azure advocates, round synthesizer, and judge.
 * - **Decision node**: "More Rounds?" routing point for iteration.
 * - **FarRightEdge**: Custom edge for the "Continue" iteration loop.
 *
 * Node positions and edge definitions are driven by `lib/debate-graph.config.ts`.
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
import { DEBATE_EDGES, buildDebateNodes } from '@/lib/debate-graph.config';

import type { RunStatus } from '@/lib/types';

const nodeTypes = {
  agent: AgentNode,
  tool: ToolNode,
  decision: DecisionNode,
  startEnd: StartEndNode,
};

const edgeTypes = {
  farRight: FarRightEdge,
};

interface DebateWorkflowGraphProps {
  activeNodes?: Set<string>;
  completedNodes?: Set<string>;
  runStatus?: RunStatus;
}

export function DebateWorkflowGraph({ activeNodes, completedNodes, runStatus }: DebateWorkflowGraphProps) {
  const initialNodes = useMemo(
    () => buildDebateNodes(activeNodes, completedNodes, runStatus),
    [activeNodes, completedNodes, runStatus],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(DEBATE_EDGES);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="w-full h-full bg-slate-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        className="bg-slate-50"
      >
        <Background color="#cbd5e1" gap={16} />
        <Controls className="bg-white shadow-md border border-slate-200 rounded-md" />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === 'agent') return '#d8b4fe';
            if (n.type === 'decision') return '#fde68a';
            return '#bfdbfe';
          }}
          className="bg-white shadow-md border border-slate-200 rounded-md"
        />
      </ReactFlow>
    </div>
  );
}
