import { useCallback, useEffect, useReducer, useRef } from "react";
import { rpc, type Adapter, type AppConfig, type TelemetryStats, type StateSnapshot, type LogEntry } from "../lib/rpc";

export interface TandemState {
  connected: boolean; bondingActive: boolean; engineState: string;
  adapters: Adapter[]; config: AppConfig | null; telemetry: TelemetryStats | null;
  error: string | null; loading: boolean; logs: LogEntry[];
}
const initialState: TandemState = { connected: false, bondingActive: false, engineState: "DISCONNECTED",
  adapters: [], config: null, telemetry: null, error: null, loading: false, logs: [] };
type Action = { patch: Partial<TandemState> } | { log: LogEntry };
export function reducer(state: TandemState, action: Action): TandemState {
  return "log" in action ? { ...state, logs: [...state.logs.slice(-499), action.log] } : { ...state, ...action.patch };
}
export function useTandem() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const busy = useRef(false);
  useEffect(() => {
    rpc.onConnectionChange = connected => dispatch({ patch: connected ? { connected, error: null } :
      { connected, bondingActive: false, engineState: "DISCONNECTED", telemetry: null, loading: false } });
    const unsubs = [
      rpc.on("state_snapshot", value => {
        const data = value as StateSnapshot;
        dispatch({ patch: { config: data.config, adapters: data.adapters, bondingActive: data.bonding_active,
          engineState: data.engine_state, logs: data.logs ?? [], error: null } });
      }),
      rpc.on("bonding_state", value => {
        const data = value as { active: boolean };
        dispatch({ patch: { bondingActive: data.active, ...(!data.active ? { telemetry: null } : {}) } });
      }),
      rpc.on("engine_state", value => {
        const data = value as { state: string; message?: string };
        dispatch({ patch: { engineState: data.state, ...(data.state === "ERROR" ? { error: data.message ?? "Cloud connection failed" } : {}) } });
      }),
      rpc.on("telemetry", value => dispatch({ patch: { telemetry: value as TelemetryStats } })),
      rpc.on("adapters", value => dispatch({ patch: { adapters: value as Adapter[] } })),
      rpc.on("config", value => dispatch({ patch: { config: value as AppConfig } })),
      rpc.on("connection_error", value => dispatch({ patch: { error: String(value) } })),
      rpc.on("log", value => dispatch({ log: value as LogEntry })),
    ];
    void rpc.connect();
    return () => { unsubs.forEach(fn => fn()); rpc.onConnectionChange = undefined; rpc.disconnect(); };
  }, []);

  const action = useCallback(async (work: () => Promise<unknown>): Promise<boolean> => {
    if (busy.current) return false;
    busy.current = true;
    dispatch({ patch: { loading: true, error: null } });
    try { await work(); return true; }
    catch (err) { dispatch({ patch: { error: (err as Error).message } }); return false; }
    finally { busy.current = false; dispatch({ patch: { loading: false } }); }
  }, []);
  const startBonding = useCallback((selected?: string[]) => action(async () => {
    const result = await rpc.startBonding({ selected_adapters: selected });
    if (!result.ok) throw new Error(result.message ?? "Connection failed");
  }), [action]);
  const stopBonding = useCallback(() => action(() => rpc.stopBonding()), [action]);
  const refreshAdapters = useCallback(() => action(async () => {
    dispatch({ patch: { adapters: await rpc.getAdapters() } });
  }), [action]);
  const saveConfig = useCallback((patch: Partial<AppConfig>) => action(async () => {
    dispatch({ patch: { config: await rpc.saveConfig(patch) } });
  }), [action]);
  const resetProxy = useCallback(() => action(() => rpc.resetProxy()), [action]);
  const clearLogs = useCallback(() => dispatch({ patch: { logs: [] } }), []);
  return { state, startBonding, stopBonding, refreshAdapters, saveConfig, resetProxy, clearLogs };
}
