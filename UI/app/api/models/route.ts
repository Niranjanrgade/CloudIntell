/**
 * GET /api/models — Return available LLM models for the model selector.
 *
 * This is a static catalog that mirrors the backend's
 * `src/cloudy_intell/config/models.py` AVAILABLE_MODELS.  Served from the
 * Next.js API route so the frontend can populate the model selector
 * without a direct backend dependency.
 */
import { NextResponse } from 'next/server';

export interface ModelInfo {
  id: string;
  display_name: string;
  provider: 'openai' | 'anthropic' | 'google';
  tier: 'reasoning' | 'execution';
  description: string;
}

const AVAILABLE_MODELS: ModelInfo[] = [
  // OpenAI — GPT-5.4 family (March 2026)
  {
    id: 'gpt-5.4',
    display_name: 'GPT-5.4',
    provider: 'openai',
    tier: 'reasoning',
    description: 'Flagship model for complex reasoning, coding, and agentic workflows (1M context)',
  },
  {
    id: 'gpt-5.4-mini',
    display_name: 'GPT-5.4 Mini',
    provider: 'openai',
    tier: 'execution',
    description: 'Strong mini model for coding, computer use, and sub-agents (400K context)',
  },
  {
    id: 'gpt-5.4-nano',
    display_name: 'GPT-5.4 Nano',
    provider: 'openai',
    tier: 'execution',
    description: 'Cheapest GPT-5.4-class model for simple high-volume tasks (400K context)',
  },
  // Anthropic — Claude 4.6 / 4.5 family (March 2026)
  {
    id: 'claude-opus-4-6',
    display_name: 'Claude Opus 4.6',
    provider: 'anthropic',
    tier: 'reasoning',
    description: 'Most intelligent model for agents and coding (1M context, extended thinking)',
  },
  {
    id: 'claude-sonnet-4-6',
    display_name: 'Claude Sonnet 4.6',
    provider: 'anthropic',
    tier: 'reasoning',
    description: 'Best combination of speed and intelligence (1M context, extended thinking)',
  },
  {
    id: 'claude-haiku-4-5',
    display_name: 'Claude Haiku 4.5',
    provider: 'anthropic',
    tier: 'execution',
    description: 'Fastest model with near-frontier intelligence (200K context)',
  },
  // Google — Gemini 3.x / 2.5 family (March 2026)
  {
    id: 'gemini-3.1-pro-preview',
    display_name: 'Gemini 3.1 Pro',
    provider: 'google',
    tier: 'reasoning',
    description: 'Advanced intelligence for complex problem-solving and agentic coding',
  },
  {
    id: 'gemini-3-flash-preview',
    display_name: 'Gemini 3 Flash',
    provider: 'google',
    tier: 'execution',
    description: 'Frontier-class performance at a fraction of the cost',
  },
  {
    id: 'gemini-2.5-flash',
    display_name: 'Gemini 2.5 Flash',
    provider: 'google',
    tier: 'execution',
    description: 'Best price-performance for low-latency reasoning tasks',
  },
];

export async function GET() {
  return NextResponse.json(AVAILABLE_MODELS);
}
