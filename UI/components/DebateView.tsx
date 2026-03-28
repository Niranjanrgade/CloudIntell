'use client';

/**
 * DebateView — Multi-round AWS vs Azure debate display.
 *
 * Shows the debate progression:
 * 1. Compact collapsible architecture summaries at top
 * 2. Debate rounds as two-column advocate argument cards
 * 3. Judge's verdict in a full-width highlighted card at bottom
 */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronDown, ChevronUp, Gavel, Swords, Shield } from 'lucide-react';
import type { DebateRound } from '@/lib/types';

interface DebateViewProps {
  /** The user's original cloud architecture problem statement. */
  userProblem?: string;
  /** Polished markdown summary of the AWS architecture (from architecture_summary). */
  awsSummary?: string | null;
  /** Polished markdown summary of the Azure architecture. */
  azureSummary?: string | null;
  /** Array of debate round objects, each containing AWS and Azure arguments. */
  debateRounds?: DebateRound[];
  /** The judge's final verdict markdown, rendered after all rounds complete. */
  debateSummary?: string | null;
  /** Whether the debate orchestration is currently running. */
  isRunning?: boolean;
  /** Current phase of the debate lifecycle:
   *  'generating' = building AWS/Azure architectures,
   *  'debating' = advocates exchanging arguments,
   *  'judging' = neutral judge evaluating,
   *  'completed' = debate finished,
   *  'idle' = no debate started. */
  debatePhase?: string;
}

// Shared Tailwind Typography (prose) classes used across all markdown-rendered
// sections in this component.  Extracted to a constant to avoid repetition.
const proseClasses =
  'prose prose-sm prose-slate max-w-none prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100';

