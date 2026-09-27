import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Settings,
  ScrollText,
  Link2,
  X,
  Minus,
  Square,
} from "lucide-react";
import { cn } from "../../lib/utils";

type Page = "dashboard" | "settings" | "logs";

interface SidebarProps {
  page: Page;
  onNavigate: (p: Page) => void;
  connected: boolean;
  bondingActive: boolean;
}

const NAV_ITEMS: { id: Page; label: string; Icon: React.ElementType }[] = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "settings",  label: "Settings",  Icon: Settings },
  { id: "logs",      label: "Logs",       Icon: ScrollText },
];

export function Sidebar({ page, onNavigate, connected, bondingActive }: SidebarProps) {
  return (
    <aside className="flex flex-col w-56 shrink-0 h-full glass border-r border-white/10 relative z-10">
      {/* Drag region / titlebar area */}
      <div
        data-tauri-drag-region="true"
        className="h-10 flex items-center justify-between px-4 border-b border-white/8"
      >
        {/* Window controls — no-drag */}
        <div className="flex items-center gap-1.5" data-tauri-drag-region="false">
          <WinBtn color="bg-red-500" title="Close" />
          <WinBtn color="bg-amber-400" title="Minimise" />
          <WinBtn color="bg-emerald-500" title="Maximise" />
        </div>
      </div>

      {/* Logo */}
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-700/30">
            <Link2 className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-none">Tandem</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Multi-Link Bonding</p>
          </div>
        </div>
      </div>

      {/* Connection status pill */}
      <div className="px-3 mb-4">
        <div className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border",
          connected
            ? bondingActive
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-sky-500/10 border-sky-500/30 text-sky-400"
            : "bg-slate-700/30 border-slate-600/30 text-slate-500"
        )}>
          <motion.div
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              connected
                ? bondingActive ? "bg-emerald-400" : "bg-sky-400"
                : "bg-slate-500"
            )}
            animate={connected ? { scale: [1, 1.4, 1] } : { scale: 1 }}
            transition={{ duration: 1.5, repeat: connected ? Infinity : 0 }}
          />
          {!connected
            ? "Disconnected"
            : bondingActive
              ? "Bonding Active"
              : "Standby"}
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={cn("nav-item w-full text-left", page === id && "active")}
          >
            <Icon className="w-4 h-4 shrink-0" strokeWidth={1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 pb-4 border-t border-white/8 pt-3">
        <p className="text-[10px] text-slate-600">Tandem v1.0.0</p>
        <p className="text-[10px] text-slate-700">© 2025 Aizaz Noor</p>
      </div>
    </aside>
  );
}

function WinBtn({ color, title }: { color: string; title: string }) {
  return (
    <button
      title={title}
      data-tauri-drag-region="false"
      className={cn("w-3 h-3 rounded-full opacity-60 hover:opacity-100 transition-opacity", color)}
    />
  );
}
