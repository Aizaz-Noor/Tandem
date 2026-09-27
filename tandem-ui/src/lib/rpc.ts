import { invoke, isTauri } from "@tauri-apps/api/core";
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
  engine_state: string;
  logs: LogEntry[];
}

export interface LogEntry { ts: string; level: "info" | "warn" | "error" | "debug"; msg: string }
export interface Connection { url: string; token: string }
type EventHandler = (data: unknown) => void;
const desktopConnection = async (): Promise<Connection> => {
  if (!isTauri()) throw new Error("Open Tandem desktop to connect to the network backend.");
  return invoke<Connection>("sidecar_connection");
};

export class TandemRPC {
  private ws: WebSocket | null = null;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: ReturnType<typeof setTimeout> }>();
  private listeners = new Map<string, Set<EventHandler>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private handshakeTimer: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;
  private connecting = false;
  private stopped = false;
  private idCounter = 0;
  public connected = false;
  public onConnectionChange?: (connected: boolean) => void;

  constructor(private connectionProvider = desktopConnection, private timeoutMs = 30000) {}

  private emit(event: string, data: unknown) {
    this.listeners.get(event)?.forEach(h => h(data));
  }

  async connect() {
    if (this.connecting || (this.ws && this.ws.readyState <= WebSocket.OPEN)) return;
    this.stopped = false;
    this.connecting = true;
    const generation = ++this.generation;
    try {
      const info = await this.connectionProvider();
      if (generation !== this.generation) return;
      const ws = new WebSocket(info.url);
      this.ws = ws;
      this.handshakeTimer = setTimeout(() => ws.close(), this.timeoutMs);
      ws.onopen = () => ws.send(JSON.stringify({ token: info.token }));
      ws.onmessage = ev => {
        if (generation !== this.generation) return;
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(ev.data as string);
          if (!msg || typeof msg !== "object" || Array.isArray(msg)) return;
        } catch { return; }
        if (msg.event === "state_snapshot") {
          if (this.handshakeTimer) clearTimeout(this.handshakeTimer);
          this.handshakeTimer = null;
          this.connected = true;
          this.onConnectionChange?.(true);
        }
        if (typeof msg.event === "string") { this.emit(msg.event, msg.data); return; }
        const id = msg.id as number;
        const pending = this.pending.get(id);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(id);
        if ("error" in msg) pending.reject(new Error(String(msg.error)));
        else pending.resolve(msg.result);
      };
      ws.onerror = () => this.emit("connection_error", "Network backend connection failed.");
      ws.onclose = () => {
        if (generation !== this.generation) return;
        this.ws = null;
        this.clearPending("Backend disconnected");
        this.scheduleReconnect();
      };
    } catch (err) {
      if (generation !== this.generation) return;
      this.emit("connection_error", (err as Error).message);
      this.scheduleReconnect();
    } finally {
      if (generation === this.generation) this.connecting = false;
    }
  }

  private clearPending(message: string) {
    if (this.handshakeTimer) clearTimeout(this.handshakeTimer);
    this.handshakeTimer = null;
    this.connected = false;
    this.onConnectionChange?.(false);
    this.pending.forEach(p => { clearTimeout(p.timer); p.reject(new Error(message)); });
    this.pending.clear();
  }

  disconnect() {
    this.stopped = true;
    ++this.generation;
    this.connecting = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    const ws = this.ws;
    this.ws = null;
    if (ws) { ws.onclose = null; ws.onopen = null; ws.onmessage = null; ws.close(); }
    this.clearPending("Backend disconnected");
  }

  private scheduleReconnect() {
    if (this.stopped || this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => { this.reconnectTimer = null; void this.connect(); }, 2000);
  }

  on(event: string, handler: EventHandler): () => void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(handler);
    return () => { this.listeners.get(event)?.delete(handler); };
  }

  private call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
    return new Promise((resolve, reject) => {
      if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error("Not connected to the network backend")); return;
      }
      const id = ++this.idCounter;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("Backend request timed out. Reconnecting to refresh its status."));
        this.ws?.close();
      }, this.timeoutMs);
      this.pending.set(id, { resolve: value => resolve(value as T), reject, timer });
      try { this.ws.send(JSON.stringify({ id, method, params: params ?? null })); }
      catch (err) { clearTimeout(timer); this.pending.delete(id); reject(err); }
    });
  }

  getAdapters() { return this.call<Adapter[]>("get_adapters"); }
  getConfig() { return this.call<AppConfig>("get_config"); }
  saveConfig(patch: Partial<AppConfig>) { return this.call<AppConfig>("save_config", patch); }
  startBonding(params?: { mode?: string; selected_adapters?: string[] }) {
    return this.call<{ ok: boolean; message?: string; mode?: string }>("start_bonding", params);
  }
  stopBonding() { return this.call<{ ok: boolean }>("stop_bonding"); }
  resetProxy() { return this.call<boolean>("reset_proxy"); }
  getStatus() { return this.call<{ bonding_active: boolean; engine_state: string }>("get_status"); }
}
export const rpc = new TandemRPC();
