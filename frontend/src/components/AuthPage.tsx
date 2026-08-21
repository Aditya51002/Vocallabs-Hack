import React, { useState } from "react";
import { ShieldCheck, Mail, Lock, User, ArrowRight, AlertCircle, Loader2, ArrowLeft } from "lucide-react";
import { useAuth } from "../context/AuthContext";

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
      setValidationError("Please enter your name.");
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
      // Error handled by AuthContext
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
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 sm:p-6 text-slate-100 font-sans relative selection:bg-indigo-500 selection:text-white">
      {/* Subtle Background Glow */}
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_center,rgba(99,102,241,0.12),transparent_70%)] pointer-events-none" />

      {/* Back to Landing button */}
      <button
        onClick={onBackToLanding}
        className="absolute top-6 left-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Home
      </button>

      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative z-10">
        {/* Logo */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center mb-4 shadow-lg shadow-indigo-500/25">
            <ShieldCheck className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {mode === "login" ? "Welcome Back to ResearchSwarm" : "Create Your Account"}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {mode === "login"
              ? "Sign in to access your multi-agent research briefs"
              : "Start generating source-grounded decision briefs"}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 p-1 bg-slate-950/80 rounded-xl border border-slate-800 mb-6">
          <button
            type="button"
            onClick={() => toggleMode("login")}
            className={`py-2 text-xs font-semibold rounded-lg transition-all ${
              mode === "login"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => toggleMode("signup")}
            className={`py-2 text-xs font-semibold rounded-lg transition-all ${
              mode === "signup"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Inline Alerts */}
        {(validationError || authError) && (
          <div className="mb-6 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{validationError || authError}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  required
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950/80 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/30 transition-all flex items-center justify-center gap-2 text-sm mt-6 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin text-white" />
            ) : (
              <>
                {mode === "login" ? "Sign In" : "Create Account"}
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer Link */}
        <div className="text-center mt-6 pt-4 border-t border-slate-800/80">
          <p className="text-xs text-slate-400">
            {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => toggleMode(mode === "login" ? "signup" : "login")}
              className="text-indigo-400 hover:underline font-semibold"
            >
              {mode === "login" ? "Sign Up" : "Sign In"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};
