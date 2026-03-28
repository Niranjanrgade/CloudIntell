/**
 * POST /api/runs/stream — Start a streaming LangGraph run.
 *
 * This API route acts as a proxy between the Next.js frontend and the LangGraph
 * backend server.  It:
 *
 * 1. Validates the request body (requires `thread_id` and `user_problem`).
 * 2. Constructs the initial graph state matching `create_initial_state()` from
 *    the Python backend (all State fields with their default values).
 * 3. Calls `client.runs.stream()` with `streamMode: ['updates']` so the frontend
 *    receives per-node state deltas rather than the full state on every update.
 * 4. Converts the LangGraph SDK's async iterator into a standard SSE ReadableStream
 *    that the browser's `fetch` API can consume.
 *
 * Each SSE event is formatted as `data: {"event": "...", "data": {...}}\n\n`.
 * The stream ends with `data: [DONE]\n\n`.
 */
import { NextRequest } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function POST(req: NextRequest) {
  try {
    // --- 1. Parse & destructure request body ---
    // Extract run configuration from the client.  Defaults match the Python
    // backend's `create_initial_state()` for non-debate runs.
    const body = await req.json();
    const {
      thread_id,
      user_problem,
      cloud_provider = 'aws',
      min_iterations = 1,
      max_iterations = 3,
      aws_architecture_summary,
      azure_architecture_summary,
      max_debate_rounds = 2,
      reasoning_model,
      execution_model,
    } = body as {
      thread_id: string;
      user_problem: string;
      cloud_provider?: string;
      min_iterations?: number;
      max_iterations?: number;
      aws_architecture_summary?: string;
      azure_architecture_summary?: string;
      max_debate_rounds?: number;
      reasoning_model?: string;
      execution_model?: string;
    };

    // --- 2. Input validation ---
    // Both fields are mandatory; without them the backend graph can't start.
    if (!thread_id || !user_problem) {
      return new Response(
        JSON.stringify({ error: 'thread_id and user_problem are required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    // --- 3. Instantiate the server-side LangGraph SDK client ---
    const client = getLanggraphClient();

    // --- 4. Determine graph variant ---
    // 'debate' mode triggers the debate graph; otherwise use the provider graph.
    const isDebate = cloud_provider === 'debate';

    // --- 5. Construct initial graph state ---
    // This object must include every field from the Python State TypedDict
    // (src/cloudy_intell/schemas/models.py) with appropriate defaults.
    // The debate graph sets iteration fields to 0 (not applicable) and
    // populates the architecture summaries from prior runs.
    const input = isDebate
      ? {
          messages: [{ role: 'human', content: user_problem }],
          user_problem,
          iteration_count: 0,
          min_iterations: 0,
          max_iterations: 0,
          architecture_domain_tasks: {},
          architecture_components: {},
          proposed_architecture: {},
          validation_feedback: [],
          validation_summary: null,
          audit_feedback: [],
          factual_errors_exist: false,
          design_flaws_exist: false,
          final_architecture: null,
          architecture_summary: null,
          aws_architecture_summary: aws_architecture_summary || null,
          azure_architecture_summary: azure_architecture_summary || null,
          debate_rounds: [],
          current_debate_round: 0,
          max_debate_rounds,
          debate_summary: null,
          reasoning_model: reasoning_model || null,
          execution_model: execution_model || null,
        }
      : {
          messages: [{ role: 'human', content: user_problem }],
          user_problem,
          iteration_count: 0,
          min_iterations,
          max_iterations,
          architecture_domain_tasks: {},
          architecture_components: {},
          proposed_architecture: {},
          validation_feedback: [],
          validation_summary: null,
          audit_feedback: [],
          factual_errors_exist: false,
          design_flaws_exist: false,
          final_architecture: null,
          architecture_summary: null,
          // Debate fields — inert defaults for non-debate runs
          aws_architecture_summary: null,
          azure_architecture_summary: null,
          debate_rounds: [],
          current_debate_round: 0,
          max_debate_rounds: 2,
          debate_summary: null,
          // Model selection — per-run overrides
          reasoning_model: reasoning_model || null,
          execution_model: execution_model || null,
        };

    // --- 6. Select the correct graph name ---
    // Graph names must match the `graphs` keys in langgraph.json.
    //   - 'cloudy-intell'        → AWS architecture generation
    //   - 'cloudy-intell-azure'  → Azure architecture generation
    //   - 'cloudy-intell-debate' → Head-to-head AWS vs Azure debate
    let graphName: string;
    if (isDebate) {
      graphName = 'cloudy-intell-debate';
    } else if (cloud_provider === 'azure') {
      graphName = 'cloudy-intell-azure';
    } else {
      graphName = 'cloudy-intell';
    }

    // --- 7. Start the streaming run ---
    // `streamMode: ['updates']` makes the SDK emit per-node state deltas
    // instead of the full accumulated state, which keeps payloads small.
    const streamResponse = client.runs.stream(thread_id, graphName, {
      input,
      streamMode: ['updates'],
    });

    // --- 8. Convert async iterator → SSE ReadableStream ---
    // The Web Streams API ReadableStream sends SSE-formatted chunks to the
    // browser.  Each chunk is prefixed with "data: " and terminated with a
    // double newline, conforming to the Server-Sent Events spec.
    const encoder = new TextEncoder();
    const readable = new ReadableStream({
      async start(controller) {
        try {
          // Forward each LangGraph SDK event as a JSON SSE message.
          for await (const event of streamResponse) {
            const ssePayload = `data: ${JSON.stringify({ event: event.event, data: event.data })}\n\n`;
            controller.enqueue(encoder.encode(ssePayload));
          }
          // Signal the end of the stream to the client.
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
        } catch (err) {
          // On stream error, send an error event so the client can surface
          // the failure message instead of hanging indefinitely.
          const msg = err instanceof Error ? err.message : 'Stream error';
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ event: 'error', data: { message: msg } })}\n\n`),
          );
          controller.close();
        }
      },
    });

    // Return SSE response with appropriate headers to disable buffering/caching.
    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',  // SSE MIME type
        'Cache-Control': 'no-cache',           // Prevent CDN / browser caching
        Connection: 'keep-alive',              // Keep TCP connection open for streaming
      },
    });
  } catch (error: unknown) {
    // Catch-all: if anything fails before the stream starts, return a 502
    // to indicate the LangGraph backend is unreachable or misconfigured.
    const message = error instanceof Error ? error.message : 'Failed to start run';
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
