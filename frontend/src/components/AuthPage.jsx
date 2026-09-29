import React, { useState } from "react";
import {
  Sparkles,
  Lock,
  Mail,
  User,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { registerUser, loginUser, getMe } from "../services/api";

export default function AuthPage({ onAuthSuccess }) {
  const [isLogin, setIsLogin] = useState(false); // default to Sign Up per request
  const [showPassword, setShowPassword] = useState(false);
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    const emailTrimmed = formData.email.trim().toLowerCase();

    // Basic domain check matching backend allowed domains
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
        // 1. Register user (populates both created_at and login_at at the same time)
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

        // 3. Immediately redirect to chat page with both created_at & login_at populated!
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

        onAuthSuccess(authedUser);
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

        onAuthSuccess(authedUser);
      }
    } catch (err) {
      console.error("Auth error:", err);
      setErrorMsg(err.message || "Authentication failed. Please check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-root">
      <div className="auth-card-wrapper animate-fade-in">
        {/* Brand Header */}
        <div className="auth-brand-header">
          <div className="auth-sparkle-icon">
            <Sparkles size={28} className="text-primary" />
          </div>
          <h1 className="auth-brand-title">Medical Literature Assistant</h1>
          <p className="auth-brand-subtitle">
            Diabetic & Clinical Literature Assistant backed by Hybrid RAG
          </p>
        </div>

        {/* Tab Switcher: Sign Up / Log In */}
        <div className="auth-tab-switch">
          <button
            type="button"
            className={`auth-tab-btn ${!isLogin ? "active" : ""}`}
            onClick={() => {
              setIsLogin(false);
              setErrorMsg("");
            }}
          >
            Create Account
          </button>
          <button
            type="button"
            className={`auth-tab-btn ${isLogin ? "active" : ""}`}
            onClick={() => {
              setIsLogin(true);
              setErrorMsg("");
            }}
          >
            Log In
          </button>
        </div>

        {/* Error Alert Banner */}
        {errorMsg && (
          <div className="auth-error-banner animate-fade-in">
            <AlertCircle size={18} className="text-rose-500 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Auth Form */}
        <form className="auth-form" onSubmit={handleSubmit}>
          {/* Username (Sign Up only) */}
          {!isLogin && (
            <div className="form-group">
              <label className="form-label" htmlFor="username">
                Username
              </label>
              <div className="input-with-icon">
                <User size={18} className="input-icon-left" />
                <input
                  id="username"
                  type="text"
                  required
                  placeholder="e.g. vaibhav_clinical"
                  value={formData.username}
                  onChange={(e) => handleChange("username", e.target.value)}
                  className="auth-input"
                  minLength={3}
                  maxLength={50}
                />
              </div>
            </div>
          )}

          {/* Email */}
          <div className="form-group">
            <div className="form-label-row">
              <label className="form-label" htmlFor="email">
                Email Address
              </label>
              <span className="form-label-hint">Gmail, Outlook, Yahoo</span>
            </div>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon-left" />
              <input
                id="email"
                type="email"
                required
                placeholder="name@gmail.com"
                value={formData.email}
                onChange={(e) => handleChange("email", e.target.value)}
                className="auth-input"
              />
            </div>
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <div className="input-with-icon">
              <Lock size={18} className="input-icon-left" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                placeholder="Enter password"
                value={formData.password}
                onChange={(e) => handleChange("password", e.target.value)}
                className="auth-input"
              />
              <button
                type="button"
                className="btn-toggle-password"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Confirm Password & Checklist (Sign Up only) */}
          {!isLogin && (
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="confirmPassword">
                  Confirm Password
                </label>
                <div className="input-with-icon">
                  <Lock size={18} className="input-icon-left" />
                  <input
                    id="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="Re-enter password"
                    value={formData.confirmPassword}
                    onChange={(e) => handleChange("confirmPassword", e.target.value)}
                    className="auth-input"
                  />
                </div>
              </div>

              {/* Password Requirements Real-Time Checklist */}
              <div className="password-checklist">
                <div className={`check-item ${passwordChecks.length ? "checked" : ""}`}>
                  <CheckCircle2 size={13} />
                  <span>At least 8 characters</span>
                </div>
                <div className={`check-item ${passwordChecks.uppercase ? "checked" : ""}`}>
                  <CheckCircle2 size={13} />
                  <span>One uppercase letter</span>
                </div>
                <div className={`check-item ${passwordChecks.lowercase ? "checked" : ""}`}>
                  <CheckCircle2 size={13} />
                  <span>One lowercase letter</span>
                </div>
                <div className={`check-item ${passwordChecks.digit ? "checked" : ""}`}>
                  <CheckCircle2 size={13} />
                  <span>At least one number</span>
                </div>
                <div className={`check-item ${passwordChecks.special ? "checked" : ""}`}>
                  <CheckCircle2 size={13} />
                  <span>Special character (!@#$%^&*)</span>
                </div>
                {formData.confirmPassword && (
                  <div className={`check-item ${passwordChecks.match ? "checked" : ""}`}>
                    <CheckCircle2 size={13} />
                    <span>Passwords match</span>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            className="btn-auth-submit"
            disabled={loading || (!isLogin && !isPasswordValid)}
          >
            {loading ? (
              <span className="auth-spinner" />
            ) : (
              <>
                <span>{!isLogin ? "Sign Up & Start Chat" : "Log In & Continue"}</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        {/* Footer Security Badge */}
        <div className="auth-footer-badge">
          <ShieldCheck size={15} className="text-emerald-500" />
          <span>PostgreSQL + JWT Secure Session Management</span>
        </div>
      </div>
    </div>
  );
}
