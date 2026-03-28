/**
 * Home Page — Main layout for the CloudyIntel application.
 *
 * This is the root page component that assembles the three-panel layout:
 *
 * 1. **SidebarNavigator** (left): Navigation between AWS, Azure, and Compare views.
 * 2. **Main content area** (center): Either a WorkflowGraph (for AWS/Azure views)
 *    or a CompareView (for comparison mode).
 * 3. **CopilotSidebar** (right or bottom): Chat interface for submitting
 *    architecture problems and viewing real-time agent status updates.
 *
 * The `useRunOrchestration` hook manages all run state (status, active/completed
 * nodes, messages, architecture results) and is shared across all child components.
 *
 * In Compare mode, the layout switches from a horizontal split (graph + sidebar)
 * to a vertical split (comparison + bottom chat) for better use of screen space.
 */
'use client';

import { useState } from 'react';
import { CopilotSidebar, ViewMode } from '@/components/CopilotSidebar';
import { CompareView } from '@/components/CompareView';
import { DebateView } from '@/components/DebateView';
import { SidebarNavigator } from '@/components/SidebarNavigator';
import { WorkflowGraph } from '@/components/WorkflowGraph';
import { ArchitectureFullView } from '@/components/ArchitectureFullView';
import { useRunOrchestration } from '@/hooks/useRunOrchestration';

