"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { Zap, AlertTriangle, Eye, EyeOff, TrendingUp, Target, Clock, BarChart3, Bell, Users, X } from "lucide-react";

const FEATURES = [
  { icon: TrendingUp, title: "Live market tracking", text: "Polls up to 500 Polymarket prediction markets every 30 seconds for probability shifts." },
  { icon: Target, title: "Automated rule engine", text: "Keyword, exact-market, or multi-market AND conditions auto-trigger stock trades via Alpaca." },
  { icon: BarChart3, title: "Backtesting engine", text: "Validate a rule idea against historical Polymarket and stock price data before going live." },
  { icon: Clock, title: "Always-on evaluator", text: "An independent AWS Lambda checks every rule on its own schedule, even when this app is closed." },
  { icon: Bell, title: "Watchlist & alerts", text: "Track any ticker with custom price thresholds and real-time email notifications." },
  { icon: Users, title: "Multi-account support", text: "Each account gets its own private rules and watchlist, with JWT-secured auth." },
];

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleReady, setGoogleReady] = useState(false);
  const [showFeatures, setShowFeatures] = useState(true);
  const googleButtonRef = useRef<HTMLDivElement>(null);

  async function handleGoogleCredential(response: { credential: string }) {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      });
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Google sign-in failed");
      }
      const data = await r.json();
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", data.username);
      router.push("/");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGuestLogin() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/auth/guest`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json();
        throw new Error(err.detail || "Guest login failed");
      }
      const data = await r.json();
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", data.username);
      router.push("/");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!googleReady || !GOOGLE_CLIENT_ID) return;
    const google = (window as any).google;
    if (!google || !googleButtonRef.current) return;
    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleCredential,
    });
    google.accounts.id.renderButton(googleButtonRef.current, {
      theme: "outline",
      size: "large",
      width: 328,
      text: "continue_with",
    });
  }, [googleReady]);

  async function handleSubmit() {
    if (!username || !password) { setError("Username and password are required."); return; }
    setLoading(true);
    setError(null);
    try {
      if (mode === "login") {
        // Login uses OAuth2 form encoding
        const body = new URLSearchParams({ username, password });
        const r = await fetch(`${API}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        });
        if (!r.ok) {
          const err = await r.json();
          throw new Error(err.detail || "Login failed");
        }
        const data = await r.json();
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("username", data.username);
        router.push("/");
      } else {
        // Register uses JSON
        const r = await fetch(`${API}/api/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, email: email || null }),
        });
        if (!r.ok) {
          const err = await r.json();
          throw new Error(err.detail || "Registration failed");
        }
        const data = await r.json();
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("username", data.username);
        router.push("/");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSubmit();
  }

  return (
    <div className="min-h-screen bg-[#0D1117] flex items-center justify-center px-4">
      {showFeatures && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center px-4">
          <div className="w-full max-w-lg bg-[#161B22] border border-[#30363D] rounded-xl p-6 relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowFeatures(false)}
              className="absolute top-4 right-4 text-[#8B949E] hover:text-white transition-colors">
              <X size={18} />
            </button>
            <div className="flex flex-col items-center mb-6 text-center">
              <div className="w-12 h-12 bg-[#00C48C] rounded-xl flex items-center justify-center mb-3">
                <Zap size={24} className="text-black" />
              </div>
              <h2 className="text-white font-bold text-xl">What Polymarket Trader does</h2>
              <p className="text-[#8B949E] text-sm mt-1">A full-stack automated trading platform — here's everything it can do.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-3 mb-6">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <div key={title} className="flex gap-3 bg-[#0D1117] border border-[#30363D] rounded-lg p-3">
                  <Icon size={18} className="text-[#00C48C] shrink-0 mt-0.5" />
                  <div>
                    <p className="text-white text-sm font-medium">{title}</p>
                    <p className="text-[#8B949E] text-xs mt-0.5">{text}</p>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={() => { setShowFeatures(false); handleGuestLogin(); }}
              disabled={loading}
              className="w-full bg-[#00C48C] hover:bg-[#00a876] disabled:opacity-50 text-black font-semibold rounded-lg py-2.5 text-sm transition-colors">
              {loading ? "Loading demo..." : "Try it now — Continue as Guest"}
            </button>
            <button
              onClick={() => setShowFeatures(false)}
              className="w-full text-[#8B949E] hover:text-white text-xs mt-3 transition-colors">
              Skip, I'll sign in myself
            </button>
          </div>
        </div>
      )}
      {GOOGLE_CLIENT_ID && (
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
          onReady={() => setGoogleReady(true)}
        />
      )}
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-[#00C48C] rounded-xl flex items-center justify-center mb-4">
            <Zap size={24} className="text-black" />
          </div>
          <h1 className="text-white font-bold text-xl">Polymarket Trader</h1>
          <p className="text-[#8B949E] text-sm mt-1">Prediction markets → automated trades</p>
        </div>

        {/* Card */}
        <div className="bg-[#161B22] border border-[#30363D] rounded-xl p-6">
          {GOOGLE_CLIENT_ID && (
            <>
              <div className="flex justify-center mb-4">
                <div ref={googleButtonRef} />
              </div>
              <div className="flex items-center gap-3 mb-6">
                <div className="h-px bg-[#30363D] flex-1" />
                <span className="text-[#8B949E] text-xs">or</span>
                <div className="h-px bg-[#30363D] flex-1" />
              </div>
            </>
          )}

          {/* Mode toggle */}
          <div className="flex bg-[#0D1117] rounded-lg p-1 mb-6">
            <button
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "login" ? "bg-[#00C48C] text-black" : "text-[#8B949E] hover:text-white"
              }`}>
              Sign In
            </button>
            <button
              onClick={() => { setMode("register"); setError(null); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "register" ? "bg-[#00C48C] text-black" : "text-[#8B949E] hover:text-white"
              }`}>
              Create Account
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-[#8B949E] mb-1.5 block">Username</label>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter your username"
                autoComplete="username"
                className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E] transition-colors"
              />
            </div>

            {mode === "register" && (
              <div>
                <label className="text-xs text-[#8B949E] mb-1.5 block">Email (optional)</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="you@example.com"
                  autoComplete="email"
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E] transition-colors"
                />
                <p className="text-[#8B949E] text-xs mt-1">Only used for rule/alert notifications — leave blank to skip.</p>
              </div>
            )}

            <div>
              <label className="text-xs text-[#8B949E] mb-1.5 block">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={mode === "register" ? "At least 6 characters" : "Enter your password"}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  className="w-full bg-[#0D1117] border border-[#30363D] rounded-lg px-3 py-2.5 pr-10 text-white text-sm focus:outline-none focus:border-[#00C48C] placeholder-[#8B949E] transition-colors"
                />
                <button
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8B949E] hover:text-white transition-colors">
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5">
                <AlertTriangle size={14} className="shrink-0" />
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full bg-[#00C48C] hover:bg-[#00a876] disabled:opacity-50 text-black font-semibold rounded-lg py-2.5 text-sm transition-colors mt-2">
              {loading
                ? mode === "login" ? "Signing in..." : "Creating account..."
                : mode === "login" ? "Sign In" : "Create Account"}
            </button>

            <button
              onClick={handleGuestLogin}
              disabled={loading}
              className="w-full bg-transparent hover:bg-[#0D1117] disabled:opacity-50 text-[#8B949E] hover:text-white border border-[#30363D] font-medium rounded-lg py-2.5 text-sm transition-colors">
              Continue as Guest
            </button>
          </div>
        </div>

        {mode === "register" && (
          <p className="text-[#8B949E] text-xs text-center mt-4">
            Username must be at least 3 characters · Password at least 6
          </p>
        )}
      </div>
    </div>
  );
}
