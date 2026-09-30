import React, { useState } from "react";
import {
  Plus,
  Search,
  MessageSquare,
  Trash2,
  Edit2,
  Check,
  X,
  Settings as SettingsIcon,
  LogOut,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

export default function Sidebar({
  threads = [],
  activeThreadId,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onRenameThread,
  onClearAllThreads,
  onOpenSettings,
  onOpenLogout,
  user,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [editingThreadId, setEditingThreadId] = useState(null);
  const [editTitleValue, setEditTitleValue] = useState("");
  const getThreadTitle = (t) => t?.title || t?.preview || "New Conversation";

  const formatLoginTime = (timeStr) => {
    if (!timeStr) return "Online";
    try {
      const d = new Date(timeStr);
      if (isNaN(d.getTime())) return "Online";
      return `Logged in: ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    } catch (e) {
      return "Online";
    }
  };

  const filteredThreads = (threads || []).filter((t) =>
    getThreadTitle(t).toLowerCase().includes((searchQuery || "").toLowerCase())
  );

  const startEditing = (e, thread) => {
    e.stopPropagation();
    setEditingThreadId(thread.thread_id);
    setEditTitleValue(getThreadTitle(thread));
  };

  const saveEditing = (e, threadId) => {
    e.stopPropagation();
    if (editTitleValue.trim()) {
      onRenameThread(threadId, editTitleValue.trim());
    }
    setEditingThreadId(null);
  };

  const cancelEditing = (e) => {
    e.stopPropagation();
    setEditingThreadId(null);
  };

  // Render Compact Rail when Collapsed
  if (isCollapsed) {
    return (
      <aside className="sidebar-container sidebar-collapsed animate-fade-in">
        {/* Top: Expand Button */}
        <div className="sidebar-collapsed-header">
          <button
            className="btn-collapse-sidebar collapsed"
            onClick={onToggleCollapse}
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen size={20} strokeWidth={2.2} />
          </button>
        </div>

        {/* Action Buttons: New Chat & Search */}
        <div className="sidebar-collapsed-actions">
          <button
            className="btn-collapsed-round btn-new-chat-collapsed"
            onClick={onNewChat}
            title="New chat"
            aria-label="New chat"
          >
            <Plus size={18} strokeWidth={2.5} />
          </button>
          <button
            className="btn-collapsed-round"
            onClick={() => {
              if (onToggleCollapse) onToggleCollapse();
              setIsSearchOpen(true);
            }}
            title="Search conversations"
            aria-label="Search conversations"
          >
            <Search size={16} strokeWidth={2.2} />
          </button>
        </div>

        {/* Recent Thread History Icons */}
        <div className="sidebar-threads-scroll collapsed">
          {filteredThreads.slice(0, 10).map((thread) => {
            const isActive = thread.thread_id === activeThreadId;
            const title = getThreadTitle(thread);
            return (
              <button
                key={thread.thread_id}
                className={`thread-item-collapsed ${isActive ? "active" : ""}`}
                onClick={() => onSelectThread(thread.thread_id)}
                title={title}
                aria-label={title}
              >
                <MessageSquare size={17} strokeWidth={isActive ? 2.3 : 1.8} />
                {isActive && <span className="thread-active-dot-collapsed" />}
              </button>
            );
          })}
        </div>

        {/* Bottom Actions: Settings, User Avatar, Logout */}
        <div className="sidebar-collapsed-bottom">
          <button
            className="btn-collapsed-round"
            onClick={onOpenSettings}
            title="Model Settings"
            aria-label="Settings"
          >
            <SettingsIcon size={18} strokeWidth={2} />
          </button>

          <div
            className="user-avatar-circle collapsed"
            title={`${user?.username || user?.name || "User"} (${formatLoginTime(user?.login_at)})`}
          >
            <span className="user-avatar-letter">
              {(user?.username || user?.name || user?.email || "U")[0].toUpperCase()}
            </span>
          </div>

          <button
            className="btn-collapsed-round btn-logout-collapsed"
            onClick={onOpenLogout}
            title="Log out"
            aria-label="Logout"
          >
            <LogOut size={16} strokeWidth={2} />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="sidebar-container">
      {/* Brand Title with Collapse Button */}
      <div className="sidebar-brand-wrapper">
        <h1 className="sidebar-brand">Medical Literature Diabetic Assistant</h1>
        {onToggleCollapse && (
          <button
            className="btn-collapse-sidebar"
            onClick={onToggleCollapse}
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={18} strokeWidth={2.2} />
          </button>
        )}
      </div>

      {/* Top Action Row: New Chat + Search */}
      <div className="sidebar-top-actions">
        <button
          className="btn-new-chat"
          onClick={onNewChat}
          title="Start a new conversation"
        >
          <Plus size={18} strokeWidth={2.5} />
          <span>New chat</span>
        </button>

        <button
          className={`btn-search-round ${isSearchOpen ? "active" : ""}`}
          onClick={() => {
            setIsSearchOpen(!isSearchOpen);
            if (isSearchOpen) setSearchQuery("");
          }}
          title={isSearchOpen ? "Close search" : "Search conversations"}
          aria-label="Search conversations"
        >
          <Search size={16} strokeWidth={2.2} />
        </button>
      </div>

      {/* Expandable Search Input */}
      {isSearchOpen && (
        <div className="sidebar-search-bar animate-fade-in">
          <Search size={14} className="search-input-icon" />
          <input
            type="text"
            placeholder="Filter conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
            className="search-input"
          />
          {searchQuery && (
            <button
              className="search-clear-btn"
              onClick={() => setSearchQuery("")}
            >
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {/* Conversations Section Header */}
      <div className="sidebar-section-header">
        <span className="section-title">Your conversations</span>
        {threads.length > 0 && (
          <button
            className="btn-clear-all"
            onClick={onClearAllThreads}
            title="Clear all conversation history"
          >
            Clear All
          </button>
        )}
      </div>

      {/* Full Conversation History List (No 7-days or 10-days grouping) */}
      <div className="sidebar-threads-scroll">
        {filteredThreads.length === 0 ? (
          <div className="threads-empty-state">
            <MessageSquare size={24} className="text-gray-300" />
            <p className="text-muted text-xs">
              {searchQuery ? "No matching conversations" : "No conversations yet"}
            </p>
          </div>
        ) : (
          filteredThreads.map((thread) => {
            const isActive = thread.thread_id === activeThreadId;
            const isEditing = editingThreadId === thread.thread_id;

            return (
              <div
                key={thread.thread_id}
                className={`thread-item ${isActive ? "active" : ""}`}
                onClick={() => !isEditing && onSelectThread(thread.thread_id)}
                title={getThreadTitle(thread)}
              >
                <div className="thread-item-icon">
                  <MessageSquare size={16} strokeWidth={1.8} />
                </div>

                {isEditing ? (
                  <div className="thread-edit-wrapper" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editTitleValue}
                      onChange={(e) => setEditTitleValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveEditing(e, thread.thread_id);
                        if (e.key === "Escape") cancelEditing(e);
                      }}
                      autoFocus
                      className="thread-edit-input"
                    />
                    <button
                      className="btn-edit-action"
                      onClick={(e) => saveEditing(e, thread.thread_id)}
                      title="Save"
                    >
                      <Check size={14} className="text-emerald-600" />
                    </button>
                    <button
                      className="btn-edit-action"
                      onClick={cancelEditing}
                      title="Cancel"
                    >
                      <X size={14} className="text-rose-600" />
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="thread-title-text">{getThreadTitle(thread)}</span>

                    {/* Actions displayed on active or hover */}
                    {isActive ? (
                      <div className="thread-actions-group">
                        <button
                          className="thread-action-btn"
                          onClick={(e) => onDeleteThread(e, thread.thread_id)}
                          title="Delete chat"
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          className="thread-action-btn"
                          onClick={(e) => startEditing(e, thread)}
                          title="Rename chat"
                        >
                          <Edit2 size={13} />
                        </button>
                        <span className="thread-active-dot" />
                      </div>
                    ) : (
                      <div className="thread-hover-actions">
                        <button
                          className="thread-action-btn"
                          onClick={(e) => onDeleteThread(e, thread.thread_id)}
                          title="Delete chat"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom Sidebar: Settings and User Profile / Logout */}
      <div className="sidebar-bottom-section">
        {/* Settings Pill Button */}
        <button
          className="btn-sidebar-card btn-settings"
          onClick={onOpenSettings}
          title="Model settings and parameters"
        >
          <div className="sidebar-card-icon">
            <SettingsIcon size={18} strokeWidth={2} />
          </div>
          <span className="sidebar-card-label">Settings</span>
        </button>

        {/* User Profile & Logout Section (below settings) */}
        <div className="sidebar-user-card" title={`Logged in as ${user?.username || user?.email || "User"}`}>
          <div className="user-profile-left">
            <div className="user-avatar-circle">
              <span className="user-avatar-letter">
                {(user?.username || user?.name || user?.email || "U")[0].toUpperCase()}
              </span>
            </div>
            <div className="user-text-info">
              <span className="user-display-name">{user?.username || user?.name || "User"}</span>
              <span className="user-status-text" title={user?.login_at ? `Login: ${new Date(user.login_at).toLocaleString()}` : "Active"}>
                {formatLoginTime(user?.login_at)}
              </span>
            </div>
          </div>

          {/* Explicit Logout Button right in that place */}
          <button
            className="btn-logout-icon"
            onClick={onOpenLogout}
            title="Log out of account"
            aria-label="Logout"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
