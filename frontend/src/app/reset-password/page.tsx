"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabaseClient";
import { useRouter } from "next/navigation";
import PasswordStrength from "@/components/PasswordStrength";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isPasswordStrong, setIsPasswordStrong] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingSession, setIsCheckingSession] = useState(true);

  useEffect(() => {
    // Check if we have an active session (Supabase sets it from the URL hash automatically)
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        // If we don't have a session, they might have arrived without a valid recovery token
        setError("Invalid or expired recovery link. Please request a new password reset.");
      }
      setIsCheckingSession(false);
    });
  }, []);

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) {
        setError(error.message);
      } else {
        setMessage("Password updated successfully! Redirecting...");
        setTimeout(() => {
          router.push("/");
        }, 2000);
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  if (isCheckingSession) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0a0a0f] transition-colors duration-200">
        <div className="animate-spin h-8 w-8 border-4 border-indigo-500 border-t-transparent rounded-full"></div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#0a0a0f] relative overflow-hidden transition-colors duration-200">
      {/* Radial Glow Background */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-indigo-600/20 rounded-full blur-[100px] pointer-events-none mix-blend-screen opacity-70"></div>
      
      <div className="relative z-10 w-full max-w-md px-4 flex flex-col items-center">
        <div className="flex items-center justify-center gap-3 mb-10">
          <img src="/logo.svg" alt="Quera Logo" className="w-10 h-10 drop-shadow-md" />
          <span className="text-2xl font-bold text-white tracking-tight">Quera</span>
        </div>

        <div className="bg-[#111118] border border-indigo-500/20 p-8 rounded-2xl shadow-2xl w-full text-left">
          <h2 className="text-2xl font-bold text-white mb-1">Set New Password</h2>
          <p className="text-gray-400 mb-8 text-sm">Please enter your new password below.</p>

          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">
              {error}
            </div>
          )}
          {message && (
            <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 text-green-400 text-sm rounded-lg">
              {message}
            </div>
          )}

          {/* Only show the form if we don't have a hard error preventing setup (like invalid session) */}
          {!error.includes("Invalid or expired") ? (
            <form onSubmit={handleResetPassword} className="flex flex-col gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full px-4 py-2.5 bg-[#0a0a0f] border border-gray-700/50 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-white placeholder-gray-600"
                />
                <PasswordStrength password={newPassword} onValidationChange={setIsPasswordStrong} />
              </div>

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

              <button
                type="submit"
                disabled={isLoading || !isPasswordStrong || newPassword !== confirmPassword || !newPassword}
                className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 px-4 rounded-xl transition-colors shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? "Saving..." : "Update Password"}
              </button>
            </form>
          ) : (
            <button
              onClick={() => router.push("/")}
              className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 px-4 rounded-xl transition-colors shadow-sm cursor-pointer"
            >
              Return to Sign In
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
