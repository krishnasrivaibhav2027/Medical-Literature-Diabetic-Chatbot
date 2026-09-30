import React, { useState } from "react";
import {
  Lock,
  Mail,
  User,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Zap,
  Layers,
  BarChart3,
  Clock,
} from "lucide-react";
import { registerUser, loginUser, getMe } from "../services/api";

export default function AuthPage({ onAuthSuccess }) {
  const [isLogin, setIsLogin] = useState(true); // Default to Sign In as shown in reference
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errorMsg) setErrorMsg("");
  };

  // Password validation checks matching backend schema
  const passwordChecks = {
    length: formData.password.length >= 8,
    uppercase: /[A-Z]/.test(formData.password),
    lowercase: /[a-z]/.test(formData.password),
    digit: /[0-9]/.test(formData.password),
    special: /[!@#$%^&*]/.test(formData.password),
    match: !isLogin ? formData.password.length > 0 && formData.password === formData.confirmPassword : true,
  };

  const isPasswordValid =
    passwordChecks.length &&
    passwordChecks.uppercase &&
    passwordChecks.lowercase &&
    passwordChecks.digit &&
    passwordChecks.special;

  const isConfirmMatch =
    formData.confirmPassword.length > 0 && formData.password === formData.confirmPassword;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    const emailTrimmed = formData.email.trim().toLowerCase();

    // Domain check matching backend allowed domains
    const allowedDomains = ["gmail", "outlook", "yahoo"];
    const domainMatch = emailTrimmed.match(/@([a-zA-Z0-9.-]+)\./);
    const domain = domainMatch ? domainMatch[1].toLowerCase() : "";

    if (!allowedDomains.includes(domain)) {
      setErrorMsg("Email domain must be one of: @gmail.com, @outlook.com, or @yahoo.com");
      return;
    }

    if (!isLogin) {
      if (formData.username.trim().length < 3) {
        setErrorMsg("Username must be at least 3 characters long.");
        return;
      }
      if (!isPasswordValid) {
        setErrorMsg("Please satisfy all password security criteria.");
        return;
      }
      if (formData.password !== formData.confirmPassword) {
        setErrorMsg("Passwords do not match.");
        return;
      }
    }

    setLoading(true);

    try {
      if (!isLogin) {
        // 1. Register user
        const userRes = await registerUser({
          username: formData.username.trim(),
          email: emailTrimmed,
          password: formData.password,
          confirm_password: formData.confirmPassword,
        });

        // 2. Immediately log in to obtain JWT access token
        const loginRes = await loginUser({
          email: emailTrimmed,
          password: formData.password,
        });

        if (loginRes.access_token) {
          localStorage.setItem("access_token", loginRes.access_token);
        }

        // 3. Redirect to chat page
        const clientNow = new Date().toISOString();
        const authedUser = {
          id: userRes.id,
          username: userRes.username,
          name: userRes.username,
          email: userRes.email,
          created_at: userRes.created_at || clientNow,
          login_at: userRes.login_at || clientNow,
          role: "Verified Member",
        };

        onAuthSuccess(authedUser, { isNewAccount: true });
      } else {
        // Login flow
        const loginRes = await loginUser({
          email: emailTrimmed,
          password: formData.password,
        });

        if (loginRes.access_token) {
          localStorage.setItem("access_token", loginRes.access_token);
        }

        // Fetch user profile from /user/me or fallback
        const me = await getMe(loginRes.access_token);
        const clientNow = new Date().toISOString();
        const authedUser = me
          ? {
              ...me,
              name: me.username,
              login_at: me.login_at || clientNow,
              role: "Verified Member",
            }
          : {
              username: emailTrimmed.split("@")[0],
              name: emailTrimmed.split("@")[0],
              email: emailTrimmed,
              login_at: clientNow,
              created_at: clientNow,
              role: "Verified Member",
            };

        onAuthSuccess(authedUser, { isNewAccount: false });
      }
    } catch (err) {
      console.error("Auth error:", err);
      setErrorMsg(err.message || "Authentication failed. Please check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="axiom-auth-root">
      {/* Background wireframe geometric shapes */}
      <div className="axiom-geo-circle" aria-hidden="true" />
      <div className="axiom-geo-cube" aria-hidden="true" />
      <div className="axiom-ambient-glow" aria-hidden="true" />

      {/* Main Split Layout with Angled Diagonal Divide */}
      <div className="axiom-split-layout">
        {/* ========================================================
            LEFT SECTION: Application Overview, RAG Explanation & Metrics
            ======================================================== */}
        <section className="axiom-overview-side">
          {/* Slanted Seam SVG Line to ensure visible slant in both light & dark mode */}
          <div className="axiom-slanted-seam-wrapper" aria-hidden="true">
            <svg
              className="axiom-slanted-seam"
              preserveAspectRatio="none"
              viewBox="0 0 60 1000"
            >
              <line x1="60" y1="0" x2="0" y2="1000" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>

          <div className="axiom-overview-inner">
            {/* Main Editorial Headline */}
            <h1 className="axiom-main-title">
              Medical Literature<br />
              <span className="axiom-title-italic">Diabetes Chatbot</span>
            </h1>

            {/* High-Level Overview Paragraphs (consumes wider space) */}
            <div className="axiom-overview-paragraphs">
              <p>
                This application is an AI-powered medical literature search and questioning assistant
                specialized in diabetes care and clinical research. When you submit a clinical question,
                the system searches thousands of verified clinical studies, trials, and diabetes guidelines
                using a high-throughput Hybrid Retrieval-Augmented Generation (RAG) architecture.
              </p>
              <p>
                The system executes parallel retrieval using Jina Embeddings v3 for deep semantic
                comprehension and Rank-BM25 for exact medical terms and drug dosages. Candidate passages
                are calibrated through Reciprocal Rank Fusion (RRF) and re-scored with Jina AI v3.5
                cross-encoders. Paired with Upstash Redis caching for sub-40ms responses, the chatbot
                delivers instant, verified answers backed by direct citations to published literature.
              </p>
            </div>

            {/* Performance Metrics Row (Including TTFT) */}
            <div className="axiom-metrics-row">
              <div className="axiom-metric-item">
                <span className="axiom-metric-value">99.9%</span>
                <span className="axiom-metric-label">Grounding SLA</span>
              </div>
              <div className="axiom-metric-item">
                <span className="axiom-metric-value">&lt; 40ms</span>
                <span className="axiom-metric-label">P99 Latency</span>
              </div>
              <div className="axiom-metric-item">
                <span className="axiom-metric-value">&lt; 280ms</span>
                <span className="axiom-metric-label">TTFT (First Token)</span>
              </div>
              <div className="axiom-metric-item">
                <span className="axiom-metric-value">Jina v3</span>
                <span className="axiom-metric-label">Neural Embeddings</span>
              </div>
            </div>

            {/* 3 Modern Feature Cards */}
            <div className="axiom-features-list">
              <div className="axiom-feature-card">
                <div className="axiom-feature-icon-box text-blue-500">
                  <Zap size={18} />
                </div>
                <div className="axiom-feature-text">
                  <h4 className="axiom-feature-title">Parallel Hybrid Retrieval</h4>
                  <p className="axiom-feature-desc">
                    Simultaneously executes pgvector dense search with Jina Embeddings v3 and Rank-BM25 exact keyword matching.
                  </p>
                </div>
              </div>

              <div className="axiom-feature-card">
                <div className="axiom-feature-icon-box text-blue-400">
                  <ShieldCheck size={18} />
                </div>
                <div className="axiom-feature-text">
                  <h4 className="axiom-feature-title">Relevance Re-ranking</h4>
                  <p className="axiom-feature-desc">
                    Jina AI v3.5 cross-encoders re-score every retrieved medical passage to select the most relevant clinical evidence.
                  </p>
                </div>
              </div>

              <div className="axiom-feature-card">
                <div className="axiom-feature-icon-box text-cyan-400">
                  <BarChart3 size={18} />
                </div>
                <div className="axiom-feature-text">
                  <h4 className="axiom-feature-title">Sub-40ms Redis Caching</h4>
                  <p className="axiom-feature-desc">
                    Multi-tier semantic vector similarity and deterministic QA cache deliver instant clinical answers.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ========================================================
            RIGHT SECTION: Sign In / Create Account
            ======================================================== */}
        <section className="axiom-auth-side">
          <div className={`axiom-auth-inner ${!isLogin ? "axiom-register-mode" : ""}`}>
            {/* Header */}
            <div className="axiom-auth-header">
              <h2 className="axiom-auth-title">
                {isLogin ? "Welcome back" : "Create an account"}
              </h2>
              {!isLogin && (
                <p className="axiom-auth-subtitle">
                  Create an account to use this chatbot
                </p>
              )}
            </div>

            {/* Segmented Switcher (Sign In / Create Account) */}
            <div className="axiom-segmented-switch">
              <button
                type="button"
                className={`axiom-segment-btn ${isLogin ? "active" : ""}`}
                onClick={() => {
                  setIsLogin(true);
                  setErrorMsg("");
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`axiom-segment-btn ${!isLogin ? "active" : ""}`}
                onClick={() => {
                  setIsLogin(false);
                  setErrorMsg("");
                }}
              >
                Create Account
              </button>
            </div>

            {/* Error Message Alert */}
            {errorMsg && (
              <div className="axiom-error-alert animate-fade-in" role="alert">
                <AlertCircle size={17} className="text-rose-400 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Form */}
            <form className="axiom-form" onSubmit={handleSubmit} noValidate>
              {/* Username (Sign Up only) */}
              {!isLogin && (
                <div className="axiom-field-group">
                  <input
                    id="username"
                    type="text"
                    required
                    placeholder="Username"
                    value={formData.username}
                    onChange={(e) => handleChange("username", e.target.value)}
                    className="axiom-input"
                    minLength={3}
                    maxLength={50}
                  />
                </div>
              )}

              {/* Email Address */}
              <div className="axiom-field-group">
                <input
                  id="email"
                  type="email"
                  required
                  placeholder="Email address"
                  value={formData.email}
                  onChange={(e) => handleChange("email", e.target.value)}
                  className="axiom-input"
                />
              </div>

              {/* Password */}
              <div className="axiom-field-group axiom-password-wrap">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="Password"
                  value={formData.password}
                  onChange={(e) => handleChange("password", e.target.value)}
                  className="axiom-input"
                />
                <button
                  type="button"
                  className="axiom-btn-toggle-eye"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {/* Password Requirements Checklist (Directly under Password field) */}
              {!isLogin && (
                <div className="axiom-password-checklist">
                  <div className={`axiom-check-item ${passwordChecks.length ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>At least 8 characters</span>
                  </div>
                  <div className={`axiom-check-item ${passwordChecks.uppercase ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>One uppercase letter</span>
                  </div>
                  <div className={`axiom-check-item ${passwordChecks.lowercase ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>One lowercase letter</span>
                  </div>
                  <div className={`axiom-check-item ${passwordChecks.digit ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>At least one number</span>
                  </div>
                  <div className={`axiom-check-item ${passwordChecks.special ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>Special char (!@#$%^&*)</span>
                  </div>
                </div>
              )}

              {/* Confirm Password (Sign Up only) */}
              {!isLogin && (
                <>
                  <div className="axiom-field-group axiom-password-wrap">
                    <input
                      id="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      required
                      placeholder="Confirm password"
                      value={formData.confirmPassword}
                      onChange={(e) => handleChange("confirmPassword", e.target.value)}
                      className="axiom-input"
                    />
                    <button
                      type="button"
                      className="axiom-btn-toggle-eye"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                    >
                      {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>

                  {/* Real-time Confirm Password Match Indicator while typing */}
                  {formData.confirmPassword.length > 0 && (
                    <div
                      className={`axiom-confirm-match-pill ${
                        isConfirmMatch ? "matched" : "mismatched"
                      }`}
                    >
                      {isConfirmMatch ? (
                        <>
                          <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
                          <span>Passwords match</span>
                        </>
                      ) : (
                        <>
                          <AlertCircle size={13} className="text-rose-500 shrink-0" />
                          <span>Passwords do not match</span>
                        </>
                      )}
                    </div>
                  )}
                </>
              )}

              {/* Submit CTA Button */}
              <button
                type="submit"
                className="axiom-btn-submit"
                disabled={loading || (!isLogin && (!isPasswordValid || !isConfirmMatch))}
              >
                {loading ? (
                  <span className="axiom-spinner" />
                ) : (
                  <span>{isLogin ? "Sign In" : "Create Account"}</span>
                )}
              </button>
            </form>

            {/* Allowed Domain Notice & Security Footnote */}
            <div className="axiom-auth-footnote">
              <span>Allowed domains: @gmail.com, @outlook.com, @yahoo.com</span>
              <div className="axiom-security-badge">
                <ShieldCheck size={14} className="text-emerald-500" />
                <span>PostgreSQL pgvector • JWT Session Security</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
