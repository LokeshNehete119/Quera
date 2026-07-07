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
  pendingAction?: {
    actionId: string;
    summary: string;
    isDestructive: boolean;
  };
  actionStatus?: "pending" | "approved" | "rejected";
  isStreaming?: boolean;
};

type Theme = "light" | "dark" | "system";

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

// ... previous type definitions ...

export default function ChatUI({ session, onSwitchDatabase }: { session: Session; onSwitchDatabase?: () => void }) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  
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
        headers: { "Authorization": `Bearer ${session.access_token}` },
        credentials: "include" 
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
    try {
      const res = await fetch(`${API_URL}/chats/${chatId}/messages`, { 
        headers: { "Authorization": `Bearer ${session.access_token}` },
        credentials: "include" 
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
             isStreaming: false
           };
        });
        setMessages(mapped);
      }
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;

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
                 "Authorization": `Bearer ${session.access_token}`
               },
               body: JSON.stringify({ action_id: msg.pendingAction.actionId, decision: "reject" }),
               credentials: "include",
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
      content: inputValue.trim(),
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
          "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify(payload),
        credentials: "include",
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
            "Authorization": `Bearer ${session.access_token}`
          },
          body: JSON.stringify({ message_id: frontendMsgId }),
          credentials: "include"
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
          "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify({ action_id: actionId, decision, confirm_text: confirmText }),
        credentials: "include",
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
  };

  const handleDelete = async (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this chat?")) {
       try {
         await fetch(`${API_URL}/chats/${chatId}`, { 
           method: "DELETE", 
           headers: { "Authorization": `Bearer ${session.access_token}` },
           credentials: "include" 
         });
         if (activeChatId === chatId) {
           startNewChat();
         }
         fetchChats();
       } catch (err) {
         console.error(err);
       }
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
            "Authorization": `Bearer ${session.access_token}`
          },
          body: JSON.stringify({ title: editTitle.trim() }),
          credentials: "include"
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
              className="flex-1 flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded-lg transition-colors border border-gray-700"
            >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            New Chat
          </button>
          
          <button 
            onClick={nextTheme}
            className="ml-2 p-2 bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors flex-shrink-0 text-gray-300 hover:text-white"
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
                    <button onClick={(e) => handleDelete(e, chat.id)} className="text-gray-400 hover:text-red-400 p-1" title="Delete">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
              <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-full mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-600 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-200 mb-2">How can I help you today?</h2>
              <p className="text-sm">Start a new conversation to begin.</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto w-full space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div className="flex flex-col gap-2 max-w-[85%] min-w-0">
                    <div
                      className={`rounded-2xl px-5 py-3 shadow-sm break-words ${
                        msg.role === "user"
                          ? "bg-blue-600 text-white rounded-br-none"
                          : msg.role === "system"
                          ? "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-bl-none font-medium"
                          : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-bl-none border border-gray-200 dark:border-gray-700"
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
                    
                    {msg.sql && !msg.pendingAction && (
                      <details className="text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mt-1">
                        <summary className="cursor-pointer px-4 py-2 font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors list-none flex items-center gap-2 select-none">
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
                      <div className="mt-2 border border-blue-200 dark:border-blue-800 rounded-xl overflow-hidden bg-white dark:bg-gray-800 shadow-sm">
                        <div className="bg-blue-50 dark:bg-blue-900/30 px-4 py-3 border-b border-blue-100 dark:border-blue-800 flex items-start gap-3">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <div>
                            <h4 className="font-semibold text-blue-900 dark:text-blue-100 text-sm">Action Required</h4>
                            <p className="text-sm text-blue-800 dark:text-blue-300 mt-1">{msg.pendingAction.summary}</p>
                          </div>
                        </div>
                        
                        <div className="overflow-x-auto">
                          <SyntaxHighlighter language="sql" style={oneDark} customStyle={{ margin: 0, borderRadius: '0', fontSize: '0.75rem' }}>
                            {msg.sql || ""}
                          </SyntaxHighlighter>
                        </div>

                        <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700 flex flex-col gap-3">
                          {msg.pendingAction.isDestructive && msg.actionStatus === "pending" && (
                            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                              <label className="block text-xs font-bold text-red-700 dark:text-red-400 uppercase tracking-wide mb-2">
                                Destructive Action: Type CONFIRM to proceed
                              </label>
                              <input 
                                type="text"
                                value={confirmTexts[msg.pendingAction.actionId] || ""}
                                onChange={(e) => setConfirmTexts(prev => ({...prev, [msg.pendingAction!.actionId]: e.target.value}))}
                                placeholder="CONFIRM"
                                disabled={executingActionId === msg.pendingAction.actionId}
                                className="w-full px-3 py-2 border border-red-300 dark:border-red-700 rounded bg-white dark:bg-gray-900 focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none text-red-900 dark:text-red-100 text-sm font-mono disabled:opacity-50"
                              />
                            </div>
                          )}
                          
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleAction(msg.id, msg.pendingAction!.actionId, "approve", msg.pendingAction!.isDestructive)}
                              disabled={msg.actionStatus !== "pending" || executingActionId === msg.pendingAction!.actionId || (msg.pendingAction.isDestructive && confirmTexts[msg.pendingAction.actionId] !== "CONFIRM")}
                              className="flex-1 flex justify-center items-center bg-green-600 hover:bg-green-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 dark:disabled:text-gray-500 text-white font-semibold py-2 px-4 rounded-lg transition-colors text-sm h-10"
                            >
                              {executingActionId === msg.pendingAction!.actionId ? (
                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                              ) : msg.actionStatus === "approved" ? "Approved" : "Approve & Execute"}
                            </button>
                            <button
                              onClick={() => handleAction(msg.id, msg.pendingAction!.actionId, "reject", false)}
                              disabled={msg.actionStatus !== "pending" || executingActionId === msg.pendingAction!.actionId}
                              className="flex-1 bg-white dark:bg-gray-800 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:bg-gray-100 dark:disabled:bg-gray-900 disabled:text-gray-400 dark:disabled:text-gray-600 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 font-semibold py-2 px-4 rounded-lg transition-colors text-sm h-10"
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
                      className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-full transition-colors flex items-center gap-1"
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
            <div className="relative flex items-end bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 overflow-hidden transition-all">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message Quera..."
                className="w-full max-h-32 min-h-[56px] resize-none py-4 pl-4 pr-12 bg-transparent outline-none text-gray-900 dark:text-white"
                rows={1}
                disabled={isTyping}
              />
              <button
                onClick={handleSend}
                disabled={!inputValue.trim() || isTyping}
                className="absolute right-2 bottom-2 p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 dark:disabled:text-gray-500 transition-colors"
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
    </div>
  );
}
