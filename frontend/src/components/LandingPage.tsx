import React from "react";
import {
  ShieldCheck,
  Zap,
  Search,
  FileText,
  CheckCircle2,
  ArrowRight,
  Play,
  Layers,
  Activity,
  Award,
  Sparkles,
  Lock,
  ExternalLink,
} from "lucide-react";

interface LandingPageProps {
  onNavigateAuth: (mode: "login" | "signup") => void;
  onNavigateDemo: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigateAuth,
  onNavigateDemo,
}) => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Background Subtle Gradient & Grid */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))] pointer-events-none" />

      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              ResearchSwarm
            </span>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-indigo-400 transition-colors">
              Agent Swarm
            </a>
            <a href="#trust-ledger" className="hover:text-indigo-400 transition-colors">
              Trust Ledger
            </a>
            <a href="#how-it-works" className="hover:text-indigo-400 transition-colors">
              How It Works
            </a>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigateAuth("login")}
              className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={() => onNavigateAuth("signup")}
              className="px-4 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-md shadow-indigo-600/20 hover:shadow-indigo-500/30 transition-all flex items-center gap-1.5"
            >
              Get Started
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 md:pt-32 md:pb-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-8">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          Multi-Agent Trust-First Intelligence Engine
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold text-white tracking-tight leading-[1.1] max-w-4xl mx-auto mb-6">
          Source-Grounded Intelligence for{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-sky-400 bg-clip-text text-transparent">
            High-Stakes Decisions
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed font-normal">
          Replace flat, unverified AI reports with an audited 5-agent research swarm.
          Live web evidence harvesting, adversarial critique, and confidence bounds in real time.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <button
            onClick={() => onNavigateAuth("signup")}
            className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-2xl shadow-xl shadow-indigo-600/25 hover:shadow-indigo-500/35 transition-all flex items-center justify-center gap-2 text-base"
          >
            Start Free Research
            <ArrowRight className="w-5 h-5" />
          </button>
          <button
            onClick={onNavigateDemo}
            className="w-full sm:w-auto px-8 py-4 bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 text-slate-200 font-semibold rounded-2xl transition-all flex items-center justify-center gap-2 text-base backdrop-blur-sm"
          >
            <Play className="w-4 h-4 fill-slate-200" />
            Interactive Demo
          </button>
        </div>

        {/* Feature Badges */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto pt-8 border-t border-slate-800/60">
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/40 text-left">
            <div className="text-2xl font-bold text-white mb-1">5 Agents</div>
            <div className="text-xs text-slate-400">Specialized Pipeline</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/40 text-left">
            <div className="text-2xl font-bold text-indigo-400 mb-1">100% Grounded</div>
            <div className="text-xs text-slate-400">Live URL Source Citation</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/40 text-left">
            <div className="text-2xl font-bold text-emerald-400 mb-1">Adversarial</div>
            <div className="text-xs text-slate-400">Critic Retry Loop (&lt;50%)</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/40 text-left">
            <div className="text-2xl font-bold text-violet-400 mb-1">Multi-Export</div>
            <div className="text-xs text-slate-400">PDF, DOCX, MD, JSON</div>
          </div>
        </div>
      </section>

      {/* 5-Agent Swarm Section */}
      <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/50">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-indigo-400 mb-3">
            Autonomous Pipeline Architecture
          </h2>
          <p className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Five Autonomous Agents Working as One Team
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          {/* Planner */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
              <Layers className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">1. Planner Agent</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Deconstructs broad research queries into precise, targeted sub-questions and builds an execution DAG.
            </p>
          </div>

          {/* Researcher */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
              <Search className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">2. Researcher Agents</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Executes parallel live web searches via Tavily, harvesting verified evidence, raw snippets, and source URLs.
            </p>
          </div>

          {/* Analyst */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
              <Activity className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">3. Analyst Agent</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Synthesizes multi-source evidence into structured thematic insights, market trends, and risk vectors.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Critic */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
              <Award className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">4. Critic Agent (Adversarial Audit)</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Evaluates evidence strength and confidence scores. If confidence falls below 50%, it automatically triggers a research retry for missing evidence gaps.
            </p>
          </div>

          {/* Writer */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-amber-500/50 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">5. Writer Agent</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Compiles and streams a structured, publication-ready Executive Markdown decision brief in real time over WebSockets.
            </p>
          </div>
        </div>
      </section>

      {/* Trust Ledger Preview Section */}
      <section id="trust-ledger" className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-slate-800/50">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-4">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Full Provenance & Auditability
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-6">
              The Real-Time Trust Ledger UI
            </h2>
            <p className="text-slate-400 text-base leading-relaxed mb-6">
              No black-box generation. Watch each claim get audited with individual confidence bounds, source URLs, and Critic evaluation notes in real time.
            </p>

            <ul className="space-y-3">
              <li className="flex items-center gap-3 text-sm text-slate-300">
                <CheckCircle2 className="w-5 h-5 text-indigo-400 shrink-0" />
                Claim-level grounding with clickable web sources
              </li>
              <li className="flex items-center gap-3 text-sm text-slate-300">
                <CheckCircle2 className="w-5 h-5 text-indigo-400 shrink-0" />
                Live Critic confidence gauges (0% - 100%)
              </li>
              <li className="flex items-center gap-3 text-sm text-slate-300">
                <CheckCircle2 className="w-5 h-5 text-indigo-400 shrink-0" />
                Instant export to PDF, Word (DOCX), Markdown, & JSON
              </li>
            </ul>
          </div>

          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <Activity className="w-4 h-4 text-emerald-400" />
                Live Trust Ledger Preview
              </div>
              <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Audited • 92% Confidence
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">Claim 01</span>
                <span className="text-indigo-400 font-mono">Confidence: 94%</span>
              </div>
              <p className="text-xs text-slate-300">
                "Global enterprise AI copilot adoption grew 142% year-over-year in Q3 2025."
              </p>
              <div className="flex items-center justify-between text-[11px] pt-1">
                <span className="text-slate-400 flex items-center gap-1">
                  <ExternalLink className="w-3 h-3 text-indigo-400" />
                  source: Gartner AI Market Report 2025
                </span>
                <span className="text-emerald-400 font-medium">Verified</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-200">Critic Note</span>
                <span className="text-amber-400 font-mono">Gap Addressed</span>
              </div>
              <p className="text-xs text-slate-300 italic">
                "Critic requested secondary source validation for security policy compliance. Research retry executed successfully."
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center md:text-left flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <span className="text-base font-bold text-white">ResearchSwarm</span>
        </div>
        <p className="text-xs text-slate-500">
          © 2026 ResearchSwarm. All rights reserved. Multi-Agent Decision Brief Engine.
        </p>
      </footer>
    </div>
  );
};
