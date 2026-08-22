import React, { useEffect, useRef, useState } from "react";
import { createHologramScene, type HologramSceneHandle } from "../three/hologramScene";
import "./HologramIntro.css";

interface HologramIntroProps {
  onEnter: () => void;
}

export const HologramIntro: React.FC<HologramIntroProps> = ({ onEnter }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneHandleRef = useRef<HologramSceneHandle | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const [bootComplete, setBootComplete] = useState(false);

  useEffect(() => {
    if (!containerRef.current || sceneHandleRef.current) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    sceneHandleRef.current = createHologramScene(containerRef.current, { reducedMotion });
    const bootTimer = window.setTimeout(
      () => setBootComplete(true),
      reducedMotion ? 300 : 1800
    );

    return () => {
      window.clearTimeout(bootTimer);
      sceneHandleRef.current?.dispose();
      sceneHandleRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!sectionRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          sceneHandleRef.current?.resume();
        } else {
          sceneHandleRef.current?.pause();
        }
      },
      { threshold: 0.05 }
    );
    observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={sectionRef} className="rs-hologram-section" aria-label="ResearchSwarm system core">
      <div className="rs-hologram-bg-glow" />
      <div ref={containerRef} className="rs-hologram-canvas-container" />

      {/* Corner Brackets */}
      <div className="rs-bracket rs-bracket-tl" />
      <div className="rs-bracket rs-bracket-tr" />
      <div className="rs-bracket rs-bracket-bl" />
      <div className="rs-bracket rs-bracket-br" />

      {/* Top Bar */}
      <div className="rs-topbar">
        <div className="rs-sys-indicator">
          <span className="rs-sys-dot" />
          <span>RESEARCHSWARM // CORE v2.4</span>
        </div>
        <div className="rs-mono">LATENCY: &lt;14ms // REPO: ACTIVE</div>
      </div>

      {/* Center Label */}
      <div className="rs-center-label">
        <h1 className="rs-core-title">Autonomous Swarm Core</h1>
        <p className="rs-core-sub">5-Agent Verified Intelligence Matrix</p>
      </div>

      {/* 5-Agent Status Stack */}
      <div className="rs-status-stack">
        <div className="rs-agent-badge active">
          <span className="rs-agent-dot" />
          <span>01 // PLANNER</span>
        </div>
        <div className="rs-agent-badge active">
          <span className="rs-agent-dot" />
          <span>02 // RESEARCHER</span>
        </div>
        <div className="rs-agent-badge active">
          <span className="rs-agent-dot" />
          <span>03 // ANALYST</span>
        </div>
        <div className="rs-agent-badge active">
          <span className="rs-agent-dot" />
          <span>04 // CRITIC</span>
        </div>
        <div className="rs-agent-badge active">
          <span className="rs-agent-dot" />
          <span>05 // WRITER</span>
        </div>
      </div>

      {/* Right Metrics Readout */}
      <div className="rs-readout">
        <div className="rs-metric">
          <span className="rs-metric-val">100%</span>
          <span className="rs-metric-lbl">Grounding Rate</span>
        </div>
        <div className="rs-metric">
          <span className="rs-metric-val">&lt;50%</span>
          <span className="rs-metric-lbl">Critic Retry Gate</span>
        </div>
        <div className="rs-metric">
          <span className="rs-metric-val">13,000</span>
          <span className="rs-metric-lbl">Token Ceiling</span>
        </div>
      </div>

      {/* Enter CTA */}
      <div className={`rs-enter-wrap ${bootComplete ? "in" : ""}`}>
        <button type="button" className="rs-enter-btn" onClick={onEnter}>
          ENTER RESEARCHSWARM →
        </button>
      </div>
    </section>
  );
};