export default function Home() {
  // ── Local UI state ────────────────────────────────────────────────────────
  // `viewMode` tracks which view the user has selected in the left sidebar:
  // 'AWS' | 'Azure' → shows the React Flow graph, 'Compare' → side-by-side
  // report, 'Debate' → AWS vs Azure debate view.
  const [viewMode, setViewMode] = useState<ViewMode>('AWS');

  // Controls whether to show the full architecture report overlay instead of
  // the React Flow graph (only applicable in single-provider AWS/Azure mode).
  const [showFullReport, setShowFullReport] = useState(false);

  // ── Run orchestration hook ────────────────────────────────────────────────
  // `useRunOrchestration` is the central hook that manages the entire
  // LangGraph run lifecycle.  It returns:
  //   - runStatus: 'idle' | 'running' | 'completed' | 'error'
  //   - activeNodes / completedNodes: Sets<string> for graph node highlighting
  //   - messages / setMessages: Chat message array for the CopilotSidebar
  //   - architectureResult: Final architecture state from the backend
  //   - awsResult / azureResult: Per-provider results for Compare view
  //   - debateResult / debatePhase: Debate mode state
  //   - startRun: Callback to kick off a new architecture generation run
  const {
    runStatus,
    activeNodes,
    completedNodes,
    messages,
    setMessages,
    architectureResult,
    awsResult,
    azureResult,
    debateResult,
    debatePhase,
    startRun,
  } = useRunOrchestration();

  return (
    // Root container: full-screen horizontal flex layout
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">

      {/* ── Left Sidebar Navigator ─────────────────────────────────────────
           Fixed-width dark sidebar with nav buttons for AWS, Azure, Compare,
           and Debate modes.  Passes viewMode and setter to allow switching. */}
      <SidebarNavigator viewMode={viewMode} setViewMode={setViewMode} />

      {/* ── Main Content Area ──────────────────────────────────────────────
           Layout direction changes based on view mode:
           - Compare / Debate → flex-col (content on top, chat on bottom)
           - AWS / Azure → flex-row (graph on left, chat sidebar on right)  */}
      <main
        className={`flex flex-1 overflow-hidden ${viewMode === 'Compare' || viewMode === 'Debate' ? 'flex-col' : 'flex-row'}`}
      >
        {/* ── Debate View ────────────────────────────────────────────────
             Displays the multi-round debate between AWS and Azure advocates.
             The CopilotSidebar is shown as a bottom bar in this mode. */}
        {viewMode === 'Debate' ? (
          <>
            <div className="flex-1 relative overflow-hidden flex flex-col">
              {/* View header — static title and description for the Debate panel */}
              <div className="p-6 pb-0 z-10 bg-slate-50">
                <h2 className="text-2xl font-bold text-slate-800">
                  Debate Mode
                </h2>
                <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                  AWS and Azure advocates debate the merits of their platform
                  for your architecture problem.
                </p>
              </div>
              {/* DebateView renders collapsible summaries, debate round cards,
                  and the judge's verdict.  It receives the debate results from
                  the orchestration hook and the current phase for animations. */}
              <DebateView
                userProblem={debateResult ? undefined : undefined}
                awsSummary={debateResult?.awsSummary}
                azureSummary={debateResult?.azureSummary}
                debateRounds={debateResult?.rounds}
                debateSummary={debateResult?.summary}
                isRunning={runStatus === 'running'}
                debatePhase={debatePhase}
              />
            </div>
            {/* Bottom chat bar — allows the user to submit problems while
                viewing debate results above */}
            <CopilotSidebar
              provider={viewMode}
              variant="bottom"
              onRunStart={startRun}
              runStatus={runStatus}
              messages={messages}
              setMessages={setMessages}
            />
          </>
        ) : viewMode === 'Compare' ? (
          /* ── Compare View ──────────────────────────────────────────────
               Renders AWS and Azure architecture reports side-by-side using
               ReactMarkdown.  Also uses a bottom chat bar layout. */
          <>
            <div className="flex-1 relative overflow-hidden flex flex-col">
              {/* View header — static title for the comparison panel */}
              <div className="p-6 pb-0 z-10 bg-slate-50">
                <h2 className="text-2xl font-bold text-slate-800">
                  Compare Solutions
                </h2>
                <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                  Side-by-side comparison of the proposed AWS and Azure
                  architectures.
                </p>
              </div>
              {/* CompareView reads from awsResult and azureResult to display
                  the full markdown architecture_summary for each provider. */}
              <CompareView awsResult={awsResult} azureResult={azureResult} />
            </div>
            {/* Bottom chat bar for Compare mode */}
            <CopilotSidebar
              provider={viewMode}
              variant="bottom"
              onRunStart={startRun}
              runStatus={runStatus}
              messages={messages}
              setMessages={setMessages}
            />
          </>
        ) : (
          /* ── Single Provider View (AWS / Azure) ────────────────────────
               Two-panel horizontal layout:
               Left:  React Flow graph OR full architecture report overlay
               Right: CopilotSidebar (chat interface) */
          <>
            {/* Conditionally show the full report overlay or the React Flow graph.
                The report is shown when the user clicks "View Full Architecture Report"
                in the sidebar after a run completes. */}
            {showFullReport && architectureResult ? (
              // Full-screen architecture report rendered as styled markdown
              <ArchitectureFullView
                result={architectureResult}
                onBack={() => setShowFullReport(false)}
              />
            ) : (
              <div className="flex-1 h-full relative flex flex-col">
                {/* Header Overlay — floats on top of the React Flow canvas.
                    pointer-events-none ensures graph interactions pass through. */}
                <div className="absolute top-0 left-0 right-0 p-6 z-10 pointer-events-none">
                  <h2 className="text-2xl font-bold text-slate-800">
                    {viewMode} Architecture
                  </h2>
                  <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                    An agentic AI framework using LangGraph to automate and
                    validate complex cloud architectures via a recursive
                    Evaluator-Optimizer pattern.
                  </p>
                </div>

                {/* React Flow Graph — interactive visualization of the LangGraph
                    agent pipeline.  Nodes light up in real time as the backend
                    graph executes (active = pulsing purple, completed = green). */}
                <div className="w-full h-full">
                  <WorkflowGraph
                    provider={viewMode}
                    activeNodes={activeNodes}
                    completedNodes={completedNodes}
                    runStatus={runStatus}
                  />
                </div>
              </div>
            )}

            {/* Right Sidebar — CopilotSidebar in 'sidebar' variant (full height).
                In single-provider mode, it also shows the "View Full Report" button
                after a run completes, and passes the architectureResult for context. */}
            <CopilotSidebar
              provider={viewMode}
              variant="sidebar"
              onRunStart={startRun}
              runStatus={runStatus}
              messages={messages}
              setMessages={setMessages}
              architectureResult={architectureResult}
              onViewFullReport={() => setShowFullReport(true)}
            />
          </>
        )}
      </main>
    </div>
  );
}
