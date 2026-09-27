import { useEffect, useRef } from "react";
import { Trash2, Circle } from "lucide-react";

import type { LogEntry } from "../lib/rpc";

const LEVEL_COLOR = {
  info:  "text-slate-400",
  debug: "text-slate-600",
  warn:  "text-amber-400",
  error: "text-red-400",
} as const;

export function LogsPage({ entries, onClear }: { entries: LogEntry[]; onClear: () => void }) {
  const bottomRef = useRef<HTMLDivElement>(null);

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
          onClick={onClear}
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
