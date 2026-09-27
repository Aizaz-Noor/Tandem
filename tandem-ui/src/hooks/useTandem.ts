/**
 * useTandem — central state hook
 * Connects to the Python sidecar, listens for events, and exposes actions.
 */
import { useCallback, useEffect, useReducer, useRef } from "react";
import { rpc, type Adapter, type AppConfig, type TelemetryStats } from "../lib/rpc";

// ─── State ────────────────────────────────────────────────────────────────────

export interface TandemState {
  connected: boolean;          // sidecar WebSocket connected
  bondingActive: boolean;
  engineState: string;         // DISCONNECTED | CONNECTING | CONNECTED
  adapters: Adapter[];
  config: AppConfig | null;
  telemetry: TelemetryStats | null;
  error: string | null;
  loading: boolean;
}

type Action =
  | { type: "SET_CONNECTED";     payload: boolean }
  | { type: "SET_SNAPSHOT";      payload: { config: AppConfig; adapters: Adapter[]; bonding_active: boolean } }
  | { type: "SET_BONDING";       payload: { active: boolean; mode?: string } }
  | { type: "SET_ENGINE_STATE";  payload: { state: string } }
  | { type: "SET_TELEMETRY";     payload: TelemetryStats }
  | { type: "SET_ADAPTERS";      payload: Adapter[] }
  | { type: "SET_CONFIG";        payload: AppConfig }
  | { type: "SET_ERROR";         payload: string | null }
  | { type: "SET_LOADING";       payload: boolean };

const initialState: TandemState = {
  connected: false,
  bondingActive: false,
  engineState: "DISCONNECTED",
  adapters: [],
  config: null,
  telemetry: null,
  error: null,
  loading: false,
};

function reducer(state: TandemState, action: Action): TandemState {
  switch (action.type) {
    case "SET_CONNECTED":    return { ...state, connected: action.payload };
    case "SET_SNAPSHOT":     return {
      ...state,
      config: action.payload.config,
      adapters: action.payload.adapters,
      bondingActive: action.payload.bonding_active,
    };
    case "SET_BONDING":      return { ...state, bondingActive: action.payload.active };
    case "SET_ENGINE_STATE": return { ...state, engineState: action.payload.state };
    case "SET_TELEMETRY":    return { ...state, telemetry: action.payload };
    case "SET_ADAPTERS":     return { ...state, adapters: action.payload };
    case "SET_CONFIG":       return { ...state, config: action.payload };
    case "SET_ERROR":        return { ...state, error: action.payload };
    case "SET_LOADING":      return { ...state, loading: action.payload };
    default:                 return state;
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useTandem() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const cleanups = useRef<Array<() => void>>([]);

  useEffect(() => {
    // Handle connection changes
    rpc.onConnectionChange = (c) => dispatch({ type: "SET_CONNECTED", payload: c });

    // Server events
    const unsubs = [
      rpc.on("state_snapshot", (data) => {
        const d = data as { config: AppConfig; adapters: Adapter[]; bonding_active: boolean };
        dispatch({ type: "SET_SNAPSHOT", payload: d });
      }),
      rpc.on("bonding_state", (data) => {
        dispatch({ type: "SET_BONDING", payload: data as { active: boolean; mode?: string } });
      }),
      rpc.on("engine_state", (data) => {
        dispatch({ type: "SET_ENGINE_STATE", payload: data as { state: string } });
      }),
      rpc.on("telemetry", (data) => {
        dispatch({ type: "SET_TELEMETRY", payload: data as TelemetryStats });
      }),
    ];

    cleanups.current = unsubs;
    rpc.connect();

    return () => {
      cleanups.current.forEach((fn) => fn());
    };
  }, []);

  // ── Actions ────────────────────────────────────────────────────────────────

  const startBonding = useCallback(async (selectedAdapters?: string[]) => {
    dispatch({ type: "SET_LOADING", payload: true });
    dispatch({ type: "SET_ERROR",   payload: null });
    try {
      const result = await rpc.startBonding({ selected_adapters: selectedAdapters });
      if (!result.ok) {
        dispatch({ type: "SET_ERROR", payload: result.message ?? "Failed to start bonding" });
      }
    } catch (err) {
      dispatch({ type: "SET_ERROR", payload: (err as Error).message });
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  }, []);

  const stopBonding = useCallback(async () => {
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      await rpc.stopBonding();
    } catch (err) {
      dispatch({ type: "SET_ERROR", payload: (err as Error).message });
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  }, []);

  const refreshAdapters = useCallback(async () => {
    try {
      const adapters = await rpc.getAdapters();
      dispatch({ type: "SET_ADAPTERS", payload: adapters });
    } catch { /* silent */ }
  }, []);

  const saveConfig = useCallback(async (patch: Partial<AppConfig>) => {
    try {
      await rpc.saveConfig(patch);
      if (state.config) {
        dispatch({ type: "SET_CONFIG", payload: { ...state.config, ...patch } });
      }
    } catch (err) {
      dispatch({ type: "SET_ERROR", payload: (err as Error).message });
    }
  }, [state.config]);

  const resetProxy = useCallback(async () => {
    try {
      await rpc.resetProxy();
    } catch { /* silent */ }
  }, []);

  return {
    state,
    startBonding,
    stopBonding,
    refreshAdapters,
    saveConfig,
    resetProxy,
  };
}
