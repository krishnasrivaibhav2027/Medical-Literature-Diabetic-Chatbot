import React, { useState } from "react";
import { X, Sliders, RotateCcw, Check, Sparkles, Cpu, Layers, Zap } from "lucide-react";
import { DEFAULT_SETTINGS } from "../constants/initialData";

export default function SettingsModal({ isOpen, onClose, settings, modelInfo, onSaveSettings }) {
  if (!isOpen) return null;

  const [formData, setFormData] = useState({ ...settings });
  const [savedToast, setSavedToast] = useState(false);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleReset = () => {
    setFormData({ ...DEFAULT_SETTINGS });
  };

  const handleSave = () => {
    onSaveSettings(formData);
    setSavedToast(true);
    setTimeout(() => {
      setSavedToast(false);
      onClose();
    }, 400);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge">
              <Sliders size={20} className="text-primary" />
            </div>
            <div>
              <h2 className="modal-title">Model Settings & Parameters</h2>
              <p className="modal-subtitle">Configure generation parameters and Hybrid RAG retrieval pipeline</p>
            </div>
          </div>
          <button className="btn-icon-ghost" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* Active Model Indicator */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Cpu size={16} className="text-indigo-600" />
                <span className="setting-name">Underlying Model</span>
              </div>
              <span className="badge badge-indigo">{modelInfo?.provider || "Xkiro Cloud API"}</span>
            </div>
            <p className="setting-desc">
              Currently powered by <code className="code-inline">{modelInfo?.model || formData.model || "cohere/command-a-reasoning"}</code> with <code className="code-inline">{modelInfo?.embedding_model || "google/embeddinggemma-300m"}</code> dense embeddings.
            </p>
          </div>

          {/* Temperature Slider */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Sparkles size={16} className="text-amber-500" />
                <span className="setting-name">Temperature</span>
              </div>
              <div className="setting-value-chip">{formData.temperature.toFixed(2)}</div>
            </div>
            <p className="setting-desc">
              Controls randomness. Lower values (e.g. 0.1 - 0.3) provide factual, deterministic clinical answers, while higher values encourage creative formulation.
            </p>
            <div className="range-container">
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={formData.temperature}
                onChange={(e) => handleChange("temperature", parseFloat(e.target.value))}
                className="custom-range"
              />
              <div className="range-labels">
                <span>0.0 (Precise / Factual)</span>
                <span>0.5 (Balanced)</span>
                <span>1.0 (Creative)</span>
              </div>
            </div>
          </div>

          {/* Top_P Slider */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Layers size={16} className="text-blue-500" />
                <span className="setting-name">Top P (Nucleus Sampling)</span>
              </div>
              <div className="setting-value-chip">{formData.top_p.toFixed(2)}</div>
            </div>
            <p className="setting-desc">
              Controls cumulative probability cutoff for token selection. Only tokens comprising the top P probability mass are considered.
            </p>
            <div className="range-container">
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={formData.top_p}
                onChange={(e) => handleChange("top_p", parseFloat(e.target.value))}
                className="custom-range"
              />
              <div className="range-labels">
                <span>0.1 (Strict)</span>
                <span>0.9 (Standard)</span>
                <span>1.0 (Full Mass)</span>
              </div>
            </div>
          </div>

          {/* Top_K Slider */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Sliders size={16} className="text-emerald-500" />
                <span className="setting-name">Top K (Vocabulary Pool)</span>
              </div>
              <div className="setting-value-chip">{formData.top_k}</div>
            </div>
            <p className="setting-desc">
              Restricts token selection to the K highest probability vocabulary items at each generation step.
            </p>
            <div className="range-container">
              <input
                type="range"
                min="1"
                max="100"
                step="1"
                value={formData.top_k}
                onChange={(e) => handleChange("top_k", parseInt(e.target.value, 10))}
                className="custom-range"
              />
              <div className="range-labels">
                <span>1 (Single Best)</span>
                <span>40 (Recommended)</span>
                <span>100 (Broad)</span>
              </div>
            </div>
          </div>

          {/* RRF & Cross-Encoder Top N */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Layers size={16} className="text-violet-500" />
                <span className="setting-name">Reranker Top N Documents</span>
              </div>
              <div className="setting-value-chip">{formData.reranker_top_n} docs</div>
            </div>
            <p className="setting-desc">
              Number of top retrieved candidate chunks passed from Reciprocal Rank Fusion (RRF) through the Cross-Encoder reranker.
            </p>
            <div className="range-container">
              <input
                type="range"
                min="3"
                max="20"
                step="1"
                value={formData.reranker_top_n}
                onChange={(e) => handleChange("reranker_top_n", parseInt(e.target.value, 10))}
                className="custom-range"
              />
              <div className="range-labels">
                <span>3 chunks</span>
                <span>10 chunks (Default)</span>
                <span>20 chunks</span>
              </div>
            </div>
          </div>

          {/* Redis Token Stream Replay Mode */}
          <div className="setting-card">
            <div className="setting-card-header">
              <div className="setting-label-wrap">
                <Zap size={16} className="text-amber-500" />
                <span className="setting-name">Cache Stream Replay Mode</span>
              </div>
              <div className="setting-value-chip">
                {formData.stream_mode === "instant"
                  ? "Single Instant"
                  : formData.stream_mode === "smooth"
                  ? "Smooth Paced"
                  : "High-Speed Burst"}
              </div>
            </div>
            <p className="setting-desc">
              Controls how cached responses replay from Redis: High-Speed Burst provides rapid micro-batch SSE streaming (~40ms), while Single Instant returns the full text immediately (&lt;5ms).
            </p>
            <div style={{ display: "flex", gap: "8px", marginTop: "6px" }}>
              {[
                { id: "burst", label: "⚡ High-Speed Burst (Default)" },
                { id: "instant", label: "🚀 Single Instant (<5ms)" },
                { id: "smooth", label: "⏳ Smooth Paced" },
              ].map((opt) => {
                const active = (formData.stream_mode || "burst") === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => handleChange("stream_mode", opt.id)}
                    style={{
                      flex: 1,
                      padding: "8px 10px",
                      borderRadius: "10px",
                      fontSize: "0.78rem",
                      fontWeight: active ? 700 : 500,
                      border: active ? "1.5px solid var(--primary)" : "1px solid var(--border-light)",
                      background: active ? "var(--primary-light)" : "var(--bg-card)",
                      color: active ? "var(--primary)" : "var(--text-secondary)",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <button className="btn-secondary" onClick={handleReset}>
            <RotateCcw size={16} />
            <span>Reset to Defaults</span>
          </button>
          <div className="footer-actions-right">
            <button className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button className="btn-primary" onClick={handleSave}>
              <Check size={16} />
              <span>{savedToast ? "Saved!" : "Save Changes"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
