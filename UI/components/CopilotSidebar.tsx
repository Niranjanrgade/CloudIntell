/**
 * CopilotSidebar — Chat interface for CloudyIntel.
 *
 * This component provides the conversational UI where users describe their
 * cloud architecture problem and receive real-time status updates as the
 * LangGraph agents work.  Features:
 *
 * - **Message display**: Shows user messages, assistant responses, and
 *   per-node status updates (e.g. "Compute Architect — designing compute layer").
 * - **Input handling**: Text input with Enter-to-send and button submission.
 *   Disabled while a run is in progress.
 * - **LangGraph Studio link**: External link button to open the active run
 *   in LangGraph Studio for detailed observation.
 * - **Provider context switching**: Automatically appends a context-switch
 *   message when the user changes providers (AWS/Azure/Compare).
 * - **Layout variants**: Supports both sidebar (right panel) and bottom
 *   (horizontal) layouts for different view modes.
 * - **Auto-scroll**: Scrolls to the latest message as new updates arrive.
 */
'use client';

import { useState, useRef, useEffect, useCallback, Dispatch, SetStateAction } from 'react';
import { Send, Bot, User, Sparkles, X, Loader2, Activity, ExternalLink, FileText } from 'lucide-react';
import type { RunStatus, ChatMessage, ArchitectureState } from '@/lib/types';

/** All possible navigation modes — re-exported from here for use in page.tsx. */
export type ViewMode = 'AWS' | 'Azure' | 'Compare' | 'Debate';

interface CopilotSidebarProps {
  /** Current navigation mode — used for context-switch messages and provider labeling. */
  provider: ViewMode;
  /** Layout variant: 'sidebar' renders as a right panel (tall), 'bottom' renders as a
   *  horizontal bar (short) — used in Compare and Debate modes. */
  variant?: 'sidebar' | 'bottom';
  /** Callback invoked when the user submits a problem — triggers the run orchestration. */
  onRunStart: (problem: string, provider: string, modelOverrides?: { reasoning_model?: string; execution_model?: string }) => Promise<void>;
  /** Current run lifecycle status — disables input while 'running'. */
  runStatus: RunStatus;
  /** The array of chat messages to display (user, assistant, and status messages). */
  messages: ChatMessage[];
  /** State setter for messages — used by the context-switch effect to append messages. */
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  /** Final architecture result — when present and run is completed, shows the
   *  "View Full Architecture Report" button. Only passed in sidebar variant. */
  architectureResult?: ArchitectureState | null;
  /** Callback to switch the parent's view to the full architecture report overlay. */
  onViewFullReport?: () => void;
  /** Currently selected model overrides from sidebar. */
  modelOverrides?: { reasoning_model?: string; execution_model?: string };
}

