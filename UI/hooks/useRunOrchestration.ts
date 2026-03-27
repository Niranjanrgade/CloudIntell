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

const WELCOME_MESSAGE: ChatMessage = {
  id: 1,
  role: 'assistant',
  content:
    'Hello! I am CloudyIntel, your agentic AI assistant for Cloud Solution Architects. I use LangGraph to automate and validate complex cloud architectures. What would you like to build today?',
};

export function useRunOrchestration() {
  const [runStatus, setRunStatus] = useState<RunStatus>('idle');
  const [activeNodes, setActiveNodes] = useState<Set<string>>(new Set());
  const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [architectureResult, setArchitectureResult] =
    useState<ArchitectureState | null>(null);
  const [awsResult, setAwsResult] = useState<ArchitectureState | null>(null);
  const [azureResult, setAzureResult] = useState<ArchitectureState | null>(null);
  const [debateResult, setDebateResult] = useState<{
    rounds: DebateRound[];
    summary: string | null;
    awsSummary: string | null;
    azureSummary: string | null;
  } | null>(null);
  const [debatePhase, setDebatePhase] = useState<string>('idle');
  const threadIdRef = useRef<string | null>(null);
  const msgIdRef = useRef(100);
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Clean up pending timeouts on unmount
  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach(clearTimeout);
    };
  }, []);

  const runSingleProvider = useCallback(
    async (
      userProblem: string,
      cloudProvider: string,
      threadId: string,
    ): Promise<ArchitectureState | null> => {
      // Start streaming run for a single provider
      const streamRes = await fetch('/api/runs/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: threadId,
          user_problem: userProblem,
          cloud_provider: cloudProvider,
        }),
      });
      if (!streamRes.ok || !streamRes.body)
        throw new Error(`Failed to start streaming run for ${cloudProvider.toUpperCase()}`);

      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let lastArchState: ArchitectureState | null = null;

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
          try {
            parsed = JSON.parse(trimmed);
          } catch {
            continue;
          }

          if (parsed.event === 'error') {
            const errData = parsed.data as { message?: string };
            throw new Error(errData.message || 'Stream error');
          }

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
              const uiNodeId = BACKEND_TO_UI_NODE[nodeName];
              const label = NODE_LABELS[nodeName] || nodeName;

              if (uiNodeId) {
                setActiveNodes((prev) => {
                  const next = new Set(prev);
                  next.add(uiNodeId);
                  return next;
                });

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
                timeoutIdsRef.current.push(tid);
              }

              setMessages((prev) => [
                ...prev,
                {
                  id: ++msgIdRef.current,
                  role: 'status',
                  content: `[${cloudProvider.toUpperCase()}] ${label}`,
                },
              ]);

              const nodeState = updates[nodeName];
              lastArchState = { ...(lastArchState ?? {}), ...nodeState };
            }
          }
        }
      }

      // Fetch final state
      const stateRes = await fetch(`/api/threads/${threadId}/state`);
      if (stateRes.ok) {
        const fullState = await stateRes.json();
        const values = (fullState.values || fullState) as ArchitectureState;
        lastArchState = values;
      }

      return lastArchState;
    },
    [],
  );

  const startRun = useCallback(async (userProblem: string, provider: string = 'AWS') => {
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userProblem,
    };
    setMessages((prev) => [...prev, userMsg]);
    setRunStatus('running');
    setActiveNodes(new Set());
    setCompletedNodes(new Set());
    setAwsResult(null);
    setAzureResult(null);
    setDebateResult(null);
    setDebatePhase('idle');
    timeoutIdsRef.current.forEach(clearTimeout);
    timeoutIdsRef.current = [];

    const isCompare = provider === 'Compare';
    const isDebate = provider === 'Debate';

    try {
      if (isDebate) {
        // ── Debate mode: 3-phase flow ──────────────────────────────
        setDebatePhase('generating');

        // Phase A: Run AWS and Azure in parallel
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

        const [awsSettled, azureSettled] = await Promise.allSettled([
          runSingleProvider(userProblem, 'aws', awsThreadId),
          runSingleProvider(userProblem, 'azure', azureThreadId),
        ]);

        const awsState = awsSettled.status === 'fulfilled' ? awsSettled.value : null;
        const azureState = azureSettled.status === 'fulfilled' ? azureSettled.value : null;

        if (awsState) { setAwsResult(awsState); setArchitectureResult(awsState); }
        if (azureState) setAzureResult(azureState);

        // Check both succeeded before debating
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

        // Phase B: Start debate
        setDebatePhase('debating');
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.3,
            role: 'assistant',
            content: 'Phase 2: Both architectures generated. Starting AWS vs Azure debate…',
          },
        ]);

        const debateThreadRes = await fetch('/api/threads', { method: 'POST' });
        if (!debateThreadRes.ok) throw new Error('Failed to create debate thread');
        const { thread_id: debateThreadId } = await debateThreadRes.json();

        // Phase C: Stream the debate graph
        const debateStreamRes = await fetch('/api/runs/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id: debateThreadId,
            user_problem: userProblem,
            cloud_provider: 'debate',
            aws_architecture_summary: awsState.architecture_summary,
            azure_architecture_summary: azureState.architecture_summary,
          }),
        });

        if (!debateStreamRes.ok || !debateStreamRes.body)
          throw new Error('Failed to start debate streaming run');

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

                // Track when judge is running
                if (nodeName === 'debate_judge') setDebatePhase('judging');
              }
            }
          }
        }

        // Fetch final debate state
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
        // ── Compare mode: run AWS and Azure in parallel ────────────
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

        // Run both providers concurrently
        const [awsSettled, azureSettled] = await Promise.allSettled([
          runSingleProvider(userProblem, 'aws', awsThreadId),
          runSingleProvider(userProblem, 'azure', azureThreadId),
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
        // ── Single-provider mode ───────────────────────────────────
        const threadRes = await fetch('/api/threads', { method: 'POST' });
        if (!threadRes.ok) throw new Error('Failed to create thread');
        const { thread_id } = await threadRes.json();
        threadIdRef.current = thread_id;

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 0.1,
            role: 'assistant',
            content: `Thread ID: ${thread_id} — use this to trace the run in LangSmith.`,
          },
        ]);

        const cloudProvider = provider.toLowerCase();
        const result = await runSingleProvider(userProblem, cloudProvider, thread_id);
        setArchitectureResult(result);

        // Also populate the provider-specific result for Compare view
        if (cloudProvider === 'aws') setAwsResult(result);
        else if (cloudProvider === 'azure') setAzureResult(result);

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
