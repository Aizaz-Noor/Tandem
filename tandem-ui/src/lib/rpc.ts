/**
 * Tandem WebSocket RPC Client
 * Connects to the Python sidecar on ws://127.0.0.1:7878
 * and provides a typed, promise-based interface for all RPC calls.
 */

export interface Adapter {
  name: string;
  description: string;
  type: "wifi" | "ethernet" | "usb_tether" | "other";
  ip: string;
  status: string;
  speed: string;
}

export interface TelemetryStats {
  elapsed_seconds: number;
  adapters: Record<string, {
    rx_mbps: number;
    tx_mbps: number;
    rx_mb_s: number;
    tx_mb_s: number;
  }>;
  total: {
    rx_mbps: number;
    tx_mbps: number;
    rx_mb_s: number;
    tx_mb_s: number;
  };
}

export interface AppConfig {
  mode: "local_dispatcher" | "cloud_bonding";
  proxy_port: number;
  distribution_strategy: "round_robin" | "weighted";
  auto_system_proxy: boolean;
  adapter_weights: Record<string, number>;
  server_host: string;
  server_port: number;
  auth_key: string;
  scheduler: string;
  insecure: boolean;
  dns: string[];
  kill_switch: boolean;
  auto_reconnect: boolean;
  auto_connect_on_launch: boolean;
  selected_adapters: string[];
}

export interface StateSnapshot {
  config: AppConfig;
  adapters: Adapter[];
  bonding_active: boolean;
}

type EventHandler = (data: unknown) => void;

export class TandemRPC {
  private ws: WebSocket | null = null;
  private pending = new Map<string | number, {
    resolve: (v: unknown) => void;
    reject: (e: Error) => void;
  }>();
  private idCounter = 0;
  private listeners = new Map<string, Set<EventHandler>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;

  public connected = false;
  public onConnectionChange?: (connected: boolean) => void;

  constructor(url = "ws://127.0.0.1:7878") {
    this.url = url;
  }

  connect() {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.connected = true;
      this.onConnectionChange?.(true);
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.ws.onmessage = (ev) => {
      let msg: Record<string, unknown>;
      try { msg = JSON.parse(ev.data as string); } catch { return; }

      // Server-initiated event
      if ("event" in msg) {
        const handlers = this.listeners.get(msg.event as string);
        handlers?.forEach((h) => h(msg.data));
        return;
      }

      // RPC response
      const id = msg.id as string | number;
      const pending = this.pending.get(id);
      if (!pending) return;
      this.pending.delete(id);

      if ("error" in msg) {
        pending.reject(new Error(msg.error as string));
      } else {
        pending.resolve(msg.result);
      }
    };

    this.ws.onerror = () => {
      /* errors are followed by onclose */
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.onConnectionChange?.(false);
      // Reject all pending calls
      this.pending.forEach((p) => p.reject(new Error("WebSocket closed")));
      this.pending.clear();
      this._scheduleReconnect();
    };
  }

  private _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  /** Subscribe to a server-pushed event. */
  on(event: string, handler: EventHandler): () => void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(handler);
    return () => this.listeners.get(event)?.delete(handler);
  }

  /** Send an RPC call and await its typed result. */
  private call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error("Not connected to Tandem sidecar"));
        return;
      }
      const id = ++this.idCounter;
      this.pending.set(id, {
        resolve: (v) => resolve(v as T),
        reject,
      });
      this.ws.send(JSON.stringify({ id, method, params: params ?? null }));
    });
  }

  // ── Typed API wrappers ───────────────────────────────────────────

  getAdapters()                        { return this.call<Adapter[]>("get_adapters"); }
  getConfig()                          { return this.call<AppConfig>("get_config"); }
  saveConfig(data: Partial<AppConfig>) { return this.call<boolean>("save_config", data as Record<string, unknown>); }
  startBonding(params?: { mode?: string; selected_adapters?: string[] }) {
    return this.call<{ ok: boolean; message?: string; mode?: string }>("start_bonding", params as Record<string, unknown>);
  }
  stopBonding()  { return this.call<{ ok: boolean }>("stop_bonding"); }
  getStatus()    { return this.call<{ bonding_active: boolean; engine_state: string }>("get_status"); }
  resetProxy()   { return this.call<boolean>("reset_proxy"); }
  startCloud(params: { server_host: string; server_port: number; auth_key: string }) {
    return this.call<{ ok: boolean }>("start_cloud", params as Record<string, unknown>);
  }
  stopCloud()    { return this.call<{ ok: boolean }>("stop_cloud"); }
}

// Singleton shared across the app
export const rpc = new TandemRPC();
