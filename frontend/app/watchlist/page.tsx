"use client";

import { useEffect, useState, useRef } from "react";
import { Zap, ArrowLeft, Plus, Trash2, Bell, BellOff, RefreshCw, TrendingUp, TrendingDown, RotateCcw } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

const REFRESH_INTERVAL = 60_000;

interface WatchlistItem {
  id: number; ticker: string; label: string;
  alert_above: number | null; alert_below: number | null; active: boolean;
  last_price: number | null; last_checked: string | null; created_at: string | null;
  alert_triggered: boolean; alert_triggered_at: string | null; notes: string | null;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [countdown, setCountdown] = useState(60);
  const [alerts, setAlerts] = useState<{ ticker: string; price: number; trigger: string; threshold: number }[]>([]);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const [form, setForm] = useState({ ticker: "", label: "", alert_above: "", alert_below: "", notes: "" });

  async function fetchWatchlist() {
    try {
      const r = await apiFetch("/api/watchlist");
      if (r.ok) setItems((await r.json()).items);
    } catch {}
    finally { setLoading(false); }
  }

  async function refreshPrices() {
    try {
      setRefreshing(true);
      const r = await apiFetch("/api/watchlist/refresh", { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        if (data.alerts_fired?.length > 0) {
          setAlerts(prev => [...data.alerts_fired, ...prev].slice(0, 10));
          if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
            for (const alert of data.alerts_fired) {
              new Notification(`Price Alert: ${alert.ticker}`, {
                body: `${alert.ticker} hit $${alert.price.toFixed(2)} (${alert.trigger} $${alert.threshold.toFixed(2)})`,
                icon: "/favicon.ico", tag: `watchlist-${alert.ticker}`,
              });
            }
          }
        }
        await fetchWatchlist();
        setCountdown(60);
      }
    } catch {}
    finally { setRefreshing(false); }
  }

  useEffect(() => {
    fetchWatchlist();
    refreshPrices();
    const t = setInterval(refreshPrices, REFRESH_INTERVAL);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    countdownRef.current = setInterval(() => { setCountdown(c => c <= 1 ? 60 : c - 1); }, 1000);
    return () => { if (countdownRef.current) clearInterval(countdownRef.current); };
  }, []);

