import React, { useState, useRef, useEffect } from "react";
import { Send, Square, Key } from "lucide-react";

export default function ChatInput({
  onSendMessage,
  isGenerating,
  onAbortGeneration,
  placeholder = "What's in your mind?...",
  isApiKeyMissing = false,
  onOpenSettings,
}) {
  const [inputText, setInputText] = useState("");
  const textareaRef = useRef(null);

  // Auto-resize textarea according to text height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const nextHeight = Math.min(textareaRef.current.scrollHeight, 140);
      textareaRef.current.style.height = `${Math.max(nextHeight, 24)}px`;
    }
  }, [inputText]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (isApiKeyMissing) {
      if (onOpenSettings) onOpenSettings();
      return;
    }
    if (isGenerating) return;
    if (!inputText.trim()) return;

    onSendMessage(inputText.trim());
    setInputText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "24px";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputClick = () => {
    if (isApiKeyMissing && onOpenSettings) {
      onOpenSettings();
    }
  };

  const resolvedPlaceholder = isApiKeyMissing
    ? "⚠️ AI Model API Key Required to chat. Click here to configure in Settings..."
    : placeholder;

  return (
    <div className="chat-input-wrapper">
      {/* Ambient Gradient Blur Overlay for scrolling content */}
      <div className="chat-bottom-blur-overlay" aria-hidden="true" />

      <form className="chat-input-pill" onSubmit={handleSubmit}>
        {/* Input Text Area */}
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={(e) => {
            if (isApiKeyMissing) {
              if (onOpenSettings) onOpenSettings();
              return;
            }
            setInputText(e.target.value);
          }}
          onClick={handleInputClick}
          onKeyDown={handleKeyDown}
          placeholder={resolvedPlaceholder}
          rows={1}
          className="chat-textarea"
          disabled={isGenerating}
        />

        {/* Dynamic Action Button:
            - When key missing: Red key button that prompts settings
            - When generating: Circular red button with stop icon to terminate session
            - When idle: Circular royal blue send button with paper airplane
        */}
        {isApiKeyMissing ? (
          <button
            type="button"
            className="btn-circular-action"
            style={{
              background: "linear-gradient(135deg, #ef4444, #dc2626)",
              color: "#fff",
              boxShadow: "0 2px 8px rgba(239, 68, 68, 0.4)",
            }}
            onClick={onOpenSettings}
            title="AI Model API Key Required (Click to configure)"
            aria-label="Configure API Key"
          >
            <Key size={16} />
          </button>
        ) : isGenerating ? (
          <button
            type="button"
            className="btn-circular-action btn-terminate-generation"
            onClick={onAbortGeneration}
            title="Terminate session (stopped execution will not be saved to history)"
            aria-label="Stop generation and terminate session"
          >
            <Square size={16} fill="currentColor" strokeWidth={0} />
            <span className="pulse-ring" />
          </button>
        ) : (
          <button
            type="submit"
            className="btn-circular-action btn-send-message"
            disabled={!inputText.trim()}
            title="Send query (Enter)"
            aria-label="Send message"
          >
            <Send size={18} strokeWidth={2.2} />
          </button>
        )}
      </form>
    </div>
  );
}
