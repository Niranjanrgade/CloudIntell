/**
 * ArchitectureFullView — Full-page architecture report viewer.
 *
 * Renders the complete architecture_summary as styled markdown in a scrollable
 * full-page panel that overlays the React Flow graph.  Includes a header bar
 * with a "Back to Graph" button and a "Download" button that exports the
 * report as a .md file.
 *
 * This component is shown when the user clicks "View Full Architecture Report"
 * in the CopilotSidebar after a run completes.  It replaces the graph view
 * and can be dismissed to return to the React Flow visualization.
 */
'use client';

import { ArrowLeft, FileText, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ArchitectureState } from '@/lib/types';

interface ArchitectureFullViewProps {
  /** The complete architecture state containing architecture_summary and/or final_architecture. */
  result: ArchitectureState;
  /** Callback to return to the React Flow graph view. */
  onBack: () => void;
}

export function ArchitectureFullView({ result, onBack }: ArchitectureFullViewProps) {
  // Extract the best available content for display.
  // Priority: architecture_summary (polished markdown) > final_architecture (raw JSON) > placeholder.
  const content =
    result.architecture_summary ||
    (result.final_architecture
      ? JSON.stringify(result.final_architecture, null, 2)
      : 'No architecture output available.');

  /**
   * handleDownload — Exports the architecture report as a downloadable .md file.
   * Creates a temporary Blob URL, triggers a click on a hidden <a> element,
   * then revokes the URL to free memory.
   */
  const handleDownload = () => {
    // Create a Blob containing the markdown content
    const blob = new Blob([typeof content === 'string' ? content : ''], {
      type: 'text/markdown;charset=utf-8',
    });
    // Generate a temporary object URL for the blob
    const url = URL.createObjectURL(blob);
    // Programmatically create and click a download link
    const a = document.createElement('a');
    a.href = url;
    a.download = 'architecture-report.md';
    a.click();
    // Clean up the temporary URL to prevent memory leaks
    URL.revokeObjectURL(url);
  };

  return (
    // Fills the available flex space, with a fixed header and scrollable content body
    <div className="flex-1 h-full flex flex-col overflow-hidden bg-white">
      {/* ── Header bar ─────────────────────────────────────────────────────
           Contains navigation (Back to Graph), title, and download button.
           shrink-0 prevents the header from collapsing when content overflows. */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80 shrink-0">
        <div className="flex items-center gap-3">
          {/* Back button — returns to the React Flow graph visualization */}
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Graph
          </button>
          {/* Vertical divider between back button and title */}
          <div className="w-px h-6 bg-slate-200" />
          <div className="flex items-center gap-2 text-slate-700">
            <FileText className="w-5 h-5 text-indigo-500" />
            <h1 className="text-lg font-semibold">Architecture Report</h1>
          </div>
        </div>
        {/* Download button — exports the report content as a .md file */}
        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors border border-indigo-200"
        >
          <Download className="w-4 h-4" />
          Download
        </button>
      </div>

      {/* ── Content body ───────────────────────────────────────────────────
           Scrollable area with max-width centering for readability.
           Uses Tailwind Typography (prose) classes for styled markdown rendering. */}
      <div className="flex-1 overflow-y-auto">
        <article className="max-w-4xl mx-auto px-8 py-10 prose prose-slate prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100">
          {/* Render as markdown if string content, otherwise show formatted JSON */}
          {typeof content === 'string' ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          ) : (
            <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(content, null, 2)}</pre>
          )}
        </article>
      </div>
    </div>
  );
}
