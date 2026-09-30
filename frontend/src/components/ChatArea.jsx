import React, { useState, useEffect, useRef, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Copy,
  Check,
  RotateCw,
  MoreVertical,
  Edit3,
  Sparkles,
  BookOpen,
  ShieldCheck,
  Cpu,
  Clock,
  Zap,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Bot,
  X,
  Loader2,
} from "lucide-react";
import { SUGGESTED_PROMPTS } from "../services/greetingGenerator";
import { contributeResponse } from "../services/api";

export default function ChatArea({
  thread,
  user,
  greetingData,
  onSendMessage,
  onRegenerate,
  onInspectSources,
  isGenerating,
  streamingMessage,
  modelInfo,
}) {
  const messagesEndRef = useRef(null);
  const [copiedId, setCopiedId] = useState(null);
  const [expandedSources, setExpandedSources] = useState({}); // { [msgId]: boolean }
  const [contributeState, setContributeState] = useState({}); // { [msgKey]: 'idle' | 'loading' | 'success' | 'dismissed' | 'error' }
  const [contributeError, setContributeError] = useState({});

  // Deduplicate consecutive identical user queries so query is displayed only once even across multiple regenerations
  const messages = useMemo(() => {
    const raw = thread?.messages || [];
    const filtered = [];
    for (let i = 0; i < raw.length; i++) {
      const cur = raw[i];
      const prev = filtered[filtered.length - 1];
      if (
        cur.role === "user" &&
        prev &&
        prev.role === "user" &&
        cur.content.trim() === prev.content.trim()
      ) {
        continue;
      }
      filtered.push(cur);
    }
    return filtered;
  }, [thread?.messages]);

  const lastAssistantIndex = messages.map((m) => m.role).lastIndexOf("assistant");

  // Scroll to bottom when new messages arrive or while streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingMessage?.content]);

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const toggleSources = (msgId) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const handleContribute = async (msg, index) => {
    const msgKey = msg.id || `msg-${index}`;
    const userQuery =
      msg.metadata?.query ||
      (index > 0 && messages[index - 1]?.role === "user"
        ? messages[index - 1].content
        : "");

    if (!userQuery) {
      setContributeError((prev) => ({
        ...prev,
        [msgKey]: "Cannot determine associated user question.",
      }));
      return;
    }

    setContributeState((prev) => ({ ...prev, [msgKey]: "loading" }));
    try {
      await contributeResponse({
        query: userQuery,
        response: msg.content,
        category: msg.metadata?.intent || "Diabetes Management",
        sources: msg.sources || [],
      });
      setContributeState((prev) => ({ ...prev, [msgKey]: "success" }));
    } catch (err) {
      console.error("Failed to contribute response:", err);
      setContributeState((prev) => ({ ...prev, [msgKey]: "error" }));
      setContributeError((prev) => ({
        ...prev,
        [msgKey]: err.message || "Failed to contribute response",
      }));
    }
  };

  const handleDismissContribute = (msg, index) => {
    const msgKey = msg.id || `msg-${index}`;
    setContributeState((prev) => ({ ...prev, [msgKey]: "dismissed" }));
  };

  const hasMessages = messages.length > 0 || (isGenerating && streamingMessage);

  return (
    <div className="chat-messages-container">
      {!hasMessages ? (
        /* Empty State: Default Greeting Message (Randomly generated with time-of-day and welcome variations) */
        <div className="chat-empty-greeting-container animate-fade-in">
          <div className="greeting-sparkle-badge">
            <Sparkles size={28} className="text-primary animate-pulse" />
          </div>

          <h2 className="greeting-main-title">{greetingData?.greeting || `Welcome, ${user?.firstName || "Andrew"}!`}</h2>
          <p className="greeting-subtitle">{greetingData?.subtitle || "What brings you here today? Ask me about clinical diabetes management or general questions."}</p>

          <div className="greeting-suggestions-grid">
            {SUGGESTED_PROMPTS.map((item, idx) => (
              <button
                key={idx}
                className="suggestion-card"
                onClick={() => onSendMessage(item.prompt)}
              >
                <div className="suggestion-card-header">
                  <span className="suggestion-tag">{item.tag}</span>
                  <Sparkles size={14} className="text-blue-400" />
                </div>
                <h4 className="suggestion-card-title">{item.title}</h4>
                <p className="suggestion-card-desc">{item.prompt}</p>
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* Active Chat Message Stream */
        <div className="chat-messages-list">
          {messages.map((msg, index) => {
            if (msg.role === "user") {
              return (
                <div key={msg.id || index} className="message-row user-row animate-fade-in">
                  <div className="user-avatar-wrap">
                    <div className="user-avatar-circle">
                      <span className="user-avatar-letter">
                        {(user?.username || user?.name || user?.email || "U")[0].toUpperCase()}
                      </span>
                    </div>
                  </div>

                  <div className="message-content user-message-content">
                    <p className="user-text-query">{msg.content}</p>
                  </div>

                  <div className="user-message-actions">
                    <button
                      className="btn-msg-ghost"
                      onClick={() => onSendMessage(msg.content)}
                      title="Edit / re-ask question"
                      aria-label="Edit question"
                    >
                      <Edit3 size={15} />
                    </button>
                  </div>
                </div>
              );
            }

            // Assistant message
            const isLatestAssistant = index === lastAssistantIndex && !isGenerating;
            const hasSources = msg.sources && msg.sources.length > 0;
            const sourcesOpen = expandedSources[msg.id];
            const msgKey = msg.id || `msg-${index}`;
            const userQuery =
              msg.metadata?.query ||
              (index > 0 && messages[index - 1]?.role === "user"
                ? messages[index - 1].content
                : "");
            const isDirectCache =
              msg.metadata?.can_contribute === false ||
              msg.metadata?.model?.includes("Direct") ||
              (msg.metadata?.similarity !== undefined && msg.metadata?.similarity >= 0.80);
            const canContribute = isLatestAssistant && userQuery && !isDirectCache;

            return (
              <div key={msg.id || index} className="message-row assistant-row animate-fade-in">
                {/* Assistant Robot Avatar Alike User Profile Icon */}
                <div className="assistant-avatar-wrap">
                  <div className="assistant-avatar-circle">
                    <Bot size={18} strokeWidth={2.2} />
                  </div>
                </div>

                {/* Assistant Markdown Content */}
                <div className="assistant-content-wrapper">
                  <div className="markdown-prose">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* Post-generation Associated Metadata & Sources */}
                  {(msg.metadata || hasSources) && (
                    <div className="post-response-meta-container">
                      {/* Metadata Badges Bar */}
                      <div className="meta-badges-row">
                        {msg.metadata?.intent && (
                          <span
                            className={`meta-badge-chip ${
                              msg.metadata.intent === "Diabetes"
                                ? "chip-intent-diabetes"
                                : "chip-intent-other"
                            }`}
                            title={`Query classified as: ${msg.metadata.intent}`}
                          >
                            <ShieldCheck size={13} />
                            <span>Intent: {msg.metadata.intent}</span>
                          </span>
                        )}

                        {msg.metadata?.total_tokens && (
                          <span className="meta-badge-chip chip-tokens" title="Tokens used for response">
                            <Zap size={13} />
                            <span>{msg.metadata.total_tokens} tokens</span>
                          </span>
                        )}

                        {msg.metadata?.execution_time_ms && (
                          <span className="meta-badge-chip chip-timing" title="End-to-end execution time">
                            <Clock size={13} />
                            <span>{(msg.metadata.execution_time_ms / 1000).toFixed(2)}s</span>
                          </span>
                        )}

                        <span className="meta-badge-chip chip-model" title="Underlying model">
                          <Cpu size={13} />
                          <span>{msg.metadata?.model || modelInfo?.model || "cohere/command-a-reasoning"}</span>
                        </span>

                        {/* Sources toggle trigger */}
                        {hasSources && (
                          <button
                            className="btn-sources-toggle"
                            onClick={() => toggleSources(msg.id)}
                            title="View Hybrid RAG retrieval sources"
                          >
                            <BookOpen size={13} />
                            <span>{msg.sources.length} Sources</span>
                            {sourcesOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                        )}
                      </div>

                      {/* Expandable Sources Preview Cards */}
                      {hasSources && sourcesOpen && (
                        <div className="sources-preview-drawer animate-fade-in">
                          <div className="sources-preview-header">
                            <span className="sources-preview-title">
                              Retrieved Context Documents (Chroma Dense + BM25 + Cross-Encoder)
                            </span>
                            <button
                              className="btn-link-inspect"
                              onClick={() => onInspectSources(msg.sources, msg.metadata)}
                            >
                              <span>Inspect All in Detail</span>
                              <ExternalLink size={12} />
                            </button>
                          </div>

                          <div className="sources-chips-grid">
                            {msg.sources.map((src, sIdx) => (
                              <div
                                key={src.id || sIdx}
                                className="source-preview-card"
                                onClick={() => onInspectSources([src], msg.metadata)}
                              >
                                <div className="src-card-top">
                                  <span className="src-card-num">[{sIdx + 1}]</span>
                                  <span className="src-card-title">{src.title}</span>
                                  {src.score && (
                                    <span className="src-score-badge">
                                      {(src.score * 100).toFixed(0)}%
                                    </span>
                                  )}
                                </div>
                                <p className="src-card-snippet">{src.content}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Contribute Response Prompt & Note (Only for latest conversation when canContribute is allowed) */}
                  {canContribute && (
                    <div className="contribute-response-wrapper">
                      {contributeState[msgKey] === "success" ? (
                        <div className="contribute-success-chip animate-fade-in">
                          <Check size={14} className="text-emerald-600" />
                          <span>Response contributed to pre-computed QA cache! Faster responses enabled for similar queries.</span>
                        </div>
                      ) : contributeState[msgKey] === "dismissed" ? null : (
                        <div className="contribute-response-bar animate-fade-in">
                          <div className="contribute-info">
                            <span className="contribute-badge">
                              <Sparkles size={13} />
                              <span>Contribute response</span>
                            </span>
                            <p className="contribute-note-text">
                              This will be used for faster responses for other users with a similar query.
                            </p>
                          </div>

                          <div className="contribute-actions-group">
                            {contributeState[msgKey] === "loading" ? (
                              <div className="contribute-spinner-wrap">
                                <Loader2 size={15} className="animate-spin" />
                                <span className="contribute-saving-label">Saving...</span>
                              </div>
                            ) : (
                              <>
                                <button
                                  className="btn-contribute-tick"
                                  onClick={() => handleContribute(msg, index)}
                                  title="Confirm: Save to pre-computed QA"
                                  aria-label="Confirm contribution"
                                >
                                  <Check size={15} strokeWidth={2.8} />
                                </button>
                                <button
                                  className="btn-contribute-cross"
                                  onClick={() => handleDismissContribute(msg, index)}
                                  title="Dismiss note without saving"
                                  aria-label="Dismiss note"
                                >
                                  <X size={15} strokeWidth={2.8} />
                                </button>
                              </>
                            )}
                          </div>

                          {contributeState[msgKey] === "error" && (
                            <span className="contribute-error-msg">{contributeError[msgKey]}</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Assistant Actions Bar: Copy, More, Regenerate */}
                  <div className="assistant-actions-footer">
                    <div className="actions-left-group">
                      <button
                        className="btn-action-icon"
                        onClick={() => handleCopy(msg.id, msg.content)}
                        title={copiedId === msg.id ? "Copied to clipboard!" : "Copy message"}
                        aria-label="Copy response"
                      >
                        {copiedId === msg.id ? (
                          <Check size={15} className="text-emerald-600" />
                        ) : (
                          <Copy size={15} />
                        )}
                      </button>

                      <button
                        className="btn-action-icon"
                        onClick={() => {
                          alert(`Metadata Export:\n${JSON.stringify(msg.metadata || {}, null, 2)}`);
                        }}
                        title="Export details / More options"
                        aria-label="More options"
                      >
                        <MoreVertical size={15} />
                      </button>

                      {canContribute && contributeState[msgKey] === "dismissed" && (
                        <button
                          className="btn-action-icon"
                          onClick={() => setContributeState((prev) => ({ ...prev, [msgKey]: "idle" }))}
                          title="Reopen contribute response prompt"
                          aria-label="Contribute response"
                        >
                          <Sparkles size={15} />
                        </button>
                      )}
                    </div>

                    <div className="actions-right-group">
                      <button
                        className="btn-regenerate"
                        onClick={() => onRegenerate(index)}
                        disabled={isGenerating}
                        title="Regenerate this response"
                      >
                        <RotateCw size={14} className={isGenerating ? "animate-spin" : ""} />
                        <span>Regenerate</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Active In-Progress Streaming Message */}
          {isGenerating && streamingMessage && (
            <div className="message-row assistant-row streaming-row animate-fade-in">
              {/* Assistant Robot Avatar Alike User Profile Icon */}
              <div className="assistant-avatar-wrap">
                <div className="assistant-avatar-circle">
                  <Bot size={18} strokeWidth={2.2} />
                </div>
              </div>

              <div className="assistant-content-wrapper">
                <div className="markdown-prose">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {streamingMessage.content}
                  </ReactMarkdown>
                  <span className="streaming-cursor-caret" />
                </div>
                <div className="generating-indicator-badge">
                  <span className="pulse-dot" />
                  <span>Synthesizing response & running RRF ranker...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  );
}
