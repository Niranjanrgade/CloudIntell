/**
 * useRunOrchestration — Central orchestration hook for the CloudyIntel UI.
 *
 * This hook manages the entire lifecycle of a cloud architecture generation run:
 *
 * 1. **Thread creation**: Creates a new LangGraph thread via the `/api/threads` endpoint.
 * 2. **LangGraph Studio**: Opens a LangGraph Studio tab for real-time run observation.
 * 3. **SSE streaming**: Initiates a streaming run via `/api/runs/stream` and processes
 *    Server-Sent Events (SSE) to update the UI in real time.
 * 4. **Node status tracking**: Maps backend node names (e.g. "architect_phase:compute_architect")
 *    to UI node IDs and manages active/completed sets for the workflow graph visualization.
 * 5. **Chat messages**: Maintains the chat history shown in the CopilotSidebar, including
 *    user messages, status updates (which node is currently executing), and assistant responses.
 * 6. **Final state fetch**: After the stream ends, fetches the complete final state from
 *    `/api/threads/{threadId}/state` to populate the CompareView with architecture results.
 *
 * The hook exposes `runStatus` (idle/running/completed/error), node status sets, messages,
 * the architecture result, and the `startRun` callback for the UI to consume.
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import type { RunStatus, ChatMessage, ArchitectureState, DebateRound } from '@/lib/types';
import { BACKEND_TO_UI_NODE, NODE_LABELS } from '@/lib/node-mapping';

// Default welcome message shown when the app first loads, before any run is started.
const WELCOME_MESSAGE: ChatMessage = {
  id: 1,
  role: 'assistant',
  content:
    'Hello! I am CloudyIntel, your agentic AI assistant for Cloud Solution Architects. I use LangGraph to automate and validate complex cloud architectures. What would you like to build today?',
};

export function useRunOrchestration() {
  // ── State declarations ──────────────────────────────────────────────────
  // Overall run lifecycle status: idle → running → completed/error
  const [runStatus, setRunStatus] = useState<RunStatus>('idle');
  // Set of UI node IDs that are currently executing (shown with pulse animation in the graph)
  const [activeNodes, setActiveNodes] = useState<Set<string>>(new Set());
  // Set of UI node IDs that have finished executing (shown in green in the graph)
  const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
  // Chat message history displayed in the CopilotSidebar
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  // Final architecture result for single-provider mode (also used as "current" result)
  const [architectureResult, setArchitectureResult] =
    useState<ArchitectureState | null>(null);
  // Per-provider results used by the CompareView for side-by-side display
  const [awsResult, setAwsResult] = useState<ArchitectureState | null>(null);
  const [azureResult, setAzureResult] = useState<ArchitectureState | null>(null);
  // Debate mode results: rounds, judge's verdict, and provider summaries
  const [debateResult, setDebateResult] = useState<{
    rounds: DebateRound[];
    summary: string | null;
    awsSummary: string | null;
    azureSummary: string | null;
  } | null>(null);
  // Tracks which debate phase is active for UI animations/labels
  const [debatePhase, setDebatePhase] = useState<string>('idle');
  // Ref to store the current thread ID (not reactive — only used for LangSmith linking)
  const threadIdRef = useRef<string | null>(null);
  // Monotonically increasing message ID counter (starts at 100 to avoid collision with welcome msg)
  const msgIdRef = useRef(100);
  // Stores setTimeout IDs so we can clear them on unmount or new run
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Clean up any pending node-status transition timeouts when the component unmounts.
  // Without this, timeouts could fire after unmount and cause state-update-on-unmounted warnings.
  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach(clearTimeout);
    };
  }, []);

  /**
   * runSingleProvider — Runs a single cloud provider pipeline and streams results.
   *
   * This function handles the full streaming lifecycle for one provider:
   * 1. POSTs to /api/runs/stream to start the LangGraph run.
   * 2. Reads the SSE stream using a ReadableStream reader.
   * 3. Parses each SSE event, extracting node names and state updates.
   * 4. Maps backend node names to UI node IDs using BACKEND_TO_UI_NODE.
   * 5. Updates activeNodes/completedNodes sets with a 600ms delay for visual effect.
   * 6. Appends status messages to the chat for each node execution.
   * 7. After the stream ends, fetches the final complete state from the backend.
   *
   * @param userProblem    The user's architecture problem description.
   * @param cloudProvider  'aws' or 'azure' — determines which LangGraph graph to invoke.
   * @param threadId       The LangGraph thread ID for this run.
   * @returns              The final ArchitectureState, or null on failure.
   */
  const runSingleProvider = useCallback(
    async (
      userProblem: string,
      cloudProvider: string,
      threadId: string,
      modelOverrides?: { reasoning_model?: string; execution_model?: string },
    ): Promise<ArchitectureState | null> => {
      // ── Step 1: Initiate the streaming run ────────────────────────────
      // POST to the Next.js API route which proxies to the LangGraph backend.
      const streamRes = await fetch('/api/runs/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: threadId,
          user_problem: userProblem,
          cloud_provider: cloudProvider,
          ...(modelOverrides?.reasoning_model && { reasoning_model: modelOverrides.reasoning_model }),
          ...(modelOverrides?.execution_model && { execution_model: modelOverrides.execution_model }),
        }),
      });
      if (!streamRes.ok || !streamRes.body)
        throw new Error(`Failed to start streaming run for ${cloudProvider.toUpperCase()}`);

      // ── Step 2: Set up SSE stream reader ──────────────────────────────
      // Use the ReadableStream API to consume the SSE response incrementally.
      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';  // Accumulates partial SSE chunks between reads
      let lastArchState: ArchitectureState | null = null;  // Running merge of all state updates

      // ── Step 3: Process SSE events ────────────────────────────────────
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;  // Stream ended

        // Decode the binary chunk and append to the buffer.
        // stream:true tells the decoder to handle multi-byte characters split across chunks.
        buffer += decoder.decode(value, { stream: true });
        // SSE events are separated by double newlines; split and keep the last partial chunk.
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';  // Last element may be incomplete — keep in buffer

        for (const line of lines) {
          // Strip the "data: " prefix that SSE format requires
          const trimmed = line.replace(/^data: /, '').trim();
          if (!trimmed || trimmed === '[DONE]') continue;  // Skip empty lines and end sentinel

          // Parse the JSON event payload
          let parsed: { event: string; data: unknown };
          try {
            parsed = JSON.parse(trimmed);
          } catch {
            continue;  // Skip malformed JSON (partial chunks, etc.)
          }

          // Handle error events from the backend stream
          if (parsed.event === 'error') {
            const errData = parsed.data as { message?: string };
            throw new Error(errData.message || 'Stream error');
          }

          // Handle "updates" events — these carry per-node state deltas.
          // The data object is keyed by backend node name (e.g. "architect_phase:compute_architect")
          // with partial ArchitectureState as the value.
          if (
            parsed.event === 'updates' &&
            parsed.data &&
            typeof parsed.data === 'object'
          ) {
            const updates = parsed.data as Record<
              string,
              Partial<ArchitectureState>
            >;
            for (const nodeName of Object.keys(updates)) {
              // Map the backend node name to a UI React Flow node ID
              const uiNodeId = BACKEND_TO_UI_NODE[nodeName];
              // Get a human-friendly label for the chat status message
              const label = NODE_LABELS[nodeName] || nodeName;

              if (uiNodeId) {
                // Mark the node as active (pulsing purple) immediately
                setActiveNodes((prev) => {
                  const next = new Set(prev);
                  next.add(uiNodeId);
                  return next;
                });

                // After a 600ms delay, transition from active → completed.
                // This creates a brief visual "flash" on the graph node before
                // it settles into the green completed state.
                const tid = setTimeout(() => {
                  setActiveNodes((prev) => {
                    const next = new Set(prev);
                    next.delete(uiNodeId);
                    return next;
                  });
                  setCompletedNodes((prev) => {
                    const next = new Set(prev);
                    next.add(uiNodeId);
                    return next;
                  });
                }, 600);
                timeoutIdsRef.current.push(tid);  // Track for cleanup
              }

              // Append a status message to the chat (e.g. "[AWS] Compute Architect — designing")
              setMessages((prev) => [
                ...prev,
                {
                  id: ++msgIdRef.current,
                  role: 'status',
                  content: `[${cloudProvider.toUpperCase()}] ${label}`,
                },
              ]);

              // Merge this node's partial state into the running cumulative state
              const nodeState = updates[nodeName];
              lastArchState = { ...(lastArchState ?? {}), ...nodeState };
            }
          }
        }
      }

      // ── Step 4: Fetch the final complete state ────────────────────────
      // The stream only sends deltas; fetch the full state for the complete picture.
      const stateRes = await fetch(`/api/threads/${threadId}/state`);
      if (stateRes.ok) {
        const fullState = await stateRes.json();
        // The response may wrap values under a "values" key or be flat
        const values = (fullState.values || fullState) as ArchitectureState;
        lastArchState = values;
      }

      return lastArchState;
    },
    [],
  );

  /**
   * startRun — Main entry point for kicking off a new architecture generation run.
   *
   * Called by the CopilotSidebar when the user submits a problem description.
   * Handles three execution modes based on the current provider view:
   *   1. Debate mode:  Generate AWS & Azure in parallel → run debate graph → judge.
   *   2. Compare mode:  Generate AWS & Azure in parallel → populate CompareView.
   *   3. Single mode:   Generate for one provider (AWS or Azure) → show results.
   *
   * @param userProblem  The user's cloud architecture problem description.
   * @param provider     'AWS' | 'Azure' | 'Compare' | 'Debate' — determines the execution mode.
   */
  const startRun = useCallback(async (
    userProblem: string,
    provider: string = 'AWS',
    modelOverrides?: { reasoning_model?: string; execution_model?: string },
  ) => {
    // Add the user's message to the chat immediately for visual feedback
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userProblem,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Reset all state for a fresh run
    setRunStatus('running');
    setActiveNodes(new Set());       // Clear graph node highlights
    setCompletedNodes(new Set());
    setAwsResult(null);              // Clear previous provider results
    setAzureResult(null);
    setDebateResult(null);
    setDebatePhase('idle');
    // Cancel any pending node-status transition timeouts from the previous run
    timeoutIdsRef.current.forEach(clearTimeout);
    timeoutIdsRef.current = [];

    // Determine which execution mode to use based on the current view
    const isCompare = provider === 'Compare';
    const isDebate = provider === 'Debate';

    try {
      if (isDebate) {
        // ── Debate mode: 3-phase flow ──────────────────────────────
        // Phase A: Run AWS and Azure pipelines in parallel to get architecture summaries.
        // Phase B: Feed both summaries into the debate graph.
        // Phase C: Stream the debate and fetch the judge's final verdict.
        setDebatePhase('generating');

        // Phase A: Run AWS and Azure in parallel
        // Phase A: Create separate LangGraph threads for AWS and Azure,
        // then run both provider pipelines concurrently using Promise.allSettled
        // (allSettled rather than all so one failure doesn't cancel the other).
        const [awsThreadRes, azureThreadRes] = await Promise.all([
          fetch('/api/threads', { method: 'POST' }),
          fetch('/api/threads', { method: 'POST' }),
        ]);
        if (!awsThreadRes.ok) throw new Error('Failed to create AWS thread');
        if (!azureThreadRes.ok) throw new Error('Failed to create Azure thread');

        const [{ thread_id: awsThreadId }, { thread_id: azureThreadId }] =
          await Promise.all([awsThreadRes.json(), azureThreadRes.json()]);

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.1,
            role: 'assistant',
            content: `Phase 1: Generating AWS and Azure architectures in parallel…`,
          },
        ]);

        // Run both providers concurrently — each calls runSingleProvider which
        // handles the full SSE streaming, node status updates, and state fetching.
        const [awsSettled, azureSettled] = await Promise.allSettled([
          runSingleProvider(userProblem, 'aws', awsThreadId, modelOverrides),
          runSingleProvider(userProblem, 'azure', azureThreadId, modelOverrides),
        ]);

        // Extract results from settled promises
        const awsState = awsSettled.status === 'fulfilled' ? awsSettled.value : null;
        const azureState = azureSettled.status === 'fulfilled' ? azureSettled.value : null;

        // Store provider results for CompareView and general display
        if (awsState) { setAwsResult(awsState); setArchitectureResult(awsState); }
        if (azureState) setAzureResult(azureState);

        // Both architecture summaries are required for the debate.
        // If either is missing, report the error and abort the debate.
        if (!awsState?.architecture_summary || !azureState?.architecture_summary) {
          const errors: string[] = [];
          if (awsSettled.status === 'rejected') errors.push(`AWS failed: ${awsSettled.reason}`);
          if (azureSettled.status === 'rejected') errors.push(`Azure failed: ${azureSettled.reason}`);
          if (!awsState?.architecture_summary) errors.push('AWS architecture summary missing.');
          if (!azureState?.architecture_summary) errors.push('Azure architecture summary missing.');
          setMessages((prev) => [
            ...prev,
            { id: Date.now() + 0.2, role: 'assistant', content: `Cannot start debate: ${errors.join(' ')}` },
          ]);
          setDebatePhase('idle');
          setRunStatus('error');
          return;
        }

        // Phase B: Transition to debate phase — create a new thread for the debate graph.
        setDebatePhase('debating');
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.3,
            role: 'assistant',
            content: 'Phase 2: Both architectures generated. Starting AWS vs Azure debate…',
          },
        ]);

        // Create a dedicated thread for the debate graph (separate from the architecture threads).
        const debateThreadRes = await fetch('/api/threads', { method: 'POST' });
        if (!debateThreadRes.ok) throw new Error('Failed to create debate thread');
        const { thread_id: debateThreadId } = await debateThreadRes.json();

        // Phase C: Stream the debate graph.
        // The debate graph receives both architecture summaries as input and
        // orchestrates multi-round arguments between AWS and Azure advocates,
        // followed by a neutral judge evaluation.
        const debateStreamRes = await fetch('/api/runs/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id: debateThreadId,
            user_problem: userProblem,
            cloud_provider: 'debate',
            aws_architecture_summary: awsState.architecture_summary,
            azure_architecture_summary: azureState.architecture_summary,
            ...(modelOverrides?.reasoning_model && { reasoning_model: modelOverrides.reasoning_model }),
            ...(modelOverrides?.execution_model && { execution_model: modelOverrides.execution_model }),
          }),
        });

        if (!debateStreamRes.ok || !debateStreamRes.body)
          throw new Error('Failed to start debate streaming run');

        // Read the debate stream using the same SSE pattern as runSingleProvider,
        // but with simpler processing (no graph node highlighting for debate nodes).
        const reader = debateStreamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.replace(/^data: /, '').trim();
            if (!trimmed || trimmed === '[DONE]') continue;

            let parsed: { event: string; data: unknown };
            try { parsed = JSON.parse(trimmed); } catch { continue; }

            if (parsed.event === 'error') {
              const errData = parsed.data as { message?: string };
              throw new Error(errData.message || 'Debate stream error');
            }

            if (parsed.event === 'updates' && parsed.data && typeof parsed.data === 'object') {
              const updates = parsed.data as Record<string, Partial<ArchitectureState>>;
              for (const nodeName of Object.keys(updates)) {
                const label = NODE_LABELS[nodeName] || nodeName;
                setMessages((prev) => [
                  ...prev,
                  { id: ++msgIdRef.current, role: 'status', content: `[DEBATE] ${label}` },
                ]);

                // When the debate_judge node starts executing, update the phase
                // so the UI can show "Judge Evaluating" in the status badge.
                if (nodeName === 'debate_judge') setDebatePhase('judging');
              }
            }
          }
        }

        // Fetch the final debate state to get the complete rounds and verdict.
        const debateStateRes = await fetch(`/api/threads/${debateThreadId}/state`);
        if (debateStateRes.ok) {
          const fullState = await debateStateRes.json();
          const values = (fullState.values || fullState) as ArchitectureState;
          setDebateResult({
            rounds: values.debate_rounds || [],
            summary: values.debate_summary || null,
            awsSummary: awsState.architecture_summary,
            azureSummary: azureState.architecture_summary,
          });
        }

        setDebatePhase('completed');
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.4,
            role: 'assistant',
            content: 'Debate completed! The judge has rendered a verdict. See the Debate view for full results.',
          },
        ]);
        setRunStatus('completed');
      } else if (isCompare) {
        // ── Compare mode: run AWS and Azure pipelines in parallel ───
        // Creates two independent threads and runs both provider graphs
        // concurrently.  Results are stored separately for the CompareView.
        const [awsThreadRes, azureThreadRes] = await Promise.all([
          fetch('/api/threads', { method: 'POST' }),
          fetch('/api/threads', { method: 'POST' }),
        ]);
        if (!awsThreadRes.ok) throw new Error('Failed to create AWS thread');
        if (!azureThreadRes.ok) throw new Error('Failed to create Azure thread');

        const [{ thread_id: awsThreadId }, { thread_id: azureThreadId }] =
          await Promise.all([awsThreadRes.json(), azureThreadRes.json()]);

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.1,
            role: 'assistant',
            content: `Starting AWS and Azure pipelines in parallel (AWS Thread: ${awsThreadId}, Azure Thread: ${azureThreadId})…`,
          },
        ]);

        // Run both provider pipelines concurrently using Promise.allSettled.
        // allSettled (not all) so a failure in one provider doesn't cancel the other.
        const [awsSettled, azureSettled] = await Promise.allSettled([
          runSingleProvider(userProblem, 'aws', awsThreadId, modelOverrides),
          runSingleProvider(userProblem, 'azure', azureThreadId, modelOverrides),
        ]);

        const awsState =
          awsSettled.status === 'fulfilled' ? awsSettled.value : null;
        const azureState =
          azureSettled.status === 'fulfilled' ? azureSettled.value : null;

        if (awsState) {
          setAwsResult(awsState);
          setArchitectureResult(awsState);
        }
        if (azureState) {
          setAzureResult(azureState);
        }

        // Report any per-provider errors
        const errors: string[] = [];
        if (awsSettled.status === 'rejected')
          errors.push(`AWS failed: ${awsSettled.reason}`);
        if (azureSettled.status === 'rejected')
          errors.push(`Azure failed: ${azureSettled.reason}`);

        if (errors.length) {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now() + 0.2,
              role: 'assistant',
              content: errors.join('\n'),
            },
          ]);
        }

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.3,
            role: 'assistant',
            content:
              awsState && azureState
                ? 'Both AWS and Azure architectures have been generated. Switch to the Compare view to see the side-by-side comparison.'
                : 'Architecture generation finished with partial results. Check errors above.',
          },
        ]);
        setRunStatus(errors.length === 2 ? 'error' : 'completed');
      } else {
        // ── Single-provider mode (AWS or Azure) ────────────────────
        // Creates one thread and runs the pipeline for the selected provider.
        // This is the default flow for the AWS and Azure views.
        const threadRes = await fetch('/api/threads', { method: 'POST' });
        if (!threadRes.ok) throw new Error('Failed to create thread');
        const { thread_id } = await threadRes.json();
        threadIdRef.current = thread_id;  // Store for potential LangSmith linking

        // Inform the user of the thread ID for run traceability in LangSmith
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.1,
            role: 'assistant',
            content: `Thread ID: ${thread_id} — use this to trace the run in LangSmith.`,
          },
        ]);

        // Run the single provider pipeline
        const cloudProvider = provider.toLowerCase();
        const result = await runSingleProvider(userProblem, cloudProvider, thread_id, modelOverrides);
        setArchitectureResult(result);

        // Also store the result under the specific provider key so it's
        // available if the user later switches to the Compare view.
        if (cloudProvider === 'aws') setAwsResult(result);
        else if (cloudProvider === 'azure') setAzureResult(result);

        // Show the architecture summary in the chat, or a generic completion message
        const summary =
          result?.architecture_summary ||
          'Architecture generation completed. Switch to the Compare view to see the results.';
        setMessages((prev) => [
          ...prev,
          { id: Date.now(), role: 'assistant', content: summary },
        ]);
        setRunStatus('completed');
      }
    } catch (err) {
      // ── Global error handler ────────────────────────────────────────
      // Catches thread creation failures, stream errors, and any other
      // unexpected exceptions.  Displays the error in the chat and sets
      // the run status to 'error' so the UI unlocks the input.
      const msg = err instanceof Error ? err.message : 'An error occurred';
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content: `Error: ${msg}. Please try again.`,
        },
      ]);
      setRunStatus('error');
    }
  }, [runSingleProvider]);

  // ── Public API ───────────────────────────────────────────────────────
  // Returns all state and callbacks needed by the UI components.
  return {
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
  };
}