export function DebateView({
  userProblem,
  awsSummary,
  azureSummary,
  debateRounds = [],
  debateSummary,
  isRunning = false,
  debatePhase = 'idle',
}: DebateViewProps) {
  // Local toggle state for expanding/collapsing the architecture summaries
  const [awsExpanded, setAwsExpanded] = useState(false);
  const [azureExpanded, setAzureExpanded] = useState(false);

  // Phase label configuration — maps each debate phase to a human-readable
  // text label and Tailwind color classes for the status badge.
  const phaseLabel: Record<string, { text: string; color: string }> = {
    idle: { text: 'Ready', color: 'bg-slate-100 text-slate-600' },
    generating: {
      text: 'Generating Solutions…',
      color: 'bg-amber-50 text-amber-700 border-amber-200',
    },
    debating: {
      text: 'Debate in Progress',
      color: 'bg-purple-50 text-purple-700 border-purple-200',
    },
    judging: {
      text: 'Judge Evaluating',
      color: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    },
    completed: {
      text: 'Debate Completed',
      color: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
  };

  // Look up the current phase's display config, defaulting to 'idle'
  const phase = phaseLabel[debatePhase] || phaseLabel.idle;

  return (
    <div className="w-full h-full flex flex-col gap-5 p-6 bg-slate-50 overflow-y-auto">
      {/* ── Header ──────────────────────────────────────────────────────────
           Shows the Debate Mode title with a swords icon and the current
           phase status badge (e.g. "Debate in Progress").  The badge pulses
           with animate-pulse when the debate is actively running. */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Swords className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">Debate Mode</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              AWS and Azure advocates argue for their platform
            </p>
          </div>
        </div>
        <span
          className={`px-3 py-1.5 text-xs font-semibold rounded-full border ${phase.color} ${isRunning ? 'animate-pulse' : ''}`}
        >
          {phase.text}
        </span>
      </div>

      {/* ── Collapsible Architecture Summaries ───────────────────────────
           Two side-by-side collapsible cards showing the AWS and Azure
           architecture summaries that were generated before the debate.
           Users can expand/collapse each to review the source material
           the advocates are debating about. */}
      {(awsSummary || azureSummary) && (
        <div className="flex gap-4">
          {/* AWS Summary — orange accent, collapsible */}
          <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <button
              onClick={() => setAwsExpanded(!awsExpanded)}
              className="w-full flex items-center justify-between px-4 py-3 bg-orange-50/50 hover:bg-orange-50 transition-colors"
            >
              <span className="text-sm font-semibold text-orange-600 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                AWS Architecture
              </span>
              {awsExpanded ? (
                <ChevronUp className="w-4 h-4 text-orange-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-orange-400" />
              )}
            </button>
            {awsExpanded && (
              <div className="px-4 py-3 border-t border-orange-100 max-h-64 overflow-y-auto">
                <article className={proseClasses}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {awsSummary || 'Awaiting AWS architecture…'}
                  </ReactMarkdown>
                </article>
              </div>
            )}
          </div>

          {/* Azure Summary — blue accent, collapsible */}
          <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <button
              onClick={() => setAzureExpanded(!azureExpanded)}
              className="w-full flex items-center justify-between px-4 py-3 bg-blue-50/50 hover:bg-blue-50 transition-colors"
            >
              <span className="text-sm font-semibold text-blue-600 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Azure Architecture
              </span>
              {azureExpanded ? (
                <ChevronUp className="w-4 h-4 text-blue-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-blue-400" />
              )}
            </button>
            {azureExpanded && (
              <div className="px-4 py-3 border-t border-blue-100 max-h-64 overflow-y-auto">
                <article className={proseClasses}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {azureSummary || 'Awaiting Azure architecture…'}
                  </ReactMarkdown>
                </article>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Debate Rounds ──────────────────────────────────────────────
           Each round is rendered as a pair of side-by-side cards:
           - Left card: AWS Advocate's argument (orange border)
           - Right card: Azure Advocate's argument (blue border)
           A centered round number badge sits above each pair. */}
      {debateRounds.length > 0 && (
        <div className="space-y-5">
          {debateRounds.map((round) => (
            <div key={round.round} className="relative">
              {/* Round badge */}
              <div className="flex justify-center mb-3">
                <span className="px-4 py-1.5 bg-purple-600 text-white text-xs font-bold rounded-full shadow-md">
                  Round {round.round}
                </span>
              </div>

              <div className="flex gap-4">
                {/* ── AWS Advocate argument card ── */}
                <div className="flex-1 bg-white rounded-xl border-2 border-orange-200 shadow-sm p-5">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-orange-100">
                    <div className="w-2 h-2 bg-orange-500 rounded-full" />
                    <h4 className="text-sm font-bold text-orange-600">
                      AWS Advocate
                    </h4>
                  </div>
                  <div className="overflow-y-auto max-h-96">
                    <article className={proseClasses}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {round.aws_argument}
                      </ReactMarkdown>
                    </article>
                  </div>
                </div>

                {/* ── Azure Advocate argument card ── */}
                <div className="flex-1 bg-white rounded-xl border-2 border-blue-200 shadow-sm p-5">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-blue-100">
                    <div className="w-2 h-2 bg-blue-500 rounded-full" />
                    <h4 className="text-sm font-bold text-blue-600">
                      Azure Advocate
                    </h4>
                  </div>
                  <div className="overflow-y-auto max-h-96">
                    <article className={proseClasses}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {round.azure_argument}
                      </ReactMarkdown>
                    </article>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Loading placeholder ─────────────────────────────────────────
           Shown while architectures are being generated or while waiting
           for the debate to begin (no rounds yet, not idle, no verdict). */}
      {debateRounds.length === 0 && !debateSummary && debatePhase !== 'idle' && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Swords className="w-12 h-12 text-purple-300 mx-auto animate-pulse" />
            <p className="text-sm text-slate-400">
              {debatePhase === 'generating'
                ? 'Generating AWS and Azure architectures…'
                : 'Waiting for debate to begin…'}
            </p>
          </div>
        </div>
      )}

      {/* ── Judge's Verdict ─────────────────────────────────────────────
           Full-width card with a gradient background (indigo → purple) to
           visually distinguish the judge's evaluation from advocate arguments.
           Only rendered after the debate_judge node completes. */}
      {debateSummary && (
        <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border-2 border-indigo-200 shadow-md p-6">
          <div className="flex items-center gap-3 mb-4 pb-3 border-b border-indigo-200">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <Gavel className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-indigo-800">
                Judge&apos;s Verdict
              </h3>
              <p className="text-xs text-indigo-500">
                Neutral evaluation of the debate
              </p>
            </div>
          </div>
          <div className="overflow-y-auto max-h-[600px]">
            <article className={proseClasses}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {debateSummary}
              </ReactMarkdown>
            </article>
          </div>
        </div>
      )}

      {/* ── Empty state (idle) ─────────────────────────────────────────
           Centered placeholder when no debate has been started yet.
           Prompts the user to submit a problem to begin the debate. */}
      {debatePhase === 'idle' && !debateSummary && debateRounds.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3 max-w-md">
            <Swords className="w-16 h-16 text-slate-200 mx-auto" />
            <h3 className="text-lg font-semibold text-slate-400">
              No debate yet
            </h3>
            <p className="text-sm text-slate-400">
              Submit a cloud architecture problem to start a debate between AWS
              and Azure advocates. Both sides will generate solutions and then
              argue for their platform in a structured multi-round debate.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
