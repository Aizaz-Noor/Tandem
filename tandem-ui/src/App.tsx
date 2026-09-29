import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./components/ui/Sidebar";
import { DashboardPage } from "./pages/DashboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LogsPage } from "./pages/LogsPage";
import { useTandem } from "./hooks/useTandem";

type Page = "dashboard" | "settings" | "logs";

const PAGE_VARIANTS = {
  initial:  { opacity: 0, x: 10 },
  animate:  { opacity: 1, x: 0 },
  exit:     { opacity: 0, x: -10 },
};

const PAGE_TITLES: Record<Page, { title: string; detail: string }> = {
  dashboard: { title: "Dashboard", detail: "Connection overview" },
  settings: { title: "Settings", detail: "Network and cloud configuration" },
  logs: { title: "Activity log", detail: "Connection events and diagnostics" },
};

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const { state, startBonding, stopBonding, refreshAdapters, saveConfig, resetProxy, clearLogs } = useTandem();

  return (
    <div className="flex h-screen w-screen bg-mesh overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        page={page}
        onNavigate={setPage}
        connected={state.connected}
        bondingActive={state.bondingActive}
      />

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="min-h-20 flex items-center justify-between gap-4 px-6 border-b border-white/10 bg-black/10">
          <div>
            <h1 className="text-lg font-semibold text-white">{PAGE_TITLES[page].title}</h1>
            <p className="text-xs text-slate-400 mt-0.5">{PAGE_TITLES[page].detail}</p>
          </div>
          <span className={`shrink-0 text-xs font-medium px-3 py-1.5 rounded-full border ${state.connected
            ? "text-emerald-300 bg-emerald-400/10 border-emerald-400/20"
            : "text-slate-400 bg-white/5 border-white/10"}`}>
            {state.connected ? "Backend ready" : "Backend offline"}
          </span>
        </header>

        {state.error && <div role="alert" className="mx-6 mt-3 text-sm text-red-300">{state.error}</div>}
        {/* Animated page body */}
        <div className="flex-1 overflow-hidden relative p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={page}
              variants={PAGE_VARIANTS}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="absolute inset-6 flex flex-col"
            >
              {page === "dashboard" && (
                <DashboardPage
                  state={state}
                  onStart={startBonding}
                  onStop={stopBonding}
                  onRefresh={refreshAdapters}
                  onSelect={saveConfig}
                />
              )}
              {page === "settings" && (
                <SettingsPage
                  state={state}
                  onSave={saveConfig}
                  onResetProxy={resetProxy}
                />
              )}
              {page === "logs" && <LogsPage entries={state.logs} onClear={clearLogs} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
