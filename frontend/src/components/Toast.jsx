import React from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

export default function Toast({ toast, onClose }) {
  if (!toast) return null;

  const { type = "info", message } = toast;

  const getIcon = () => {
    switch (type) {
      case "success":
        return <CheckCircle2 size={18} className="text-emerald-500" />;
      case "warning":
        return <AlertCircle size={18} className="text-amber-500" />;
      case "error":
        return <AlertCircle size={18} className="text-rose-500" />;
      default:
        return <Info size={18} className="text-blue-500" />;
    }
  };

  return (
    <div className={`toast-notification toast-${type} animate-slide-up`}>
      <div className="toast-icon-wrap">{getIcon()}</div>
      <span className="toast-message">{message}</span>
      <button className="toast-close-btn" onClick={onClose} aria-label="Dismiss notification">
        <X size={14} />
      </button>
    </div>
  );
}
