import React, { useState, useRef, useEffect } from "react";
import {
  ShieldCheck,
  Mail,
  Lock,
  User,
  ArrowRight,
  AlertCircle,
  Loader2,
  ArrowLeft,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { createHologramScene, type HologramSceneHandle } from "../three/hologramScene";
import "./AuthPage.css";

interface AuthPageProps {
  initialMode?: "login" | "signup";
  onBackToLanding: () => void;
  onSuccess: () => void;
}

export const AuthPage: React.FC<AuthPageProps> = ({
  initialMode = "login",
  onBackToLanding,
  onSuccess,
}) => {
  const { login, signup, error: authError, clearError } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">(initialMode);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [validationError, setValidationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Background 3D Hologram
  const hologramContainerRef = useRef<HTMLDivElement>(null);
  const sceneHandleRef = useRef<HologramSceneHandle | null>(null);

  useEffect(() => {
    if (!hologramContainerRef.current || sceneHandleRef.current) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    sceneHandleRef.current = createHologramScene(hologramContainerRef.current, { reducedMotion });

    return () => {
      sceneHandleRef.current?.dispose();
      sceneHandleRef.current = null;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();

    if (!email.trim() || !email.includes("@")) {
      setValidationError("Please enter a valid email address.");
      return;
    }

    if (!password || password.length < 8) {
      setValidationError("Password must be at least 8 characters long.");
      return;
    }

    if (mode === "signup" && !name.trim()) {
      setValidationError("Please enter your full name.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "signup") {
        await signup(email, name, password);
      } else {
        await login(email, password);
      }
      onSuccess();
    } catch {
      // Error is set in AuthContext
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = (newMode: "login" | "signup") => {
    setMode(newMode);
    setValidationError(null);
    clearError();
  };

  return (
    <div className="rs-auth-page">
      {/* 3D Hologram Canvas in background */}
      <div ref={hologramContainerRef} className="rs-auth-hologram-bg" />
      <div className="rs-auth-glow" />

      {/* Back to Home button */}
      <button
        type="button"
        onClick={onBackToLanding}
        className="rs-auth-back-btn"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>BACK TO HOME</span>
      </button>

      {/* Center Auth Card */}
      <div className="rs-auth-card">
        <div className="rs-auth-header">
          <div className="rs-auth-icon-box">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="rs-auth-title">
            {mode === "login" ? "Sign In to ResearchSwarm" : "Create Your Account"}
          </h1>
          <p className="rs-auth-subtitle">
            {mode === "login"
              ? "Access your audited multi-agent research briefs"
              : "Generate source-grounded intelligence briefs"}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="rs-auth-tabs">
          <button
            type="button"
            onClick={() => toggleMode("login")}
            className={`rs-auth-tab ${mode === "login" ? "active" : ""}`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => toggleMode("signup")}
            className={`rs-auth-tab ${mode === "signup" ? "active" : ""}`}
          >
            Sign Up
          </button>
        </div>

        {/* Inline Alerts */}
        {(validationError || authError) && (
          <div className="rs-auth-error">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{validationError || authError}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit}>
          {mode === "signup" && (
            <div className="rs-form-group">
              <label className="rs-form-label">Full Name</label>
              <div className="rs-input-wrap">
                <User className="rs-input-icon" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  className="rs-form-input"
                  required
                />
              </div>
            </div>
          )}

          <div className="rs-form-group">
            <label className="rs-form-label">Email Address</label>
            <div className="rs-input-wrap">
              <Mail className="rs-input-icon" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="rs-form-input"
                required
              />
            </div>
          </div>

          <div className="rs-form-group">
            <label className="rs-form-label">Password</label>
            <div className="rs-input-wrap">
              <Lock className="rs-input-icon" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="rs-form-input"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="rs-auth-submit-btn"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="rs-auth-footer">
          <span>{mode === "login" ? "Don't have an account?" : "Already have an account?"}</span>
          <button
            type="button"
            onClick={() => toggleMode(mode === "login" ? "signup" : "login")}
            className="rs-auth-switch-link"
          >
            {mode === "login" ? "Sign Up" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
};
