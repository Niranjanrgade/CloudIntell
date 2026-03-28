/**
 * IaCCodeView — Full-page IaC code viewer with syntax display and download.
 *
 * Renders the generated IaC output in a scrollable full-page panel (mirroring
 * the ArchitectureFullView layout pattern).  Includes:
 * - Header with "Back to Report" button, format badge, and action buttons.
 * - Copy-to-clipboard button.
 * - Download button that exports as .tf / .yaml / .bicep based on format.
 * - Styled code display with monospace font and dark theme.
 */
'use client';

import { useState } from 'react';
import { ArrowLeft, Code2, Download, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { IaCFormat } from '@/lib/types';

// File extension and label mapping per format
const FORMAT_META: Record<string, { label: string; extension: string; lang: string }> = {
  terraform:      { label: 'Terraform (HCL)', extension: '.tf',    lang: 'hcl' },
  cloudformation: { label: 'CloudFormation',   extension: '.yaml',  lang: 'yaml' },
  bicep:          { label: 'Bicep',            extension: '.bicep', lang: 'bicep' },
};

interface IaCCodeViewProps {
  iacOutput: string;
  iacFormat: IaCFormat;
  onBack: () => void;
}

export function IaCCodeView({ iacOutput, iacFormat, onBack }: IaCCodeViewProps) {
  const [copied, setCopied] = useState(false);
  const meta = FORMAT_META[iacFormat] || FORMAT_META.terraform;

  // Extract raw code from markdown code fences if present
  const extractCode = (raw: string): string => {
    const fenceMatch = raw.match(/```[\w]*\n([\s\S]*?)```/);
    return fenceMatch ? fenceMatch[1].trim() : raw;
  };

  const rawCode = extractCode(iacOutput);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(rawCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([rawCode], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `infrastructure${meta.extension}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex-1 h-full flex flex-col overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Report
          </button>
          <div className="w-px h-6 bg-slate-200" />
          <div className="flex items-center gap-2 text-slate-700">
            <Code2 className="w-5 h-5 text-emerald-500" />
            <h1 className="text-lg font-semibold">Infrastructure Code</h1>
          </div>
          {/* Format badge */}
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
            {meta.label}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors border border-slate-200"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-500" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors border border-emerald-200"
          >
            <Download className="w-4 h-4" />
            Download {meta.extension}
          </button>
        </div>
      </div>

      {/* Code content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6">
          <article className="prose prose-slate prose-pre:bg-slate-900 prose-pre:text-slate-100 max-w-none prose-code:text-emerald-600 prose-code:before:content-none prose-code:after:content-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {iacOutput}
            </ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
}
