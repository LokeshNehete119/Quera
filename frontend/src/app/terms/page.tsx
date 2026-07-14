import Link from "next/link";

export default function Terms() {
  return (
    <main className="flex min-h-screen flex-col items-center p-8 bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      <div className="w-full max-w-3xl bg-white dark:bg-gray-800 p-10 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 mt-10">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">Terms of Service</h1>
        
        <div className="prose dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 space-y-6">
          <p>
            By using Quera, you agree to these terms.
          </p>

          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mt-8 mb-4">Usage Rules</h2>
          <p>
            Quera is a portfolio project provided "as is". While we implement extensive safety checks (such as AST-based query validation to block destructive operations during read-only requests), you remain entirely responsible for reviewing and approving any database modifications (writes, updates, drops) before they are executed.
          </p>

          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mt-8 mb-4">Liability</h2>
          <p>
            We cannot guarantee zero risk when granting an AI assistant access to a database. You agree that we are not liable for any data loss, corruption, or downtime that results from queries executed through the application. We strongly recommend testing Quera on non-production or staging databases.
          </p>
        </div>

        <div className="mt-12 pt-6 border-t border-gray-200 dark:border-gray-700">
          <Link href="/" className="text-blue-500 hover:text-blue-600 dark:hover:text-blue-400 font-medium transition-colors">
            &larr; Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
