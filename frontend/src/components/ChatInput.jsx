import React, { useState, useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";

export default function ChatInput({
  onSendMessage,
  isGenerating,
  onAbortGeneration,
  placeholder = "What's in your mind?...",
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

  return (
    <div className="chat-input-wrapper">
      {/* Ambient Gradient Blur Overlay for scrolling content */}
      <div className="chat-bottom-blur-overlay" aria-hidden="true" />

      <form className="chat-input-pill" onSubmit={handleSubmit}>
        {/* Input Text Area */}
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          className="chat-textarea"
          disabled={isGenerating}
        />

        {/* Dynamic Action Button:
            - When idle: Circular royal blue send button with paper airplane
            - When generating: Circular red button with stop icon to terminate session
        */}
        {isGenerating ? (
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
