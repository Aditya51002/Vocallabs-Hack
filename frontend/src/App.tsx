import React, { useState } from "react";
import { Sparkles, LogOut, User as UserIcon, Rocket, ShieldCheck } from "lucide-react";

import Dashboard from "./components/Dashboard";
import ReplayMode from "./components/ReplayMode";
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

  // 1. Landing Page View
  if (view === "landing" && authStatus !== "authenticated") {
    return (
      <LandingPage
        onNavigateAuth={handleNavigateAuth}
        onNavigateDemo={() => {
          setView("app");
        }}
      />
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
      <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
        <nav className="sticky top-0 z-50 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-4 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-md shadow-indigo-500/20">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-indigo-400 font-semibold">ResearchSwarm</p>
              <p className="text-base font-bold text-white">Live Swarm Orchestration</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs">
                <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
                <span className="font-semibold text-slate-200">{user.name}</span>
                <span className="text-slate-500">({user.email})</span>
              </div>
            )}
            <button
              onClick={resetSession}
              className="rounded-xl border border-slate-700/80 px-4 py-2 text-xs font-semibold text-slate-200 transition-all hover:border-indigo-500 hover:text-indigo-400 bg-slate-900"
            >
              New Research
            </button>
            {authStatus === "authenticated" && (
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-xl bg-slate-900 border border-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-400 hover:text-rose-400 hover:border-rose-500/30 transition-all"
                title="Log out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            )}
          </div>
        </nav>
        <div className="px-4 pt-6 sm:px-8">
          <ReplayMode
            sessionId={sessionId}
            onReplay={(id) => {
              setSessionId(id);
              setIsReplay(true);
            }}
          />
        </div>
        <Dashboard sessionId={sessionId} isReplay={isReplay} />
      </div>
    );
  }

  // 4. Authenticated Query Submission View
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-4 py-4 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-md shadow-indigo-500/20">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            ResearchSwarm
          </span>
        </div>

        <div className="flex items-center gap-4">
          {user && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs">
              <UserIcon className="w-3.5 h-3.5 text-indigo-400" />
              <span className="font-semibold text-slate-200">{user.name}</span>
            </div>
          )}
          {authStatus === "authenticated" ? (
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl bg-slate-900 border border-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-400 hover:text-rose-400 hover:border-rose-500/30 transition-all"
            >
              <LogOut className="w-3.5 h-3.5" />
              Log out
            </button>
          ) : (
            <button
              onClick={() => handleNavigateAuth("login")}
              className="rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 text-xs font-semibold transition-all shadow-md shadow-indigo-600/20"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* Main Query Card */}
      <main className="relative flex-1 flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="fixed inset-0 -z-10 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.15),transparent)]" />
        <div className="w-full max-w-2xl rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl backdrop-blur-xl sm:p-10">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Rocket className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest font-semibold text-indigo-400">Multi-Agent Swarm Engine</p>
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Live Research Orchestration</h1>
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
              className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm sm:text-base text-slate-100 placeholder:text-slate-500 transition-all duration-300 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
              <span className="text-xs text-slate-500">
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
              className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-6 py-3.5 text-sm font-semibold text-white transition-all shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status === "loading" ? "Launching Swarm..." : "Launch Research Swarm"}
              <Sparkles className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-800/80">
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
