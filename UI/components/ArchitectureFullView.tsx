'use client';

import { ArrowLeft, FileText, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ArchitectureState } from '@/lib/types';

interface ArchitectureFullViewProps {
  result: ArchitectureState;
  onBack: () => void;
}

export function ArchitectureFullView({ result, onBack }: ArchitectureFullViewProps) {
  const content =
    result.architecture_summary ||
    (result.final_architecture
      ? JSON.stringify(result.final_architecture, null, 2)
      : 'No architecture output available.');

  const handleDownload = () => {
    const blob = new Blob([typeof content === 'string' ? content : ''], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'architecture-report.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex-1 h-full flex flex-col overflow-hidden bg-white">
      {/* Header bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Graph
          </button>
          <div className="w-px h-6 bg-slate-200" />
          <div className="flex items-center gap-2 text-slate-700">
            <FileText className="w-5 h-5 text-indigo-500" />
            <h1 className="text-lg font-semibold">Architecture Report</h1>
          </div>
        </div>
        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors border border-indigo-200"
        >
          <Download className="w-4 h-4" />
          Download
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <article className="max-w-4xl mx-auto px-8 py-10 prose prose-slate prose-headings:text-slate-800 prose-p:text-slate-600 prose-li:text-slate-600 prose-strong:text-slate-800 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100">
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
