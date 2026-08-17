"use client";

import { useEffect, useState } from "react";
import { Zap, ArrowLeft, Save, RotateCcw, CheckCircle, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface Setting {
  value: string;
  description: string;
  is_default: boolean;
}

interface Settings {
  poll_interval_seconds: Setting;
  signal_threshold_pct: Setting;
  max_trade_size_usd: Setting;
  max_open_positions: Setting;
  cooldown_minutes: Setting;
  paper_trading: Setting;
  markets_limit: Setting;
  notifications_enabled: Setting;
}

const SETTING_LABELS: Record<string, { label: string; type: string; unit?: string }> = {
  poll_interval_seconds: { label: "Poll Interval", type: "number", unit: "seconds" },
  signal_threshold_pct: { label: "Signal Threshold", type: "number", unit: "%" },
  max_trade_size_usd: { label: "Max Trade Size", type: "number", unit: "$" },
  max_open_positions: { label: "Max Open Positions", type: "number", unit: "positions" },
  cooldown_minutes: { label: "Trade Cooldown", type: "number", unit: "minutes" },
  paper_trading: { label: "Paper Trading Mode", type: "boolean" },
  markets_limit: { label: "Markets to Watch", type: "number", unit: "markets" },
  notifications_enabled: { label: "Browser Notifications", type: "boolean" },
};

const GROUPS = [
  { title: "Trading Engine", color: "text-[#00C48C]", keys: ["poll_interval_seconds", "markets_limit", "signal_threshold_pct"] },
  { title: "Risk Controls", color: "text-red-400", keys: ["max_trade_size_usd", "max_open_positions", "cooldown_minutes"] },
  { title: "Account", color: "text-yellow-400", keys: ["paper_trading", "notifications_enabled"] },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);

  async function fetchSettings() {
    try {
      const r = await apiFetch("/api/settings");
      if (r.ok) {
        const data = await r.json();
        setSettings(data);
        const vals: Record<string, string> = {};
        for (const [key, s] of Object.entries(data as Settings)) {
          vals[key] = (s as Setting).value;
        }
        setValues(vals);
      }
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => { fetchSettings(); }, []);

  async function saveSetting(key: string, overrideValue?: string) {
    const val = overrideValue !== undefined ? overrideValue : values[key];
    setSaving(s => ({ ...s, [key]: true }));
    setErrors(e => ({ ...e, [key]: "" }));
    try {
      const r = await apiFetch(`/api/settings/${key}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: val }),
      });
      if (!r.ok) {
        const err = await r.json();
        setErrors(e => ({ ...e, [key]: err.detail || "Failed to save" }));
      } else {
        setSaved(s => ({ ...s, [key]: true }));
        setTimeout(() => setSaved(s => ({ ...s, [key]: false })), 2000);
        fetchSettings();
      }
    } catch {
      setErrors(e => ({ ...e, [key]: "Network error" }));
    } finally {
      setSaving(s => ({ ...s, [key]: false }));
    }
  }

  async function resetAll() {
    setResetting(true);
    try {
      await apiFetch("/api/settings/reset", { method: "POST" });
      await fetchSettings();
    } catch {}
    finally { setResetting(false); }
  }

  function handleKeyDown(e: React.KeyboardEvent, key: string) {
    if (e.key === "Enter") saveSetting(key);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D1117] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#00C48C] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <header className="border-b border-[#30363D] px-6 py-4 sticky top-0 bg-[#0D1117]/95 backdrop-blur z-10">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#00C48C] rounded-lg flex items-center justify-center"><Zap size={16} className="text-black" /></div>
            <div><h1 className="text-white font-semibold text-sm">Polymarket Trader</h1><p className="text-[#8B949E] text-xs">Settings</p></div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={resetAll} disabled={resetting}
              className="flex items-center gap-1.5 text-[#8B949E] hover:text-white text-xs transition-colors border border-[#30363D] hover:border-red-500 px-3 py-1.5 rounded-lg">
              <RotateCcw size={11} className={resetting ? "animate-spin" : ""} />Reset to defaults
            </button>
            <Link href="/" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white text-sm transition-colors"><ArrowLeft size={14} />Dashboard</Link>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white mb-1">Settings</h2>
          <p className="text-[#8B949E] text-sm">Configure the trading engine without editing code. Changes take effect on the next poll.</p>
        </div>

        <div className="space-y-6">
          {GROUPS.map((group) => (
            <div key={group.title} className="bg-[#161B22] border border-[#30363D] rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-[#30363D]">
                <h3 className={`font-semibold text-sm ${group.color}`}>{group.title}</h3>
              </div>
              <div className="divide-y divide-[#30363D]">
                {group.keys.map((key) => {
                  const meta = SETTING_LABELS[key];
                  const setting = settings?.[key as keyof Settings];
                  if (!meta || !setting) return null;
                  return (
                    <div key={key} className="px-5 py-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium">{meta.label}</p>
                          <p className="text-[#8B949E] text-xs mt-0.5">{setting.description}</p>
                          {setting.is_default && <p className="text-[#8B949E] text-xs mt-1 font-mono opacity-60">using default</p>}
                          {errors[key] && (
                            <p className="text-red-400 text-xs mt-1 flex items-center gap-1">
                              <AlertTriangle size={10} /> {errors[key]}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {meta.type === "boolean" ? (
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-[#8B949E]">{values[key] === "true" ? "On" : "Off"}</span>
                              <button
                                onClick={() => {
                                  const newVal = values[key] === "true" ? "false" : "true";
                                  setValues(v => ({ ...v, [key]: newVal }));
                                  saveSetting(key, newVal);
                                }}
                                className={`relative w-11 h-6 rounded-full transition-colors ${values[key] === "true" ? "bg-[#00C48C]" : "bg-[#30363D]"}`}>
                                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${values[key] === "true" ? "translate-x-5" : "translate-x-0"}`} />
                              </button>
                              {saved[key] && <CheckCircle size={14} className="text-[#00C48C]" />}
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              {meta.unit && <span className="text-[#8B949E] text-xs font-mono">{meta.unit}</span>}
                              <input type="number" value={values[key] || ""} onChange={e => setValues(v => ({ ...v, [key]: e.target.value }))}
                                onKeyDown={e => handleKeyDown(e, key)}
                                className="w-24 bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-1.5 text-white text-sm font-mono text-right focus:outline-none focus:border-[#00C48C]" />
                              <button onClick={() => saveSetting(key)} disabled={saving[key]}
                                className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg transition-colors font-medium ${
                                  saved[key] ? "bg-[#00C48C]/20 text-[#00C48C] border border-[#00C48C]/30" : "bg-[#00C48C] hover:bg-[#00a876] text-black border border-transparent"
                                } disabled:opacity-50`}>
                                {saved[key] ? <><CheckCircle size={11} /> Saved</> : <><Save size={11} /> {saving[key] ? "..." : "Save"}</>}
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 bg-[#161B22] border border-[#30363D] rounded-xl p-5">
          <h3 className="text-white font-semibold mb-3 text-sm">How settings work</h3>
          <div className="space-y-2 text-xs text-[#8B949E]">
            <p>• <span className="text-white">Poll Interval</span> — how often the app fetches Polymarket data. Lower = more responsive but more API calls.</p>
            <p>• <span className="text-white">Signal Threshold</span> — a market must shift by this % between polls to show as a signal. Lower = more noise, higher = fewer but stronger signals.</p>
            <p>• <span className="text-white">Max Trade Size</span> — no single trade will exceed this dollar value.</p>
            <p>• <span className="text-white">Max Open Positions</span> — the engine won't place new trades if you already have this many open.</p>
            <p>• <span className="text-white">Trade Cooldown</span> — prevents the same rule from firing repeatedly on the same ticker.</p>
            <p>• <span className="text-white">Paper Trading</span> — when on, all trades are simulated with fake money.</p>
            <p>• Changes take effect on the <span className="text-white">next poll cycle</span> — no restart needed.</p>
          </div>
        </div>
      </main>
    </div>
  );
}