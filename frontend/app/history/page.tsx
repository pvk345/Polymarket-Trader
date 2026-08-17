"use client";

import { useEffect, useState } from "react";
import { Zap, ArrowLeft, Activity, RefreshCw, ChevronUp, ChevronDown, Filter } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface TradeHistory {
  id: number; alpaca_order_id: string | null; ticker: string; action: string;
  quantity: number; filled_price: number | null; filled_qty: number | null;
  total_value: number | null; status: string; rule_name: string;
  market_question: string; probability: number; shift: number | null;
  triggered_at: string; execution_error: string | null;
}

interface Summary {
  total_trades: number; total_buys: number; total_sells: number; total_value_traded: number;
}

type SortField = "triggered_at" | "ticker" | "total_value" | "probability";
type SortDir = "asc" | "desc";

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
      <p className="text-[#8B949E] text-sm mb-2">{label}</p>
      <p className={`text-2xl font-bold font-mono ${color || "text-white"}`}>{value}</p>
      {sub && <p className="text-xs text-[#8B949E] mt-1">{sub}</p>}
    </div>
  );
}

export default function HistoryPage() {
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [tickerFilter, setTickerFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const [sortField, setSortField] = useState<SortField>("triggered_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  async function fetchHistory() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (tickerFilter) params.set("ticker", tickerFilter.toUpperCase());
      if (actionFilter !== "all") params.set("action", actionFilter);
      params.set("sort", "desc");
      params.set("limit", "100");
      const r = await apiFetch(`/api/history?${params}`);
      if (r.ok) {
        const data = await r.json();
        setHistory(data.history || []);
        setSummary(data.summary || null);
      }
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => { fetchHistory(); }, [tickerFilter, actionFilter]);

  const sorted = [...history].sort((a, b) => {
    let valA: any, valB: any;
    if (sortField === "triggered_at") { valA = new Date(a.triggered_at).getTime(); valB = new Date(b.triggered_at).getTime(); }
    else if (sortField === "ticker") { valA = a.ticker; valB = b.ticker; }
    else if (sortField === "total_value") { valA = a.total_value || 0; valB = b.total_value || 0; }
    else if (sortField === "probability") { valA = a.probability; valB = b.probability; }
    if (valA < valB) return sortDir === "asc" ? -1 : 1;
    if (valA > valB) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  function toggleSort(field: SortField) {
    if (sortField === field) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortField(field); setSortDir("desc"); }
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return <ChevronUp size={12} className="text-[#30363D]" />;
    return sortDir === "desc" ? <ChevronDown size={12} className="text-[#00C48C]" /> : <ChevronUp size={12} className="text-[#00C48C]" />;
  }

  const tickers = Array.from(new Set(history.map(h => h.ticker))).sort();

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <header className="border-b border-[#30363D] px-6 py-4 sticky top-0 bg-[#0D1117]/95 backdrop-blur z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#00C48C] rounded-lg flex items-center justify-center"><Zap size={16} className="text-black" /></div>
            <div><h1 className="text-white font-semibold text-sm">Polymarket Trader</h1><p className="text-[#8B949E] text-xs">Trade History</p></div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/rules" className="text-[#8B949E] hover:text-white text-xs transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">Rules</Link>
            <Link href="/" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white text-sm transition-colors"><ArrowLeft size={14} />Dashboard</Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white mb-1">Trade History</h2>
          <p className="text-[#8B949E] text-sm">Every trade placed by the rule engine, with full Polymarket context</p>
        </div>

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard label="Total Trades" value={String(summary.total_trades)} sub="all time" />
            <StatCard label="Total Buys" value={String(summary.total_buys)} color="text-[#00C48C]" />
            <StatCard label="Total Sells" value={String(summary.total_sells)} color="text-red-400" />
            <StatCard label="Total Value Traded" value={`$${summary.total_value_traded.toLocaleString("en-US", { minimumFractionDigits: 2 })}`} sub="paper money" />
          </div>
        )}

        <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-4 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2"><Filter size={14} className="text-[#8B949E]" /><span className="text-[#8B949E] text-sm">Filter:</span></div>
          <div className="flex gap-2">
            {["all", "buy", "sell"].map((a) => (
              <button key={a} onClick={() => setActionFilter(a)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors font-mono ${
                  actionFilter === a
                    ? a === "buy" ? "border-[#00C48C] bg-[#00C48C]/20 text-[#00C48C]"
                    : a === "sell" ? "border-red-500 bg-red-500/20 text-red-400"
                    : "border-[#00C48C] bg-[#00C48C]/20 text-[#00C48C]"
                    : "border-[#30363D] text-[#8B949E] hover:border-[#8B949E]"
                }`}>
                {a.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[#8B949E] text-xs">Ticker:</span>
            <select value={tickerFilter} onChange={e => setTickerFilter(e.target.value)}
              className="bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-[#00C48C]">
              <option value="">All</option>
              {tickers.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <button onClick={fetchHistory} className="ml-auto flex items-center gap-1.5 text-[#8B949E] hover:text-white text-xs transition-colors">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />Refresh
          </button>
        </div>

        <div className="bg-[#161B22] border border-[#30363D] rounded-xl overflow-hidden">
          <div className="grid grid-cols-[1fr_90px_80px_90px_90px_90px_120px] gap-4 px-4 py-3 border-b border-[#30363D] text-xs text-[#8B949E] font-mono">
            <button className="text-left flex items-center gap-1 hover:text-white transition-colors" onClick={() => toggleSort("triggered_at")}>MARKET / RULE <SortIcon field="triggered_at" /></button>
            <button className="text-left flex items-center gap-1 hover:text-white transition-colors" onClick={() => toggleSort("ticker")}>TICKER <SortIcon field="ticker" /></button>
            <span>ACTION</span><span>QTY</span>
            <button className="text-left flex items-center gap-1 hover:text-white transition-colors" onClick={() => toggleSort("total_value")}>VALUE <SortIcon field="total_value" /></button>
            <button className="text-left flex items-center gap-1 hover:text-white transition-colors" onClick={() => toggleSort("probability")}>PROB <SortIcon field="probability" /></button>
            <span>TIME</span>
          </div>

          {loading ? (
            <div className="space-y-px">{[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-[#0D1117]/40 animate-pulse border-b border-[#30363D]" />)}</div>
          ) : sorted.length === 0 ? (
            <div className="text-center py-16">
              <Activity size={32} className="text-[#30363D] mx-auto mb-3" />
              <p className="text-[#8B949E] text-sm">No trade history yet</p>
              <p className="text-[#8B949E] text-xs mt-1">Trades appear here once rules trigger and execute</p>
              <Link href="/rules" className="inline-block mt-4 text-[#00C48C] text-xs hover:underline">Create a rule →</Link>
            </div>
          ) : (
            <div>
              {sorted.map((trade) => (
                <div key={trade.id} className={`grid grid-cols-[1fr_90px_80px_90px_90px_90px_120px] gap-4 px-4 py-4 border-b border-[#30363D]/50 last:border-0 hover:bg-[#0D1117]/40 transition-colors ${trade.execution_error ? "opacity-60" : ""}`}>
                  <div className="min-w-0">
                    <p className="text-white text-sm truncate leading-snug">{trade.market_question || "—"}</p>
                    <p className="text-[#8B949E] text-xs mt-0.5 truncate">Rule: {trade.rule_name}</p>
                    {trade.execution_error && <p className="text-red-400 text-xs mt-0.5 truncate">Error: {trade.execution_error}</p>}
                  </div>
                  <div className="font-mono font-bold text-white text-sm self-center">{trade.ticker}</div>
                  <div className="self-center">
                    <span className={`text-xs font-mono font-bold px-2 py-1 rounded ${trade.action === "buy" ? "bg-[#00C48C]/20 text-[#00C48C]" : "bg-red-500/20 text-red-400"}`}>
                      {trade.action?.toUpperCase()}
                    </span>
                  </div>
                  <div className="font-mono text-white text-sm self-center">{trade.filled_qty ?? trade.quantity}</div>
                  <div className="self-center">
                    {trade.total_value ? (
                      <div>
                        <p className="font-mono text-white text-sm">${trade.total_value.toLocaleString("en-US", { minimumFractionDigits: 2 })}</p>
                        {trade.filled_price && <p className="text-[#8B949E] text-xs font-mono">@${trade.filled_price.toFixed(2)}</p>}
                      </div>
                    ) : <span className="text-[#8B949E] text-xs">pending</span>}
                  </div>
                  <div className="self-center">
                    <p className={`font-mono text-sm font-bold ${trade.probability >= 70 ? "text-[#00C48C]" : trade.probability >= 40 ? "text-yellow-400" : "text-red-400"}`}>
                      {trade.probability?.toFixed(1)}%
                    </p>
                    {trade.shift !== null && trade.shift !== undefined && (
                      <p className={`text-xs font-mono ${trade.shift > 0 ? "text-[#00C48C]" : trade.shift < 0 ? "text-red-400" : "text-[#8B949E]"}`}>
                        {trade.shift > 0 ? "+" : ""}{trade.shift.toFixed(1)}%
                      </p>
                    )}
                  </div>
                  <div className="self-center">
                    <p className="text-[#8B949E] text-xs font-mono">{new Date(trade.triggered_at).toLocaleDateString()}</p>
                    <p className="text-[#8B949E] text-xs font-mono">{new Date(trade.triggered_at).toLocaleTimeString()}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {sorted.length > 0 && <p className="text-[#8B949E] text-xs text-center mt-4 font-mono">{sorted.length} trade{sorted.length > 1 ? "s" : ""} shown</p>}
      </main>
    </div>
  );
}