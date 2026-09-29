import React from "react";
import { LogOut, X, AlertCircle } from "lucide-react";

export default function LogoutModal({ isOpen, onClose, onConfirm, user }) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card modal-card-small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge bg-rose-50">
              <LogOut size={20} className="text-rose-600" />
            </div>
            <div>
              <h2 className="modal-title">Sign Out</h2>
              <p className="modal-subtitle">Confirm ending current user session</p>
            </div>
          </div>
          <button className="btn-icon-ghost" onClick={onClose} aria-label="Close logout modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="logout-confirm-box">
            <div className="user-profile-summary">
              <div className="user-avatar-circle user-avatar-large">
                {user?.avatar ? (
                  <img
                    src={user.avatar}
                    alt={user?.username || "User"}
                    className="user-profile-avatar-large"
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                ) : (
                  <span className="user-avatar-letter-large">
                    {(user?.username || user?.name || "U")[0].toUpperCase()}
                  </span>
                )}
              </div>
              <div className="user-summary-text-block">
                <h4 className="user-summary-name">{user?.username || user?.name || "User"}</h4>
                <p className="user-summary-email">{user?.email || ""}</p>
                <div className="user-timestamps-row">
                  {user?.created_at && (
                    <span className="timestamp-badge">
                      Joined: {new Date(user.created_at).toLocaleDateString()}
                    </span>
                  )}
                  {user?.login_at && (
                    <span className="timestamp-badge">
                      Session: {new Date(user.login_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <p className="logout-note">
              Are you sure you want to sign out? You will be redirected to the sign in page.
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-danger" onClick={onConfirm}>
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );
}
