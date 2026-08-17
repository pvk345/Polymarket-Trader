"use client";

import { useState, useEffect } from "react";
import { Zap, ArrowLeft, Play, Activity, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area } from "recharts";
import { apiFetch } from "@/lib/api";

interface BacktestSummary {
  total_trades: number; total_pnl: number; win_rate: number;
  wins: number; losses: number; best_trade: number; worst_trade: number; avg_trade: number;
}

interface ChartPoint {
  date: string; price: number; probability: number; in_position: boolean;
  trade: { type: string; price: number; probability: number; pnl?: number } | null;
}

interface Trade {
  date: string; type: string; price: number; probability: number;
  pnl?: number; entry_price?: number; market_question?: string;
}

interface BacktestResult {
  summary: BacktestSummary; chart_data: ChartPoint[]; trades: Trade[];
  meta: { keyword: string | null; market_id: string | null; ticker: string; threshold: number; action: string; start: string; end: string; market_question: string | null; prob_points: number; price_points: number; };
}

interface MarketOption {
  id: string; question: string; probability: number; category: string;
}

const PRESETS = [
  { label: "Fed → TLT", keyword: "Fed interest rates", ticker: "TLT", threshold: 60, action: "buy" },
  { label: "Recession → SPY", keyword: "recession", ticker: "SPY", threshold: 40, action: "sell" },
  { label: "Iran deal → Oil", keyword: "Iran", ticker: "USO", threshold: 50, action: "sell" },
  { label: "Trump tariff → AAPL", keyword: "tariff", ticker: "AAPL", threshold: 60, action: "sell" },
];

