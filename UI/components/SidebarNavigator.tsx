/**
 * SidebarNavigator — Left sidebar navigation for CloudyIntel.
 *
 * Provides navigation between the three main views:
 * - **AWS Architecture**: Shows the AWS agent workflow graph.
 * - **Azure Architecture**: Shows the Azure agent workflow graph.
 * - **Compare Solutions**: Shows a side-by-side architecture comparison.
 *
 * Also includes a Settings button (currently a placeholder for future
 * configuration options like model selection, iteration bounds, etc.).
 */
import { Cloud, Columns, Settings, Server, Swords } from 'lucide-react';
import { ViewMode } from './CopilotSidebar';

/**
 * SidebarNavigator component — the main left sidebar.
 *
 * @param viewMode   The currently active view ('AWS' | 'Azure' | 'Compare' | 'Debate').
 * @param setViewMode  Callback to update the active view when a nav button is clicked.
 */
export function SidebarNavigator({ viewMode, setViewMode }: { viewMode: ViewMode, setViewMode: (mode: ViewMode) => void }) {
  return (
    // Fixed-width dark sidebar (w-64) that spans the full viewport height.
    // shrink-0 prevents it from being squeezed by the flex main content area.
    // z-50 ensures it layers above other floating elements.
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
      
      {/* ── Navigation ────────────────────────────────────────────────────
           Two sections: "Architectures" (AWS & Azure) and "Analysis"
           (Compare & Debate).  Each NavItem highlights with its provider's
           brand color when active. */}
      <nav className="flex-1 px-4 space-y-2">
        {/* Section label — Architectures */}
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
          Architectures
        </div>
        {/* AWS nav item — orange accent when active */}
        <NavItem 
          icon={<Cloud className="w-5 h-5" />} 
          label="AWS Architecture" 
          active={viewMode === 'AWS'} 
          onClick={() => setViewMode('AWS')} 
          activeColor="bg-orange-500"
        />
        {/* Azure nav item — blue accent when active */}
        <NavItem 
          icon={<Server className="w-5 h-5" />} 
          label="Azure Architecture" 
          active={viewMode === 'Azure'} 
          onClick={() => setViewMode('Azure')} 
          activeColor="bg-blue-600"
        />
        
        {/* Section label — Analysis */}
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-3 px-2">
          Analysis
        </div>
        {/* Compare nav item — side-by-side architecture comparison */}
        <NavItem 
          icon={<Columns className="w-5 h-5" />} 
          label="Compare Solutions" 
          active={viewMode === 'Compare'} 
          onClick={() => setViewMode('Compare')} 
          activeColor="bg-indigo-600"
        />
        {/* Debate nav item — AWS vs Azure advocate debate */}
        <NavItem 
          icon={<Swords className="w-5 h-5" />} 
          label="Debate Mode" 
          active={viewMode === 'Debate'} 
          onClick={() => setViewMode('Debate')} 
          activeColor="bg-purple-600"
        />
      </nav>
      
      {/* ── Footer ────────────────────────────────────────────────────────
           Settings button placeholder — currently non-functional, reserved
           for future configuration UI (model selection, iteration bounds, etc.). */}
      <div className="p-4 border-t border-slate-800">
        <NavItem 
          icon={<Settings className="w-5 h-5" />} 
          label="Settings" 
          active={false} 
          onClick={() => {}} 
          activeColor="bg-slate-700"
        />
      </div>
    </div>
  );
}

/**
 * NavItem — Individual navigation button within the sidebar.
 *
 * Renders an icon + label row that highlights with the provider-specific
 * `activeColor` when selected.  Inactive items show a subtle hover effect.
 *
 * @param icon        React node (Lucide icon) displayed to the left of the label.
 * @param label       Human-readable text for the navigation destination.
 * @param active      Whether this item represents the currently selected view.
 * @param onClick     Callback fired when the button is clicked.
 * @param activeColor Tailwind background class applied when active (e.g. 'bg-orange-500').
 */
function NavItem({ 
  icon, 
  label, 
  active, 
  onClick,
  activeColor
}: { 
  icon: React.ReactNode, 
  label: string, 
  active: boolean, 
  onClick: () => void,
  activeColor: string
}) {
  return (
    // Full-width button with conditional styling:
    // Active: provider-colored background + white text + shadow
    // Inactive: transparent background with hover:bg-slate-800 + muted text
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
