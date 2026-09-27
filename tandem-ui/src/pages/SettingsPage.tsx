import { useState } from "react";
import { motion } from "framer-motion";
import { Save, ShieldOff } from "lucide-react";
import { cn } from "../lib/utils";
import type { AppConfig } from "../lib/rpc";
import type { TandemState } from "../hooks/useTandem";

interface SettingsPageProps {
  state: TandemState;
  onSave: (patch: Partial<AppConfig>) => void;
  onResetProxy: () => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card flex flex-col gap-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <p className="text-sm font-medium text-slate-200">{label}</p>
        {hint && <p className="text-xs text-slate-500 mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={cn("relative toggle-bg", value ? "bg-brand-600" : "bg-slate-700")}
    >
      <motion.div
        className="toggle-dot"
        animate={{ x: value ? 20 : 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      />
    </button>
  );
}

export function SettingsPage({ state, onSave, onResetProxy }: SettingsPageProps) {
  const cfg = state.config;
  const [localPort, setLocalPort] = useState(String(cfg?.proxy_port ?? 8080));
  const [localHost, setLocalHost] = useState(cfg?.server_host ?? "");
  const [localSPort, setLocalSPort] = useState(String(cfg?.server_port ?? 443));
  const [localKey, setLocalKey] = useState(cfg?.auth_key ?? "");
  const [saved, setSaved] = useState(false);

  if (!cfg) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Connect to sidecar to load settings…
      </div>
    );
  }

  const saveAll = () => {
    onSave({
      proxy_port:            parseInt(localPort, 10) || 8080,
      server_host:           localHost,
      server_port:           parseInt(localSPort, 10) || 443,
      auth_key:              localKey,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputCls = "w-full bg-slate-800/60 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500/60";

  return (
    <div className="flex flex-col gap-4 h-full overflow-y-auto pr-1">
      {/* General */}
      <Section title="General">
        <Field label="Mode" hint="How traffic is distributed across adapters">
          <select
            value={cfg.mode}
            onChange={(e) => onSave({ mode: e.target.value as AppConfig["mode"] })}
            className={cn(inputCls, "w-48")}
          >
            <option value="local_dispatcher">Local Dispatcher</option>
            <option value="cloud_bonding">Cloud Bonding</option>
          </select>
        </Field>

        <Field label="Auto-connect on launch" hint="Start bonding when the app opens">
          <Toggle
            value={cfg.auto_connect_on_launch}
            onChange={(v) => onSave({ auto_connect_on_launch: v })}
          />
        </Field>

        <Field label="Set system proxy automatically" hint="Configures Windows proxy settings">
          <Toggle
            value={cfg.auto_system_proxy}
            onChange={(v) => onSave({ auto_system_proxy: v })}
          />
        </Field>

        <Field label="Kill switch" hint="Block internet if bonding drops unexpectedly">
          <Toggle
            value={cfg.kill_switch}
            onChange={(v) => onSave({ kill_switch: v })}
          />
        </Field>
      </Section>

      {/* Local Dispatcher */}
      <Section title="Local Dispatcher">
        <Field label="Proxy port" hint="SOCKS5 / HTTP proxy listens on localhost:PORT">
          <input
            type="number"
            value={localPort}
            min={1024} max={65535}
            onChange={(e) => setLocalPort(e.target.value)}
            className={cn(inputCls, "w-24 text-center")}
          />
        </Field>

        <Field label="Distribution strategy" hint="How traffic is spread across adapters">
          <select
            value={cfg.distribution_strategy}
            onChange={(e) => onSave({ distribution_strategy: e.target.value as AppConfig["distribution_strategy"] })}
            className={cn(inputCls, "w-40")}
          >
            <option value="round_robin">Round Robin</option>
            <option value="weighted">Weighted</option>
          </select>
        </Field>
      </Section>

      {/* Cloud Bonding */}
      <Section title="Cloud Bonding (VPN Gateway)">
        <Field label="Server host">
          <input
            value={localHost}
            onChange={(e) => setLocalHost(e.target.value)}
            placeholder="e.g. 150.136.212.160"
            className={cn(inputCls, "w-56")}
          />
        </Field>
        <Field label="Server port">
          <input
            type="number"
            value={localSPort}
            min={1} max={65535}
            onChange={(e) => setLocalSPort(e.target.value)}
            className={cn(inputCls, "w-24 text-center")}
          />
        </Field>
        <Field label="Auth key">
          <input
            type="password"
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder="•••••••••"
            className={cn(inputCls, "w-56")}
          />
        </Field>
      </Section>

      {/* Danger zone */}
      <Section title="Diagnostics">
        <Field label="Reset system proxy" hint="Clears any orphaned Windows proxy settings and restores direct internet">
          <button onClick={onResetProxy} className="btn-danger text-xs py-1.5 px-3">
            <ShieldOff className="w-3.5 h-3.5" />
            Reset Now
          </button>
        </Field>
      </Section>

      {/* Save */}
      <div className="mt-auto pt-2">
        <motion.button
          onClick={saveAll}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.98 }}
          className={cn(
            "btn-primary w-full py-3",
            saved && "bg-emerald-600 hover:bg-emerald-600 border-emerald-500/50"
          )}
        >
          <Save className="w-4 h-4" />
          {saved ? "Saved!" : "Save Settings"}
        </motion.button>
      </div>
    </div>
  );
}