function SummaryCard({ label, value, sub, positive }: { label: string; value: string; sub?: string; positive?: boolean }) {
  const color = positive === undefined ? "text-white" : positive ? "text-[#00C48C]" : "text-red-400";
  return (
    <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-4">
      <p className="text-[#8B949E] text-xs mb-1">{label}</p>
      <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
      {sub && <p className="text-[#8B949E] text-xs mt-0.5">{sub}</p>}
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-[#161B22] border border-[#30363D] rounded-lg p-3 text-xs shadow-xl">
      <p className="text-[#8B949E] mb-1 font-mono">{label}</p>
      <p className="text-white font-mono">Price: <span className="text-[#00C48C]">${d?.price?.toFixed(2)}</span></p>
      <p className="text-white font-mono">Prob: <span className="text-yellow-400">{d?.probability?.toFixed(1)}%</span></p>
      {d?.trade && (
        <div className="mt-1 pt-1 border-t border-[#30363D]">
          <p className={`font-mono font-bold ${d.trade.type.includes("BUY") ? "text-[#00C48C]" : "text-red-400"}`}>{d.trade.type} @ ${d.trade.price?.toFixed(2)}</p>
          {d.trade.pnl !== undefined && <p className={`font-mono ${d.trade.pnl >= 0 ? "text-[#00C48C]" : "text-red-400"}`}>P&L: {d.trade.pnl >= 0 ? "+" : ""}${d.trade.pnl?.toFixed(2)}</p>}
        </div>
      )}
    </div>
  );
}

function CustomDot(props: any) {
  const { cx, cy, payload } = props;
  if (!payload?.trade) return null;
  const isBuy = payload.trade.type.includes("BUY");
  return (
    <g>
      <circle cx={cx} cy={cy} r={7} fill={isBuy ? "#00C48C" : "#EF4444"} stroke="#0D1117" strokeWidth={2} />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontSize={8} fontWeight="bold" fill="#0D1117">{isBuy ? "B" : "S"}</text>
    </g>
  );
}

export default function BacktestPage() {
  const [entryMode, setEntryMode] = useState<"keyword" | "market">("keyword");
  const [keyword, setKeyword] = useState("Fed interest rates");
  const [marketId, setMarketId] = useState("");
  const [marketQuestion, setMarketQuestion] = useState("");
  const [marketSearch, setMarketSearch] = useState("");
  const [marketResults, setMarketResults] = useState<MarketOption[]>([]);
  const [searchingMarkets, setSearchingMarkets] = useState(false);
  const [ticker, setTicker] = useState("TLT");
  const [threshold, setThreshold] = useState("60");
  const [action, setAction] = useState("buy");
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState(new Date().toISOString().split("T")[0]);
  const [qty, setQty] = useState("1");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyPreset(p: typeof PRESETS[0]) {
    setEntryMode("keyword");
    setMarketId(""); setMarketQuestion(""); setMarketSearch(""); setMarketResults([]);
    setKeyword(p.keyword); setTicker(p.ticker); setThreshold(String(p.threshold)); setAction(p.action);
  }

  useEffect(() => {
    if (entryMode !== "market" || marketSearch.trim().length < 2 || marketId) { setMarketResults([]); return; }
    const t = setTimeout(async () => {
      setSearchingMarkets(true);
      try {
        const r = await apiFetch(`/api/markets?search=${encodeURIComponent(marketSearch)}&limit=100`);
        if (r.ok) {
          const d = await r.json();
          setMarketResults(d.markets.slice(0, 15).map((m: any) => ({
            id: m.id, question: m.question, probability: m.probability, category: m.category,
          })));
        }
      } catch {}
      finally { setSearchingMarkets(false); }
    }, 350);
    return () => clearTimeout(t);
  }, [marketSearch, entryMode, marketId]);

  function pickMarket(m: MarketOption) {
    setMarketId(m.id); setMarketQuestion(m.question);
    setMarketSearch(m.question); setMarketResults([]);
  }

  function clearMarket() {
    setMarketId(""); setMarketQuestion(""); setMarketSearch("");
  }

  async function runBacktest() {
    setLoading(true); setError(null); setResult(null);
    try {
      const params = new URLSearchParams({ ticker, threshold, action, start, end, qty });
      if (entryMode === "market") params.set("market_id", marketId);
      else params.set("keyword", keyword);
      const r = await apiFetch(`/api/backtest?${params}`);
      if (!r.ok) { const err = await r.json(); throw new Error(err.detail || "Backtest failed"); }
      setResult(await r.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  const pnlPositive = result ? result.summary.total_pnl >= 0 : undefined;

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <header className="border-b border-[#30363D] px-6 py-4 sticky top-0 bg-[#0D1117]/95 backdrop-blur z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#00C48C] rounded-lg flex items-center justify-center"><Zap size={16} className="text-black" /></div>
            <div><h1 className="text-white font-semibold text-sm">Polymarket Trader</h1><p className="text-[#8B949E] text-xs">Backtesting</p></div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/history" className="text-[#8B949E] hover:text-white text-xs transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">History</Link>
            <Link href="/rules" className="text-[#8B949E] hover:text-white text-xs transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">Rules</Link>
            <Link href="/" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white text-sm transition-colors"><ArrowLeft size={14} />Dashboard</Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white mb-1">Backtesting</h2>
          <p className="text-[#8B949E] text-sm">Simulate how a rule would have performed using historical Polymarket + stock data</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-6">
            <h3 className="text-white font-semibold mb-4">Rule Configuration</h3>
            <div className="mb-5">
              <p className="text-[#8B949E] text-xs mb-2">Quick presets:</p>
              <div className="grid grid-cols-2 gap-2">
                {PRESETS.map((p) => (
                  <button key={p.label} onClick={() => applyPreset(p)}
                    className="text-xs px-2 py-1.5 rounded-lg border border-[#30363D] text-[#8B949E] hover:border-[#00C48C] hover:text-[#00C48C] transition-colors text-left">
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-1 mb-2 bg-[#0D1117] border border-[#30363D] rounded-lg p-1 w-fit">
                  <button type="button" onClick={() => setEntryMode("keyword")}
                    className={`text-xs px-2.5 py-1 rounded-md transition-colors ${entryMode === "keyword" ? "bg-[#00C48C] text-black font-semibold" : "text-[#8B949E] hover:text-white"}`}>
                    By keyword
                  </button>
                  <button type="button" onClick={() => setEntryMode("market")}
                    className={`text-xs px-2.5 py-1 rounded-md transition-colors ${entryMode === "market" ? "bg-[#00C48C] text-black font-semibold" : "text-[#8B949E] hover:text-white"}`}>
                    Pick exact market
                  </button>
                </div>

                {entryMode === "keyword" ? (
                  <>
                    <label className="text-xs text-[#8B949E] mb-1 block">Polymarket keyword</label>
                    <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="e.g. Fed, recession, tariff"
                      className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                    <p className="text-xs text-[#8B949E] mt-1">Backtests whichever market this matches first by volume — may not be what you expect.</p>
                  </>
                ) : (
                  <>
                    <label className="text-xs text-[#8B949E] mb-1 block">Search Polymarket markets</label>
                    <input value={marketSearch}
                      onChange={e => { setMarketSearch(e.target.value); if (marketId) { setMarketId(""); setMarketQuestion(""); } }}
                      placeholder="Search by title, e.g. Fed, election, Bitcoin"
                      className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                    {searchingMarkets && <p className="text-xs text-[#8B949E] mt-1">Searching...</p>}
                    {marketResults.length > 0 && (
                      <div className="mt-1 border border-[#30363D] rounded-lg overflow-hidden max-h-56 overflow-y-auto">
                        {marketResults.map(m => (
                          <button type="button" key={m.id} onClick={() => pickMarket(m)}
                            className="w-full text-left px-3 py-2 hover:bg-[#0D1117] border-b border-[#30363D] last:border-0 flex items-center justify-between gap-2">
                            <span className="text-xs text-white line-clamp-1">{m.question}</span>
                            <span className="text-xs font-mono text-[#00C48C] shrink-0">{m.probability.toFixed(1)}%</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {marketId && (
                      <div className="mt-2 bg-[#0D1117] border border-[#00C48C]/30 rounded-lg px-3 py-2 flex items-center justify-between gap-2">
                        <span className="text-xs text-white line-clamp-1">📌 {marketQuestion}</span>
                        <button type="button" onClick={clearMarket} className="text-xs text-[#8B949E] hover:text-red-400 shrink-0">clear</button>
                      </div>
                    )}
                    <p className="text-xs text-[#8B949E] mt-1">Backtests this exact market's price history — no guessing.</p>
                  </>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">Condition</label>
                  <select value={action} onChange={e => setAction(e.target.value)}
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C]">
                    <option value="buy">Buy when above</option>
                    <option value="sell">Sell when above</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">Threshold %</label>
                  <input type="number" min="0" max="100" value={threshold} onChange={e => setThreshold(e.target.value)}
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C]" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">Stock ticker</label>
                  <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} placeholder="TLT"
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                </div>
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">Shares</label>
                  <input type="number" min="1" value={qty} onChange={e => setQty(e.target.value)}
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-[#00C48C]" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">Start date</label>
                  <input type="date" value={start} onChange={e => setStart(e.target.value)}
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C]" />
                </div>
                <div>
                  <label className="text-xs text-[#8B949E] mb-1 block">End date</label>
                  <input type="date" value={end} onChange={e => setEnd(e.target.value)}
                    className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00C48C]" />
                </div>
              </div>
              {(entryMode === "market" ? marketId : keyword) && ticker && (
                <div className="bg-[#0D1117] border border-[#30363D] rounded-lg px-4 py-3">
                  <p className="text-xs text-[#8B949E] mb-1">Simulating:</p>
                  <p className="text-sm text-white">
                    If <span className="text-[#00C48C] font-mono">"{entryMode === "market" ? marketQuestion : keyword}"</span> probability{" "}
                    <span className="text-yellow-400">above {threshold}%</span>{" → "}
                    <span className={action === "buy" ? "text-[#00C48C]" : "text-red-400"}>{action.toUpperCase()}</span>{" "}
                    <span className="font-mono">{qty} share{Number(qty) > 1 ? "s" : ""} of {ticker}</span>
                  </p>
                </div>
              )}
              {error && (
                <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <AlertTriangle size={14} />{error}
                </div>
              )}
              <button onClick={runBacktest} disabled={loading || !(entryMode === "market" ? marketId : keyword) || !ticker}
                className="w-full bg-[#00C48C] hover:bg-[#00a876] disabled:opacity-50 text-black font-semibold rounded-lg py-2.5 text-sm transition-colors flex items-center justify-center gap-2">
                <Play size={14} />{loading ? "Running simulation..." : "Run Backtest"}
              </button>
            </div>
          </div>

          <div className="lg:col-span-2 flex flex-col gap-6">
            {loading && (
              <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-12 flex flex-col items-center justify-center">
                <div className="w-8 h-8 border-2 border-[#00C48C] border-t-transparent rounded-full animate-spin mb-4" />
                <p className="text-[#8B949E] text-sm">Fetching Polymarket history and stock data...</p>
              </div>
            )}
            {!loading && !result && !error && (
              <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-12 flex flex-col items-center justify-center">
                <Activity size={40} className="text-[#30363D] mb-4" />
                <p className="text-[#8B949E] text-sm">Configure a rule and click Run Backtest</p>
                <p className="text-[#8B949E] text-xs mt-1">Results and chart will appear here</p>
              </div>
            )}
            {result && !loading && (
              <>
                {result.meta.market_question && (
                  <div className="bg-[#161B22] border border-[#30363D] rounded-xl px-5 py-3">
                    <p className="text-xs text-[#8B949E] mb-0.5">Polymarket market matched:</p>
                    <p className="text-white text-sm">{result.meta.market_question}</p>
                    <p className="text-[#8B949E] text-xs mt-1 font-mono">{result.meta.prob_points} probability points · {result.meta.price_points} price bars</p>
                  </div>
                )}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <SummaryCard label="Total P&L" value={`${result.summary.total_pnl >= 0 ? "+" : ""}$${result.summary.total_pnl.toFixed(2)}`} sub={`${result.summary.total_trades} trades`} positive={pnlPositive} />
                  <SummaryCard label="Win Rate" value={`${result.summary.win_rate}%`} sub={`${result.summary.wins}W / ${result.summary.losses}L`} positive={result.summary.win_rate >= 50} />
                  <SummaryCard label="Best Trade" value={`+$${result.summary.best_trade.toFixed(2)}`} positive={true} />
                  <SummaryCard label="Worst Trade" value={`$${result.summary.worst_trade.toFixed(2)}`} positive={result.summary.worst_trade >= 0} />
                </div>
                <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-white font-semibold">{result.meta.ticker} Price + Trade Markers</h3>
                    <div className="flex items-center gap-4 text-xs text-[#8B949E]">
                      <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#00C48C] inline-block" /> Buy</span>
                      <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500 inline-block" /> Sell</span>
                    </div>
                  </div>
                  {result.chart_data.length === 0 ? (
                    <p className="text-[#8B949E] text-sm text-center py-8">No chart data available</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={320}>
                      <ComposedChart data={result.chart_data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
                        <XAxis dataKey="date" tick={{ fill: "#8B949E", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#30363D" }} interval="preserveStartEnd" tickFormatter={v => v.slice(5)} />
                        <YAxis yAxisId="price" tick={{ fill: "#8B949E", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} domain={["auto", "auto"]} />
                        <YAxis yAxisId="prob" orientation="right" tick={{ fill: "#8B949E", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} domain={[0, 100]} />
                        <Tooltip content={<CustomTooltip />} />
                        <ReferenceLine yAxisId="prob" y={result.meta.threshold} stroke="#F59E0B" strokeDasharray="4 4"
                          label={{ value: `${result.meta.threshold}%`, fill: "#F59E0B", fontSize: 10, position: "right" }} />
                        <Area yAxisId="prob" type="monotone" dataKey="probability" stroke="#F59E0B" strokeWidth={1.5} fill="#F59E0B" fillOpacity={0.06} dot={false} />
                        <Line yAxisId="price" type="monotone" dataKey="price" stroke="#00C48C" strokeWidth={2} dot={<CustomDot />} activeDot={{ r: 4, fill: "#00C48C" }} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                  <p className="text-[#8B949E] text-xs text-center mt-2">Green = {result.meta.ticker} price · Yellow = probability · Dashed = threshold · B/S = trade markers</p>
                </div>
                {result.trades.length > 0 && (
                  <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
                    <h3 className="text-white font-semibold mb-4">Simulated Trade Log</h3>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {result.trades.map((trade, i) => (
                        <div key={i} className="flex items-center justify-between py-2 border-b border-[#30363D]/50 last:border-0">
                          <div className="flex items-center gap-3">
                            <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${trade.type.includes("BUY") ? "bg-[#00C48C]/20 text-[#00C48C]" : "bg-red-500/20 text-red-400"}`}>{trade.type}</span>
                            <span className="text-[#8B949E] text-xs font-mono">{trade.date}</span>
                            <span className="text-yellow-400 text-xs font-mono">{trade.probability?.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-4">
                            <span className="text-white font-mono text-sm">${trade.price?.toFixed(2)}</span>
                            {trade.pnl !== undefined && (
                              <span className={`font-mono text-sm font-bold ${trade.pnl >= 0 ? "text-[#00C48C]" : "text-red-400"}`}>
                                {trade.pnl >= 0 ? "+" : ""}${trade.pnl?.toFixed(2)}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}