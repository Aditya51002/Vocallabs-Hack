import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ShieldCheck,
  FileDown,
  FileText,
  Activity,
  Link2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Sparkles,
  Award,
} from "lucide-react";
import { ReportEnvelope } from "../hooks/useSwarm";
import { apiBaseUrl, apiHeaders } from "../config";
import "./ExecutiveReportView.css";

interface ExecutiveReportViewProps {
  sessionId: string;
  reportMarkdown: string;
  report: ReportEnvelope | null;
  onBackToOrchestration: () => void;
  onResetSession: () => void;
}

export const ExecutiveReportView: React.FC<ExecutiveReportViewProps> = ({
  sessionId,
  reportMarkdown,
  report,
  onBackToOrchestration,
  onResetSession,
}) => {
  const [showAllClaims, setShowAllClaims] = useState(true);

  const allClaims = report?.claim_ledger ?? [];
  const criticNotes = report?.critic_notes ?? [];
  const finalConfidence =
    typeof report?.confidence === "number" ? Math.round(report.confidence * 100) : null;

  const getConfidenceLevel = (confidence: number) => {
    const pct = Math.round(confidence * 100);
    if (pct >= 70) return "high";
    if (pct >= 40) return "medium";
    return "low";
  };

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

  return (
    <div className="rs-report-page">
      {/* Top Sticky Header */}
      <header className="rs-report-header">
        <div className="rs-report-header-container">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBackToOrchestration}
              className="rs-btn-ghost flex items-center gap-1.5"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Pipeline</span>
            </button>
            <div className="rs-brand">
              <div className="rs-brand-icon" style={{ width: "32px", height: "32px" }}>
                <ShieldCheck className="w-4 h-4" />
              </div>
              <span className="rs-brand-title" style={{ fontSize: "17px" }}>Executive Report</span>
            </div>
          </div>

          {/* View switcher tabs */}
          <div className="rs-report-view-nav">
            <button
              type="button"
              onClick={onBackToOrchestration}
              className="rs-report-nav-btn"
            >
              <span>⚡ Live Swarm</span>
            </button>
            <button
              type="button"
              className="rs-report-nav-btn active"
            >
              <span>📄 Full Report</span>
            </button>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleExport("markdown")}
              disabled={!reportMarkdown}
              className="rs-btn-secondary"
              style={{ padding: "6px 14px", fontSize: "11.5px" }}
              title="Download as Markdown"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>MD</span>
            </button>
            <button
              type="button"
              onClick={() => void handleExport("pdf")}
              disabled={!reportMarkdown}
              className="rs-btn-secondary"
              style={{ padding: "6px 14px", fontSize: "11.5px" }}
              title="Download as PDF"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>PDF</span>
            </button>
            <button
              type="button"
              onClick={() => void handleExport("docx")}
              disabled={!reportMarkdown}
              className="rs-btn-secondary"
              style={{ padding: "6px 14px", fontSize: "11.5px" }}
              title="Download as Word DOCX"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>DOCX</span>
            </button>
            <button
              type="button"
              onClick={onResetSession}
              className="rs-btn-primary"
              style={{ padding: "6px 16px", fontSize: "11.5px" }}
            >
              <span>New Research</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="rs-report-container">
        {/* Paper Document Canvas */}
        <article className="rs-report-paper">
          <div className="rs-paper-meta-strip">
            <div className="rs-paper-doc-badge">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>AUDITED DECISION BRIEF // SESSION {sessionId.slice(0, 8)}</span>
            </div>
            {finalConfidence !== null && (
              <div className={`rs-paper-confidence-pill ${getConfidenceLevel(finalConfidence / 100)}`}>
                <Award className="w-4 h-4" />
                <span>{finalConfidence}% Verified Confidence</span>
              </div>
            )}
          </div>

          <div className="rs-prose">
            {reportMarkdown ? (
              <ReactMarkdown>{reportMarkdown}</ReactMarkdown>
            ) : (
              <div className="py-16 text-center text-slate-500">
                <Sparkles className="w-8 h-8 mx-auto mb-3 text-amber-500 animate-pulse" />
                <p>Synthesizing audited executive decision brief...</p>
              </div>
            )}
          </div>
        </article>

        {/* Claim Ledger & Adversarial Audit Panel */}
        <section className="rs-report-ledger-panel">
          <div className="rs-ledger-panel-header">
            <div>
              <h2 className="rs-ledger-panel-title">Audited Claim Ledger & Evidence</h2>
              <p className="rs-ledger-panel-sub">
                Every assertion evaluated against live primary web sources and adversarial Critic scrutiny.
              </p>
            </div>
            {allClaims.length > 4 && (
              <button
                type="button"
                onClick={() => setShowAllClaims((prev) => !prev)}
                className="rs-btn-ghost flex items-center gap-1 text-xs"
              >
                <span>{showAllClaims ? "Show Less" : `View All (${allClaims.length})`}</span>
                {showAllClaims ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          <div className="rs-claims-grid">
            {/* Left: Verified Claims */}
            <div className="space-y-3">
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2">
                Grounding Evidence ({allClaims.length} Claims)
              </div>
              {allClaims.length === 0 ? (
                <p className="text-xs text-slate-500">Evidence harvest in progress...</p>
              ) : (
                allClaims.map((item, index) => {
                  const pct = Math.round(item.confidence * 100);
                  const isHigh = pct >= 70;
                  return (
                    <div key={`${item.task_id ?? "claim"}-${index}`} className="rs-claim-item-card">
                      <div className="flex items-start gap-2 text-sm text-slate-200">
                        <Link2 className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <p className="leading-snug">{item.claim}</p>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-xs">
                        <span
                          className={`px-2 py-0.5 rounded font-mono font-semibold text-[11px] ${
                            isHigh
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                          }`}
                        >
                          {pct}% confidence
                        </span>
                        {item.source && (
                          <a
                            href={item.source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sky-400 hover:text-sky-300 underline underline-offset-2"
                          >
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

            {/* Right: Critic Notes */}
            <div className="space-y-3">
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2">
                Adversarial Critic Notes ({criticNotes.length})
              </div>
              {criticNotes.length === 0 ? (
                <p className="text-xs text-slate-500">Critic evaluation appears before report generation.</p>
              ) : (
                <div className="rs-critic-notes-list">
                  {criticNotes.map((note, index) => (
                    <div key={`${note}-${index}`} className="rs-critic-note-item">
                      <div className="flex items-start gap-2">
                        <Activity className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <span>{note}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};
