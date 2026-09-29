import React, { useState, useEffect, useRef } from "react";
import { Sun, Moon } from "lucide-react";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import ChatInput from "./components/ChatInput";
import SettingsModal from "./components/SettingsModal";
import SourcesModal from "./components/SourcesModal";
import LogoutModal from "./components/LogoutModal";
import DeleteThreadModal from "./components/DeleteThreadModal";
import AuthPage from "./components/AuthPage";
import ForbiddenPage from "./components/ForbiddenPage";
import Toast from "./components/Toast";
import {
  DEFAULT_SETTINGS,
  INITIAL_THREADS,
} from "./constants/initialData";
import { generateDynamicGreeting } from "./services/greetingGenerator";
import {
  streamChatMessage,
  streamRegenerateChatMessage,
  logoutUser,
  fetchUserThreads,
  fetchThreadHistory,
  createNewChatThread,
  deleteChatThread,
  fetchModelInfo,
  getMe,
} from "./services/api";

export default function App() {
  // Authentication state (null if not logged in)
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("rag_chat_user");
    return saved ? JSON.parse(saved) : null;
  });

  // Strict route authorization view: 'authenticated' | 'forbidden' | 'login'
  const [authView, setAuthView] = useState(() => {
    const token = localStorage.getItem("access_token");
    return token ? "authenticated" : "forbidden";
  });

  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem("rag_chat_settings");
    return saved ? JSON.parse(saved) : DEFAULT_SETTINGS;
  });

  // Dark & Light Mode Theme State
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("rag_theme");
    if (saved === "dark" || saved === "light") return saved;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("rag_theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  // Collapsible Sidebar State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    return localStorage.getItem("rag_sidebar_collapsed") === "true";
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("rag_sidebar_collapsed", String(next));
      return next;
    });
  };

  const [modelInfo, setModelInfo] = useState(() => ({
    model: settings?.model || "cohere/command-a-reasoning",
    provider: "Xkiro Cloud API",
    embedding_model: "google/embeddinggemma-300m",
  }));

  useEffect(() => {
    fetchModelInfo().then((info) => {
      if (info && info.model) {
        setModelInfo(info);
        setSettings((prev) => ({
          ...prev,
          model: info.model,
        }));
      }
    });
  }, []);

  // Sync and strictly verify user profile from backend on mount
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setUser(null);
      setAuthView("forbidden");
      return;
    }

    getMe(token)
      .then((profile) => {
        if (profile && profile.username) {
          setUser((prev) => ({
            ...prev,
            ...profile,
          }));
          setAuthView("authenticated");
        } else {
          localStorage.removeItem("access_token");
          localStorage.removeItem("rag_chat_user");
          setUser(null);
          setAuthView("forbidden");
        }
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("rag_chat_user");
        setUser(null);
        setAuthView("forbidden");
      });
  }, []);

  const [threads, setThreads] = useState(() => {
    const saved = localStorage.getItem("rag_chat_threads");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }
    return [];
  });

  const [activeThreadId, setActiveThreadId] = useState(() => {
    const saved = localStorage.getItem("rag_active_thread_id");
    return saved || null;
  });

  // Dynamic greeting state for empty chat
  const [greetingData, setGreetingData] = useState(() =>
    generateDynamicGreeting(user?.username || "there")
  );

  // Streaming and Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState(null);
  const abortControllerRef = useRef(null);

  // Active generation snapshot (for rolling back if user terminates generation)
  const preGenerationSnapshotRef = useRef(null);

  // Modals state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLogoutOpen, setIsLogoutOpen] = useState(false);
  const [inspectSourcesData, setInspectSourcesData] = useState(null);
  const [threadToDelete, setThreadToDelete] = useState(null);
  const [isDeletingThread, setIsDeletingThread] = useState(false);
  const [isClearAllOpen, setIsClearAllOpen] = useState(false);
  const [isClearingAll, setIsClearingAll] = useState(false);

  // Notification Toast state
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "info") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast((cur) => (cur?.message === message ? null : cur));
    }, 3800);
  };

  // Sync to local storage
  useEffect(() => {
    if (user) {
      localStorage.setItem("rag_chat_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("rag_chat_user");
    }
  }, [user]);

  useEffect(() => {
    localStorage.setItem("rag_chat_threads", JSON.stringify(threads));
  }, [threads]);

  useEffect(() => {
    localStorage.setItem("rag_chat_settings", JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    if (activeThreadId) {
      localStorage.setItem("rag_active_thread_id", activeThreadId);
    } else {
      localStorage.removeItem("rag_active_thread_id");
    }
  }, [activeThreadId]);

  // On mount or user change: Fetch threads directly from backend POST /chatbot/threads
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token && user) {
      fetchUserThreads(token)
        .then((backendThreads) => {
          if (backendThreads && backendThreads.length > 0) {
            setThreads((prev) => {
              const map = new Map(prev.map((t) => [t.thread_id, t]));
              return backendThreads.map((bt) => {
                const local = map.get(bt.thread_id);
                const isMeaningful = (text) => text && text.trim() && text.trim() !== "New Conversation";
                const resolvedTitle = isMeaningful(bt.preview)
                  ? bt.preview
                  : (isMeaningful(local?.title) ? local.title : (bt.preview || "New Conversation"));
                return {
                  ...bt,
                  title: resolvedTitle,
                  messages: local?.messages || [],
                };
              });
            });
          }
        })
        .catch((e) => console.warn("Initial threads fetch error:", e));
    }
  }, [user]);

  // Hydrate active thread history from backend GET /chatbot/history/{thread_id} if empty
  useEffect(() => {
    if (!activeThreadId) return;
    const target = threads.find((t) => t.thread_id === activeThreadId);
    if (!target || !target.messages || target.messages.length === 0) {
      const token = localStorage.getItem("access_token");
      if (token) {
        fetchThreadHistory(activeThreadId, token)
          .then((msgs) => {
            if (msgs && msgs.length > 0) {
              setThreads((prev) =>
                prev.map((t) =>
                  t.thread_id === activeThreadId ? { ...t, messages: msgs } : t
                )
              );
            }
          })
          .catch((e) => console.warn("Failed fetching active thread history:", e));
      }
    }
  }, [activeThreadId, threads.length]);

  // Auth Success Handler: immediately called post-signup or post-login
  const handleAuthSuccess = async (authedUser) => {
    setUser(authedUser);
    localStorage.setItem("rag_chat_user", JSON.stringify(authedUser));
    setAuthView("authenticated");

    // Refresh greeting with newly signed-up username
    setGreetingData(generateDynamicGreeting(authedUser.username || "there"));

    // Always land on the new conversation chat window upon login
    setActiveThreadId(null);
    localStorage.removeItem("rag_active_thread_id");

    // Fetch user threads from backend to populate sidebar history (without navigating away from new chat screen)
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const backendThreads = await fetchUserThreads(token);
        if (backendThreads && backendThreads.length > 0) {
          const mappedThreads = backendThreads.map((bt) => ({
            ...bt,
            title: bt.preview || "New Conversation",
            messages: [],
          }));
          setThreads(mappedThreads);
        } else {
          setThreads([]);
        }
      } catch {
        setThreads([]);
      }
    } else {
      setThreads([]);
    }

    showToast(`Welcome, ${authedUser.username}!`, "success");
  };

  // Current active thread object (null if on new chat screen)
  const activeThread = activeThreadId
    ? threads.find((t) => t.thread_id === activeThreadId) || null
    : null;

  // New Chat Handler:
  // - Does NOT create an item in the sidebar recents space until the user sends a query
  // - If already on a new empty chat screen, stays right here without creating duplicate entries
  const handleNewChat = () => {
    if (isGenerating) {
      handleAbortGeneration();
    }
    if (!activeThreadId || (activeThread && activeThread.messages.length === 0)) {
      return;
    }
    setActiveThreadId(null);
    setGreetingData(generateDynamicGreeting(user?.username || "there"));
  };

  // Select existing thread
  const handleSelectThread = async (threadId) => {
    if (isGenerating) {
      handleAbortGeneration();
    }
    setActiveThreadId(threadId);
    setGreetingData(generateDynamicGreeting(user?.username || "there"));

    // If thread history is not loaded yet, fetch from backend
    const target = threads.find((t) => t.thread_id === threadId);
    if (target && (!target.messages || target.messages.length === 0)) {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const msgs = await fetchThreadHistory(threadId, token);
          if (msgs && msgs.length > 0) {
            setThreads((prev) =>
              prev.map((t) =>
                t.thread_id === threadId ? { ...t, messages: msgs } : t
              )
            );
          }
        } catch (e) {
          console.warn("Could not fetch thread history:", e);
        }
      }
    }
  };

  // Open delete thread confirmation modal
  const handleDeleteThread = (e, threadId) => {
    e.stopPropagation();
    const thread = threads.find((t) => t.thread_id === threadId);
    setThreadToDelete(thread || { thread_id: threadId, title: "this conversation" });
  };

  // Confirm delete thread execution
  const handleConfirmDeleteThread = async () => {
    if (!threadToDelete) return;
    const threadId = threadToDelete.thread_id;
    setIsDeletingThread(true);

    try {
      await deleteChatThread(threadId);
    } catch (err) {
      console.warn("Backend chat deletion failed:", err);
    }

    const updated = threads.filter((t) => t.thread_id !== threadId);
    setThreads(updated);
    if (activeThreadId === threadId) {
      if (updated.length > 0) {
        setActiveThreadId(updated[0].thread_id);
      } else {
        setActiveThreadId(null);
      }
    }
    showToast("Conversation deleted", "info");
    setIsDeletingThread(false);
    setThreadToDelete(null);
  };

  // Rename thread
  const handleRenameThread = (threadId, newTitle) => {
    setThreads((prev) =>
      prev.map((t) => (t.thread_id === threadId ? { ...t, title: newTitle } : t))
    );
    showToast("Conversation renamed", "success");
  };

  // Open clear all confirmation modal
  const handleClearAllThreads = () => {
    if (threads.length === 0) return;
    setIsClearAllOpen(true);
  };

  // Confirm clear all threads execution
  const handleConfirmClearAllThreads = async () => {
    setIsClearingAll(true);
    if (isGenerating) handleAbortGeneration();

    // Delete all existing threads from backend in parallel
    try {
      await Promise.allSettled(
        threads.map((t) => deleteChatThread(t.thread_id))
      );
    } catch (err) {
      console.warn("Bulk backend delete error:", err);
    }

    setThreads([]);
    setActiveThreadId(null);
    setGreetingData(generateDynamicGreeting(user?.username || "there"));
    showToast("All conversations cleared", "warning");
    setIsClearingAll(false);
    setIsClearAllOpen(false);
  };

  // Send message
  const handleSendMessage = async (queryText) => {
    if (!queryText.trim() || isGenerating) return;

    const token = localStorage.getItem("access_token");
    let targetThreadId = activeThreadId;
    const isNewConversation =
      !targetThreadId || !threads.some((t) => t.thread_id === targetThreadId);

    // 1. If this is a new conversation, call backend endpoint POST /chatbot/create-thread
    if (isNewConversation) {
      try {
        const newChatData = await createNewChatThread(token);
        if (newChatData?.thread_id) {
          targetThreadId = newChatData.thread_id;
        }
      } catch (err) {
        console.warn("Backend new-chat call failed, falling back to local ID:", err);
      }
      if (!targetThreadId) {
        targetThreadId = `thread-${Date.now()}`;
      }
    }

    const userMessageId = `msg-${Date.now()}-u`;
    const userMsg = {
      id: userMessageId,
      role: "user",
      content: queryText.trim(),
      timestamp: new Date().toISOString(),
    };

    const threadTitle =
      queryText.length > 32 ? `${queryText.substring(0, 32)}...` : queryText;

    if (isNewConversation) {
      // NOW AND ONLY NOW: Add the conversation to recents space (threads)
      const newThread = {
        thread_id: targetThreadId,
        title: threadTitle,
        intent: "Diabetes",
        last_updated: new Date().toISOString(),
        messages: [userMsg],
      };
      setThreads((prev) => [
        newThread,
        ...prev.filter((t) => t.thread_id !== targetThreadId),
      ]);
      setActiveThreadId(targetThreadId);
      preGenerationSnapshotRef.current = {
        threadId: targetThreadId,
        messages: [],
      };
    } else {
      const currentMessages = activeThread?.messages || [];
      preGenerationSnapshotRef.current = {
        threadId: targetThreadId,
        messages: [...currentMessages],
      };
      setThreads((prev) =>
        prev.map((t) =>
          t.thread_id === targetThreadId
            ? {
                ...t,
                last_updated: new Date().toISOString(),
                messages: [...t.messages, userMsg],
              }
            : t
        )
      );
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsGenerating(true);

    const assistantTempId = `msg-${Date.now()}-a`;
    setStreamingMessage({
      id: assistantTempId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    });

    let accumulatedContent = "";
    let capturedMetadata = null;

    try {
      await streamChatMessage({
        query: queryText,
        threadId: targetThreadId,
        settings,
        signal: controller.signal,
        onToken: (token) => {
          accumulatedContent += token;
          setStreamingMessage((prev) => ({
            ...prev,
            content: accumulatedContent,
          }));
        },
        onMetadata: (metadata) => {
          capturedMetadata = metadata;
          if (metadata?.model) {
            setModelInfo((prev) => ({
              ...prev,
              model: metadata.model,
            }));
            setSettings((prev) => ({
              ...prev,
              model: metadata.model,
            }));
          }
        },
      });

      const finalAssistantMsg = {
        id: assistantTempId,
        role: "assistant",
        content: accumulatedContent,
        timestamp: new Date().toISOString(),
        metadata: capturedMetadata || {
          thread_id: targetThreadId,
          total_tokens: Math.round(accumulatedContent.length / 4),
          execution_time_ms: 950,
          intent: "Diabetes",
          model: settings.model,
        },
        sources: capturedMetadata?.sources || [],
      };

      setThreads((prev) =>
        prev.map((t) =>
          t.thread_id === targetThreadId
            ? {
                ...t,
                intent: finalAssistantMsg.metadata.intent,
                last_updated: new Date().toISOString(),
                messages: [...t.messages, finalAssistantMsg],
              }
            : t
        )
      );

      // Refresh threads from backend to ensure previews and timestamps are in sync
      if (token) {
        fetchUserThreads(token)
          .then((backendThreads) => {
            if (backendThreads && backendThreads.length > 0) {
              setThreads((prev) => {
                const map = new Map(prev.map((t) => [t.thread_id, t]));
                return backendThreads.map((bt) => {
                  const local = map.get(bt.thread_id);
                  const isMeaningful = (text) => text && text.trim() && text.trim() !== "New Conversation";
                  const resolvedTitle = isMeaningful(bt.preview)
                    ? bt.preview
                    : (isMeaningful(local?.title) ? local.title : (bt.preview || "New Conversation"));
                  return {
                    ...bt,
                    title: resolvedTitle,
                    messages: local?.messages || [],
                  };
                });
              });
            }
          })
          .catch((e) => console.warn("Background threads sync error:", e));
      }
    } catch (err) {
      if (err.name === "AbortError" || controller.signal.aborted) {
        if (preGenerationSnapshotRef.current) {
          const { threadId, messages: savedMessages } =
            preGenerationSnapshotRef.current;
          if (savedMessages.length === 0) {
            setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
            setActiveThreadId(null);
          } else {
            setThreads((prev) =>
              prev.map((t) =>
                t.thread_id === threadId ? { ...t, messages: savedMessages } : t
              )
            );
          }
        }
        showToast(
          "Generation stopped. Session was terminated without saving to chat history.",
          "warning"
        );
      } else if (err.message && err.message.includes("FORBIDDEN")) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("rag_chat_user");
        setUser(null);
        setAuthView("forbidden");
        showToast("Access forbidden: session expired or unauthorized.", "error");
      } else {
        console.error("Chat error:", err);
        showToast(err.message || "An error occurred during response generation.", "error");
      }
    } finally {
      setIsGenerating(false);
      setStreamingMessage(null);
      abortControllerRef.current = null;
      preGenerationSnapshotRef.current = null;
    }
  };

  const handleAbortGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleRegenerate = async (assistantIndex) => {
    if (isGenerating || !activeThread) return;
    const messages = activeThread.messages || [];

    // Find the user query that triggered this assistant answer
    let userMsg = null;
    let userIdx = -1;
    for (let i = assistantIndex - 1; i >= 0; i--) {
      if (messages[i]?.role === "user") {
        userMsg = messages[i];
        userIdx = i;
        break;
      }
    }
    if (!userMsg) return;

    // Retain history up to userIdx (inclusive) and ensure no duplicate consecutive user queries
    const rawBefore = messages.slice(0, userIdx + 1);
    const baseMessages = [];
    for (let i = 0; i < rawBefore.length; i++) {
      const cur = rawBefore[i];
      const prev = baseMessages[baseMessages.length - 1];
      if (
        cur.role === "user" &&
        prev &&
        prev.role === "user" &&
        cur.content.trim() === prev.content.trim()
      ) {
        continue;
      }
      baseMessages.push(cur);
    }

    // Set active thread messages to baseMessages (query displayed only once, old assistant response removed)
    setThreads((prev) =>
      prev.map((t) =>
        t.thread_id === activeThreadId ? { ...t, messages: baseMessages } : t
      )
    );

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsGenerating(true);

    const assistantTempId = `msg-${Date.now()}-a`;
    setStreamingMessage({
      id: assistantTempId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    });

    let accumulatedContent = "";
    let capturedMetadata = null;

    try {
      await streamRegenerateChatMessage({
        query: userMsg.content,
        threadId: activeThreadId,
        settings,
        signal: controller.signal,
        onToken: (token) => {
          accumulatedContent += token;
          setStreamingMessage((prev) => ({
            ...prev,
            content: accumulatedContent,
          }));
        },
        onMetadata: (metadata) => {
          capturedMetadata = metadata;
          if (metadata?.model) {
            setModelInfo((prev) => ({
              ...prev,
              model: metadata.model,
            }));
            setSettings((prev) => ({
              ...prev,
              model: metadata.model,
            }));
          }
        },
      });

      const finalAssistantMsg = {
        id: assistantTempId,
        role: "assistant",
        content: accumulatedContent,
        timestamp: new Date().toISOString(),
        metadata: capturedMetadata || {
          thread_id: activeThreadId,
          total_tokens: Math.round(accumulatedContent.length / 4),
          execution_time_ms: 950,
          intent: "Diabetes",
          model: settings.model,
        },
        sources: capturedMetadata?.sources || [],
      };

      setThreads((prev) =>
        prev.map((t) =>
          t.thread_id === activeThreadId
            ? {
                ...t,
                intent: finalAssistantMsg.metadata.intent,
                last_updated: new Date().toISOString(),
                messages: [...baseMessages, finalAssistantMsg],
              }
            : t
        )
      );

      const token = localStorage.getItem("access_token");
      if (token) {
        fetchUserThreads(token)
          .then((backendThreads) => {
            if (backendThreads && backendThreads.length > 0) {
              setThreads((prev) => {
                const map = new Map(prev.map((t) => [t.thread_id, t]));
                return backendThreads.map((bt) => {
                  const local = map.get(bt.thread_id);
                  const isMeaningful = (text) => text && text.trim() && text.trim() !== "New Conversation";
                  const resolvedTitle = isMeaningful(bt.preview)
                    ? bt.preview
                    : (isMeaningful(local?.title) ? local.title : (bt.preview || "New Conversation"));
                  return {
                    ...bt,
                    title: resolvedTitle,
                    messages: local?.messages || [],
                  };
                });
              });
            }
          })
          .catch((e) => console.warn("Background threads sync error:", e));
      }
    } catch (err) {
      if (err.name === "AbortError" || controller.signal.aborted) {
        showToast("Regeneration stopped.", "warning");
      } else if (err.message && err.message.includes("FORBIDDEN")) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("rag_chat_user");
        setUser(null);
        setAuthView("forbidden");
        showToast("Access forbidden: session expired or unauthorized.", "error");
      } else {
        console.error("Regeneration error:", err);
        showToast(err.message || "An error occurred during response regeneration.", "error");
      }
    } finally {
      setIsGenerating(false);
      setStreamingMessage(null);
      abortControllerRef.current = null;
    }
  };

  const handleInspectSources = (sources, metadata) => {
    setInspectSourcesData({ sources, metadata });
  };

  // Sign out handler
  const handleConfirmLogout = async () => {
    const token = localStorage.getItem("access_token");
    if (token) {
      await logoutUser(token);
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("rag_chat_user");
    localStorage.removeItem("rag_chat_threads");
    localStorage.removeItem("rag_active_thread_id");
    setUser(null);
    setThreads([]);
    setActiveThreadId(null);
    setIsLogoutOpen(false);
    setAuthView("login");
    showToast("Signed out successfully", "info");
  };

  // If user is unauthenticated, render the 403 Forbidden Access Denied barrier
  if (authView === "forbidden") {
    return (
      <div className="app-root-unauthed">
        <div className="auth-top-actions">
          <button
            id="auth-theme-toggle-btn"
            className="theme-toggle-switch"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle dark and light mode"
          >
            <div className={`theme-switch-track ${theme}`}>
              <div className="theme-switch-icons">
                <Sun size={12} className="switch-icon sun" />
                <Moon size={12} className="switch-icon moon" />
              </div>
              <div className="theme-switch-thumb">
                {theme === "dark" ? (
                  <Moon size={11} className="thumb-icon" />
                ) : (
                  <Sun size={11} className="thumb-icon" />
                )}
              </div>
            </div>
            <span className="theme-switch-label">
              {theme === "dark" ? "Dark" : "Light"}
            </span>
          </button>
        </div>
        <ForbiddenPage onGoToLogin={() => setAuthView("login")} />
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    );
  }

  // If user navigated to login or has not yet authenticated
  if (authView === "login" || !user) {
    return (
      <div className="app-root-unauthed">
        <div className="auth-top-actions">
          <button
            id="auth-theme-toggle-btn"
            className="theme-toggle-switch"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle dark and light mode"
          >
            <div className={`theme-switch-track ${theme}`}>
              <div className="theme-switch-icons">
                <Sun size={12} className="switch-icon sun" />
                <Moon size={12} className="switch-icon moon" />
              </div>
              <div className="theme-switch-thumb">
                {theme === "dark" ? (
                  <Moon size={11} className="thumb-icon" />
                ) : (
                  <Sun size={11} className="thumb-icon" />
                )}
              </div>
            </div>
            <span className="theme-switch-label">
              {theme === "dark" ? "Dark" : "Light"}
            </span>
          </button>
        </div>
        <AuthPage onAuthSuccess={handleAuthSuccess} />
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    );
  }

  return (
    <div className="app-layout-root">
      {/* Left Sidebar */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        onDeleteThread={handleDeleteThread}
        onRenameThread={handleRenameThread}
        onClearAllThreads={handleClearAllThreads}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenLogout={() => setIsLogoutOpen(true)}
        user={user}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />

      {/* Main Chat Viewport */}
      <main className="main-chat-viewport">
        {/* Top Right Theme Toggle Switch */}
        <div className="chat-top-actions">
          <button
            id="chat-theme-toggle-btn"
            className="theme-toggle-switch"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle dark and light mode"
          >
            <div className={`theme-switch-track ${theme}`}>
              <div className="theme-switch-icons">
                <Sun size={12} className="switch-icon sun" />
                <Moon size={12} className="switch-icon moon" />
              </div>
              <div className="theme-switch-thumb">
                {theme === "dark" ? (
                  <Moon size={11} className="thumb-icon" />
                ) : (
                  <Sun size={11} className="thumb-icon" />
                )}
              </div>
            </div>
            <span className="theme-switch-label">
              {theme === "dark" ? "Dark" : "Light"}
            </span>
          </button>
        </div>

        {/* Chat Messages / Greeting Screen */}
        <ChatArea
          thread={activeThread}
          user={user}
          greetingData={greetingData}
          onSendMessage={handleSendMessage}
          onRegenerate={handleRegenerate}
          onInspectSources={handleInspectSources}
          isGenerating={isGenerating}
          streamingMessage={streamingMessage}
          modelInfo={modelInfo}
        />

        {/* Floating Pill Input Bar at Bottom */}
        <ChatInput
          onSendMessage={handleSendMessage}
          isGenerating={isGenerating}
          onAbortGeneration={handleAbortGeneration}
          placeholder="What's in your mind?..."
        />
      </main>

      {/* Settings Modal (Temperature, Top_k, Top_p, etc.) */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        modelInfo={modelInfo}
        onSaveSettings={(newSettings) => {
          setSettings(newSettings);
          showToast("Model parameters updated successfully", "success");
        }}
      />

      {/* Detailed Sources & Context Modal */}
      <SourcesModal
        isOpen={!!inspectSourcesData}
        onClose={() => setInspectSourcesData(null)}
        sources={inspectSourcesData?.sources || []}
        metadata={inspectSourcesData?.metadata}
        modelInfo={modelInfo}
      />

      {/* Logout Confirmation Modal */}
      <LogoutModal
        isOpen={isLogoutOpen}
        onClose={() => setIsLogoutOpen(false)}
        onConfirm={handleConfirmLogout}
        user={user}
      />

      {/* Delete Thread Confirmation Modal */}
      <DeleteThreadModal
        isOpen={!!threadToDelete}
        onClose={() => setThreadToDelete(null)}
        onConfirm={handleConfirmDeleteThread}
        threadTitle={threadToDelete?.title || "this conversation"}
        isDeleting={isDeletingThread}
      />

      {/* Clear All Threads Confirmation Modal */}
      <DeleteThreadModal
        isOpen={isClearAllOpen}
        onClose={() => setIsClearAllOpen(false)}
        onConfirm={handleConfirmClearAllThreads}
        isClearAll={true}
        threadCount={threads.length}
        isDeleting={isClearingAll}
      />

      {/* Toast Alerts */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
