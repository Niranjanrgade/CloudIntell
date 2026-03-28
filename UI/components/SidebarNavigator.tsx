/**
 * SidebarNavigator — Left sidebar navigation for CloudyIntel.
 *
 * Provides navigation between the three main views:
 * - **AWS Architecture**: Shows the AWS agent workflow graph.
 * - **Azure Architecture**: Shows the Azure agent workflow graph.
 * - **Compare Solutions**: Shows a side-by-side architecture comparison.
 *
 * Also includes a model selector for choosing reasoning and execution LLMs.
 */
import { useState } from 'react';
import { Cloud, Columns, Server, Swords, ChevronDown, ChevronUp, Brain, Cpu } from 'lucide-react';
import { ViewMode } from './CopilotSidebar';
import type { ModelInfo } from '@/lib/types';

/** Provider logo colors for visual grouping in the model dropdown. */
const PROVIDER_COLORS: Record<string, string> = {
  openai: 'text-green-400',
  anthropic: 'text-amber-400',
  google: 'text-blue-400',
};

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
};

interface SidebarNavigatorProps {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  models: ModelInfo[];
  reasoningModel: string;
  executionModel: string;
  onReasoningModelChange: (modelId: string) => void;
  onExecutionModelChange: (modelId: string) => void;
}

export function SidebarNavigator({
  viewMode,
  setViewMode,
  models,
  reasoningModel,
  executionModel,
  onReasoningModelChange,
  onExecutionModelChange,
}: SidebarNavigatorProps) {
  const [modelsExpanded, setModelsExpanded] = useState(false);

  const reasoningModels = models.filter((m) => m.tier === 'reasoning');
  const executionModels = models.filter((m) => m.tier === 'execution');
  // Allow any model to be used in either role — show all in both lists,
  // but sort tier-matched models first.
  const allForReasoning = [...reasoningModels, ...models.filter((m) => m.tier !== 'reasoning')];
  const allForExecution = [...executionModels, ...models.filter((m) => m.tier !== 'execution')];

  return (
    <div className="w-64 h-full bg-slate-900 text-slate-300 flex flex-col shrink-0 z-50 shadow-xl">
      {/* ── App Logo & Title ──────────────────────────────────────────── */}
      <div className="p-6 mb-4">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <Cloud className="w-6 h-6 text-indigo-400" />
          CloudyIntel
        </h1>
        <p className="text-xs text-slate-500 mt-2 leading-relaxed">
          Agentic AI framework for Cloud Solution Architects
        </p>
      </div>

      {/* ── Navigation ──────────────────────────────────────────────────── */}
      <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
          Architectures
        </div>
        <NavItem
          icon={<Cloud className="w-5 h-5" />}
          label="AWS Architecture"
          active={viewMode === 'AWS'}
          onClick={() => setViewMode('AWS')}
          activeColor="bg-orange-500"
        />
        <NavItem
          icon={<Server className="w-5 h-5" />}
          label="Azure Architecture"
          active={viewMode === 'Azure'}
          onClick={() => setViewMode('Azure')}
          activeColor="bg-blue-600"
        />

        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-3 px-2">
          Analysis
        </div>
        <NavItem
          icon={<Columns className="w-5 h-5" />}
          label="Compare Solutions"
          active={viewMode === 'Compare'}
          onClick={() => setViewMode('Compare')}
          activeColor="bg-indigo-600"
        />
        <NavItem
          icon={<Swords className="w-5 h-5" />}
          label="Debate Mode"
          active={viewMode === 'Debate'}
          onClick={() => setViewMode('Debate')}
          activeColor="bg-purple-600"
        />

        {/* ── Model Selection ────────────────────────────────────────────── */}
        <div className="mt-8">
          <button
            onClick={() => setModelsExpanded(!modelsExpanded)}
            className="w-full flex items-center justify-between px-2 mb-3 group"
          >
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider group-hover:text-slate-400 transition-colors">
              Models
            </span>
            {modelsExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-500 group-hover:text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500 group-hover:text-slate-400" />
            )}
          </button>

          {modelsExpanded && (
            <div className="space-y-4 px-1">
              {/* Reasoning model selector */}
              <ModelSelector
                icon={<Brain className="w-4 h-4 text-purple-400" />}
                label="Reasoning"
                sublabel="Supervisors & Synthesizers"
                models={allForReasoning}
                selectedModel={reasoningModel}
                onChange={onReasoningModelChange}
              />
              {/* Execution model selector */}
              <ModelSelector
                icon={<Cpu className="w-4 h-4 text-cyan-400" />}
                label="Execution"
                sublabel="Domain Agents & Tools"
                models={allForExecution}
                selectedModel={executionModel}
                onChange={onExecutionModelChange}
              />
            </div>
          )}
        </div>
      </nav>
    </div>
  );
}

/** Individual navigation button. */
function NavItem({
  icon,
  label,
  active,
  onClick,
  activeColor,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  activeColor: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
        active
          ? `${activeColor} text-white shadow-md`
          : 'hover:bg-slate-800 hover:text-white text-slate-400'
      }`}
    >
      {icon}
      <span className="font-medium text-sm">{label}</span>
    </button>
  );
}

/** Dropdown model selector for a specific tier. */
function ModelSelector({
  icon,
  label,
  sublabel,
  models,
  selectedModel,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  models: ModelInfo[];
  selectedModel: string;
  onChange: (modelId: string) => void;
}) {
  const selected = models.find((m) => m.id === selectedModel);

  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        {icon}
        <div>
          <div className="text-xs font-semibold text-slate-300">{label}</div>
          <div className="text-[10px] text-slate-500">{sublabel}</div>
        </div>
      </div>
      <select
        value={selectedModel}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-slate-800 text-slate-200 text-xs rounded-md px-3 py-2 border border-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none appearance-none cursor-pointer hover:border-slate-600 transition-colors"
        title={selected?.description}
      >
        {/* Group by provider */}
        {(['openai', 'anthropic', 'google'] as const).map((provider) => {
          const providerModels = models.filter((m) => m.provider === provider);
          if (providerModels.length === 0) return null;
          return (
            <optgroup key={provider} label={PROVIDER_LABELS[provider]}>
              {providerModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </optgroup>
          );
        })}
      </select>
    </div>
  );
}
