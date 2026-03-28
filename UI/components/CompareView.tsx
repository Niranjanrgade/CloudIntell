'use client';

/**
 * CompareView — Side-by-side AWS vs Azure full architecture report.
 *
 * Renders the complete architecture_summary (markdown) for each provider
 * using ReactMarkdown, mirroring the ArchitectureFullView rendering.
 */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ArchitectureState } from '@/lib/types';

interface CompareViewProps {
  /** Architecture result object for AWS, fetched after the AWS run completes. */
  awsResult?: ArchitectureState | null;
  /** Architecture result object for Azure, fetched after the Azure run completes. */
  azureResult?: ArchitectureState | null;
}

/**
 * Extracts the displayable markdown content from a provider's architecture result.
 * Priority order:
 *   1. architecture_summary (polished markdown from the final_architecture_generator)
 *   2. final_architecture (raw JSON fallback, pretty-printed)
 *   3. Placeholder text if nothing is available yet
 */
function getReportContent(result?: ArchitectureState | null): string {
  if (!result) return 'No architecture output available yet.';
  if (result.architecture_summary) return result.architecture_summary;
  if (result.final_architecture)
    return JSON.stringify(result.final_architecture, null, 2);
  return 'No architecture output available.';
}

export function CompareView({ awsResult, azureResult }: CompareViewProps) {
  // Extract renderable markdown content for each cloud provider
  const awsContent = getReportContent(awsResult);
  const azureContent = getReportContent(azureResult);

  return (
    // Horizontal flex container — two equal-width columns with a gap between them.
    // overflow-y-auto enables independent scrolling within the comparison area.
    <div className="w-full h-full flex gap-6 p-6 bg-slate-50 overflow-y-auto">
      {/* ── AWS Column ─────────────────────────────────────────────────────
           White card with orange accent for the AWS provider.  Contains a
           header row with title + status badge, and a scrollable article
           body that renders the architecture_summary as styled markdown. */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
          <h2 className="text-xl font-bold text-orange-600 flex items-center gap-2">
            AWS Architecture
          </h2>
          {/* Status badge — dynamically shows "Generated Solution" or "Awaiting Results"
              depending on whether the backend has produced an architecture_summary yet */}
          <span className="px-3 py-1 bg-orange-50 text-orange-600 text-xs font-semibold rounded-full border border-orange-100">
            {awsResult?.architecture_summary ? 'Generated Solution' : 'Awaiting Results'}
          </span>
        </div>

        {/* Scrollable markdown body — uses Tailwind Typography plugin (prose classes)
            for clean rendering of headings, paragraphs, lists, code blocks, etc. */}
        <div className="flex-1 overflow-y-auto pr-2">
          <article className="prose prose-sm prose-slate max-w-none prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100">
            {/* remarkGfm enables GitHub Flavored Markdown (tables, strikethrough, etc.) */}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{awsContent}</ReactMarkdown>
          </article>
        </div>
      </div>

      {/* ── Azure Column ───────────────────────────────────────────────────
           Mirrors the AWS column structure but uses blue accent colors for
           the Azure brand identity. */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
          <h2 className="text-xl font-bold text-blue-600 flex items-center gap-2">
            Azure Architecture
          </h2>
          <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-semibold rounded-full border border-blue-100">
            {azureResult?.architecture_summary ? 'Generated Solution' : 'Awaiting Results'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto pr-2">
          <article className="prose prose-sm prose-slate max-w-none prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{azureContent}</ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
}
