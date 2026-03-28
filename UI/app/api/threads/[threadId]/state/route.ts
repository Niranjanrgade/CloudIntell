/**
 * GET /api/threads/[threadId]/state — Fetch the final graph state.
 *
 * After a streaming run completes, the frontend calls this endpoint to retrieve
 * the complete final state from LangGraph.  This state contains the full
 * architecture result including:
 * - `architecture_components`: Per-domain component designs.
 * - `architecture_summary`: Polished final architecture document.
 * - `final_architecture`: Complete architecture artifact dict.
 * - `validation_summary`: Consolidated validation feedback.
 *
 * The state is used to populate the CompareView and display final results.
 */
import { NextRequest, NextResponse } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ threadId: string }> },
) {
  try {
    // Extract the dynamic route segment — `threadId` is resolved from the URL
    // e.g. /api/threads/abc-123/state → threadId = 'abc-123'.
    // Next.js 15 wraps dynamic params in a Promise.
    const { threadId } = await params;

    // Fetch the complete graph state from the LangGraph backend.
    // This includes all accumulated fields (architecture_components,
    // final_architecture, validation_summary, etc.).
    const client = getLanggraphClient();
    const state = await client.threads.getState(threadId);
    return NextResponse.json(state);
  } catch (error: unknown) {
    // 502 indicates the LangGraph backend could not be reached.
    const message = error instanceof Error ? error.message : 'Failed to fetch state';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
