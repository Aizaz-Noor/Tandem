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
        {/* Page header */}
        <div
          data-tauri-drag-region="true"
          className="h-10 flex items-center px-6 border-b border-white/8 bg-black/10"
        >
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest select-none">
            {page === "dashboard" ? "Dashboard" : page === "settings" ? "Settings" : "Logs"}
          </span>
        </div>

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
