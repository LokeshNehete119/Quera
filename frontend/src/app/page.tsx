"use client";

import { useEffect, useState, FormEvent } from "react";
import ChatUI from "@/components/ChatUI";
import { supabase } from "@/lib/supabaseClient";
import { Session } from "@supabase/supabase-js";

type DBConnection = {
  id: string;
  name: string;
  created_at: string;
};

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isSelectingDB, setIsSelectingDB] = useState(false);
  const [savedConnections, setSavedConnections] = useState<DBConnection[]>([]);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);

  const [connectionString, setConnectionString] = useState("");
  const [connectionName, setConnectionName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

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
      try {
        const res = await fetch(`${API_URL}/db/status`, {
          credentials: "include",
        });
        const data = await res.json();
        setIsConnected(data.connected);

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
        credentials: "include",
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
        credentials: "include",
      });

      if (res.ok) {
        const data = await res.json();
        const newConnectionId = data.id;
        
        // Add the newly created connection to the local state so it appears in the list later
        setSavedConnections(prev => [{
          id: data.id,
          name: data.name,
          created_at: new Date().toISOString()
        }, ...prev]);

        // Automatically select the newly created connection
        const selectRes = await fetch(`${API_URL}/db/connections/${newConnectionId}/select`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${session?.access_token}` },
          credentials: "include",
        });

        if (selectRes.ok) {
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
        credentials: "include",
      });
      if (res.ok) {
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

  const handleDeleteConnection = async (id: string) => {
    if (!confirm("Are you sure you want to remove this saved database?")) return;
    try {
      const res = await fetch(`${API_URL}/db/connections/${id}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${session?.access_token}` },
        credentials: "include",
      });
      if (res.ok) {
        setSavedConnections(prev => prev.filter(c => c.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete", err);
    }
  };

  // Derive sensible default name when pasting a string
  useEffect(() => {
    if (connectionString && !connectionName) {
      try {
        const url = new URL(connectionString);
        if (url.hostname) {
          setConnectionName(url.hostname.split('.')[0]);
        }
      } catch (e) {
        // invalid URL, ignore
      }
    }
  }, [connectionString, connectionName]);

  // 1. Loading State (Auth)
  if (isAuthLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </main>
    );
  }

  // 2. Auth Gate (Not signed in)
  if (!session) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50">
        <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-sm text-center">
          <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Welcome to Quera
          </h1>
          <p className="text-gray-500 mb-8 text-sm">
            Sign in to securely access and manage your database chats.
          </p>
          
          <button
            onClick={handleGoogleSignIn}
            className="w-full flex items-center justify-center gap-3 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold py-3 px-4 rounded-xl transition-colors shadow-sm"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>
        </div>
      </main>
    );
  }

  // 3. Loading State (DB Connection check)
  if (isConnected === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </main>
    );
  }

  // 4. Connected State (Gate Passed) - unless they asked to select DB
  if (isConnected === true && !isSelectingDB) {
    // We pass onSwitchDatabase to flip isSelectingDB without destroying backend session
    return <ChatUI session={session} onSwitchDatabase={() => setIsSelectingDB(true)} />;
  }

  // 5. Not Connected or explicitly switching State -> Database Selection / Creation
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-gray-50 relative">
      <button 
        onClick={() => supabase.auth.signOut()}
        className="absolute top-6 right-6 text-sm text-gray-500 hover:text-gray-900 transition-colors"
      >
        Sign Out
      </button>

      <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-lg">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Your Databases
        </h1>
        <p className="text-gray-500 mb-6 text-sm">
          Welcome back, {session.user.email}. Select a saved database or connect a new one.
        </p>
        
        {isConnected && isSelectingDB && !showNewForm && (
          <button
            onClick={() => setIsSelectingDB(false)}
            className="w-full mb-6 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-2 px-4 rounded-xl transition-colors shadow-sm"
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
                  <li key={conn.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-xl hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer group" onClick={() => handleSelectConnection(conn.id)}>
                    <div>
                      <h3 className="font-semibold text-gray-900">{conn.name}</h3>
                      <p className="text-xs text-gray-500 mt-1">Saved {new Date(conn.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <button 
                        onClick={(e) => { e.stopPropagation(); handleDeleteConnection(conn.id); }}
                        className="text-gray-400 hover:text-red-500 p-2 rounded-full hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
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
              <div className="text-center text-gray-500 py-6 bg-gray-50 rounded-xl border border-dashed border-gray-300 text-sm">
                No saved databases found.
              </div>
            )}
            
            <button
              onClick={() => setShowNewForm(true)}
              className="w-full mt-4 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold py-3 px-4 rounded-xl transition-colors shadow-sm flex items-center justify-center gap-2"
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
              <label htmlFor="connString" className="block text-sm font-medium text-gray-700 mb-1">
                Connection String
              </label>
              <input
                id="connString"
                type="password"
                placeholder="postgresql://user:password@host:port/dbname"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-gray-900"
                value={connectionString}
                onChange={(e) => setConnectionString(e.target.value)}
                required
              />
            </div>
            
            <div>
              <label htmlFor="connName" className="block text-sm font-medium text-gray-700 mb-1">
                Connection Name
              </label>
              <input
                id="connName"
                type="text"
                placeholder="e.g. Production DB"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-gray-900"
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                required
              />
            </div>

            {errorMessage && (
              <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
                {errorMessage}
              </div>
            )}

            <div className="flex gap-3 mt-2">
              <button
                type="button"
                onClick={() => { setShowNewForm(false); setErrorMessage(""); }}
                className="flex-1 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 font-semibold py-2 px-4 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-[2] bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? "Connecting..." : "Save & Connect"}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
