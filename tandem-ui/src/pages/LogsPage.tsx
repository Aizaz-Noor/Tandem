import { useEffect, useRef, useState } from "react";
import { Trash2, Circle } from "lucide-react";
import { rpc } from "../lib/rpc";

interface LogEntry {
  ts: string;
  level: "info" | "warn" | "error" | "debug";
  msg: string;
}

const LEVEL_COLOR = {
  info:  "text-slate-400",
  debug: "text-slate-600",
  warn:  "text-amber-400",
  error: "text-red-400",
} as const;

export function LogsPage() {
  const [entries, setEntries] = useState<LogEntry[]>([
    { ts: new Date().toISOString(), level: "info", msg: "Tandem UI started. Connecting to sidecar…" },
  ]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const addLog = (level: LogEntry["level"]) => (data: unknown) => {
      const msg = typeof data === "string" ? data : JSON.stringify(data);
      setEntries((prev) => [
        ...prev.slice(-499),
        { ts: new Date().toISOString(), level, msg },
      ]);
    };

    const unsubs = [
      rpc.on("log_info",  addLog("info")),
      rpc.on("log_warn",  addLog("warn")),
      rpc.on("log_error", addLog("error")),
      rpc.on("bonding_state", (data) => {
        const d = data as { active: boolean; mode?: string };
        const msg = d.active
          ? `Bonding started — mode: ${d.mode ?? "unknown"}`
          : "Bonding stopped";
        addLog("info")(msg);
      }),
      rpc.on("engine_state", (data) => {
        const d = data as { state: string };
        addLog("info")(`Engine state → ${d.state}`);
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Activity Log</h2>
          <p className="text-xs text-slate-500 mt-0.5">{entries.length} entries</p>
        </div>
        <button
          onClick={() => setEntries([])}
          className="btn-ghost text-xs"
          title="Clear logs"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto card font-mono text-xs leading-relaxed">
        {entries.map((entry, i) => (
          <div key={i} className="flex gap-3 py-0.5 hover:bg-white/4 px-1 rounded group">
            <span className="text-slate-600 shrink-0 tabular-nums">
              {new Date(entry.ts).toLocaleTimeString()}
            </span>
            <Circle
              className={`w-2 h-2 mt-1 shrink-0 fill-current ${LEVEL_COLOR[entry.level]}`}
            />
            <span className={LEVEL_COLOR[entry.level]}>{entry.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
