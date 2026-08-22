import React, { useEffect, useRef } from "react";
import {
  ShieldCheck,
  Search,
  FileText,
  CheckCircle2,
  ArrowRight,
  Play,
  Layers,
  Activity,
  Award,
  Sparkles,
  ExternalLink,
} from "lucide-react";
import "./LandingPage.css";

interface LandingPageProps {
  onNavigateAuth: (mode: "login" | "signup") => void;
  onNavigateDemo: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigateAuth,
  onNavigateDemo,
}) => {
  const pageRef = useRef<HTMLDivElement>(null);

  // Scroll reveal observer for section entrances
  useEffect(() => {
    if (!pageRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("rs-revealed");
          }
        });
      },
      { threshold: 0.1 }
    );

    const sections = pageRef.current.querySelectorAll("section");
    sections.forEach((sec) => observer.observe(sec));

    return () => observer.disconnect();
  }, []);

  return (
    <div ref={pageRef} className="rs-landing">
      {/* Top Navbar */}
      <nav className="rs-nav">
        <div className="rs-nav-container">
          <div className="rs-brand">
            <div className="rs-brand-icon">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="rs-brand-title">ResearchSwarm</span>
          </div>

          <div className="rs-nav-links">
            <a href="#pipeline">Agent Swarm</a>
            <a href="#trust-ledger">Trust Ledger</a>
            <a href="#methodology">Auditing Specs</a>
          </div>

          <div className="rs-nav-actions">
            <button
              type="button"
              onClick={() => onNavigateAuth("login")}
              className="rs-btn-ghost"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => onNavigateAuth("signup")}
              className="rs-btn-primary"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="rs-hero-section">
        <div className="rs-hero-pill">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Multi-Agent Trust-First Intelligence Engine</span>
        </div>

        <h1 className="rs-hero-title">
          Source-Grounded Intelligence for{" "}
          <span className="rs-hero-title-highlight">High-Stakes Decisions</span>
        </h1>

        <p className="rs-hero-desc">
          Replace flat, unverified AI reports with an audited 5-agent research swarm.
          Live web evidence harvesting, adversarial critique, and confidence bounds in real time.
        </p>

        <div className="rs-hero-ctas">
          <button
            type="button"
            onClick={() => onNavigateAuth("signup")}
            className="rs-btn-primary"
          >
            <span>Start Free Research</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={onNavigateDemo}
            className="rs-btn-secondary"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Interactive Demo</span>
          </button>
        </div>

        {/* Real Metric Strip */}
        <div className="rs-metric-strip">
          <div className="rs-metric-card">
            <div className="rs-metric-number amber">5 Agents</div>
            <div className="rs-metric-label">Specialized Pipeline</div>
          </div>
          <div className="rs-metric-card">
            <div className="rs-metric-number verdigris">100% Grounded</div>
            <div className="rs-metric-label">Live URL Source Citation</div>
          </div>
          <div className="rs-metric-card">
            <div className="rs-metric-number amber">Adversarial</div>
            <div className="rs-metric-label">Critic Retry Loop (&lt;50%)</div>
          </div>
          <div className="rs-metric-card">
            <div className="rs-metric-number">Multi-Export</div>
            <div className="rs-metric-label">PDF, DOCX, MD, JSON</div>
          </div>
        </div>
      </section>

      {/* 5-Agent Pipeline Architecture */}
      <section id="pipeline" className="rs-pipeline-section">
        <div className="rs-section-header">
          <div className="rs-section-tag">Autonomous Pipeline Architecture</div>
          <h2 className="rs-section-title">Five Autonomous Agents Working as One Team</h2>
        </div>

        <div className="rs-agents-grid-top">
          {/* Planner */}
          <div className="rs-agent-card">
            <div className="rs-agent-icon-box">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="rs-agent-card-title">1. Planner Agent</h3>
            <p className="rs-agent-card-desc">
              Deconstructs broad research queries into precise, targeted sub-questions and builds an execution DAG.
            </p>
          </div>

          {/* Researcher */}
          <div className="rs-agent-card">
            <div className="rs-agent-icon-box">
              <Search className="w-5 h-5" />
            </div>
            <h3 className="rs-agent-card-title">2. Researcher Agents</h3>
            <p className="rs-agent-card-desc">
              Executes parallel live web searches via Tavily, harvesting verified evidence, raw snippets, and source URLs.
            </p>
          </div>

          {/* Analyst */}
          <div className="rs-agent-card">
            <div className="rs-agent-icon-box">
              <Activity className="w-5 h-5" />
            </div>
            <h3 className="rs-agent-card-title">3. Analyst Agent</h3>
            <p className="rs-agent-card-desc">
              Synthesizes multi-source evidence into structured thematic insights, market trends, and risk vectors.
            </p>
          </div>
        </div>

        <div className="rs-agents-grid-bottom">
          {/* Critic */}
          <div className="rs-agent-card">
            <div className="rs-agent-icon-box">
              <Award className="w-5 h-5" />
            </div>
            <h3 className="rs-agent-card-title">4. Critic Agent (Adversarial Audit)</h3>
            <p className="rs-agent-card-desc">
              Evaluates evidence strength and confidence scores. If confidence falls below 50%, it automatically triggers a research retry for missing evidence gaps.
            </p>
          </div>

          {/* Writer */}
          <div className="rs-agent-card">
            <div className="rs-agent-icon-box">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="rs-agent-card-title">5. Writer Agent</h3>
            <p className="rs-agent-card-desc">
              Compiles and streams a structured, publication-ready Executive Markdown decision brief in real time over WebSockets.
            </p>
          </div>
        </div>
      </section>

      {/* Trust Ledger Preview Section */}
      <section id="trust-ledger" className="rs-ledger-section">
        <div className="rs-ledger-container">
          <div>
            <div className="rs-section-tag">Full Provenance & Auditability</div>
            <h2 className="rs-section-title" style={{ textAlign: "left", marginBottom: "20px" }}>
              The Real-Time Trust Ledger UI
            </h2>
            <p className="rs-hero-desc" style={{ textAlign: "left", margin: "0 0 24px 0" }}>
              No black-box generation. Watch each claim get audited with individual confidence bounds, source URLs, and Critic evaluation notes in real time.
            </p>

            <div className="rs-ledger-list">
              <div className="rs-ledger-list-item">
                <CheckCircle2 className="w-5 h-5 rs-ledger-check" />
                <span>Claim-level grounding with clickable web sources</span>
              </div>
              <div className="rs-ledger-list-item">
                <CheckCircle2 className="w-5 h-5 rs-ledger-check" />
                <span>Live Critic confidence gauges (0% - 100%)</span>
              </div>
              <div className="rs-ledger-list-item">
                <CheckCircle2 className="w-5 h-5 rs-ledger-check" />
                <span>Instant export to PDF, Word (DOCX), Markdown, & JSON</span>
              </div>
            </div>
          </div>

          {/* Paper Mockup with Real Copy */}
          <div className="rs-paper-mockup">
            <div className="rs-paper-header">
              <div className="rs-paper-title">
                <Activity className="w-4 h-4" />
                <span>Live Trust Ledger Preview</span>
              </div>
              <span className="rs-confidence-tag">Audited • 94% Confidence</span>
            </div>

            <div className="rs-claim-box">
              <p className="rs-claim-quote">
                "Global enterprise AI copilot adoption grew 142% year-over-year in Q3 2025."
              </p>
              <div className="rs-claim-meta">
                <span className="inline-flex items-center gap-1">
                  Source: Gartner AI Market Report 2025
                  <ExternalLink className="w-3 h-3" />
                </span>
                <span style={{ color: "var(--rs-verdigris, #7fa98f)", fontWeight: 600 }}>
                  94% Score
                </span>
              </div>
            </div>

            <div className="rs-critic-note-box">
              <span style={{ fontWeight: 600 }}>Critic Note:</span> Evidence verified across 3 independent market analyst filings with consistent citation methodology.
            </div>
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="rs-cta-banner">
        <div className="rs-cta-inner">
          <h2 className="rs-cta-title">Ready for Source-Grounded Intelligence?</h2>
          <p className="rs-cta-desc">
            Transform ambiguous questions into audited executive decision briefs with five specialized AI agents.
          </p>
          <div className="rs-hero-ctas" style={{ marginBottom: 0 }}>
            <button
              type="button"
              onClick={() => onNavigateAuth("signup")}
              className="rs-btn-primary"
            >
              <span>Start Free Research</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={onNavigateDemo}
              className="rs-btn-secondary"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>Try Interactive Demo</span>
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="rs-footer">
        RESEARCHSWARM // MULTI-AGENT INTELLIGENCE ENGINE // ALL SYSTEMS OPERATIONAL
      </footer>
    </div>
  );
};
