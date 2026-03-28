/**
 * useIaCGeneration — Hook for managing on-demand IaC generation lifecycle.
 *
 * This hook mirrors the SSE streaming pattern from `useRunOrchestration` but
 * targets the IaC generation graph (`/api/iac/stream`).  It is invoked after
 * the user views the architecture report and chooses to generate IaC code.
 *
 * Flow:
 * 1. Create a new LangGraph thread via `/api/threads`.
 * 2. Stream the IaC generation via `/api/iac/stream` with the architecture
 *    summary and selected format.
 * 3. Parse SSE events for progress tracking.
 * 4. Fetch the final state to get the merged IaC output.
 */

'use client';

import { useState, useCallback } from 'react';
import type { IaCFormat, IaCStatus, ArchitectureState } from '@/lib/types';


export function useIaCGeneration() {
  const [iacStatus, setIacStatus] = useState<IaCStatus>('idle');
  const [iacOutput, setIacOutput] = useState<string | null>(null);
  const [iacFormat, setIacFormat] = useState<IaCFormat | null>(null);
  const [iacError, setIacError] = useState<string | null>(null);
  const [iacProgress, setIacProgress] = useState<string[]>([]);

  const generateIaC = useCallback(
    async (
      architectureSummary: string,
      format: IaCFormat,
      cloudProvider: string,
      modelOverrides?: { reasoning_model?: string; execution_model?: string },
    ) => {
      setIacStatus('generating');
      setIacOutput(null);
      setIacError(null);
      setIacFormat(format);
      setIacProgress([]);

      try {
        // 1. Create a new thread for the IaC run
        const threadRes = await fetch('/api/threads', { method: 'POST' });
        if (!threadRes.ok) throw new Error('Failed to create IaC thread');
        const { thread_id } = await threadRes.json();

        setIacProgress((prev) => [...prev, 'Thread created, starting IaC generation…']);

        // 2. Start the SSE stream
        const streamRes = await fetch('/api/iac/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id,
            architecture_summary: architectureSummary,
            iac_format: format,
            cloud_provider: cloudProvider.toLowerCase(),
            ...(modelOverrides?.reasoning_model && { reasoning_model: modelOverrides.reasoning_model }),
            ...(modelOverrides?.execution_model && { execution_model: modelOverrides.execution_model }),
          }),
        });

        if (!streamRes.ok || !streamRes.body) throw new Error('Failed to start IaC streaming run');

        // 3. Process SSE events
        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // Map backend node names to human-readable labels for progress
        const NODE_LABELS: Record<string, string> = {
          iac_supervisor: 'IaC Supervisor — planning',
          compute_iac_generator: 'Compute IaC — generating',
          network_iac_generator: 'Network IaC — generating',
          storage_iac_generator: 'Storage IaC — generating',
          database_iac_generator: 'Database IaC — generating',
          iac_synthesizer: 'IaC Synthesizer — merging code',
        };

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
              throw new Error(errData.message || 'IaC stream error');
            }

            if (parsed.event === 'updates' && parsed.data && typeof parsed.data === 'object') {
              const updates = parsed.data as Record<string, Partial<ArchitectureState>>;
              for (const nodeName of Object.keys(updates)) {
                const label = NODE_LABELS[nodeName] || nodeName;
                setIacProgress((prev) => [...prev, label]);
              }
            }
          }
        }

        // 4. Fetch the final state
        const stateRes = await fetch(`/api/threads/${thread_id}/state`);
        if (stateRes.ok) {
          const fullState = await stateRes.json();
          const values = (fullState.values || fullState) as ArchitectureState;
          setIacOutput(values.iac_output || null);
        }

        setIacStatus('completed');
        setIacProgress((prev) => [...prev, 'IaC generation complete!']);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'IaC generation failed';
        setIacError(msg);
        setIacStatus('error');
        setIacProgress((prev) => [...prev, `Error: ${msg}`]);
      }
    },
    [],
  );

  const resetIaC = useCallback(() => {
    setIacStatus('idle');
    setIacOutput(null);
    setIacFormat(null);
    setIacError(null);
    setIacProgress([]);
  }, []);

  return {
    iacStatus,
    iacOutput,
    iacFormat,
    iacError,
    iacProgress,
    generateIaC,
    resetIaC,
  };
}
