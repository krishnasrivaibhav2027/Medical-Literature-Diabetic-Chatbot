import React, { useState } from "react";
import {
  X,
  Sliders,
  RotateCcw,
  Check,
  Sparkles,
  Cpu,
  Layers,
  Zap,
  Key,
  Eye,
  EyeOff,
  ShieldCheck,
} from "lucide-react";
import { DEFAULT_SETTINGS } from "../constants/initialData";

export default function SettingsModal({ isOpen, onClose, settings, modelInfo, onSaveSettings }) {
  const [activeTab, setActiveTab] = useState("byok"); // "byok" | "parameters"
  const [formData, setFormData] = useState({
    ...DEFAULT_SETTINGS,
    ...settings,
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [showJinaKey, setShowJinaKey] = useState(false);
  const [savedToast, setSavedToast] = useState(false);

  if (!isOpen) return null;

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleProviderSelect = (providerId) => {
    let defaultBaseUrl = formData.base_url;
    let defaultModel = formData.model;

    if (providerId === "xkiro") {
      defaultBaseUrl = "https://api.xkiro.com/v1";
      defaultModel = "cohere/command-a-reasoning";
    } else if (providerId === "openai") {
      defaultBaseUrl = "https://api.openai.com/v1";
      defaultModel = "gpt-4o";
    } else if (providerId === "groq") {
      defaultBaseUrl = "https://api.groq.com/openai/v1";
      defaultModel = "llama-3.3-70b-versatile";
    }

    setFormData((prev) => ({
      ...prev,
      provider: providerId,
      base_url: defaultBaseUrl,
      model: defaultModel,
    }));
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
      <div className="modal-card" style={{ maxWidth: "580px" }} onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge">
              <Sliders size={20} className="text-primary" />
            </div>
            <div>
              <h2 className="modal-title">Model Settings & API Keys</h2>
              <p className="modal-subtitle">Configure BYOK credentials and Hybrid RAG retrieval pipeline</p>
            </div>
          </div>
          <button className="btn-icon-ghost" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: "flex", gap: "6px", padding: "10px 24px 0", borderBottom: "1px solid var(--border-light)" }}>
          <button
            type="button"
            onClick={() => setActiveTab("byok")}
            style={{
              padding: "8px 14px",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "byok" ? "2px solid var(--primary)" : "2px solid transparent",
              color: activeTab === "byok" ? "var(--primary)" : "var(--text-secondary)",
              fontWeight: activeTab === "byok" ? 700 : 500,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <Key size={15} />
            <span>API Credentials (BYOK)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("parameters")}
            style={{
              padding: "8px 14px",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "parameters" ? "2px solid var(--primary)" : "2px solid transparent",
              color: activeTab === "parameters" ? "var(--primary)" : "var(--text-secondary)",
              fontWeight: activeTab === "parameters" ? 700 : 500,
              fontSize: "0.85rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <Sliders size={15} />
            <span>Parameters & Cache</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ maxHeight: "65vh", overflowY: "auto", padding: "20px 24px" }}>
          {activeTab === "byok" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* BYOK Info Banner */}
              <div style={{
                display: "flex",
                gap: "10px",
                padding: "12px 14px",
                borderRadius: "12px",
                background: "rgba(37, 99, 235, 0.08)",
                border: "1px solid rgba(37, 99, 235, 0.2)",
                fontSize: "0.8rem",
                color: "var(--text-secondary)",
                lineHeight: "1.45"
              }}>
                <ShieldCheck size={20} className="text-primary" style={{ flexShrink: 0, marginTop: "2px" }} />
                <span>
                  <strong>Bring Your Own Key (BYOK):</strong> Your API keys are encrypted locally in your browser and passed per request via secure headers. If fields are left blank, the assistant uses the system default server keys.
                </span>
              </div>

              {/* Provider Selection */}
              <div className="byok-field-group">
                <label className="byok-label">AI Model Provider</label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
                  {[
                    { id: "xkiro", label: "XKiro (Default)" },
                    { id: "openai", label: "OpenAI (GPT-4o)" },
                    { id: "groq", label: "Groq Cloud" },
                    { id: "custom", label: "Custom Compatible" },
                  ].map((p) => {
                    const isSelected = (formData.provider || "xkiro") === p.id;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleProviderSelect(p.id)}
                        style={{
                          padding: "8px 12px",
                          borderRadius: "8px",
                          fontSize: "0.82rem",
                          fontWeight: isSelected ? 700 : 500,
                          background: isSelected ? "var(--primary-light)" : "var(--bg-card)",
                          color: isSelected ? "var(--primary)" : "var(--text-secondary)",
                          border: isSelected ? "1.5px solid var(--primary)" : "1px solid var(--border-light)",
                          cursor: "pointer",
                          textAlign: "center",
                          transition: "all 0.15s ease",
                        }}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Base URL */}
              <div className="byok-field-group">
                <label className="byok-label" htmlFor="byok-base-url">
                  API Base URL
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    id="byok-base-url"
                    type="text"
                    value={formData.base_url || ""}
                    onChange={(e) => handleChange("base_url", e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    className="byok-input"
                  />
                </div>
                <span className="byok-info-note">Supports any OpenAI-compatible `/v1/chat/completions` endpoint.</span>
              </div>

              {/* Model Name */}
              <div className="byok-field-group">
                <label className="byok-label" htmlFor="byok-model-name">
                  Model Identifier
                </label>
                <input
                  id="byok-model-name"
                  type="text"
                  value={formData.model || ""}
                  onChange={(e) => handleChange("model", e.target.value)}
                  placeholder="e.g. gpt-4o, cohere/command-a-reasoning, llama-3.3-70b-versatile"
                  className="byok-input"
                />
              </div>

              {/* LLM API Key */}
              <div className="byok-field-group">
                <label className="byok-label" htmlFor="byok-api-key">
                  LLM API Key
                </label>
                <div className="byok-input-password-wrap">
                  <input
                    id="byok-api-key"
                    type={showApiKey ? "text" : "password"}
                    value={formData.api_key || ""}
                    onChange={(e) => handleChange("api_key", e.target.value)}
                    placeholder="Paste your API key (sk-...)"
                    className="byok-input"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="byok-eye-btn"
                    onClick={() => setShowApiKey((v) => !v)}
                    title={showApiKey ? "Hide key" : "Show key"}
                  >
                    {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <span className="byok-info-note">Leave empty to use the system default server key.</span>
              </div>

              {/* Jina Reranker API Key */}
              <div className="byok-field-group">
                <label className="byok-label" htmlFor="byok-jina-key">
                  Jina AI Reranker API Key (Optional)
                </label>
                <div className="byok-input-password-wrap">
                  <input
                    id="byok-jina-key"
                    type={showJinaKey ? "text" : "password"}
                    value={formData.jina_api_key || ""}
                    onChange={(e) => handleChange("jina_api_key", e.target.value)}
                    placeholder="jina_..."
                    className="byok-input"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    className="byok-eye-btn"
                    onClick={() => setShowJinaKey((v) => !v)}
                    title={showJinaKey ? "Hide key" : "Show key"}
                  >
                    {showJinaKey ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <span className="byok-info-note">If blank, utilizes the server's Jina Reranker v3.5 with RRF fallback.</span>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Active Model Indicator */}
              <div className="setting-card">
                <div className="setting-card-header">
                  <div className="setting-label-wrap">
                    <Cpu size={16} className="text-blue-600" />
                    <span className="setting-name">Underlying Model</span>
                  </div>
                  <span className="badge badge-blue">{formData.provider || modelInfo?.provider || "Xkiro Cloud API"}</span>
                </div>
                <p className="setting-desc">
                  Configured model: <code className="code-inline">{formData.model || "cohere/command-a-reasoning"}</code> with <code className="code-inline">{modelInfo?.embedding_model || "jina-embeddings-v3"}</code> dense embeddings.
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
                <Layers size={16} className="text-blue-500" />
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
      )}
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
