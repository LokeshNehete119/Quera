# Quera

Quera is a full-stack AI chatbot that lets you talk to your PostgreSQL/Supabase database in plain English — ask questions, get real answers, and make changes safely, all through conversation instead of writing SQL by hand.

Connect any Postgres or Supabase database with a connection string, then just talk to it:

- **"how many users signed up this week?"** → Quera writes the SQL, runs it, and answers in plain language
- **"create a table called students with id, name, grade"** → Quera shows you the exact SQL it wants to run and waits for your approval before touching anything
- **"delete all rows from orders"** → destructive actions require an extra typed confirmation, not just a click, before they're allowed to execute

Quera also handles ordinary conversation naturally — you can chat with it like any assistant, and it only reaches for SQL when your message actually calls for it.

## Why this project exists

Natural-language-to-SQL is a genuinely useful, current pattern — but letting an AI freely run generated SQL against a real database is risky if there's no human in the loop. Quera's core idea is a **human-in-the-loop safety layer**: the AI can read your data freely, but every write, schema change, or destructive operation is shown to you in full (the exact SQL, plus a plain-language summary) and requires explicit approval — with an extra confirmation step for anything irreversible like `DROP TABLE` or an unscoped `DELETE`.

## Key features

- **Conversational interface** — a Gemini/ChatGPT-style chat UI, with casual conversation, read queries, and write operations all handled through the same natural chat
- **Approve/Reject flow for writes** — any AI-generated `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`ALTER`/`DROP` is shown to you before it runs, never executed silently
- **CONFIRM-gated destructive actions** — dropping a table or deleting without a `WHERE` clause requires typing a confirmation word, not just a button click, enforced on the backend, not just the UI
- **Multi-database support** — connect and save multiple databases per account, encrypted at rest, and switch between them anytime; each database gets its own scoped chat history
- **Google sign-in with real multi-user isolation** — every user's saved connections and chats are isolated using Postgres Row Level Security, with application-layer filtering as a second line of defense
- **Two-database architecture** — the app's own storage (chats, users, saved connections) lives in a dedicated Supabase project, completely separate from whatever database you connect to, so the AI's schema-awareness can never see or touch its own internal tables
- **Dockerized** — the whole app (frontend + backend) runs with a single `docker-compose up` command

## Tech stack

**Frontend**
- Next.js (App Router) + Tailwind CSS
- Supabase Auth (`@supabase/supabase-js`) for Google OAuth sign-in

**Backend**
- Python, FastAPI
- Google Gemini (2.5 Flash / 3.1 Flash-Lite) for intent classification and SQL generation
- `psycopg2` for connecting to user-supplied Postgres/Supabase databases
- `cryptography` (Fernet) for encrypting saved connection strings at rest
- `supabase-py` for verifying auth JWTs and talking to the app's own storage project

**Data layer**
- Two separate Supabase projects:
  1. **User-connected databases** — whatever Postgres/Supabase instance the user connects (their own data, untouched except through the approval flow)
  2. **App storage** — a dedicated project holding users, chats, messages, and encrypted saved connections, protected by Row Level Security

**Infrastructure**
- Docker Compose (multi-stage builds for both services)

## How it works, under the hood

1. **Message comes in** → Gemini classifies it as `casual`, `read`, or `write`
2. **Casual** → Gemini replies naturally, no database involved
3. **Read** → the backend fetches the connected database's schema, asks Gemini to generate a `SELECT`-only query, validates it server-side (rejecting anything that isn't read-only even if Gemini was only asked for `SELECT`), executes it, and phrases the result in plain language — with the raw SQL available via a "Show query" toggle
4. **Write** → the same schema-aware generation happens, but the query is never executed automatically. It's returned as a **pending action** with a plain-language summary and the exact SQL, and only runs after the user clicks Approve (or types a confirmation word, for destructive operations) — the backend re-fetches the pending SQL by its own stored ID rather than trusting anything sent back from the frontend, so the executed query can never be tampered with in transit

## Security decisions worth knowing about

- Saved database connection strings are encrypted (Fernet) before being stored, and only decrypted in-memory for the moment a query actually runs
- Row Level Security is enforced at the Postgres level for chats, messages, and saved connections — backed up by explicit `user_id` filters in application code as defense-in-depth, since the backend uses a service-role key that would otherwise bypass RLS entirely
- Destructive SQL keywords are checked server-side, not just requested of the AI — the AI's instructions are treated as advisory, never as the actual safety mechanism

## Running it locally

```bash
git clone https://github.com/LokeshNehete119/Quera.git
cd Quera
docker-compose --env-file frontend/.env.local up --build
```

You'll need to set up your own `.env` files first (see `backend/.env.example` and `frontend/.env.local.example`) with:
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey))
- Two Supabase projects (one for app storage/auth, one to connect to as user data)
- A generated Fernet encryption key for connection string storage
- Google OAuth credentials configured on your app-storage Supabase project

Once running: `http://localhost:3000` for the app, `http://localhost:8001/docs` for the backend's API reference.

## Status

Actively developed as a personal project. Core functionality (connection gate, chat, read/write pipeline with approval, multi-user auth, multi-database support, Docker) is complete and tested. Planned next: low-privilege database roles for the AI's connections, live deployment, and expanded database support (MySQL).