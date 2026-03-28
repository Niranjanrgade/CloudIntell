/**
 * IaCGenerationPanel — Post-report IaC generation trigger.
 *
 * This component renders as a compact bar at the bottom of the architecture
 * report view.  It provides:
 * - A format selector dropdown (Terraform / CloudFormation / Bicep) filtered
 *   by the cloud provider.
 * - A "Generate Infrastructure Code" button.
 * - A progress indicator during generation.
 *
 * It is only shown after the architecture run completes and the user has
 * opened the full report view.  It does NOT modify any existing components.
 */
'use client';

import { useState } from 'react';
import { Code2, Loader2, ChevronDown } from 'lucide-react';
import type { IaCFormat, IaCStatus } from '@/lib/types';
import { IAC_FORMAT_OPTIONS } from '@/lib/types';

interface IaCGenerationPanelProps {
  cloudProvider: string;
  iacStatus: IaCStatus;
  iacProgress: string[];
  onGenerate: (format: IaCFormat) => void;
}

export function IaCGenerationPanel({
  cloudProvider,
  iacStatus,
  iacProgress,
  onGenerate,
}: IaCGenerationPanelProps) {
  const providerKey = cloudProvider.toLowerCase();
  const formats = IAC_FORMAT_OPTIONS[providerKey] || IAC_FORMAT_OPTIONS['aws'];
  const [selectedFormat, setSelectedFormat] = useState<IaCFormat>(formats[0].value);

  const isGenerating = iacStatus === 'generating';

  return (
    <div className="border-t border-slate-200 bg-slate-50/80 px-6 py-3 shrink-0">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Label + format selector */}
        <div className="flex items-center gap-3">
          <Code2 className="w-5 h-5 text-emerald-600" />
          <span className="text-sm font-medium text-slate-700">
            Generate Infrastructure Code
          </span>
          <div className="relative">
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value as IaCFormat)}
              disabled={isGenerating}
              className="appearance-none bg-white border border-slate-200 rounded-lg pl-3 pr-8 py-1.5 text-sm text-slate-700 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {formats.map((fmt) => (
                <option key={fmt.value} value={fmt.value}>
                  {fmt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>
        </div>

        {/* Right: Generate button + progress */}
        <div className="flex items-center gap-3">
          {isGenerating && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
              <span className="max-w-[200px] truncate">
                {iacProgress.length > 0 ? iacProgress[iacProgress.length - 1] : 'Generating…'}
              </span>
            </div>
          )}
          <button
            onClick={() => onGenerate(selectedFormat)}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 disabled:cursor-not-allowed rounded-lg transition-colors shadow-sm"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Code2 className="w-4 h-4" />
                Generate
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
