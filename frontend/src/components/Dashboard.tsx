import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import {
  Activity,
  Bot,
  Brain,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Cpu,
  ExternalLink,
  Feather,
  FileDown,
  FileText,
  Link2,
  Loader,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Award,
  ArrowRight,
} from "lucide-react";

import { AgentState, useSwarm } from "../hooks/useSwarm";
import { apiBaseUrl, apiHeaders } from "../config";
import { ExecutiveReportView } from "./ExecutiveReportView";
import "./Dashboard.css";

type DashboardProps = {
  sessionId: string;
  isReplay?: boolean;
  onResetSession?: () => void;
};

const AGENT_CONFIG = [
  { id: "PLANNER", label: "Planner", icon: Brain },
  { id: "RESEARCHER", label: "Researcher Pool", icon: Search },
  { id: "ANALYST", label: "Analyst", icon: Cpu },
  { id: "CRITIC", label: "Critic", icon: ShieldAlert },
  { id: "WRITER", label: "Writer", icon: Feather },
];

const statusStyles: Record<string, string> = {
  idle: "rs-status-pulse-idle",
  running: "rs-status-pulse-running",
  done: "rs-status-pulse-done",
  error: "bg-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.7)]",
  retry: "rs-status-pulse-running",
};

const statusLabel: Record<string, string> = {
  idle: "Idle",
  running: "Running",
  done: "Done",
  error: "Error",
  retry: "Retry",
};

