import React, { useState, useEffect } from "react";
import { Sparkles, ArrowRight, Info, Mic } from "lucide-react";
import "./ReviewerDisclaimerModal.css";

interface ReviewerDisclaimerModalProps {
  onDismiss?: () => void;
}

export const ReviewerDisclaimerModal: React.FC<ReviewerDisclaimerModalProps> = ({ onDismiss }) => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // Check if previously dismissed in this session
    const hasDismissed = sessionStorage.getItem("rs_disclaimer_dismissed");
    if (!hasDismissed) {
      setIsOpen(true);
    }
  }, []);

  const handleContinue = () => {
    sessionStorage.setItem("rs_disclaimer_dismissed", "true");
    setIsOpen(false);
    if (onDismiss) onDismiss();
  };

  if (!isOpen) return null;

  return (
    <div className="rs-disclaimer-overlay" role="dialog" aria-modal="true">
      <div className="rs-disclaimer-modal">
        <div className="rs-disclaimer-glow" />

        <div className="rs-disclaimer-header">
          <div className="rs-disclaimer-icon">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <div className="rs-disclaimer-tag">Hackathon Submission Note</div>
            <h2 className="rs-disclaimer-title">Message to the Vocallabs.AI Review Team</h2>
          </div>
        </div>

        <div className="rs-disclaimer-body">
          <p>
            Welcome to <strong>ResearchSwarm</strong>! Thank you very much for taking your valuable time to review and evaluate this project.
          </p>

          <p>
            As a student project, this live cloud deployment operates on <strong>free-tier API keys</strong> (Groq Whisper/Qwen, Google Gemini Vision, and Tavily Search). Due to rigorous pre-submission testing, these free-tier quotas may occasionally hit daily rate limits during peak usage.
          </p>

          {/* Voice Microphone Note on HTTP vs HTTPS */}
          <div className="rs-disclaimer-highlight-box" style={{ borderLeftColor: "#7fa98f" }}>
            <div className="flex items-center gap-2 font-mono text-xs font-semibold text-emerald-400 mb-1">
              <Mic className="w-4 h-4" />
              <span>Voice / Microphone Note (Browser HTTP Policy):</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-300">
              The live instance is hosted on plain HTTP (<code>http://3.111.34.142:3000</code>), not HTTPS. Modern web browsers automatically block microphone access (<code>getUserMedia</code>) on any remote non-secure origin except <code>localhost</code> — this is a hard browser security policy, not something our code controls. The backend Groq Whisper audio pipeline is fully verified; testing locally on <code>localhost:3000</code> or serving over HTTPS enables live microphone transcription seamlessly.
            </p>
          </div>

          {/* Recommended Testing Method */}
          <div className="rs-disclaimer-highlight-box">
            <div className="flex items-center gap-2 font-mono text-xs font-semibold text-amber-400 mb-1">
              <Info className="w-4 h-4" />
              <span>Recommended Testing Method:</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-300">
              If the live cloud instance encounters free-tier rate limits, you can easily run the full system on your local machine by cloning the repo and providing your personal API keys in <code>.env</code>, or by exploring the built-in deterministic <strong>Interactive Demo</strong> mode.
            </p>
          </div>

          <p className="text-xs text-slate-400 italic">
            I sincerely apologize for any minor inconvenience this may cause. I put my absolute best effort into engineering this 5-agent trust-first architecture. Thank you once again for your support and feedback!
          </p>
        </div>

        <div className="rs-disclaimer-footer">
          <button
            type="button"
            onClick={handleContinue}
            className="rs-disclaimer-btn"
          >
            <span>Continue to ResearchSwarm</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
