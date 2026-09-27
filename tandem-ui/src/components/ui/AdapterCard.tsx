import { motion } from "framer-motion";
import { Wifi, Network, Smartphone, Globe, CheckCircle2, Circle } from "lucide-react";
import { cn } from "../../lib/utils";
import type { Adapter } from "../../lib/rpc";

const ICON_MAP = {
  wifi:       Wifi,
  ethernet:   Network,
  usb_tether: Smartphone,
  other:      Globe,
} as const;

const TYPE_LABEL = {
  wifi:       "Wi-Fi",
  ethernet:   "Ethernet",
  usb_tether: "USB Tether",
  other:      "Network",
} as const;

const TYPE_COLOR = {
  wifi:       "text-sky-400",
  ethernet:   "text-emerald-400",
  usb_tether: "text-violet-400",
  other:      "text-slate-400",
} as const;

const TYPE_BG = {
  wifi:       "bg-sky-400/10 border-sky-400/20",
  ethernet:   "bg-emerald-400/10 border-emerald-400/20",
  usb_tether: "bg-violet-400/10 border-violet-400/20",
  other:      "bg-slate-400/10 border-slate-400/20",
} as const;

interface AdapterCardProps {
  adapter: Adapter;
  selected: boolean;
  disabled?: boolean;
  rxMbps?: number;
  txMbps?: number;
  onToggle: (name: string) => void;
}

export function AdapterCard({ adapter, selected, disabled = false, rxMbps = 0, txMbps = 0, onToggle }: AdapterCardProps) {
  const Icon = ICON_MAP[adapter.type as keyof typeof ICON_MAP] ?? Globe;
  const typeColor = TYPE_COLOR[adapter.type as keyof typeof TYPE_COLOR] ?? TYPE_COLOR.other;
  const typeBg    = TYPE_BG[adapter.type as keyof typeof TYPE_BG] ?? TYPE_BG.other;
  const typeLabel = TYPE_LABEL[adapter.type as keyof typeof TYPE_LABEL] ?? "Network";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      role="checkbox"
      aria-checked={selected}
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onKeyDown={e => { if (!disabled && (e.key === " " || e.key === "Enter")) { e.preventDefault(); onToggle(adapter.name); } }}
      onClick={() => { if (!disabled) onToggle(adapter.name); }}
      className={cn(
        "card glass-hover cursor-pointer select-none transition-all duration-200",
        selected
          ? "border-brand-500/50 bg-brand-600/10"
          : "hover:border-white/20"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon badge */}
        <div className={cn("p-2.5 rounded-xl border", typeBg)}>
          <Icon className={cn("w-5 h-5", typeColor)} strokeWidth={1.8} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-white truncate">{adapter.name}</p>
            <span className={cn(
              "text-[10px] font-medium px-1.5 py-0.5 rounded-md border",
              typeBg, typeColor
            )}>
              {typeLabel}
            </span>
          </div>
          <p className="text-xs text-slate-500 truncate mt-0.5">{adapter.ip}</p>

          {/* Speed row — only shown when bonding active */}
          {(rxMbps > 0 || txMbps > 0) && (
            <div className="flex items-center gap-3 mt-2">
              <SpeedBadge direction="down" mbps={rxMbps} />
              <SpeedBadge direction="up"   mbps={txMbps} />
            </div>
          )}
        </div>

        {/* Checkmark */}
        <div className="shrink-0 mt-0.5">
          {selected ? (
            <CheckCircle2 className="w-5 h-5 text-brand-400" />
          ) : (
            <Circle className="w-5 h-5 text-slate-600" />
          )}
        </div>
      </div>
    </motion.div>
  );
}

function SpeedBadge({ direction, mbps }: { direction: "up" | "down"; mbps: number }) {
  const color = direction === "down" ? "text-emerald-400" : "text-amber-400";
  const arrow = direction === "down" ? "↓" : "↑";
  const display = mbps >= 1 ? `${mbps.toFixed(1)}` : `${(mbps * 1000).toFixed(0)}`;
  const unit   = mbps >= 1 ? "Mbps" : "Kbps";

  return (
    <div className="flex items-baseline gap-1">
      <span className={cn("text-xs font-bold font-mono", color)}>{arrow} {display}</span>
      <span className="text-[10px] text-slate-500 font-mono">{unit}</span>
    </div>
  );
}
