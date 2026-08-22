import React, { useState, useRef } from "react";
import { Sparkles, LogOut, User as UserIcon, Rocket, ShieldCheck } from "lucide-react";

import Dashboard from "./components/Dashboard";
import ReplayMode from "./components/ReplayMode";
import { HologramIntro } from "./components/HologramIntro";
import { LandingPage } from "./components/LandingPage";
import { AuthPage } from "./components/AuthPage";
import { VoiceInput } from "./components/VoiceInput";
import { ImageUpload } from "./components/ImageUpload";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { apiBaseUrl, apiHeaders } from "./config";

function MainAppContent() {
  const { user, status: authStatus, logout } = useAuth();
  const [view, setView] = useState<"landing" | "auth" | "app">("landing");
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const landingScrollRef = useRef<HTMLDivElement>(null);

  const [query, setQuery] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isReplay, setIsReplay] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  // Automatically transition to "app" if user becomes authenticated
  React.useEffect(() => {
    if (authStatus === "authenticated" && view !== "app") {
      setView("app");
    }
  }, [authStatus, view]);

  const handleSubmit = async () => {
    if (!query.trim()) return;
    setStatus("loading");
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/sessions`, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ query: query.trim() }),
      });

      if (response.status === 401) {
        logout();
        setView("auth");
        throw new Error("Session expired. Please log in again.");
      }

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || "Unable to start session");
      }

      const data = (await response.json()) as { session_id: string };
      setSessionId(data.session_id);
      setIsReplay(false);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const resetSession = () => {
    setSessionId(null);
    setQuery("");
    setStatus("idle");
    setError(null);
    setIsReplay(false);
  };

  const handleNavigateAuth = (mode: "login" | "signup") => {
    setAuthMode(mode);
    setView("auth");
  };

  const handleLogout = () => {
    logout();
    setSessionId(null);
    setQuery("");
    setView("landing");
  };

  // 1. Landing Page View with Hologram Intro
  if (view === "landing" && authStatus !== "authenticated") {
    return (
      <>
        <HologramIntro
          onEnter={() => landingScrollRef.current?.scrollIntoView({ behavior: "smooth" })}
        />
        <div ref={landingScrollRef}>
          <LandingPage
            onNavigateAuth={handleNavigateAuth}
            onNavigateDemo={() => {
              setView("app");
            }}
          />
        </div>
      </>
    );
  }

  // 2. Auth Page View
  if (view === "auth" && authStatus !== "authenticated") {
    return (
      <AuthPage
        initialMode={authMode}
        onBackToLanding={() => setView("landing")}
        onSuccess={() => setView("app")}
      />
    );
  }

  // 3. Active Session View (Dashboard + Replay Mode)
  if (sessionId) {
    return (
      <div className="min-h-screen bg-[#0b1220] text-[#f5f1e8] font-sans selection:bg-[#f2b84b] selection:text-[#0b1220]">
        <nav className="sticky top-0 z-50 flex flex-wrap items-center justify-between gap-4 border-b border-[rgba(155,166,192,0.16)] bg-[#0b1220]/90 backdrop-blur-md px-4 py-3.5 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-[#f2b84b] to-[#8a6a2c] text-[#0b1220] shadow-md shadow-amber-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] font-mono uppercase tracking-widest text-[#f2b84b] font-semibold">ResearchSwarm</p>
              <p className="text-sm font-serif font-bold text-white">Live Swarm Orchestration</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#121b2e] border border-[rgba(155,166,192,0.16)] text-xs font-mono">
                <UserIcon className="w-3.5 h-3.5 text-[#f2b84b]" />
                <span className="font-semibold text-[#f5f1e8]">{user.name}</span>
                <span className="text-[#9ba6c0]">({user.email})</span>
              </div>
            )}
            <button
              onClick={resetSession}
              className="rounded-xl border border-[rgba(155,166,192,0.2)] px-3.5 py-1.5 text-xs font-mono font-semibold text-[#f5f1e8] transition-all hover:border-[#f2b84b] hover:text-[#f2b84b] bg-[#121b2e]"
            >
              New Research
            </button>
            {authStatus === "authenticated" && (
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-xl bg-[#121b2e] border border-[rgba(155,166,192,0.16)] px-3 py-1.5 text-xs font-mono font-semibold text-[#9ba6c0] hover:text-rose-400 hover:border-rose-500/30 transition-all"
                title="Log out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            )}
          </div>
        </nav>
        <Dashboard sessionId={sessionId} isReplay={isReplay} onResetSession={resetSession} />
      </div>
    );
  }

  // 4. Authenticated Query Submission View
  return (
    <div className="min-h-screen bg-[#0b1220] text-[#f5f1e8] font-sans flex flex-col justify-between selection:bg-[#f2b84b] selection:text-[#0b1220]">
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 flex items-center justify-between border-b border-[rgba(155,166,192,0.16)] bg-[#0b1220]/90 backdrop-blur-md px-4 py-3.5 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-[#f2b84b] to-[#8a6a2c] text-[#0b1220] shadow-md shadow-amber-500/20">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="text-lg font-serif font-bold tracking-tight text-white">
            ResearchSwarm
          </span>
        </div>

        <div className="flex items-center gap-4">
          {user && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#121b2e] border border-[rgba(155,166,192,0.16)] text-xs font-mono">
              <UserIcon className="w-3.5 h-3.5 text-[#f2b84b]" />
              <span className="font-semibold text-[#f5f1e8]">{user.name}</span>
            </div>
          )}
          {authStatus === "authenticated" ? (
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl bg-[#121b2e] border border-[rgba(155,166,192,0.16)] px-3 py-1.5 text-xs font-mono font-semibold text-[#9ba6c0] hover:text-rose-400 hover:border-rose-500/30 transition-all"
            >
              <LogOut className="w-3.5 h-3.5" />
              Log out
            </button>
          ) : (
            <button
              onClick={() => handleNavigateAuth("login")}
              className="rounded-xl bg-[#f2b84b] hover:bg-[#f7c96e] text-[#0b1220] px-4 py-2 text-xs font-mono font-semibold transition-all shadow-md shadow-amber-500/20"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* Main Query Card */}
      <main className="relative flex-1 flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_50%_20%,rgba(242,184,75,0.08),transparent_65%)]" />
        <div className="w-full max-w-2xl rounded-3xl border border-[rgba(242,184,75,0.25)] bg-[#121b2e]/90 p-6 shadow-2xl backdrop-blur-xl sm:p-10">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f2b84b]/10 border border-[#f2b84b]/20 text-[#f2b84b]">
              <Rocket className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-mono uppercase tracking-widest font-semibold text-[#f2b84b]">Multi-Agent Swarm Engine</p>
              <h1 className="text-2xl sm:text-3xl font-serif font-bold text-white tracking-tight">Live Research Orchestration</h1>
            </div>
          </div>

          <p className="mt-6 text-sm sm:text-base text-slate-300">
            What research topic or decision brief would you like the swarm to investigate?
          </p>

          <div className="mt-4 flex flex-col gap-4">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. Analyze global enterprise adoption trends for AI coding copilots in 2026, key vendors, and risk vectors..."
              rows={4}
              className="w-full rounded-2xl border border-[rgba(155,166,192,0.2)] bg-[#0b1220]/90 px-4 py-3 text-sm sm:text-base text-[#f5f1e8] placeholder:text-slate-500 transition-all duration-300 focus:border-[#f2b84b] focus:outline-none focus:ring-1 focus:ring-[#f2b84b]"
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <VoiceInput
                  onTranscribed={(text) => {
                    setQuery((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text));
                  }}
                  disabled={status === "loading"}
                />
                <ImageUpload
                  onImageExtracted={(findings) => {
                    if (findings.length > 0) {
                      const summary = findings.map((f: any) => f.fact).join("; ");
                      setQuery((prev) =>
                        prev.trim()
                          ? `${prev.trim()}\n[Attached visual context: ${summary}]`
                          : `Analyze attached visual data: ${summary}`
                      );
                    }
                  }}
                  onClear={() => {}}
                  disabled={status === "loading"}
                />
              </div>
              <span className="text-xs font-mono text-slate-500">
                {query.length} / 500 chars (min 10)
              </span>
            </div>

            {error && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs sm:text-sm text-rose-300">
                {error}
              </div>
            )}
            <button
              onClick={handleSubmit}
              disabled={status === "loading" || query.trim().length < 10}
              className="flex items-center justify-center gap-2 rounded-xl bg-[#f2b84b] hover:bg-[#f7c96e] px-6 py-3.5 text-sm font-mono font-semibold text-[#0b1220] transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/35 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === "loading" ? "Launching Swarm..." : "Launch Research Swarm"}
              <Sparkles className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-8 pt-6 border-t border-[rgba(155,166,192,0.16)]">
            <ReplayMode
              sessionId={sessionId}
              onReplay={(id) => {
                setSessionId(id);
                setIsReplay(true);
              }}
            />
          </div>
        </div>
      </main>

      <footer className="py-6 border-t border-slate-800/60 text-center text-xs text-slate-500">
        ResearchSwarm • Source-Grounded Multi-Agent Decision Brief Engine
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainAppContent />
    </AuthProvider>
  );
}
