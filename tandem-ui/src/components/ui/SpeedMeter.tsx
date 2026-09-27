import { motion } from "framer-motion";
import { ArrowDown, ArrowUp } from "lucide-react";
import { formatSpeed } from "../../lib/utils";

interface SpeedMeterProps {
  rxMbps: number;
  txMbps: number;
  active: boolean;
}

export function SpeedMeter({ rxMbps, txMbps, active }: SpeedMeterProps) {
  const dl = formatSpeed(rxMbps);
  const ul = formatSpeed(txMbps);

  return (
    <div className="flex items-stretch gap-4">
      {/* Download */}
      <motion.div
        className="flex-1 card flex flex-col items-center gap-1 py-5"
        animate={active ? { borderColor: "rgba(52,211,153,0.3)" } : { borderColor: "rgba(255,255,255,0.10)" }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`p-1.5 rounded-lg ${active ? "bg-emerald-400/15" : "bg-slate-700/40"}`}>
            <ArrowDown className={`w-4 h-4 ${active ? "text-emerald-400" : "text-slate-500"}`} strokeWidth={2.5} />
          </div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Download</span>
        </div>
        <motion.span
          key={dl.value}
          initial={{ scale: 0.9, opacity: 0.6 }}
          animate={{ scale: 1,   opacity: 1 }}
          className="speed-value text-emerald-300"
        >
          {active ? dl.value : "—"}
        </motion.span>
        <span className="speed-unit">{active ? dl.unit : ""}</span>
      </motion.div>

      {/* Upload */}
      <motion.div
        className="flex-1 card flex flex-col items-center gap-1 py-5"
        animate={active ? { borderColor: "rgba(251,191,36,0.3)" } : { borderColor: "rgba(255,255,255,0.10)" }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`p-1.5 rounded-lg ${active ? "bg-amber-400/15" : "bg-slate-700/40"}`}>
            <ArrowUp className={`w-4 h-4 ${active ? "text-amber-400" : "text-slate-500"}`} strokeWidth={2.5} />
          </div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Upload</span>
        </div>
        <motion.span
          key={ul.value}
          initial={{ scale: 0.9, opacity: 0.6 }}
          animate={{ scale: 1,   opacity: 1 }}
          className="speed-value text-amber-300"
        >
          {active ? ul.value : "—"}
        </motion.span>
        <span className="speed-unit">{active ? ul.unit : ""}</span>
      </motion.div>
    </div>
  );
}
