import React from "react";
import { ShieldAlert, Lock, ArrowRight, Stethoscope } from "lucide-react";

export default function ForbiddenPage({ onGoToLogin }) {
  return (
    <div className="forbidden-root">
      <div className="forbidden-card">
        <div className="forbidden-icon-badge">
          <ShieldAlert size={36} className="forbidden-icon" />
        </div>

        <div className="forbidden-header">
          <div className="forbidden-badge">
            <Lock size={12} />
            <span>HTTP 403 • FORBIDDEN</span>
          </div>
          <h1 className="forbidden-title">Access Denied</h1>
          <p className="forbidden-subtitle">
            You do not have authorization to access the Medical Literature Assistant.
          </p>
        </div>

        <div className="forbidden-body">
          <p className="forbidden-text">
            This clinical decision-support platform is strictly protected. Unauthenticated sessions
            cannot view chat conversations, patient queries, or access internal clinical knowledge bases.
          </p>
          <div className="forbidden-callout">
            <Stethoscope size={16} className="callout-icon" />
            <span>Please authenticate with valid medical staff credentials to establish an encrypted session.</span>
          </div>
        </div>

        <div className="forbidden-footer">
          <button
            id="forbidden-login-btn"
            className="btn-forbidden-login"
            onClick={onGoToLogin}
          >
            <span>Proceed to Login</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
