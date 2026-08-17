"use client";

import { useEffect, useState, useRef } from "react";
import {
  Activity, TrendingUp, TrendingDown, Zap, Circle,
  Minus, RefreshCw, AlertTriangle, Settings, CheckCircle,
  Bell, Search, Pin, X, Clock, LogOut
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_INTERVAL = 30_000;

interface HealthStatus { api: string; polymarket: string }
interface PnL {
  total_pnl: number; total_return_pct: number; realized_pnl: number;
  unrealized_pnl: number; today_pnl: number; today_pnl_pct: number;
  portfolio_value: number; cash: number; trade_count: number;
  win_rate: number; wins: number; losses: number;
  best_trade: number; worst_trade: number; avg_trade: number;
  positions: {
    symbol: string; qty: number; avg_entry_price: number;
    current_price: number; market_value: number;
    unrealized_pl: number; unrealized_plpc: number; side: string;
  }[];
}
interface Market {
  id: string; question: string; probability: number;
  previous_probability: number | null; shift: number | null;
  is_signal: boolean; direction: "up" | "down" | "flat";
  end_date: string | null; volume: string | null;
  category: string; pinned: boolean; featured: boolean;
}
interface MarketsResponse {
  markets: Market[]; signals: Market[]; pinned: Market[];
  signal_count: number; total: number; rule_trigger_count: number;
  category_counts: Record<string, number>;
}
interface Trade {
  id: string; symbol: string; qty: number; side: string;
  status: string; filled_avg_price: number | null;
  filled_qty: number; submitted_at: string | null;
}

const CATEGORIES = [
  { value: "all", label: "All" },
  { value: "politics", label: "Politics" },
  { value: "economics", label: "Economics" },
  { value: "sports", label: "Sports" },
  { value: "crypto", label: "Crypto" },
  { value: "entertainment", label: "Entertainment" },
  { value: "science", label: "Science" },
  { value: "other", label: "Other" },
];

const SORTS = [
  { value: "volume", label: "Volume" },
  { value: "probability", label: "Probability" },
  { value: "shift", label: "Signal Strength" },
];

function getMarketStatus(): { isOpen: boolean; label: string; countdown: string; nextEvent: string; } {
  const now = new Date();
  const etNow = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = etNow.getDay();
  const hours = etNow.getHours();
  const minutes = etNow.getMinutes();
  const seconds = etNow.getSeconds();
  const totalMinutes = hours * 60 + minutes;
  const OPEN = 9 * 60 + 30;
  const CLOSE = 16 * 60;
  const isWeekday = day >= 1 && day <= 5;
  const isOpen = isWeekday && totalMinutes >= OPEN && totalMinutes < CLOSE;

  function formatCountdown(diffSeconds: number): string {
    const h = Math.floor(diffSeconds / 3600);
    const m = Math.floor((diffSeconds % 3600) / 60);
    const s = diffSeconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  if (isOpen) {
    const closeSeconds = (CLOSE - totalMinutes) * 60 - seconds;
    return { isOpen: true, label: "Market Open", countdown: formatCountdown(closeSeconds), nextEvent: "closes in" };
  }

  if (isWeekday && totalMinutes < OPEN) {
    const openSeconds = (OPEN - totalMinutes) * 60 - seconds;
    return { isOpen: false, label: "Pre-Market", countdown: formatCountdown(openSeconds), nextEvent: "opens in" };
  }

  const daysUntilOpen = day === 5 ? 3 : day === 6 ? 2 : day === 0 ? 1 : 1;
  const secondsUntilMidnight = (24 - hours) * 3600 - minutes * 60 - seconds;
  const totalSeconds = secondsUntilMidnight + (daysUntilOpen - 1) * 86400 + OPEN * 60;
  const label = day === 6 || day === 0 || (day === 5 && totalMinutes >= CLOSE) ? "Weekend" : "After Hours";
  return { isOpen: false, label, countdown: formatCountdown(totalSeconds), nextEvent: "opens in" };
}

function MarketHoursIndicator() {
  const [status, setStatus] = useState(getMarketStatus());
  useEffect(() => {
    const t = setInterval(() => setStatus(getMarketStatus()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono ${
      status.isOpen ? "border-[#00C48C]/30 bg-[#00C48C]/10 text-[#00C48C]"
      : status.label === "Pre-Market" ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-400"
      : "border-[#30363D] bg-[#0D1117] text-[#8B949E]"
    }`}>
      <Clock size={10} />
      <span className="font-semibold">{status.label}</span>
      <span className="opacity-60">·</span>
      <span>{status.nextEvent} {status.countdown}</span>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const ok = status === "ok";
  return (
    <span className="flex items-center gap-1.5">
      <Circle size={8} className={ok ? "fill-[#00C48C] text-[#00C48C]" : "fill-red-500 text-red-500"} />
      <span className={ok ? "text-[#00C48C]" : "text-red-400"}>{ok ? "Live" : "Error"}</span>
    </span>
  );
}

function PnLCard({ label, value, sub, positive }: { label: string; value: string; sub?: string; positive?: boolean; }) {
  const color = positive === undefined ? "text-white" : positive ? "text-[#00C48C]" : "text-red-400";
  return (
    <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
      <div className="text-[#8B949E] text-xs mb-2">{label}</div>
      <div className={`font-bold font-mono text-lg ${color}`}>{value}</div>
      {sub && <div className="text-[#8B949E] text-xs mt-1">{sub}</div>}
    </div>
  );
}

function ProbabilityBar({ value }: { value: number }) {
  const color = value >= 70 ? "#00C48C" : value >= 40 ? "#F59E0B" : "#EF4444";
  return (
    <div className="w-full bg-[#0D1117] rounded-full h-1 mt-2">
      <div className="h-1 rounded-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color }} />
    </div>
  );
}

function MarketRow({ market, highlight, onPin }: { market: Market; highlight: boolean; onPin: (id: string, pinned: boolean) => void; }) {
  const probColor = market.probability >= 70 ? "text-[#00C48C]" : market.probability >= 40 ? "text-yellow-400" : "text-red-400";
  const categoryColors: Record<string, string> = {
    politics: "text-blue-400 bg-blue-400/10",
    economics: "text-green-400 bg-green-400/10",
    sports: "text-orange-400 bg-orange-400/10",
    crypto: "text-purple-400 bg-purple-400/10",
    entertainment: "text-pink-400 bg-pink-400/10",
    science: "text-cyan-400 bg-cyan-400/10",
    other: "text-[#8B949E] bg-[#8B949E]/10",
  };
  return (
    <div className={`p-4 rounded-lg border transition-all duration-300 group ${
      market.pinned ? "border-[#00C48C]/30 bg-[#00C48C]/5"
      : highlight ? "border-yellow-500/50 bg-yellow-500/5"
      : "border-[#30363D] bg-[#0D1117]/40"
    }`}>
      <div className="flex items-start gap-2 mb-1">
        <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${categoryColors[market.category] || categoryColors.other}`}>
          {market.category}
        </span>
        {market.pinned && <span className="text-xs text-[#00C48C] font-mono shrink-0">📌</span>}
        {highlight && (
          <span className="flex items-center gap-1 text-yellow-400 text-xs font-mono font-semibold">
            <AlertTriangle size={10} />+{market.shift?.toFixed(1)}%
          </span>
        )}
        <button onClick={() => onPin(market.id, market.pinned)}
          className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-[#8B949E] hover:text-[#00C48C]"
          title={market.pinned ? "Unpin" : "Pin market"}>
          {market.pinned ? <X size={12} /> : <Pin size={12} />}
        </button>
      </div>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[#E6EDF3] text-sm leading-snug flex-1 line-clamp-2">{market.question}</p>
        <div className="text-right shrink-0">
          <div className={`text-xl font-mono font-bold ${probColor}`}>{market.probability.toFixed(1)}%</div>
          {market.shift !== null ? (
            <div className={`flex items-center justify-end gap-1 text-xs font-mono mt-0.5 ${
              market.direction === "up" ? "text-[#00C48C]" : market.direction === "down" ? "text-red-400" : "text-[#8B949E]"
            }`}>
              {market.direction === "up" ? <TrendingUp size={14} /> : market.direction === "down" ? <TrendingDown size={14} /> : <Minus size={14} />}
              {market.shift > 0 ? "+" : ""}{market.shift.toFixed(1)}%
            </div>
          ) : (
            <div className="text-xs text-[#8B949E] font-mono mt-0.5">first read</div>
          )}
        </div>
      </div>
      <ProbabilityBar value={market.probability} />
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [pnlData, setPnlData] = useState<PnL | null>(null);
  const [marketsData, setMarketsData] = useState<MarketsResponse | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [marketsLoading, setMarketsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(30);
  const [notifPermission, setNotifPermission] = useState<string>("default");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState("volume");
  const [username, setUsername] = useState("");
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const prevTradeIdsRef = useRef<Set<string>>(new Set());
  const firstLoadRef = useRef(true);

  useEffect(() => {
    setUsername(localStorage.getItem("username") || "");
    if (typeof window === "undefined" || !("Notification" in window)) return;
    setNotifPermission(Notification.permission);
    if (Notification.permission === "default") {
      Notification.requestPermission().then(setNotifPermission);
    }
  }, []);

  async function handleLogout() {
    try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch {}
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    router.push("/login");
  }

  function fireTradeNotification(trade: Trade) {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    if (Notification.permission !== "granted") return;
    const priceLabel = trade.filled_avg_price ? `$${trade.filled_avg_price.toFixed(2)}` : "market price";
    new Notification(`Trade Executed: ${trade.side?.toUpperCase()} ${trade.symbol}`, {
      body: `${trade.qty} shares @ ${priceLabel} — ${trade.status}`,
      icon: "/favicon.ico",
      tag: trade.id,
    });
  }

  async function fetchMeta() {
    try {
      const [hRes, pRes, tRes, sRes] = await Promise.allSettled([
        apiFetch("/api/health"),
        apiFetch("/api/pnl"),
        apiFetch("/api/trades"),
        apiFetch("/api/settings"),
      ]);
      if (hRes.status === "fulfilled" && hRes.value.ok) setHealth(await hRes.value.json());
      if (pRes.status === "fulfilled" && pRes.value.ok) setPnlData(await pRes.value.json());

      let notificationsEnabled = false;
      if (sRes.status === "fulfilled" && sRes.value.ok) {
        const settingsData = await sRes.value.json();
        notificationsEnabled = settingsData?.notifications_enabled?.value === "true";
      }
      if (tRes.status === "fulfilled" && tRes.value.ok) {
        const newTrades: Trade[] = (await tRes.value.json()).trades || [];
        const newIds = new Set(newTrades.map(t => t.id));
        if (notificationsEnabled && !firstLoadRef.current) {
          for (const t of newTrades) {
            if (!prevTradeIdsRef.current.has(t.id)) fireTradeNotification(t);
          }
        }
        prevTradeIdsRef.current = newIds;
        firstLoadRef.current = false;
        setTrades(newTrades);
      }
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => {
    fetchMeta();
    const t = setInterval(fetchMeta, POLL_INTERVAL);
    return () => clearInterval(t);
  }, []);

  async function fetchMarkets() {
    try {
      setMarketsLoading(true);
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (category !== "all") params.set("category", category);
      params.set("sort", sort);
      const r = await apiFetch(`/api/markets?${params.toString()}`);
      if (r.ok) {
        setMarketsData(await r.json());
        setLastUpdated(new Date());
        setCountdown(30);
        fetchMeta();
      }
    } catch {}
    finally { setMarketsLoading(false); }
  }

  useEffect(() => {
    fetchMarkets();
    const t = setInterval(fetchMarkets, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [search, category, sort]);

  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setCountdown(c => c <= 1 ? 30 : c - 1);
    }, 1000);
    return () => { if (countdownRef.current) clearInterval(countdownRef.current); };
  }, []);

  async function handlePin(marketId: string, currentlyPinned: boolean) {
    if (currentlyPinned) {
      await apiFetch(`/api/markets/${marketId}/pin`, { method: "DELETE" });
    } else {
      await apiFetch(`/api/markets/${marketId}/pin`, { method: "POST" });
    }
    fetchMarkets();
  }

  const totalPnlPositive = pnlData ? pnlData.total_pnl >= 0 : undefined;
  const todayPnlPositive = pnlData ? pnlData.today_pnl >= 0 : undefined;

  return (
    <div className="min-h-screen bg-[#0D1117]">
      <header className="border-b border-[#30363D] px-6 py-4 sticky top-0 bg-[#0D1117]/95 backdrop-blur z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#00C48C] rounded-lg flex items-center justify-center">
              <Zap size={16} className="text-black" />
            </div>
            <div>
              <h1 className="text-white font-semibold text-sm">Polymarket Trader</h1>
              <p className="text-[#8B949E] text-xs">Paper Trading Mode</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-[#8B949E]">
              <span>API</span>
              {health ? <StatusDot status={health.api} /> : <span>—</span>}
            </div>
            <div className="flex items-center gap-2 text-[#8B949E]">
              <span>Polymarket</span>
              {health ? <StatusDot status={health.polymarket} /> : <span>—</span>}
            </div>
            {notifPermission === "denied" && (
              <span className="text-red-400 text-xs" title="Notifications blocked">🔕 blocked</span>
            )}
            <MarketHoursIndicator />
            <div className="flex items-center gap-1.5 text-[#8B949E]">
              <RefreshCw size={11} className={marketsLoading ? "animate-spin" : ""} />
              <span>refresh in {countdown}s</span>
            </div>
            <Link href="/backtest" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">
              <TrendingUp size={11} /> Backtest
            </Link>
            <Link href="/history" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">
              <Activity size={11} /> History
            </Link>
            <Link href="/rules" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">
              <Activity size={11} /> Rules
            </Link>
            <Link href="/watchlist" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">
              <Bell size={11} /> Watchlist
            </Link>
            <Link href="/settings" className="flex items-center gap-1.5 text-[#8B949E] hover:text-white transition-colors border border-[#30363D] hover:border-[#00C48C] px-3 py-1.5 rounded-lg">
              <Settings size={11} /> Settings
            </Link>
            <button onClick={handleLogout}
              title={username ? `Logged in as ${username}` : "Logout"}
              className="flex items-center gap-1.5 text-[#8B949E] hover:text-red-400 transition-colors border border-[#30363D] hover:border-red-500 px-3 py-1.5 rounded-lg">
              <LogOut size={11} /> Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-white mb-1">Dashboard</h2>
          <p className="text-[#8B949E] text-sm">Prediction market signals → automated stock trades</p>
        </div>

        {pnlData && (
          <div className={`rounded-xl border px-6 py-4 mb-6 ${
            totalPnlPositive ? "border-[#00C48C]/30 bg-[#00C48C]/5" : "border-red-500/30 bg-red-500/5"
          }`}>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <p className="text-[#8B949E] text-xs mb-1">Total P&L (all time)</p>
                <p className={`text-4xl font-bold font-mono ${totalPnlPositive ? "text-[#00C48C]" : "text-red-400"}`}>
                  {pnlData.total_pnl >= 0 ? "+" : ""}${pnlData.total_pnl.toFixed(2)}
                </p>
                <p className={`text-sm font-mono mt-1 ${totalPnlPositive ? "text-[#00C48C]" : "text-red-400"}`}>
                  {pnlData.total_return_pct >= 0 ? "+" : ""}{pnlData.total_return_pct.toFixed(3)}% return
                </p>
              </div>
              <div className="flex gap-6 text-center">
                <div>
                  <p className="text-[#8B949E] text-xs">Today</p>
                  <p className={`text-lg font-bold font-mono ${todayPnlPositive ? "text-[#00C48C]" : "text-red-400"}`}>
                    {pnlData.today_pnl >= 0 ? "+" : ""}${pnlData.today_pnl.toFixed(2)}
                  </p>
                  <p className={`text-xs font-mono ${todayPnlPositive ? "text-[#00C48C]" : "text-red-400"}`}>
                    {pnlData.today_pnl_pct >= 0 ? "+" : ""}{pnlData.today_pnl_pct.toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-[#8B949E] text-xs">Realized</p>
                  <p className={`text-lg font-bold font-mono ${pnlData.realized_pnl >= 0 ? "text-[#00C48C]" : "text-red-400"}`}>
                    {pnlData.realized_pnl >= 0 ? "+" : ""}${pnlData.realized_pnl.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-[#8B949E] text-xs">Unrealized</p>
                  <p className={`text-lg font-bold font-mono ${pnlData.unrealized_pnl >= 0 ? "text-[#00C48C]" : "text-red-400"}`}>
                    {pnlData.unrealized_pnl >= 0 ? "+" : ""}${pnlData.unrealized_pnl.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-[#8B949E] text-xs">Win Rate</p>
                  <p className={`text-lg font-bold font-mono ${pnlData.win_rate >= 50 ? "text-[#00C48C]" : "text-red-400"}`}>
                    {pnlData.win_rate.toFixed(1)}%
                  </p>
                  <p className="text-xs text-[#8B949E]">{pnlData.wins}W / {pnlData.losses}L</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-[#161B22] border border-[#30363D] rounded-xl p-5 animate-pulse">
                <div className="h-4 bg-[#30363D] rounded w-1/2 mb-3" />
                <div className="h-7 bg-[#30363D] rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : pnlData ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <PnLCard label="Portfolio Value" value={`$${pnlData.portfolio_value.toLocaleString("en-US", { minimumFractionDigits: 2 })}`} sub="paper account" />
            <PnLCard label="Best Trade" value={`+$${pnlData.best_trade.toFixed(2)}`} positive={true} />
            <PnLCard label="Worst Trade" value={`$${pnlData.worst_trade.toFixed(2)}`} positive={pnlData.worst_trade >= 0} />
            <PnLCard label="Avg Trade" value={`${pnlData.avg_trade >= 0 ? "+" : ""}$${pnlData.avg_trade.toFixed(2)}`} sub={`${pnlData.trade_count} closed trades`} positive={pnlData.avg_trade >= 0} />
          </div>
        ) : null}

        {marketsData && (
          <div className={`rounded-xl border px-5 py-3 mb-4 flex items-center justify-between ${
            marketsData.signal_count > 0 ? "border-yellow-500/40 bg-yellow-500/5" : "border-[#30363D] bg-[#161B22]"
          }`}>
            <div className="flex items-center gap-3">
              {marketsData.signal_count > 0 ? <AlertTriangle size={15} className="text-yellow-400" /> : <Activity size={15} className="text-[#8B949E]" />}
              <span className="text-sm font-semibold text-white">
                {marketsData.signal_count > 0
                  ? `${marketsData.signal_count} signal${marketsData.signal_count > 1 ? "s" : ""} detected`
                  : "No signals yet — watching for probability shifts"}
              </span>
              {marketsData.rule_trigger_count > 0 && (
                <span className="flex items-center gap-1 text-xs text-[#00C48C] font-mono">
                  <CheckCircle size={12} />
                  {marketsData.rule_trigger_count} trade{marketsData.rule_trigger_count > 1 ? "s" : ""} executed
                </span>
              )}
            </div>
            <span className="text-xs text-[#8B949E] font-mono">
              {marketsData.total} markets watched{lastUpdated && ` · ${lastUpdated.toLocaleTimeString()}`}
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Activity size={16} className="text-[#00C48C]" />
              Live Markets
              {marketsLoading && <RefreshCw size={12} className="animate-spin text-[#8B949E] ml-1" />}
            </h3>
            <div className="space-y-2 mb-3">
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8B949E]" />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search markets..."
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg pl-8 pr-3 py-2 text-white text-xs focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E]" />
                {search && (
                  <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8B949E] hover:text-white">
                    <X size={12} />
                  </button>
                )}
              </div>
              <div className="flex gap-2 flex-wrap">
                {CATEGORIES.map(c => (
                  <button key={c.value} onClick={() => setCategory(c.value)}
                    className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                      category === c.value ? "bg-[#00C48C] text-black font-semibold" : "bg-[#0D1117] text-[#8B949E] hover:text-white border border-[#30363D]"
                    }`}>
                    {c.label}
                    {marketsData?.category_counts?.[c.value] && c.value !== "all" && (
                      <span className="ml-1 opacity-60">{marketsData.category_counts[c.value]}</span>
                    )}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#8B949E]">Sort:</span>
                {SORTS.map(s => (
                  <button key={s.value} onClick={() => setSort(s.value)}
                    className={`text-xs px-2.5 py-1 rounded transition-colors ${
                      sort === s.value ? "text-white border border-[#00C48C]" : "text-[#8B949E] hover:text-white border border-[#30363D]"
                    }`}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {marketsData && marketsData.pinned.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-[#00C48C] font-mono mb-2">📌 Pinned</p>
                <div className="space-y-2">
                  {marketsData.pinned.map(m => <MarketRow key={m.id} market={m} highlight={m.is_signal} onPin={handlePin} />)}
                </div>
                <div className="border-t border-[#30363D] mt-3 mb-3" />
              </div>
            )}

            {!marketsData ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="bg-[#0D1117] rounded-lg p-4 animate-pulse">
                    <div className="h-3 bg-[#30363D] rounded w-3/4 mb-2" />
                    <div className="h-3 bg-[#30363D] rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : marketsData.markets.length === 0 ? (
              <p className="text-[#8B949E] text-sm text-center py-6">
                {search || category !== "all" ? "No markets match your filters" : "No active markets found"}
              </p>
            ) : (
              <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
                {marketsData.markets.filter(m => !m.pinned).map(market => (
                  <MarketRow key={market.id} market={market} highlight={market.is_signal} onPin={handlePin} />
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-6">
            <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle size={16} className="text-yellow-400" />
                Active Signals
                {marketsData?.signal_count ? (
                  <span className="ml-auto bg-yellow-500/20 text-yellow-400 text-xs font-mono px-2 py-0.5 rounded-full">{marketsData.signal_count}</span>
                ) : null}
              </h3>
              {!marketsData || marketsData.signals.length === 0 ? (
                <div className="text-center py-6">
                  <p className="text-[#8B949E] text-sm">No signals yet</p>
                  <p className="text-[#8B949E] text-xs mt-1">Signals appear when a market moves between polls</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {marketsData.signals.map(m => <MarketRow key={m.id} market={m} highlight={true} onPin={handlePin} />)}
                </div>
              )}
            </div>

            <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-[#00C48C]" /> Open Positions
              </h3>
              {!pnlData || pnlData.positions.length === 0 ? (
                <p className="text-[#8B949E] text-sm text-center py-4">No open positions</p>
              ) : (
                <div className="space-y-2">
                  {pnlData.positions.map(p => (
                    <div key={p.symbol} className="flex items-center justify-between py-2 border-b border-[#30363D] last:border-0">
                      <div>
                        <span className="text-white font-mono font-semibold">{p.symbol}</span>
                        <span className="text-[#8B949E] text-xs ml-2">{p.qty} shares</span>
                        <span className="text-[#8B949E] text-xs ml-2">@ ${p.avg_entry_price.toFixed(2)}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-white font-mono text-sm">${p.market_value.toLocaleString("en-US", { minimumFractionDigits: 2 })}</div>
                        <div className={`text-xs font-mono ${p.unrealized_pl >= 0 ? "text-[#00C48C]" : "text-red-400"}`}>
                          {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)} ({p.unrealized_plpc.toFixed(2)}%)
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-5">
              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                <CheckCircle size={16} className="text-[#00C48C]" /> Recent Trades
              </h3>
              {trades.length === 0 ? (
                <p className="text-[#8B949E] text-sm text-center py-4">No trades yet</p>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {trades.map(t => (
                    <div key={t.id} className="flex items-center justify-between py-2 border-b border-[#30363D] last:border-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${t.side === "buy" ? "bg-[#00C48C]/20 text-[#00C48C]" : "bg-red-500/20 text-red-400"}`}>
                          {t.side?.toUpperCase()}
                        </span>
                        <span className="text-white font-mono font-semibold">{t.symbol}</span>
                        <span className="text-[#8B949E] text-xs">{t.qty} shares</span>
                      </div>
                      <div className="text-right">
                        {t.filled_avg_price && <div className="text-white font-mono text-sm">${t.filled_avg_price.toFixed(2)}</div>}
                        <div className={`text-xs ${t.status === "filled" ? "text-[#00C48C]" : t.status === "canceled" ? "text-red-400" : "text-yellow-400"}`}>
                          {t.status}
                        </div>
                      </div>
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