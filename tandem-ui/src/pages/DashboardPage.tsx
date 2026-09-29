import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw, Link2Off } from "lucide-react";
import { AdapterCard } from "../components/ui/AdapterCard";
import { SpeedMeter } from "../components/ui/SpeedMeter";
import { ConnectButton } from "../components/ui/ConnectButton";
import { cn } from "../lib/utils";
import type { TandemState } from "../hooks/useTandem";

interface DashboardPageProps {
  state: TandemState;
  onStart: (selected?: string[]) => void;
  onStop: () => void;
  onRefresh: () => void;
  onSelect: (patch: { selected_adapters: string[] }) => Promise<boolean>;
}

export function DashboardPage({ state, onStart, onStop, onRefresh, onSelect }: DashboardPageProps) {
  const selected = new Set(state.config?.selected_adapters ?? []);
  const running = state.bondingActive || state.engineState !== "DISCONNECTED";
  const toggleAdapter = (name: string) => {
    if (running || state.loading || !state.connected) return;
    const next = new Set(selected);
    next.has(name) ? next.delete(name) : next.add(name);
    void onSelect({ selected_adapters: [...next] });
  };

  const handleConnect = () => {
    if (running) {
      onStop();
    } else {
      onStart([...selected]);
    }
  };

  const totalRx = state.telemetry?.total.rx_mbps ?? 0;
  const totalTx = state.telemetry?.total.tx_mbps ?? 0;

  return (
    <div className="flex flex-col gap-5 h-full overflow-y-auto pr-1">
      {/* Speed meters */}
      <SpeedMeter rxMbps={totalRx} txMbps={totalTx} active={state.bondingActive} />

      {/* Adapter list header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Network Adapters</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {state.adapters.length === 0
              ? "No active adapters detected"
              : `${state.adapters.length} adapter${state.adapters.length !== 1 ? "s" : ""} detected`}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="btn-ghost"
          title="Refresh adapters"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Adapter cards */}
      <div className="flex flex-col gap-3">
        <AnimatePresence>
          {state.adapters.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="card flex flex-col items-center gap-2 py-10 text-center"
            >
              <Link2Off className="w-8 h-8 text-slate-600" />
              <p className="text-sm text-slate-500">No active adapters found</p>
              <p className="text-xs text-slate-600">Connect a network interface and click Refresh</p>
            </motion.div>
          ) : (
            state.adapters.map((adapter) => {
              const adapterTelemetry = state.telemetry?.adapters[adapter.name];
              return (
                <AdapterCard
                  key={adapter.name}
                  adapter={adapter}
                  selected={selected.has(adapter.name)}
                  disabled={running || state.loading || !state.connected}
                  rxMbps={adapterTelemetry?.rx_mbps ?? 0}
                  txMbps={adapterTelemetry?.tx_mbps ?? 0}
                  onToggle={toggleAdapter}
                />
              );
            })
          )}
        </AnimatePresence>
      </div>

      <p className="text-xs text-slate-500">No specific selection uses all available adapters. Disconnect to change selection.</p>
      {state.engineState !== "DISCONNECTED" && <p className="text-xs text-slate-400">Cloud: {state.engineState.toLowerCase()}</p>}
      {/* Mode badge */}
      {state.config && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Mode:</span>
          <span className={cn(
            "text-xs font-medium px-2 py-0.5 rounded-md border",
            state.config.mode === "local_dispatcher"
              ? "text-brand-400 bg-brand-500/10 border-brand-500/25"
              : "text-emerald-400 bg-emerald-500/10 border-emerald-500/25"
          )}>
            {state.config.mode === "local_dispatcher" ? "Local Dispatcher" : "Cloud Bonding"}
          </span>
          {state.config.distribution_strategy && state.config.mode === "local_dispatcher" && (
            <span className="text-xs text-slate-600">
              · {state.config.distribution_strategy.replace("_", " ")}
            </span>
          )}
        </div>
      )}

      {/* Connect button — pinned to bottom */}
      <div className="mt-auto pt-2">
        <ConnectButton
          active={running}
          loading={state.loading}
          disabled={!state.connected}
          onClick={handleConnect}
        />
        {!state.connected && (
          <p className="text-center text-xs text-slate-600 mt-2">
            Connecting to the Tandem backend…
          </p>
        )}
      </div>
    </div>
  );
}
