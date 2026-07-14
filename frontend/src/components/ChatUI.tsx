"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

type Chat = {
  id: string;
  title: string;
  updated_at: string;
};

type Message = {
  id: string;
  role: "user" | "ai" | "system";
  content: string;
  sql?: string;
  actionId?: string;
  isDestructive?: boolean;
  actionStatus?: "pending" | "approved" | "rejected" | "executed" | "failed";
  pendingAction?: {
    actionId: string;
    summary: string;
    isDestructive: boolean;
  };
  data_json?: {
    columns: string[];
    rows: any[][];
    truncated: boolean;
  };
  isStreaming?: boolean;
};

type Theme = "light" | "dark" | "system";

const getSystemMessageType = (content: string) => {
  if (content.startsWith("✅")) return "success";
  if (content.startsWith("🚫")) return "neutral";
  return "error";
};

const TypewriterText = ({ 
  content, 
  shouldStream, 
  onComplete,
  scrollRef 
}: { 
  content: string; 
  shouldStream: boolean; 
  onComplete?: () => void;
  scrollRef: React.RefObject<HTMLDivElement | null>;
}) => {
  const [displayed, setDisplayed] = useState(shouldStream ? "" : content);
  
  useEffect(() => {
    if (!shouldStream) {
      setDisplayed(content);
      return;
    }
    
    let i = 0;
    const timer = setInterval(() => {
      i += 2; 
      setDisplayed(content.substring(0, i));
      scrollRef.current?.scrollIntoView({ behavior: "auto" });
      
      if (i >= content.length) {
        clearInterval(timer);
        setDisplayed(content);
        if (onComplete) onComplete();
      }
    }, 15);
    
    return () => clearInterval(timer);
  }, [content, shouldStream]);
  
  return <>{displayed}</>;
};

import { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import ConfirmModal from "./ConfirmModal";

// ... previous type definitions ...

export default function ChatUI({ session, activeConnId, onSwitchDatabase }: { session: Session; activeConnId: string | null; onSwitchDatabase?: () => void }) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  
  const [confirmTexts, setConfirmTexts] = useState<Record<string, string>>({});
  
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  
  const [theme, setTheme] = useState<Theme>("system");
  
  const [executingActionId, setExecutingActionId] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<string | null>(null);

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as Theme;
    if (savedTheme) {
      setTheme(savedTheme);
    }
    fetchChats();
  }, []);

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("dark");
    if (theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      root.classList.add("dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const fetchChats = async () => {
    try {
      const res = await fetch(`${API_URL}/chats`, { 
        headers: { 
          "Authorization": `Bearer ${session.access_token}`,
          "X-Connection-Id": activeConnId || ""
        }
      });
      if (res.ok) {
        const data = await res.json();
        setChats(data);
      }
    } catch (e) {
      console.error("Failed to load chats", e);
    }
  };

  const loadChat = async (chatId: string) => {
    if (activeChatId === chatId) return;
    setActiveChatId(chatId);
    setMessages([]);
    setIsLoadingChat(true);
    try {
      const res = await fetch(`${API_URL}/chats/${chatId}/messages`, { 
        headers: { 
          "Authorization": `Bearer ${session.access_token}`,
          "X-Connection-Id": activeConnId || ""
        }
      });
      if (res.ok) {
        const data = await res.json();
        const mapped: Message[] = data.map((d: any) => {
           const isAction = !!d.action_id;
           return {
             id: d.id,
             role: d.role,
             content: d.content,
             sql: d.sql,
             pendingAction: isAction ? {
                actionId: d.action_id,
                summary: d.summary,
                isDestructive: d.is_destructive
             } : undefined,
             actionStatus: isAction ? "rejected" : undefined,
             data_json: d.data_json,
             isStreaming: false
           };
        });
        setMessages(mapped);
      }
    } catch (e) {
      console.error("Failed to load messages", e);
    } finally {
      setIsLoadingChat(false);
    }
  };

  const handleSend = async (overrideText?: string) => {
    const textToSend = overrideText && typeof overrideText === 'string' ? overrideText : inputValue;
    if (!textToSend.trim() || isTyping) return;

    const pendingMsgs = messages.filter(m => m.actionStatus === "pending");
    const discardPromises = [];
    
    if (pendingMsgs.length > 0) {
      setMessages(prev => [...prev, {
        id: Date.now().toString() + "_cancel",
        role: "system",
        content: `🚫 Previous pending action was explicitly discarded.`,
        isStreaming: false
      }]);
      
      for (const msg of pendingMsgs) {
        if (msg.pendingAction) {
           discardPromises.push(
             fetch(`${API_URL}/chat/approve-action`, {
               method: "POST",
               headers: { 
                 "Content-Type": "application/json",
                 "Authorization": `Bearer ${session.access_token}`,
                 "X-Connection-Id": activeConnId || ""
               },
               body: JSON.stringify({ action_id: msg.pendingAction.actionId, decision: "reject" })
             }).catch(console.error)
           );
        }
      }
      Promise.all(discardPromises);
    }

    setMessages((prev) => 
      prev.map(msg => 
        msg.actionStatus === "pending" ? { ...msg, actionStatus: "rejected" } : msg
      )
    );

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: textToSend.trim(),
      isStreaming: false
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);
    
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    const frontendMsgId = Date.now().toString() + "_req";
    
    // 45 second timeout
    const timeoutId = setTimeout(() => {
       if (abortControllerRef.current) {
           abortControllerRef.current.abort("timeout");
       }
    }, 45000);

    try {
      const payload: any = { message: userMessage.content, frontend_msg_id: frontendMsgId };
      if (activeChatId) {
        payload.chat_id = activeChatId;
      }

      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`,
          "X-Connection-Id": activeConnId || ""
        },
        body: JSON.stringify(payload),
        signal: abortController.signal
      });

      const data = await res.json();

      if (res.ok) {
        if (!activeChatId && data.chat_id) {
           setActiveChatId(data.chat_id);
           fetchChats();
        }
        
        const aiMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "ai",
          content: data.reply,
          sql: data.sql,
          pendingAction: data.action_id ? {
            actionId: data.action_id,
            summary: data.summary,
            isDestructive: data.is_destructive
          } : undefined,
          actionStatus: data.action_id ? "pending" : undefined,
          data_json: data.data_json,
          isStreaming: true
        };
        setMessages((prev) => [...prev, aiMessage]);
      } else {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "system",
          content: `Error: ${data.detail || "Something went wrong"}`,
          isStreaming: false
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } catch (err: any) {
      if (abortController.signal.aborted) {
        const isTimeout = abortController.signal.reason === "timeout";
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "system",
          content: isTimeout ? "This is taking longer than expected. Please try again." : "Request cancelled.",
          isStreaming: false
        };
        setMessages((prev) => [...prev, errorMessage]);
        
        // Notify backend to drop the response if it completes later
        fetch(`${API_URL}/chat/cancel`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`,
            "X-Connection-Id": activeConnId || ""
          },
          body: JSON.stringify({ message_id: frontendMsgId })
        }).catch(console.error);
        
      } else {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "system",
          content: "Network error. Make sure the backend is running.",
          isStreaming: false
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } finally {
      clearTimeout(timeoutId);
      setIsTyping(false);
      abortControllerRef.current = null;
    }
  };

  const handleStreamingComplete = (msgId: string) => {
    setMessages(prev => prev.map(m => m.id === msgId ? { ...m, isStreaming: false } : m));
  };

  const handleAction = async (msgId: string, actionId: string, decision: "approve" | "reject", isDestructive: boolean) => {
    setExecutingActionId(actionId);
    
    const confirmText = confirmTexts[actionId] || "";

    try {
      const res = await fetch(`${API_URL}/chat/approve-action`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`,
          "X-Connection-Id": activeConnId || ""
        },
        body: JSON.stringify({ action_id: actionId, decision, confirm_text: confirmText })
      });
      const data = await res.json();
      const statusMap: Record<"approve" | "reject", "approved" | "rejected"> = { approve: "approved", reject: "rejected" };
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, actionStatus: statusMap[decision] } : m));
      
      if (res.ok) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: "system",
          content: decision === "approve" ? `✅ Action executed successfully.` : `🚫 Action cancelled successfully.`,
          isStreaming: false
        }]);
      } else {
        setMessages(prev => prev.map(m => m.id === msgId ? { ...m, actionStatus: "pending" } : m));
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          role: "system",
          content: `Error: ${data.detail || "Action failed."}`,
          isStreaming: false
        }]);
      }
    } catch (err) {
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, actionStatus: "pending" } : m));
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "system",
        content: "Network error during action approval.",
        isStreaming: false
      }]);
    } finally {
      setExecutingActionId(null);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startNewChat = () => {
    setActiveChatId(null);
    setMessages([]);
    setConfirmTexts({});
    setIsLoadingChat(false);
  };

  const requestDelete = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    setChatToDelete(chatId);
    setModalOpen(true);
  };

  const confirmDelete = async () => {
    if (!chatToDelete) return;
    
    setModalOpen(false);
    try {
      const res = await fetch(`${API_URL}/chats/${chatToDelete}`, {
        method: "DELETE",
        headers: { 
          "Authorization": `Bearer ${session.access_token}`,
          "X-Connection-Id": activeConnId || ""
        }
      });
      if (res.ok) {
        setChats(chats.filter(c => c.id !== chatToDelete));
        if (activeChatId === chatToDelete) {
          startNewChat();
        }
      }
    } catch (e) {
      console.error("Failed to delete chat", e);
    }
  };

  const startRename = (e: React.MouseEvent, chat: Chat) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitle(chat.title);
  };

  const saveRename = async (e?: React.FormEvent | React.FocusEvent, cancel: boolean = false) => {
    if (e) e.preventDefault();
    if (cancel) {
      setEditingChatId(null);
      return;
    }
    if (editingChatId && editTitle.trim()) {
      try {
        await fetch(`${API_URL}/chats/${editingChatId}`, {
          method: "PATCH",
          headers: { 
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`,
            "X-Connection-Id": activeConnId || ""
          },
          body: JSON.stringify({ title: editTitle.trim() })
        });
        fetchChats();
      } catch (err) {
         console.error(err);
      }
    }
    setEditingChatId(null);
  };

  const nextTheme = () => {
    if (theme === 'light') setTheme('dark');
    else if (theme === 'dark') setTheme('system');
    else setTheme('light');
  };

  const handleSwitchDatabase = () => {
    if (onSwitchDatabase) onSwitchDatabase();
  };

  return (
    <div className="flex h-screen w-full bg-gray-50 dark:bg-gray-900 overflow-hidden transition-colors duration-200">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 dark:bg-black text-white flex flex-col hidden md:flex border-r border-gray-800 transition-colors duration-200">
        <div className="p-5 flex items-center gap-3 border-b border-gray-800">
          <img src="/logo.svg" alt="Quera Logo" className="w-8 h-8 drop-shadow-sm" />
          <h1 className="text-xl font-bold tracking-tight">Quera</h1>
        </div>
        <div className="p-4 flex flex-col gap-3 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 overflow-hidden">
              <img src={session.user.user_metadata?.avatar_url || "https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y"} className="w-8 h-8 rounded-full" alt="avatar" />
              <div className="text-sm truncate">
                <p className="font-semibold truncate">{session.user.user_metadata?.full_name || "User"}</p>
                <p className="text-xs text-gray-400 truncate">{session.user.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={handleSwitchDatabase} className="text-gray-400 hover:text-white p-1" title="Switch Database">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
              </button>
              <button onClick={() => supabase.auth.signOut()} className="text-gray-400 hover:text-white p-1" title="Sign Out">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <button
              onClick={startNewChat}
              className="flex-1 flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded-xl transition-colors border border-gray-700 cursor-pointer"
            >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            New Chat
          </button>
          
          <button 
            onClick={nextTheme}
            className="ml-2 p-2 bg-gray-800 hover:bg-gray-700 rounded-xl border border-gray-700 transition-colors flex-shrink-0 text-gray-300 hover:text-white cursor-pointer"
            title={`Theme: ${theme}`}
          >
            {theme === 'light' && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            )}
            {theme === 'dark' && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
            {theme === 'system' && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            )}
          </button>
        </div>
        </div>
        
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-2 mt-2">
            Recent Chats
          </p>
          <ul className="space-y-1">
            {chats.map((chat) => (
              <li key={chat.id} className="group flex items-center justify-between px-2 py-2 rounded-lg hover:bg-gray-800 transition-colors cursor-pointer" onClick={() => loadChat(chat.id)}>
                {editingChatId === chat.id ? (
                  <form onSubmit={(e) => saveRename(e, false)} className="flex-1">
                    <input
                      type="text"
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onBlur={(e) => saveRename(e, false)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          saveRename(e, true);
                        }
                      }}
                      className="w-full bg-gray-700 text-white text-sm px-2 py-1 rounded outline-none border border-blue-500 focus:ring-1 focus:ring-blue-500"
                    />
                  </form>
                ) : (
                  <div className={`text-sm truncate flex-1 ${activeChatId === chat.id ? "text-white font-medium" : "text-gray-300 group-hover:text-white"}`}>
                    {chat.title}
                  </div>
                )}
                
                {editingChatId !== chat.id && (
                  <div className="hidden group-hover:flex items-center gap-1 ml-2">
                    <button onClick={(e) => startRename(e, chat)} className="text-gray-400 hover:text-white p-1" title="Rename">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                    <button 
                          onClick={(e) => requestDelete(e, chat.id)}
                          className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                          title="Delete Chat"
                        ><svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col bg-white dark:bg-gray-900 h-full overflow-hidden transition-colors duration-200">
        <div className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col">
          {isLoadingChat ? (
            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 dark:text-gray-400 max-w-2xl mx-auto w-full px-4">
              <img src="/logo.svg" alt="Quera Logo" className="w-16 h-16 mb-6 drop-shadow-md" />
              <h2 className="text-2xl font-medium text-gray-800 dark:text-gray-200 mb-8 text-center">
                What would you like to know, {session.user.user_metadata?.full_name?.split(' ')[0] || 'there'}?
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
                <button 
                  onClick={() => handleSend("Show me all tables in the database")}
                  className="p-4 border border-gray-300 dark:border-gray-700 rounded-2xl text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Show me my tables</p>
                  <p className="text-xs text-gray-400 mt-1">List all available tables</p>
                </button>
                <button 
                  onClick={() => handleSend("Count the number of rows in the largest table")}
                  className="p-4 border border-gray-300 dark:border-gray-700 rounded-2xl text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Count rows in a table</p>
                  <p className="text-xs text-gray-400 mt-1">Get the total record count</p>
                </button>
                <button 
                  onClick={() => handleSend("Create a new table for storing user feedback with an id, user_id, rating, and comment")}
                  className="p-4 border border-gray-300 dark:border-gray-700 rounded-2xl text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Create a new table</p>
                  <p className="text-xs text-gray-400 mt-1">Define a schema for new data</p>
                </button>
                <button 
                  onClick={() => handleSend("Show me the most recently added records in the database")}
                  className="p-4 border border-gray-300 dark:border-gray-700 rounded-2xl text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">View recent records</p>
                  <p className="text-xs text-gray-400 mt-1">See the latest data entries</p>
                </button>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto w-full space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-4 ${
                    msg.role === "user" ? "flex-row-reverse" : "flex-row"
                  }`}
                >
                  {/* Avatar */}
                  <div className="flex-shrink-0 mt-1">
                    {msg.role === "user" ? (
                      <img src={session.user.user_metadata?.avatar_url || "https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y"} className="w-8 h-8 rounded-full shadow-sm" alt="User Avatar" />
                    ) : msg.role === "ai" ? (
                      <img src="/logo.svg" className="w-8 h-8 rounded-full shadow-sm" alt="Quera AI" />
                    ) : (
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shadow-sm ${
                        getSystemMessageType(msg.content) === 'success' ? 'bg-success/20 text-success' :
                        getSystemMessageType(msg.content) === 'neutral' ? 'bg-gray-200 dark:bg-gray-800 text-gray-500' :
                        'bg-danger/20 text-danger'
                      }`}>
                        {getSystemMessageType(msg.content) === 'success' ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : getSystemMessageType(msg.content) === 'neutral' ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 max-w-[80%] min-w-0">
                    <div
                      className={`rounded-2xl px-5 py-3 shadow-sm break-words ${
                        msg.role === "user"
                          ? "bg-brand-primary text-white rounded-tr-sm"
                          : msg.role === "system"
                          ? (getSystemMessageType(msg.content) === 'success' 
                              ? "bg-success/10 text-success border border-success/30 rounded-tl-sm font-medium"
                              : getSystemMessageType(msg.content) === 'neutral'
                              ? "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-700 rounded-tl-sm font-medium"
                              : "bg-danger/10 text-danger border border-danger/30 rounded-tl-sm font-medium")
                          : "bg-surface text-foreground rounded-tl-sm border border-gray-300 dark:border-gray-700"
                      }`}
                    >
                      <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
                        <TypewriterText 
                          content={msg.content} 
                          shouldStream={!!msg.isStreaming} 
                          onComplete={() => handleStreamingComplete(msg.id)}
                          scrollRef={messagesEndRef}
                        />
                      </p>
                    </div>
                    
                    {msg.data_json && !msg.isStreaming && (
                      <div className="mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="overflow-x-auto max-w-full">
                          <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                            <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700/50 dark:text-gray-300">
                              <tr>
                                {msg.data_json.columns.map((col, idx) => (
                                  <th key={idx} className="px-4 py-3 font-medium whitespace-nowrap">{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {msg.data_json.rows.map((row, rIdx) => (
                                <tr key={rIdx} className="border-b last:border-0 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                  {row.map((val, cIdx) => (
                                    <td key={cIdx} className="px-4 py-2 whitespace-nowrap text-gray-900 dark:text-gray-200">
                                      {val !== null ? String(val) : <span className="text-gray-400 italic">null</span>}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {msg.data_json.truncated && (
                          <div className="bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-center text-gray-500 dark:text-gray-400 font-medium">
                            Showing 50 of many rows
                          </div>
                        )}
                      </div>
                    )}
                    
                    {msg.sql && !msg.pendingAction && (
                      <details className="text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg overflow-hidden mt-1">
                        <summary className="cursor-pointer px-4 py-2 font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors list-none flex items-center gap-2 select-none">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-blue-500" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                          Show SQL Query
                        </summary>
                        <div className="border-t border-gray-200 dark:border-gray-700 overflow-x-auto rounded-b-lg">
                          {msg.isStreaming ? (
                             <div className="p-4 bg-[#282c34] text-gray-100"><pre className="font-mono text-xs whitespace-pre">{msg.sql}</pre></div>
                          ) : (
                             <SyntaxHighlighter language="sql" style={oneDark} customStyle={{ margin: 0, borderRadius: '0 0 0.5rem 0.5rem', fontSize: '0.75rem' }}>
                               {msg.sql}
                             </SyntaxHighlighter>
                          )}
                        </div>
                      </details>
                    )}

                    {msg.pendingAction && !msg.isStreaming && (
                      <div className={`mt-2 border rounded-xl overflow-hidden bg-surface shadow-sm flex flex-col ${
                        msg.pendingAction.isDestructive 
                          ? 'border-warning/30 border-l-4 border-l-warning' 
                          : 'border-brand-primary/30 border-l-4 border-l-brand-primary'
                      }`}>
                        <div className={`px-4 py-3 border-b flex items-start gap-3 ${
                          msg.pendingAction.isDestructive 
                            ? 'bg-warning/10 border-warning/20' 
                            : 'bg-brand-primary/10 border-brand-primary/20'
                        }`}>
                          <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-5 mt-0.5 flex-shrink-0 ${
                            msg.pendingAction.isDestructive ? 'text-warning' : 'text-brand-primary'
                          }`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <div>
                            <h4 className={`font-semibold text-sm ${
                              msg.pendingAction.isDestructive ? 'text-warning' : 'text-brand-primary'
                            }`}>Action Required</h4>
                            <p className="text-sm text-foreground/80 mt-1">{msg.pendingAction.summary}</p>
                          </div>
                        </div>
                        
                        <div className="overflow-x-auto">
                          <SyntaxHighlighter language="sql" style={oneDark} customStyle={{ margin: 0, borderRadius: '0', fontSize: '0.75rem' }}>
                            {msg.sql || ""}
                          </SyntaxHighlighter>
                        </div>

                        <div className="p-4 bg-surface border-t border-gray-200 dark:border-gray-700 flex flex-col gap-3">
                          {msg.pendingAction.isDestructive && msg.actionStatus === "pending" && (
                            <div className="bg-warning/10 border border-warning/30 rounded-lg p-3">
                              <label className="block text-xs font-bold text-warning uppercase tracking-wide mb-2">
                                Destructive Action: Type CONFIRM to proceed
                              </label>
                              <input 
                                type="text"
                                value={confirmTexts[msg.pendingAction.actionId] || ""}
                                onChange={(e) => setConfirmTexts(prev => ({...prev, [msg.pendingAction!.actionId]: e.target.value}))}
                                placeholder="CONFIRM"
                                disabled={executingActionId === msg.pendingAction.actionId}
                                className="w-full px-3 py-2 border border-warning/50 rounded-xl bg-surface focus:ring-2 focus:ring-warning focus:border-warning outline-none text-foreground text-sm font-mono disabled:opacity-50"
                              />
                            </div>
                          )}
                          
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleAction(msg.id, msg.pendingAction!.actionId, "approve", msg.pendingAction!.isDestructive)}
                              disabled={msg.actionStatus !== "pending" || executingActionId === msg.pendingAction!.actionId || (msg.pendingAction.isDestructive && confirmTexts[msg.pendingAction.actionId] !== "CONFIRM")}
                              className="flex-1 flex justify-center items-center bg-brand-primary hover:bg-brand-primary/90 disabled:bg-gray-300 dark:disabled:bg-gray-700 dark:disabled:text-gray-500 text-white font-semibold py-2 px-4 rounded-xl transition-colors text-sm h-10 cursor-pointer disabled:cursor-not-allowed"
                            >
                              {executingActionId === msg.pendingAction!.actionId ? (
                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                              ) : msg.actionStatus === "approved" ? "Approved" : "Approve & Execute"}
                            </button>
                            <button
                              onClick={() => handleAction(msg.id, msg.pendingAction!.actionId, "reject", false)}
                              disabled={msg.actionStatus !== "pending" || executingActionId === msg.pendingAction!.actionId}
                              className="flex-1 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 disabled:bg-gray-100 dark:disabled:bg-gray-900 disabled:text-gray-400 dark:disabled:text-gray-600 text-foreground border border-gray-300 dark:border-gray-700 font-semibold py-2 px-4 rounded-xl transition-colors text-sm h-10 cursor-pointer disabled:cursor-not-allowed"
                            >
                              {msg.actionStatus === "rejected" ? "Cancelled" : "Reject"}
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {isTyping && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-3">
                    <div className="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-none px-5 py-4 flex items-center gap-1.5 border border-gray-200 dark:border-gray-700 shadow-sm">
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce"></div>
                    </div>
                    <button 
                      onClick={() => abortControllerRef.current?.abort("user_cancelled")}
                      className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-full transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} className="h-4 flex-shrink-0" />
            </div>
          )}
        </div>

        <div className="flex-shrink-0 bg-white dark:bg-gray-900 border-t border-gray-100 dark:border-gray-800 pt-4 pb-6 px-4 transition-colors duration-200">
          <div className="max-w-3xl mx-auto relative">
            <div className="relative flex items-end bg-white dark:bg-gray-800 border border-gray-400 dark:border-gray-700 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 overflow-hidden transition-all">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message Quera..."
                className="w-full max-h-32 min-h-[56px] resize-none py-4 pl-4 pr-12 bg-transparent outline-none text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400"
                rows={1}
                disabled={isTyping}
              />
              <button
                onClick={() => handleSend()}
                disabled={!inputValue.trim() || isTyping}
                className="absolute right-2 bottom-2 p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 dark:disabled:text-gray-500 transition-colors cursor-pointer disabled:cursor-not-allowed"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
            <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-2">
              Press Enter to send, Shift + Enter for a new line.
            </p>
          </div>
        </div>
      </main>

      <ConfirmModal
        isOpen={modalOpen}
        title="Delete Chat"
        message="Are you sure you want to delete this chat? This action cannot be undone."
        onConfirm={confirmDelete}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  );
}
