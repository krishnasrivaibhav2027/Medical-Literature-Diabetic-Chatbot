import React from "react";
import { X, BookOpen, ExternalLink, ShieldCheck, Cpu } from "lucide-react";

export default function SourcesModal({ isOpen, onClose, sources = [], metadata, modelInfo }) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card modal-card-large" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge bg-emerald-50">
              <BookOpen size={20} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="modal-title">Retrieved Sources & Context Metadata</h2>
              <p className="modal-subtitle">
                Verified medical chunks retrieved via Chroma Dense Embeddings + BM25 + Cross-Encoder
              </p>
            </div>
          </div>
          <button className="btn-icon-ghost" onClick={onClose} aria-label="Close sources modal">
            <X size={20} />
          </button>
        </div>

        {/* Execution Metadata Summary */}
        {metadata && (
          <div className="sources-metadata-banner">
            <div className="meta-stat">
              <span className="meta-stat-label">Query Intent</span>
              <span className={`meta-intent-pill ${metadata.intent === "Diabetes" ? "pill-diabetes" : "pill-other"}`}>
                <ShieldCheck size={14} />
                {metadata.intent || "Diabetes"}
              </span>
            </div>
            <div className="meta-stat">
              <span className="meta-stat-label">Total Tokens</span>
              <span className="meta-stat-value">⚡ {metadata.total_tokens || 0}</span>
            </div>
            <div className="meta-stat">
              <span className="meta-stat-label">Retrieval & Generation Time</span>
              <span className="meta-stat-value">⏱️ {metadata.execution_time_ms ? `${metadata.execution_time_ms} ms` : "0 ms"}</span>
            </div>
            <div className="meta-stat">
              <span className="meta-stat-label">Model Pipeline</span>
              <span className="meta-stat-value"><Cpu size={14} /> {metadata?.model || modelInfo?.model || "cohere/command-a-reasoning"}</span>
            </div>
          </div>
        )}

        {/* Sources Body */}
        <div className="modal-body">
          {sources.length === 0 ? (
            <div className="empty-sources-state">
              <BookOpen size={36} className="text-gray-300" />
              <p className="text-muted">No external sources were referenced for this query (classified as {metadata?.intent || "Other"}).</p>
            </div>
          ) : (
            <div className="sources-list-full">
              {sources.map((src, idx) => (
                <div key={src.id || idx} className="source-detail-card">
                  <div className="source-card-header">
                    <div className="source-index-badge">#{idx + 1}</div>
                    <div className="source-title-block">
                      <h4 className="source-main-title">{src.title}</h4>
                      {src.section && <span className="source-section-name">{src.section}</span>}
                    </div>
                    {src.score && (
                      <div className="source-relevance-pill">
                        Score: {(src.score * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>

                  <div className="source-method-tag">
                    <span>Pipeline: {src.retrieval_method || "Dense Vector + BM25 RRF"}</span>
                  </div>

                  <blockquote className="source-content-quote">
                    "{src.content}"
                  </blockquote>

                  {src.url && (
                    <div className="source-card-footer">
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noreferrer"
                        className="source-external-link"
                      >
                        <span>View Official Publication</span>
                        <ExternalLink size={14} />
                      </a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn-primary" onClick={onClose} style={{ marginLeft: "auto" }}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