export function CopilotSidebar({
  provider,
  variant = 'sidebar',
  onRunStart,
  runStatus,
  messages,
  setMessages,
  architectureResult,
  onViewFullReport,
  modelOverrides,
}: CopilotSidebarProps) {
  // Whether the sidebar is open or minimized to a floating button
  const [isOpen, setIsOpen] = useState(true);
  // Controlled input value for the textarea
  const [input, setInput] = useState('');
  // Ref used to scroll the message list to the bottom on new messages
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Resizable dimensions ────────────────────────────────────────────
  // Sidebar variant: resizable width (left edge drag)
  const MIN_WIDTH = 380;
  const MAX_WIDTH = 900;
  const DEFAULT_WIDTH = 580;
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH);

  // Bottom variant: resizable height (top edge drag)
  const MIN_HEIGHT = 150;
  const MAX_HEIGHT = 600;
  const DEFAULT_HEIGHT = 288; // h-72 equivalent
  const [bottomHeight, setBottomHeight] = useState(DEFAULT_HEIGHT);

  const isResizing = useRef(false);
  const resizeAxis = useRef<'x' | 'y'>('x');

  const handleMouseDown = useCallback((e: React.MouseEvent, axis: 'x' | 'y') => {
    e.preventDefault();
    isResizing.current = true;
    resizeAxis.current = axis;
    document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      if (resizeAxis.current === 'x') {
        const newWidth = window.innerWidth - e.clientX;
        setSidebarWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, newWidth)));
      } else {
        const newHeight = window.innerHeight - e.clientY;
        setBottomHeight(Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, newHeight)));
      }
    };
    const handleMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  // ── Context-switch message ──────────────────────────────────────────────
  // When the user switches between AWS/Azure/Compare/Debate via the left
  // sidebar, append an informational message so the chat history reflects
  // the context change.  Uses a ref to track the previous provider value
  // and only fires when it actually changes (not on initial mount).
  const prevProviderRef = useRef(provider);
  useEffect(() => {
    if (provider !== prevProviderRef.current) {
      prevProviderRef.current = provider;
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content: `Switched context to ${provider}. ${provider === 'Compare' ? 'I am ready to compare AWS and Azure architectures side-by-side.' : `I am ready to design and validate ${provider} architectures.`} What would you like to build?`,
        },
      ]);
    }
  }, [provider, setMessages]);

  // ── Auto-scroll ─────────────────────────────────────────────────────────
  // Smoothly scroll to the bottom of the message container whenever the
  // messages array changes (new user message, status update, or response).
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * handleSend — Processes the user's text input submission.
   * Guards against empty input and concurrent runs (disabled while running).
   * Clears the input field and delegates to the parent's onRunStart callback,
   * which triggers the full LangGraph run orchestration.
   */
  const handleSend = () => {
    if (!input.trim() || runStatus === 'running') return;
    const problem = input.trim();
    setInput('');
    onRunStart(problem, provider, modelOverrides);
  };

  // ── Collapsed state ───────────────────────────────────────────────────
  // When the sidebar is closed, render only a floating action button (FAB)
  // in the bottom-right corner that re-opens the sidebar on click.
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 p-4 bg-indigo-600 text-white rounded-full shadow-lg hover:bg-indigo-700 transition-all z-50 flex items-center justify-center"
      >
        <Sparkles className="w-6 h-6" />
      </button>
    );
  }

  // ── Layout-variant CSS ────────────────────────────────────────────────
  // Sidebar variant: fixed-width right panel (48rem) with left border.
  // Bottom variant: full-width horizontal bar (h-72) with top border.
  // Both use flex-col to stack header → messages → input vertically.
  const containerClasses =
    variant === 'sidebar'
      ? 'relative bg-white border-l border-slate-200 shadow-2xl flex flex-col h-full z-40'
      : 'relative w-full bg-white border-t border-slate-200 shadow-2xl flex flex-col z-40';

  const containerStyle =
    variant === 'sidebar'
      ? { width: sidebarWidth }
      : { height: bottomHeight };

  return (
    <div
      className={containerClasses}
      style={containerStyle}
    >
      {/* ── Resize handle ─────────────────────────────────────────────── */}
      {variant === 'sidebar' ? (
        <div
          onMouseDown={(e) => handleMouseDown(e, 'x')}
          className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-indigo-400/40 active:bg-indigo-500/50 transition-colors z-50"
        />
      ) : (
        <div
          onMouseDown={(e) => handleMouseDown(e, 'y')}
          className="absolute left-0 right-0 top-0 h-1.5 cursor-row-resize hover:bg-indigo-400/40 active:bg-indigo-500/50 transition-colors z-50"
        />
      )}
      {/* ── Header ──────────────────────────────────────────────────────────
           Shows the bot icon, title ("CloudyIntel Copilot"), subtitle, and
           a close button.  The indigo-tinted background distinguishes the
           header from the message body. */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-indigo-50/50">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-100 rounded-lg text-indigo-600">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-800 text-sm">
              CloudyIntel Copilot
            </h2>
            <p className="text-xs text-slate-500">
              Cloud Solution Architect Assistant
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Close button — collapses the sidebar to the FAB */}
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── Messages ────────────────────────────────────────────────────────
           Scrollable message list.  Three message types are rendered:
           1. 'status' — small inline status updates (e.g. "Compute Architect — designing")
              shown with a pulsing Activity icon.
           2. 'user' — user's input messages, right-aligned with dark background.
           3. 'assistant' — bot responses, left-aligned with white card background.
           Each assistant message may include an optional link (e.g. LangGraph Studio). */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
        {messages.map((msg) =>
          msg.role === 'status' ? (
            <div
              key={msg.id}
              className="flex items-center gap-2 text-xs text-slate-500 px-2 py-1"
            >
              <Activity className="w-3 h-3 text-indigo-400 animate-pulse" />
              <span>{msg.content}</span>
            </div>
          ) : (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user'
                    ? 'bg-slate-800 text-white'
                    : 'bg-indigo-100 text-indigo-600'
                }`}
              >
                {msg.role === 'user' ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>
              <div
                className={`px-4 py-3 rounded-2xl max-w-[80%] text-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-slate-800 text-white rounded-tr-sm'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                }`}
              >
                {msg.content}
                {msg.link && (
                  <a
                    href={msg.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Open in LangGraph Studio
                  </a>
                )}
              </div>
            </div>
          ),
        )}

        {/* ── Typing indicator ────────────────────────────────────────────
             Shown while the run is in progress.  Displays an animated spinner
             next to "Agents working..." text to give visual feedback that the
             backend agents are actively processing. */}
        {runStatus === 'running' && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-indigo-100 text-indigo-600">
              <Bot className="w-4 h-4" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-white border border-slate-200 text-slate-500 rounded-tl-sm shadow-sm flex items-center gap-2 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Agents working...
            </div>
          </div>
        )}

        {/* ── View Full Report button ─────────────────────────────────────
             Shown only when: (1) the run has completed, (2) an architecture
             summary exists, and (3) the onViewFullReport callback is provided
             (i.e. we're in sidebar mode, not bottom mode). */}
        {architectureResult?.architecture_summary && onViewFullReport && runStatus === 'completed' && (
          <div className="flex justify-center pt-2">
            <button
              onClick={onViewFullReport}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 transition-colors shadow-md"
            >
              <FileText className="w-4 h-4" />
              View Full Architecture Report
            </button>
          </div>
        )}

        {/* Invisible scroll anchor — messagesEndRef.scrollIntoView() targets this */}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Input Area ──────────────────────────────────────────────────────
           Sticky footer with a resizable textarea and send button.
           - Enter (without Shift) submits the message.
           - Shift+Enter inserts a newline for multi-line input.
           - The textarea and send button are disabled while a run is active.
           - Row count differs by variant: 3 rows for bottom bar, 8 for sidebar. */}
      <div className="p-4 border-t border-slate-100 bg-white">
        <div className="relative flex items-end max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              runStatus === 'running'
                ? 'Agents are working...'
                : 'Describe your cloud architecture problem...'
            }
            disabled={runStatus === 'running'}
            rows={variant === 'bottom' ? 3 : 8}
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all disabled:opacity-50 resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || runStatus === 'running'}
            className="absolute right-2 bottom-2 p-2 text-indigo-600 disabled:text-slate-300 hover:bg-indigo-50 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-2 text-center">
          <p className="text-[10px] text-slate-400">
            Powered by LangGraph
          </p>
        </div>
      </div>
    </div>
  );
}
