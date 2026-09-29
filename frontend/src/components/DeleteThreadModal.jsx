import React from "react";
import { Trash2, X, MessageSquare, AlertTriangle } from "lucide-react";

export default function DeleteThreadModal({
  isOpen,
  onClose,
  onConfirm,
  threadTitle = "this conversation",
  isClearAll = false,
  threadCount = 0,
  isDeleting = false,
}) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card modal-card-small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge bg-rose-50">
              <Trash2 size={20} className="text-rose-600" />
            </div>
            <div>
              <h2 className="modal-title">
                {isClearAll ? "Clear All Conversations" : "Delete Conversation"}
              </h2>
              <p className="modal-subtitle">
                {isClearAll ? "Confirm removing all chat history" : "Confirm removing chat thread"}
              </p>
            </div>
          </div>
          <button
            className="btn-icon-ghost"
            onClick={onClose}
            disabled={isDeleting}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="logout-confirm-box">
            <div className="user-profile-summary">
              <div
                style={{
                  width: "42px",
                  height: "42px",
                  borderRadius: "10px",
                  background: "#FEE2E2",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {isClearAll ? (
                  <AlertTriangle size={20} className="text-rose-600" />
                ) : (
                  <MessageSquare size={20} className="text-rose-600" />
                )}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <h4
                  className="user-summary-name"
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={isClearAll ? "All Conversations" : threadTitle}
                >
                  {isClearAll ? `All Conversations (${threadCount})` : threadTitle}
                </h4>
                <p className="user-summary-email">
                  {isClearAll ? "Bulk Deletion" : "Permanent Deletion"}
                </p>
              </div>
            </div>

            <p className="logout-note">
              {isClearAll
                ? "Are you sure you want to clear all conversations? All your chat threads and associated messages will be permanently removed. This action cannot be undone."
                : "Are you sure you want to delete this conversation? All associated messages and clinical context will be permanently removed. This action cannot be undone."}
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose} disabled={isDeleting}>
            Cancel
          </button>
          <button
            className="btn-danger"
            onClick={onConfirm}
            disabled={isDeleting}
            style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
          >
            <Trash2 size={16} />
            <span>
              {isDeleting
                ? isClearAll
                  ? "Clearing..."
                  : "Deleting..."
                : isClearAll
                ? "Clear All"
                : "Delete"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
