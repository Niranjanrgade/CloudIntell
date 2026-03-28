/**
 * POST /api/iac/stream — Start a streaming IaC generation run.
 *
 * This route proxies to the LangGraph IaC graph (`cloudy-intell-iac` or
 * `cloudy-intell-iac-azure`).  It accepts the completed architecture summary
 * and desired IaC format, constructs the initial state, and streams SSE
 * updates back to the client.
 *
 * The IaC graph is a separate workflow from the main architecture graph,
 * invoked on-demand after the user views the architecture report.
 */
import { NextRequest } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      thread_id,
      architecture_summary,
      iac_format = 'terraform',
      cloud_provider = 'aws',
      reasoning_model,
      execution_model,
    } = body as {
      thread_id: string;
      architecture_summary: string;
      iac_format?: string;
      cloud_provider?: string;
      reasoning_model?: string;
      execution_model?: string;
    };

    if (!thread_id || !architecture_summary) {
      return new Response(
        JSON.stringify({ error: 'thread_id and architecture_summary are required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    const client = getLanggraphClient();

    // Construct initial state for the IaC graph.
    // The IaC graph reads `architecture_input` and `iac_format` from state.
    const input = {
      messages: [{ role: 'human', content: `Generate ${iac_format} code for the architecture` }],
      user_problem: `Generate ${iac_format} Infrastructure as Code`,
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
      aws_architecture_summary: null,
      azure_architecture_summary: null,
      debate_rounds: [],
      current_debate_round: 0,
      max_debate_rounds: 0,
      debate_summary: null,
      reasoning_model: reasoning_model || null,
      execution_model: execution_model || null,
      // IaC-specific fields
      iac_format,
      architecture_input: architecture_summary,
      iac_domain_code: {},
      iac_output: null,
    };

    // Select the correct IaC graph based on provider
    const graphName = cloud_provider === 'azure'
      ? 'cloudy-intell-iac-azure'
      : 'cloudy-intell-iac';

    const streamResponse = client.runs.stream(thread_id, graphName, {
      input,
      streamMode: ['updates'],
    });

    const encoder = new TextEncoder();
    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of streamResponse) {
            const ssePayload = `data: ${JSON.stringify({ event: event.event, data: event.data })}\n\n`;
            controller.enqueue(encoder.encode(ssePayload));
          }
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Stream error';
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ event: 'error', data: { message: msg } })}\n\n`),
          );
          controller.close();
        }
      },
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to start IaC generation';
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
