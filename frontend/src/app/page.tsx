"use client";

import { useEffect, useState, FormEvent } from "react";
import ChatUI from "@/components/ChatUI";
import { supabase } from "@/lib/supabaseClient";
import { Session } from "@supabase/supabase-js";
import ConfirmModal from "@/components/ConfirmModal";
import PasswordStrength from "@/components/PasswordStrength";

type DBConnection = {
  id: string;
  name: string;
  db_type: string;
  created_at: string;
};

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  
  // Auth state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authFormLoading, setAuthFormLoading] = useState(false);
  const [isPasswordStrong, setIsPasswordStrong] = useState(false);

  // Forgot password state
  const [forgotModalOpen, setForgotModalOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotMessage, setForgotMessage] = useState("");
  const [forgotError, setForgotError] = useState("");
  const [isForgotLoading, setIsForgotLoading] = useState(false);

  // DB Connections state
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [activeConnId, setActiveConnId] = useState<string | null>(null);
  const [isSelectingDB, setIsSelectingDB] = useState(false);
  const [savedConnections, setSavedConnections] = useState<DBConnection[]>([]);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [dbToDelete, setDbToDelete] = useState<string | null>(null);

  const [theme, setTheme] = useState("system");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove("dark");
    if (theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      root.classList.add("dark");
    }
  }, [theme]);

  const [connectionString, setConnectionString] = useState("");
  const [connectionName, setConnectionName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

  const handleConnectionStringChange = (val: string) => {
    setConnectionString(val);
    if (!connectionName) {
      try {
        const url = new URL(val);
        if (url.hostname) {
          setConnectionName(url.hostname.split('.')[0]);
        }
      } catch (e) {
        // invalid URL, ignore
      }
    }
  };

  // Auth Effect
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setIsAuthLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // DB Status & Connections Effect
  useEffect(() => {
    if (!session) {
      setIsConnected(null);
      return;
    }

    async function checkStatusAndFetchConnections() {
      const savedConnId = localStorage.getItem("activeConnId");
      if (savedConnId) {
        setActiveConnId(savedConnId);
      }

      try {
        const headers: Record<string, string> = { "Authorization": `Bearer ${session?.access_token || ""}` };
        if (savedConnId) headers["X-Connection-Id"] = savedConnId;

        const res = await fetch(`${API_URL}/db/status`, { headers });
        const data = await res.json();
        setIsConnected(data.connected);
        
        if (!data.connected && savedConnId) {
          localStorage.removeItem("activeConnId");
          setActiveConnId(null);
        }

        // Always fetch saved connections so they are ready if the user clicks "Switch Database"
        // (Even if they are currently connected)
        fetchSavedConnections();
      } catch (err) {
        console.error("Failed to check status:", err);
        setIsConnected(false);
      }
    }
    checkStatusAndFetchConnections();
  }, [session, API_URL]);

  const fetchSavedConnections = async () => {
    setIsLoadingConnections(true);
    try {
      const res = await fetch(`${API_URL}/db/connections`, {
        headers: { "Authorization": `Bearer ${session?.access_token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSavedConnections(data);
      }
    } catch (err) {
      console.error("Failed to fetch connections", err);
    } finally {
      setIsLoadingConnections(false);
    }
  };

  const handleEmailAuth = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setAuthFormLoading(true);
    try {
      if (isSignUp) {
        if (password !== confirmPassword) {
          setAuthError("Passwords do not match.");
          setAuthFormLoading(false);
          return;
        }
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) setAuthError(error.message);
        else setAuthError("Check your email for the confirmation link.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) setAuthError(error.message);
      }
    } catch (err: any) {
      setAuthError(err.message || "Authentication failed");
    } finally {
      setAuthFormLoading(false);
    }
  };

  const handleForgotPassword = async (e: FormEvent) => {
    e.preventDefault();
    setForgotError("");
    setForgotMessage("");
    setIsForgotLoading(true);
    try {
      const { data, error } = await supabase.auth.resetPasswordForEmail(forgotEmail, {
        redirectTo: 'https://quera-nine.vercel.app/reset-password'
      });
      if (error) {
        console.log("Supabase API Error Object:", JSON.stringify(error, Object.getOwnPropertyNames(error)));
        // If error.message is literally rendering as {}, maybe it is an object itself. Let's make sure it falls back to stringifying it cleanly if it's not a string.
        setForgotError(typeof error.message === 'string' ? error.message : JSON.stringify(error.message) || "Unknown error");
      } else {
        setForgotMessage("Check your email for a reset link.");
      }
    } catch (err: any) {
      console.log("Catch Block Error Object:", JSON.stringify(err, Object.getOwnPropertyNames(err)));
      setForgotError(typeof err.message === 'string' ? err.message : JSON.stringify(err.message) || "An unexpected error occurred.");
    } finally {
      setIsForgotLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin
      }
    });
  };

  const handleCreateConnection = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const res = await fetch(`${API_URL}/db/connections`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session?.access_token}`
        },
        body: JSON.stringify({ name: connectionName, connection_string: connectionString }),
      });

      if (res.ok) {
        const data = await res.json();
        const newConnectionId = data.id;
        
        // Add the newly created connection to the local state so it appears in the list later
        setSavedConnections(prev => [{
          id: data.id,
          name: data.name,
          db_type: connectionString.startsWith('postgres') ? 'postgres' : 'mysql',
          created_at: new Date().toISOString()
        }, ...prev]);

        // Automatically select the newly created connection
        const selectRes = await fetch(`${API_URL}/db/connections/${newConnectionId}/select`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${session?.access_token}` },
        });

        if (selectRes.ok) {
          const selectData = await selectRes.json();
          localStorage.setItem("activeConnId", selectData.conn_id);
          setActiveConnId(selectData.conn_id);
          setIsConnected(true);
          setIsSelectingDB(false);
          setShowNewForm(false);
        } else {
          const errorData = await selectRes.json();
          setErrorMessage(errorData.detail || "Connection saved but failed to auto-select.");
        }
      } else {
        const data = await res.json();
        setErrorMessage(data.detail || "Failed to save connection.");
      }
    } catch (err) {
      setErrorMessage("Network error or server is unreachable.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectConnection = async (id: string) => {
    setErrorMessage("");
    try {
      const res = await fetch(`${API_URL}/db/connections/${id}/select`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${session?.access_token}` },
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("activeConnId", data.conn_id);
        setActiveConnId(data.conn_id);
        setIsConnected(true);
        setIsSelectingDB(false);
        setShowNewForm(false);
      } else {
        const data = await res.json();
        setErrorMessage(data.detail || "Failed to select connection.");
      }
    } catch (err) {
      setErrorMessage("Failed to connect.");
    }
  };

  const requestDeleteConnection = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDbToDelete(id);
    setModalOpen(true);
  };

  const confirmDeleteConnection = async () => {
    if (!dbToDelete) return;
    setModalOpen(false);
    try {
      const res = await fetch(`${API_URL}/db/connections/${dbToDelete}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${session?.access_token}` },
      });
      if (res.ok) {
        setSavedConnections(prev => prev.filter(c => c.id !== dbToDelete));
      }
    } catch (err) {
      console.error("Failed to delete", err);
    }
  };

  // Removed faulty useEffect that was aggressively re-populating connectionName on empty

  // 1. Loading State (Auth)
  if (isAuthLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </main>
    );
  }

  // 2. Auth Gate (Not signed in)
  if (!session) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-[#0a0a0f] relative overflow-hidden transition-colors duration-200">
        {/* Radial Glow Background */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-indigo-600/20 rounded-full blur-[100px] pointer-events-none mix-blend-screen opacity-70"></div>
        
        <div className="relative z-10 w-full max-w-md px-4 flex flex-col items-center">
          <div className="flex items-center justify-center gap-3 mb-10">
            <img src="/logo.svg" alt="Quera Logo" className="w-10 h-10 drop-shadow-md" />
            <span className="text-2xl font-bold text-white tracking-tight">Quera</span>
          </div>

          <h1 className="text-3xl font-bold text-white mb-3 text-center tracking-tight">
            Talk to your database. <span className="relative whitespace-nowrap"><span className="relative z-10">No SQL required.</span><span className="absolute left-0 bottom-1 w-full h-[3px] bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"></span></span>
          </h1>
          <p className="text-gray-400 mb-8 text-center text-sm leading-relaxed max-w-sm">
            Connect your PostgreSQL or MySQL database and query it in natural language — every write reviewed before it runs.
          </p>

          <div className="bg-[#111118] border border-indigo-500/20 p-8 rounded-2xl shadow-2xl w-full text-left">
            <h2 className="text-2xl font-bold text-white mb-1">
              {isSignUp ? "Create an account" : "Welcome back"}
            </h2>
            <p className="text-gray-400 mb-6 text-sm">
              {isSignUp ? "Sign up to start chatting with your database." : "Sign in to securely access your database chats."}
            </p>
            
            {authError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">
                {authError}
              </div>
            )}
            
            <form onSubmit={handleEmailAuth} className="flex flex-col gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  required
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-white placeholder-gray-600"
                />
              </div>
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="block text-sm font-medium text-gray-300">Password</label>
                  {!isSignUp && (
                    <button 
                      type="button"
                      onClick={() => { setForgotEmail(email); setForgotModalOpen(true); }}
                      className="text-sm font-medium text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-white placeholder-gray-600"
                />
                {isSignUp && (
                  <PasswordStrength password={password} onValidationChange={setIsPasswordStrong} />
                )}
              </div>
              
              {isSignUp && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Confirm Password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-white placeholder-gray-600"
                  />
                </div>
              )}
              
              <button
                type="submit"
                disabled={authFormLoading || (isSignUp && (!isPasswordStrong || password !== confirmPassword))}
                className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 px-4 rounded-xl transition-colors shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {authFormLoading ? "Please wait..." : (isSignUp ? "Create account" : "Sign in")}
              </button>
            </form>

            <div className="relative flex items-center justify-center mb-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-800"></div>
              </div>
              <div className="relative px-4 bg-[#111118] text-xs text-gray-500 uppercase tracking-widest">
                Or continue with
              </div>
            </div>

            <button
              onClick={handleGoogleSignIn}
              type="button"
              className="w-full flex items-center justify-center gap-3 bg-[#0a0a0f] border border-gray-700/50 hover:bg-gray-800 text-gray-300 font-medium py-2.5 px-4 rounded-xl transition-colors shadow-sm cursor-pointer mb-6"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Google
            </button>

            <p className="text-center text-sm text-gray-400">
              {isSignUp ? "Already have an account?" : "No account?"}
              <button 
                onClick={() => { setIsSignUp(!isSignUp); setAuthError(""); }} 
                className="ml-1.5 text-indigo-400 hover:text-indigo-300 font-medium transition-colors cursor-pointer"
              >
                {isSignUp ? "Sign in" : "Create one"}
              </button>
            </p>
          </div>
        </div>

        {/* Forgot Password Modal */}
        {forgotModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
            <div className="bg-[#111118] rounded-2xl w-full max-w-md p-6 shadow-2xl border border-gray-800">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-white">Reset Password</h3>
                <button 
                  onClick={() => { setForgotModalOpen(false); setForgotError(""); setForgotMessage(""); }} 
                  className="text-gray-400 hover:text-white transition-colors cursor-pointer"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              
              <p className="text-sm text-gray-400 mb-6">
                Enter your email and we'll send you a link to reset your password.
              </p>
              
              {forgotError && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">
                  {forgotError}
                </div>
              )}
              {forgotMessage && (
                <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 text-green-400 text-sm rounded-lg">
                  {forgotMessage}
                </div>
              )}
              
              <form onSubmit={handleForgotPassword} className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="name@example.com"
                    required
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-white placeholder-gray-600"
                  />
                </div>
                <div className="flex justify-end gap-3 mt-4">
                  <button
                    type="button"
                    onClick={() => { setForgotModalOpen(false); setForgotError(""); setForgotMessage(""); }}
                    className="px-4 py-2 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isForgotLoading || !forgotEmail}
                    className="px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                  >
                    {isForgotLoading ? "Sending..." : "Send Reset Link"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    );
  }

  // 3. Loading State (DB Connection check)
  if (isConnected === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </main>
    );
  }

  // 4. Connected State (Gate Passed) - unless they asked to select DB
  if (isConnected === true && !isSelectingDB) {
    return <ChatUI session={session} activeConnId={activeConnId} savedConnections={savedConnections} onSwitchDatabase={() => setIsSelectingDB(true)} onSelectConnection={handleSelectConnection} onConnectionsChange={fetchSavedConnections} />;
  }

  // 5. Not Connected or explicitly switching State -> Database Selection / Creation
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-gray-50 dark:bg-gray-900 transition-colors duration-200 relative">
      <button 
        onClick={() => supabase.auth.signOut()}
        className="absolute top-6 right-6 flex items-center gap-2 p-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl border border-gray-200 dark:border-gray-700 transition-colors text-gray-600 dark:text-gray-300 shadow-sm cursor-pointer"
        title="Sign Out"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clipRule="evenodd" />
        </svg>
      </button>

      <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-xl w-full max-w-lg border border-gray-200 dark:border-gray-700">
        <div className="flex justify-center mb-6">
          <img src="/logo.svg" alt="Quera Logo" className="w-12 h-12 drop-shadow-sm" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 text-center">
          Your Databases
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mb-6 text-sm text-center">
          Welcome back, {session.user.email}. Select a saved database or connect a new one.
        </p>
        
        {isConnected && isSelectingDB && !showNewForm && (
          <button
            onClick={() => setIsSelectingDB(false)}
            className="w-full mb-6 flex items-center justify-center gap-2 bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 font-semibold py-2 px-4 rounded-xl transition-colors shadow-sm border border-transparent dark:border-gray-600 cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
            Back to Chat
          </button>
        )}

        {!showNewForm ? (
          <div className="space-y-4">
            {isLoadingConnections ? (
              <div className="text-center text-gray-400 py-4 text-sm animate-pulse">Loading connections...</div>
            ) : savedConnections.length > 0 ? (
              <ul className="space-y-3">
                {savedConnections.map(conn => (
                  <li key={conn.id} className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-300 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors cursor-pointer group bg-white dark:bg-gray-800" onClick={() => handleSelectConnection(conn.id)}>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-gray-100">{conn.name}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Saved {new Date(conn.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <button 
                        onClick={(e) => requestDeleteConnection(e, conn.id)}
                        className="text-gray-400 hover:text-red-500 p-2 rounded-full hover:bg-red-50 dark:hover:bg-gray-700 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                        title="Delete connection"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      </button>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-blue-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-center text-gray-500 py-6 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-dashed border-gray-300 dark:border-gray-700 text-sm">
                No saved databases found.
              </div>
            )}
            
            <button
              onClick={() => setShowNewForm(true)}
              className="w-full mt-4 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 font-semibold py-3 px-4 rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2 cursor-pointer"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
              Connect new database
            </button>
          </div>
        ) : (
          <form onSubmit={handleCreateConnection} className="flex flex-col gap-4">
            <div>
              <label htmlFor="connString" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Connection String
              </label>
              <input
                id="connString"
                type="password"
                placeholder="postgresql://user:password@host:port/dbname"
                className="w-full px-4 py-2 font-mono bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                value={connectionString}
                onChange={(e) => handleConnectionStringChange(e.target.value)}
                autoComplete="new-password"
                data-1p-ignore
                required
              />
            </div>
            
            <div>
              <label htmlFor="connName" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Connection Name
              </label>
              <input
                id="connName"
                type="text"
                placeholder="e.g. Production DB"
                className="w-full px-4 py-2 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                autoComplete="off"
                data-1p-ignore
                required
              />
            </div>

            {errorMessage && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg text-sm border border-red-200 dark:border-red-800">
                {errorMessage}
              </div>
            )}

            <div className="flex gap-3 mt-2">
              <button
                type="button"
                onClick={() => { setShowNewForm(false); setErrorMessage(""); }}
                className="flex-1 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600 font-semibold py-2 px-4 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-[2] bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isSubmitting ? "Connecting..." : "Save & Connect"}
              </button>
            </div>
          </form>
        )}
      </div>

      <ConfirmModal
        isOpen={modalOpen}
        title="Remove Database"
        message="Are you sure you want to remove this saved database connection?"
        confirmText="Remove"
        onConfirm={confirmDeleteConnection}
        onCancel={() => setModalOpen(false)}
      />
    </main>
  );
}
