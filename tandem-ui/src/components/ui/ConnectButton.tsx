import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Zap, ZapOff } from "lucide-react";
import { cn } from "../../lib/utils";

interface ConnectButtonProps {
  active: boolean;
  loading: boolean;
  disabled: boolean;
  onClick: () => void;
}

export function ConnectButton({ active, loading, disabled, onClick }: ConnectButtonProps) {
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled || loading}
      whileHover={!disabled && !loading ? { scale: 1.02 } : {}}
      whileTap={!disabled && !loading ? { scale: 0.97 } : {}}
      className={cn(
        "relative w-full py-3.5 rounded-2xl text-sm font-bold tracking-wide",
        "transition-all duration-300 overflow-hidden",
        active
          ? "bg-red-600/80 hover:bg-red-500 text-white border border-red-500/50"
          : "bg-brand-600 hover:bg-brand-500 text-white border border-brand-500/50",
        (disabled || loading) && "opacity-50 cursor-not-allowed"
      )}
    >
      {/* Glow ring when active */}
      {active && (
        <motion.div
          className="absolute inset-0 rounded-2xl"
          animate={{ boxShadow: ["0 0 0px rgba(239,68,68,0)", "0 0 20px rgba(239,68,68,0.35)", "0 0 0px rgba(239,68,68,0)"] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}
      {!active && (
        <motion.div
          className="absolute inset-0 rounded-2xl"
          animate={{ boxShadow: ["0 0 0px rgba(99,102,241,0)", "0 0 20px rgba(99,102,241,0.3)", "0 0 0px rgba(99,102,241,0)"] }}
          transition={{ duration: 2.5, repeat: Infinity }}
        />
      )}

      <AnimatePresence mode="wait">
        {loading ? (
          <motion.span
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center gap-2"
          >
            <Loader2 className="w-4 h-4 animate-spin" />
            {active ? "Stopping…" : "Starting…"}
          </motion.span>
        ) : active ? (
          <motion.span
            key="stop"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-center gap-2"
          >
            <ZapOff className="w-4 h-4" />
            Stop Bonding
          </motion.span>
        ) : (
          <motion.span
            key="start"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Start Bonding
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