  async function addItem() {
    if (!form.ticker) return;
    setAdding(true);
    try {
      const body: any = {
        ticker: form.ticker.toUpperCase(),
        label: form.label || form.ticker.toUpperCase(),
        notes: form.notes || null,
        alert_above: form.alert_above ? parseFloat(form.alert_above) : null,
        alert_below: form.alert_below ? parseFloat(form.alert_below) : null,
      };
      const r = await apiFetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) { setForm({ ticker: "", label: "", alert_above: "", alert_below: "", notes: "" }); await fetchWatchlist(); }
    } catch {}
    finally { setAdding(false); }
  }

  async function removeItem(id: number) {
    await apiFetch(`/api/watchlist/${id}`, { method: "DELETE" });
    fetchWatchlist();
  }

  async function resetAlert(id: number) {
    await apiFetch(`/api/watchlist/${id}/reset-alert`, { method: "PATCH" });
    fetchWatchlist();
  }

  function priceColor(item: WatchlistItem) {
    if (!item.last_price) return "text-white";
    if (item.alert_above && item.last_price >= item.alert_above) return "text-[#00C48C]";
    if (item.alert_below && item.last_price <= item.alert_below) return "text-red-400";
    return "text-white";
  }

  function priceVsAlert(item: WatchlistItem) {
    if (!item.last_price) return null;
    if (item.alert_above) {
      const pct = ((item.alert_above - item.last_price) / item.last_price) * 100;
      if (pct > 0) return { label: `${pct.toFixed(1)}% to alert ↑`, color: "text-[#8B949E]" };
    }
    if (item.alert_below) {
      const pct = ((item.last_price - item.alert_below) / item.last_price) * 100;
      if (pct > 0) return { label: `${pct.toFixed(1)}% to alert ↓`, color: "text-[#8B949E]" };
    }
    return null;
  }

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <header className="border-b border-[#30363D] px-6 py-4 sticky top-0 bg-[#0D1117]/95 backdrop-blur z-10">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#00C48C] rounded-lg flex items-center justify-center"><Zap size={16} className="text-black" /></div>
            <div><h1 className="text-white font-semibold text-sm">Polymarket Trader</h1><p className="text-[#8B949E] text-xs">Watchlist</p></div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-[#8B949E] font-mono">
              <RefreshCw size={11} className={refreshing ? "animate-spin" : ""} />refresh in {countdown}s
            </div>
            <Link href="/" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white text-sm transition-colors"><ArrowLeft size={14} />Dashboard</Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white mb-1">Watchlist</h2>
          <p className="text-[#8B949E] text-sm">Track prices and get alerts — no trades placed automatically</p>
        </div>

        {alerts.length > 0 && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 mb-6">
            <p className="text-yellow-400 text-sm font-semibold mb-2 flex items-center gap-2"><Bell size={14} /> Recent Price Alerts</p>
            <div className="space-y-1">
              {alerts.slice(0, 3).map((a, i) => (
                <p key={i} className="text-xs text-[#E6EDF3] font-mono">
                  <span className="text-yellow-400">{a.ticker}</span> hit ${a.price.toFixed(2)} — {a.trigger === "above" ? "rose above" : "dropped below"} ${a.threshold.toFixed(2)}
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
            <h3 className="text-white font-semibold mb-4 flex items-center gap-2"><Plus size={14} className="text-[#00C48C]" />Add to Watchlist</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#8B949E] mb-1 block">Ticker</label>
                <input value={form.ticker} onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))} placeholder="e.g. AAPL, SPY, BTC"
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
              </div>
              <div>
                <label className="text-xs text-[#8B949E] mb-1 block">Label (optional)</label>
                <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} placeholder="e.g. Apple Inc"
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
              </div>
              <div className="border-t border-[#30363D] pt-3">
                <p className="text-xs text-[#8B949E] mb-2">Price alerts (optional)</p>
                <div className="space-y-2">
                  <div>
                    <label className="text-xs text-[#8B949E] mb-1 block">Alert when price rises above $</label>
                    <input type="number" value={form.alert_above} onChange={e => setForm(f => ({ ...f, alert_above: e.target.value }))} placeholder="e.g. 200.00"
                      className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                  </div>
                  <div>
                    <label className="text-xs text-[#8B949E] mb-1 block">Alert when price drops below $</label>
                    <input type="number" value={form.alert_below} onChange={e => setForm(f => ({ ...f, alert_below: e.target.value }))} placeholder="e.g. 150.00"
                      className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                  </div>
                </div>
              </div>
              <div>
                <label className="text-xs text-[#8B949E] mb-1 block">Notes (optional)</label>
                <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="e.g. watching for Fed reaction"
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
              </div>
              <button onClick={addItem} disabled={adding || !form.ticker}
                className="w-full bg-[#00C48C] hover:bg-[#00a876] disabled:opacity-50 text-black font-semibold rounded-lg py-2.5 text-sm transition-colors flex items-center justify-center gap-2">
                <Plus size={14} />{adding ? "Adding..." : "Add Ticker"}
              </button>
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                Tracked Tickers<span className="ml-auto text-xs text-[#8B949E] font-normal font-mono">prices refresh every 60s</span>
              </h3>
              {loading ? (
                <div className="space-y-3">{[...Array(3)].map((_, i) => <div key={i} className="bg-[#0D1117] rounded-lg p-4 animate-pulse h-20" />)}</div>
              ) : items.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-[#8B949E] text-sm">No tickers yet</p>
                  <p className="text-[#8B949E] text-xs mt-1">Add a ticker on the left to start tracking</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {items.map((item) => (
                    <div key={item.id} className={`p-4 rounded-lg border ${item.alert_triggered ? "border-yellow-500/40 bg-yellow-500/5" : "border-[#30363D] bg-[#0D1117]/60"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-white font-mono font-bold text-sm">{item.ticker}</span>
                            {item.label !== item.ticker && <span className="text-[#8B949E] text-xs">{item.label}</span>}
                            {item.alert_triggered && (
                              <span className="flex items-center gap-1 text-xs text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded"><Bell size={10} /> ALERT TRIGGERED</span>
                            )}
                          </div>
                          <div className="flex items-baseline gap-3 mb-2">
                            <span className={`text-2xl font-bold font-mono ${priceColor(item)}`}>{item.last_price ? `$${item.last_price.toFixed(2)}` : "—"}</span>
                            {priceVsAlert(item) && <span className={`text-xs font-mono ${priceVsAlert(item)!.color}`}>{priceVsAlert(item)!.label}</span>}
                          </div>
                          <div className="flex flex-wrap gap-3 text-xs text-[#8B949E]">
                            {item.alert_above && <span className="flex items-center gap-1"><TrendingUp size={10} className="text-[#00C48C]" />Alert above ${item.alert_above.toFixed(2)}</span>}
                            {item.alert_below && <span className="flex items-center gap-1"><TrendingDown size={10} className="text-red-400" />Alert below ${item.alert_below.toFixed(2)}</span>}
                            {!item.alert_above && !item.alert_below && <span className="flex items-center gap-1"><BellOff size={10} />No alerts set</span>}
                            {item.last_checked && <span>updated {new Date(item.last_checked).toLocaleTimeString()}</span>}
                          </div>
                          {item.notes && <p className="text-xs text-[#8B949E] mt-1 italic">{item.notes}</p>}
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {item.alert_triggered && (
                            <button onClick={() => resetAlert(item.id)} className="p-1.5 text-yellow-400 hover:text-white rounded transition-colors" title="Reset alert"><RotateCcw size={14} /></button>
                          )}
                          <button onClick={() => removeItem(item.id)} className="p-1.5 text-[#8B949E] hover:text-red-400 rounded transition-colors" title="Remove"><Trash2 size={14} /></button>
                        </div>
                      </div>
                      {item.last_price && (item.alert_above || item.alert_below) && (
                        <div className="mt-3">
                          {item.alert_above && item.alert_below && (
                            <div className="relative h-1.5 bg-[#30363D] rounded-full overflow-hidden">
                              <div className="absolute h-full bg-[#00C48C] rounded-full transition-all"
                                style={{ width: `${Math.min(100, Math.max(0, ((item.last_price - item.alert_below) / (item.alert_above - item.alert_below)) * 100))}%` }} />
                            </div>
                          )}
                          {item.alert_above && !item.alert_below && (
                            <div className="relative h-1.5 bg-[#30363D] rounded-full overflow-hidden">
                              <div className={`absolute h-full rounded-full transition-all ${item.last_price >= item.alert_above ? "bg-[#00C48C]" : "bg-[#8B949E]"}`}
                                style={{ width: `${Math.min(100, (item.last_price / item.alert_above) * 100)}%` }} />
                            </div>
                          )}
                          {item.alert_below && !item.alert_above && (
                            <div className="relative h-1.5 bg-[#30363D] rounded-full overflow-hidden">
                              <div className={`absolute h-full rounded-full transition-all ${item.last_price <= item.alert_below ? "bg-red-400" : "bg-[#8B949E]"}`}
                                style={{ width: `${Math.min(100, (item.alert_below / item.last_price) * 100)}%` }} />
                            </div>
                          )}
                          <div className="flex justify-between text-xs text-[#8B949E] font-mono mt-1">
                            {item.alert_below && <span>${item.alert_below.toFixed(2)}</span>}
                            {item.alert_above && <span className="ml-auto">${item.alert_above.toFixed(2)}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}