import { useEffect, useState } from "react";
import type { AppConfig } from "../lib/rpc";
import type { TandemState } from "../hooks/useTandem";

interface Props { state: TandemState; onSave: (patch: Partial<AppConfig>) => Promise<boolean>; onResetProxy: () => void }
const input = "mt-1.5 bg-slate-900/80 border border-white/15 rounded-lg px-3 py-2.5 text-sm text-white w-full focus:border-sky-400/60 outline-none";
export function SettingsPage({ state, onSave, onResetProxy }: Props) {
  const [draft, setDraft] = useState<AppConfig | null>(null);
  const [port, setPort] = useState("");
  const [serverPort, setServerPort] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (state.config && !dirty) {
      setDraft({ ...state.config, adapter_weights: { ...state.config.adapter_weights } });
      setPort(String(state.config.proxy_port));
      setServerPort(String(state.config.server_port));
    }
  }, [state.config, dirty]);
  if (!draft) return <p className="text-sm text-slate-400">Waiting for settings from the network backend?</p>;
  const running = state.bondingActive || state.engineState !== "DISCONNECTED";
  const edit = (patch: Partial<AppConfig>) => { setDraft({ ...draft, ...patch }); setDirty(true); setSaved(false); };
  const save = async () => {
    const proxyPort = Number(port), cloudPort = Number(serverPort);
    if (![proxyPort, cloudPort].every(p => Number.isInteger(p) && p >= 1 && p <= 65535)) {
      setError("Ports must be whole numbers between 1 and 65535."); return;
    }
    setError(null); setSaved(false);
    if (await onSave({ ...draft, proxy_port: proxyPort, server_port: cloudPort })) {
      setDirty(false); setSaved(true);
    }
  };
  const toggle = (key: "auto_connect_on_launch" | "auto_system_proxy" | "auto_reconnect" | "insecure", label: string) => (
    <label className="flex items-center gap-3 text-sm text-slate-200 cursor-pointer">
      <input type="checkbox" className="accent-sky-500 w-4 h-4" checked={draft[key]} onChange={e => edit({ [key]: e.target.checked })} />{label}
    </label>
  );
  return <div className="h-full overflow-y-auto pr-1">
    {running && <p className="mb-3 text-sm text-amber-300">Disconnect before changing settings.</p>}
    {error && <p role="alert" className="mb-3 text-sm text-red-300">{error}</p>}
    <fieldset disabled={!state.connected || running || state.loading} className="flex flex-col gap-4 disabled:opacity-60">
      <section className="card flex flex-col gap-4">
        <div><h2 className="text-sm font-semibold text-white">General</h2><p className="text-xs text-slate-400 mt-1">Choose how Tandem connects and reconnects.</p></div>
        <label className="text-sm text-slate-300">Mode
          <select className={input} value={draft.mode} onChange={e => edit({ mode: e.target.value as AppConfig["mode"] })}>
            <option value="local_dispatcher">Local Dispatcher</option><option value="cloud_bonding">Cloud Bonding</option>
          </select>
        </label>
        {toggle("auto_connect_on_launch", "Connect automatically on launch")}
        {toggle("auto_system_proxy", "Set the system proxy for local mode")}
        {toggle("auto_reconnect", "Reconnect cloud tunnel after connection loss")}
        <p className="text-xs text-slate-400">A system-wide kill switch is not supported. Traffic outside the proxy is not blocked.</p>
        {draft.kill_switch && <button className="btn-danger" onClick={() => edit({ kill_switch: false })}>Disable unsupported kill-switch setting</button>}
      </section>
      <section className="card flex flex-col gap-4">
        <div><h2 className="text-sm font-semibold text-white">Local Dispatcher</h2><p className="text-xs text-slate-400 mt-1">Route separate app connections through available adapters.</p></div>
        <label className="text-sm text-slate-300">Proxy port<input className={input} type="number" min={1} max={65535} value={port} onChange={e => { setPort(e.target.value); setDirty(true); setSaved(false); }} /></label>
        <label className="text-sm text-slate-300">Distribution
          <select className={input} value={draft.distribution_strategy} onChange={e => edit({ distribution_strategy: e.target.value as AppConfig["distribution_strategy"] })}>
            <option value="round_robin">Round robin</option><option value="weighted">Weighted connections</option>
          </select>
        </label>
        {draft.distribution_strategy === "weighted" && state.adapters.map(a => <label key={a.name} className="text-sm text-slate-300">{a.name} weight (1–100)
          <input className={input} type="number" min={1} max={100} value={draft.adapter_weights[a.name] ?? 1} onChange={e => edit({ adapter_weights: { ...draft.adapter_weights, [a.name]: Number(e.target.value) } })} />
        </label>)}
        <p className="text-xs text-slate-400">Distributes separate TCP connections across selected adapters. A single download connection uses one adapter.</p>
      </section>
      <section className="card flex flex-col gap-4">
        <div><h2 className="text-sm font-semibold text-white">Cloud Bonding</h2><p className="text-xs text-slate-400 mt-1">Requires a compatible server and administrator rights.</p></div>
        <label className="text-sm text-slate-300">Server host<input className={input} value={draft.server_host} onChange={e => edit({ server_host: e.target.value })} /></label>
        <label className="text-sm text-slate-300">Server port<input className={input} type="number" min={1} max={65535} value={serverPort} onChange={e => { setServerPort(e.target.value); setDirty(true); setSaved(false); }} /></label>
        <label className="text-sm text-slate-300">Auth key<input className={input} type="password" autoComplete="off" value={draft.auth_key} onChange={e => edit({ auth_key: e.target.value })} /></label>
        {toggle("insecure", "Allow an unverified server certificate")}
      </section>
      <button onClick={() => void save()} className="btn-primary w-full py-3">{state.loading ? "Saving…" : saved ? "Saved" : "Save Settings"}</button>
    </fieldset>
    <section className="card mt-4 flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-white">Diagnostics</h2>
      <p className="text-xs text-slate-400">Reset disconnects Tandem and clears the system proxy, including a proxy configured by another app.</p>
      <button disabled={!state.connected || state.loading} onClick={onResetProxy} className="btn-danger">Reset system proxy</button>
    </section>
  </div>;
}
