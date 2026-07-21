import Link from "next/link";

export default function Privacy() {
  return (
    <main className="flex min-h-screen flex-col items-center p-8 bg-gray-900">
      <div className="w-full max-w-3xl bg-gray-800 p-10 rounded-2xl shadow-xl border border-gray-700 mt-10">
        <h1 className="text-3xl font-bold text-white mb-6">Privacy Policy</h1>
        
        <div className="prose dark:prose-invert max-w-none text-gray-300 space-y-6">
          <p>
            Quera is an AI-powered database assistant designed to generate and safely execute SQL queries on your behalf.
          </p>

          <h2 className="text-xl font-semibold text-white mt-8 mb-4">Information We Collect</h2>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>Profile Information:</strong> When you sign in with Google, we securely receive your email address and name.</li>
            <li><strong>Database Credentials:</strong> Any database connection strings you provide are symmetrically encrypted via Fernet before being stored in our secure database.</li>
            <li><strong>Chat Data:</strong> Your prompts, the generated SQL queries, and metadata regarding query safety are stored to provide you with your conversation history.</li>
          </ul>

          <h2 className="text-xl font-semibold text-white mt-8 mb-4">How We Use Your Data</h2>
          <p>
            Your data is used strictly to provide the core chatbot service. We transmit your prompts and database schema definitions to our designated AI provider (Google Gemini) to generate SQL queries. We do not sell your personal data or share it with unauthorized third parties.
          </p>
        </div>

        <div className="mt-12 pt-6 border-t border-gray-700">
          <Link href="/" className="text-accent hover:text-accent-hover dark:hover:text-accent font-medium transition-colors">
            &larr; Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
