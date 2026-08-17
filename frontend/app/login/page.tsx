"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, AlertTriangle, Eye, EyeOff } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          body: JSON.stringify({ username, password }),
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