const formatElapsed = (seconds: number | null) => {
  if (seconds === null) return "--";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${mins}m ${remaining.toFixed(0)}s`;
};

const AgentCard = ({
  label,
  icon: Icon,
  state,
}: {
  label: string;
  icon: typeof Bot;
  state: AgentState;
}) => {
  const log = state.logs[0] || "Awaiting task dispatch...";
  const confidence = typeof state.confidence === "number" ? state.confidence : null;

  return (
    <div className="rs-dash-card">
      <div className="rs-dash-card-header">
        <div className="flex items-center gap-3">
          <div className="rs-agent-icon-wrap">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.16em] font-mono text-slate-400">{label}</p>
            <p className="text-base font-semibold text-slate-100">{statusLabel[state.status]}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={statusStyles[state.status]} />
        </div>
      </div>

      <div className="space-y-2.5 pt-2 border-t border-slate-800/80">
        <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider text-slate-500">
          <span>Status Log</span>
          <span>Elapsed</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <p className="line-clamp-2 text-xs text-slate-300">{log}</p>
          <p className="text-xs font-mono text-slate-400 shrink-0">{formatElapsed(state.elapsedSeconds)}</p>
        </div>

        {state.status === "running" && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-900">
            <div className="h-full w-2/3 animate-pulse bg-gradient-to-r from-amber-500 via-amber-300 to-amber-500 rounded-full" />
          </div>
        )}

        {confidence !== null && state.status === "done" && (
          <div className="pt-1">
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-1">
              <span>Confidence Metric</span>
              <span className="text-emerald-400 font-semibold">{Math.round(confidence * 100)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-900 overflow-hidden">
              <div
                className="h-full bg-emerald-400 rounded-full"
                style={{ width: `${Math.round(confidence * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

export default function Dashboard({ sessionId, isReplay = false, onResetSession }: DashboardProps) {
  const {
    agents,
    streamingText,
    reportMarkdown,
    report,
    sessionStatus,
    tokenBudget,
    isConnected,
  } = useSwarm(sessionId);

  const [activeTab, setActiveTab] = useState<"orchestration" | "report">("orchestration");
  const [showAllClaims, setShowAllClaims] = useState(false);
  const outputRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!outputRef.current) return;
    outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [streamingText, reportMarkdown]);

  // If report is finished and ready, notify user
  const isReportDone = agents.WRITER.status === "done" && Boolean(reportMarkdown);

  const statusKey = sessionStatus?.toLowerCase() || "running";
  const connectedLabel = isConnected ? "Live" : "Reconnecting";

  const allClaims = report?.claim_ledger ?? [];
  const displayedClaims = showAllClaims ? allClaims : allClaims.slice(0, 4);
  const criticNotes = report?.critic_notes?.slice(0, 3) ?? [];
  const finalConfidence =
    typeof report?.confidence === "number" ? Math.round(report.confidence * 100) : null;

  const getDomainFromUrl = (urlStr: string) => {
    try {
      const parsed = new URL(urlStr);
      return parsed.hostname.replace(/^www\./, "");
    } catch {
      return "Source Link";
    }
  };

  const handleExport = async (format: "markdown" | "pdf" | "docx") => {
    const response = await fetch(
      `${apiBaseUrl}/api/sessions/${sessionId}/export?format=${format}`,
      { headers: apiHeaders() }
    );
    if (!response.ok) return;
    const blob = await response.blob();
    const extension = format === "markdown" ? "md" : format;
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `researchswarm-${sessionId}.${extension}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  // If viewing the full report tab
  if (activeTab === "report") {
    return (
      <ExecutiveReportView
        sessionId={sessionId}
        reportMarkdown={reportMarkdown}
        report={report}
        onBackToOrchestration={() => setActiveTab("orchestration")}
        onResetSession={onResetSession || (() => {})}
      />
    );
  }

  return (
    <div className="rs-dashboard-page">
      <div className="rs-dashboard-glow" />

      {/* Header */}
      <header className="rs-dashboard-header">
        <div className="rs-dashboard-header-inner">
          <div className="flex items-center gap-3">
            <div className="rs-brand-icon" style={{ width: "36px", height: "36px" }}>
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] font-mono uppercase tracking-[0.2em] text-amber-400 font-semibold">ResearchSwarm</p>
              <p className="text-lg font-serif font-bold text-slate-50">Live Swarm Orchestration</p>
            </div>
          </div>

          {/* View Mode Switcher */}
          <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 p-1 rounded-xl">
            <button
              type="button"
              onClick={() => setActiveTab("orchestration")}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold uppercase tracking-wider transition-all bg-amber-400 text-slate-950 shadow-sm"
            >
              ⚡ Live Pipeline
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("report")}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold uppercase tracking-wider transition-all flex items-center gap-1.5 text-slate-400 hover:text-slate-200"
            >
              <span>📄 Full Report</span>
              {isReportDone && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {tokenBudget !== null && (
              <div
                className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs font-mono text-slate-300"
                title={`Token Usage: ${tokenBudget.total} / Hard Limit: ${tokenBudget.hardLimit}`}
              >
                <Cpu className="h-3.5 w-3.5 text-amber-400" />
                <span className="font-semibold text-amber-300">{tokenBudget.total.toLocaleString()}</span>
                <span className="text-slate-500">/ 13k tokens</span>
              </div>
            )}

            <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs font-mono text-slate-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>{connectedLabel}</span>
            </div>

            {onResetSession && (
              <button
                type="button"
                onClick={onResetSession}
                className="rs-btn-secondary"
                style={{ padding: "6px 14px", fontSize: "11.5px" }}
              >
                New Research
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto p-4 sm:p-6 lg:p-8 grid grid-cols-1 xl:grid-cols-[38%_62%] gap-6">
        {/* Left Column: 5-Agent Swarm Pipeline */}
        <section className="flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400 font-semibold">
              Agent Pipeline State
            </h2>
            <span className="text-xs font-mono text-slate-500">5 ACTIVE AGENTS</span>
          </div>

          <div className="rs-orchestration-grid">
            {AGENT_CONFIG.map((agent) => (
              <AgentCard
                key={agent.id}
                label={agent.label}
                icon={agent.icon}
                state={agents[agent.id as keyof typeof agents]}
              />
            ))}
          </div>
        </section>

        {/* Right Column: Live Writer Stream + Trust Ledger */}
        <section className="flex flex-col gap-6">
          {/* Report Ready Banner */}
          {isReportDone && (
            <div className="rs-report-ready-banner">
              <div>
                <h3 className="rs-banner-title">✨ Audited Executive Report is Ready!</h3>
                <p className="rs-banner-desc">
                  All 5 agents finished evidence synthesis and adversarial audit. View the full-page brief with one click.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab("report")}
                className="rs-btn-primary shrink-0"
              >
                <span>Read Full Report</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Writer Terminal Stream */}
          <div className="rs-dash-card">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400 font-semibold">Live Writer Output</p>
                <p className="text-base font-serif font-semibold text-slate-100">Executive Brief Stream</p>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                {agents.WRITER.status === "running" && <Loader className="h-3.5 w-3.5 animate-spin text-amber-400" />}
                <span>{agents.WRITER.status === "done" ? "Stream Completed" : "Streaming..."}</span>
              </div>
            </div>

            <div ref={outputRef} className="rs-terminal-box">
              {streamingText || "Awaiting Writer agent synthesis..."}
              {agents.WRITER.status === "running" && (
                <span className="ml-1 inline-block h-4 w-[2px] animate-pulse bg-amber-400" />
              )}
            </div>
          </div>

          {/* Trust Ledger Preview */}
          <div className="rs-dash-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs font-mono uppercase tracking-[0.2em] text-amber-400 font-semibold">Trust Ledger</p>
                <p className="text-base font-serif font-semibold text-slate-100">Claims & Adversarial Audit</p>
              </div>
              <div className="flex items-center gap-2">
                {allClaims.length > 4 && (
                  <button
                    type="button"
                    onClick={() => setShowAllClaims((prev) => !prev)}
                    className="rs-btn-ghost flex items-center gap-1 text-xs"
                  >
                    <span>{showAllClaims ? "Show Less" : `View All (${allClaims.length})`}</span>
                    {showAllClaims ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                )}
                <div className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                  {finalConfidence === null ? "Auditing..." : `${finalConfidence}% Verified`}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Evidence */}
              <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                <div className="text-xs font-mono uppercase tracking-wider text-slate-500">Verified Evidence ({allClaims.length})</div>
                {displayedClaims.length === 0 ? (
                  <p className="text-xs text-slate-500">Claims appear when research completes.</p>
                ) : (
                  displayedClaims.map((item, index) => {
                    const pct = Math.round(item.confidence * 100);
                    return (
                      <div key={`${item.task_id ?? "claim"}-${index}`} className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-200">
                        <div className="flex items-start gap-2">
                          <Link2 className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                          <p className="leading-snug">{item.claim}</p>
                        </div>
                        <div className="mt-2 flex items-center justify-between text-[11px]">
                          <span className="font-mono text-emerald-400 font-medium">{pct}% confidence</span>
                          {item.source && (
                            <a href={item.source} target="_blank" rel="noopener noreferrer" className="text-sky-400 hover:text-sky-300 inline-flex items-center gap-1">
                              <span>{getDomainFromUrl(item.source)}</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Critic Notes */}
              <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                <div className="text-xs font-mono uppercase tracking-wider text-slate-500">Critic Notes ({criticNotes.length})</div>
                {criticNotes.length === 0 ? (
                  <p className="text-xs text-slate-500">The critic evaluation appears before final brief generation.</p>
                ) : (
                  criticNotes.map((note, index) => (
                    <div key={`${note}-${index}`} className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-100 leading-snug">
                      <div className="flex items-start gap-2">
                        <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                        <span>{note}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
