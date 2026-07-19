# Quera

Talk to your own database in plain English — safely.

Quera is a full-stack AI chatbot that connects to your PostgreSQL/Supabase or MySQL database and lets you query, update, and modify it through natural conversation. Casual chat gets a conversational reply, read queries execute automatically after server-side validation, and any write or destructive action requires explicit human approval before it touches your data.

**Live app:** https://quera-nine.vercel.app
**Repo:** https://github.com/LokeshNehete119/Quera

---

## Why this project is more than "a wrapper around an LLM API"

A lot of "chat with your database" projects are a thin prompt wrapped around an LLM call. Quera's differentiator is everything happening *around* that call — a locally-trained ML classifier, AST-based SQL safety validation, and a schema-retrieval layer that reduces reliance on the LLM for tasks a smaller, purpose-built model can do faster, cheaper, and more reliably. Three of these are documented below with their actual evaluation numbers, not just a description of the approach.

---

## Architecture

```
User (browser)
      │
      ▼
Next.js frontend (Vercel)
      │  Google OAuth via Supabase Auth
      ▼
FastAPI backend (Render)
      │
      ├─ Local ML intent classifier (casual / read / write) — no API call
      ├─ Schema retrieval (embeddings + FK graph) — narrows schema before prompting
      ├─ Gemini (Flash) — SQL generation + natural language responses
      ├─ sqlglot AST validation — safety classification of generated SQL
      └─ Human-in-the-loop approval — Approve/Reject, typed CONFIRM for destructive ops
      │
      ▼
User's own PostgreSQL/Supabase or MySQL database
(connection string encrypted at rest with Fernet)
```

Two isolated Supabase projects are used deliberately: one holds the app's own chat history and connection metadata, the other is never touched by the AI — so Quera has zero schema-awareness of its own internal storage, even by accident.

---

## Engineering deep-dives

### 1. Replacing Gemini-based intent classification with a local ML model

**Problem:** every message was previously sent to Gemini just to decide "is this casual chat, a read query, or a write request?" — an extra API call and extra latency for a task that doesn't need an LLM's full reasoning.

**What was built:** a local scikit-learn pipeline (TF-IDF vectorizer → Calibrated LinearSVC) trained on a synthetic dataset, then evaluated against a genuinely separate, hand-written test set.

**What went wrong first, and how it was caught:** the model initially scored 100% accuracy on a GPT-generated 10k-row dataset. That number was correctly treated as suspicious rather than good news — it was overfitting to generation-template patterns, not learning the actual task. A 76-example, hand-written held-out set (never touched by any generator) was built specifically to get an honest number: **90.79%**, with all 7 errors being casual messages misclassified as read/write (e.g. "I need some coffee").

**Confidence-based fallback was tested and rejected with evidence, not assumption:** the natural fix — "fall back to Gemini when the classifier's confidence is low" — was tested using `predict_proba`. It failed: Gemini was **99.99% confident on examples it got wrong**, meaning a confidence threshold cannot separate correct predictions from incorrect ones. This ruled out the fallback design entirely rather than shipping it on hope.

**One targeted data augmentation pass** (adding ~29 hand-written casual examples containing SQL-adjacent words like "make," "change," "where" used in non-database contexts) brought accuracy to **94.74%**, still 100% recall on read/write. Iteration deliberately stopped here — diminishing returns, and read/write recall (the safety-relevant metric) was already perfect.

**Result:** the classifier now runs locally in under 20ms and is the *sole* classifier in production — no Gemini fallback, no confidence threshold.

---

### 2. SQL safety validation via AST parsing (sqlglot), not regex

**Problem:** the original safety check used string/keyword matching to detect destructive SQL (DROP, TRUNCATE, unscoped DELETE). Regex-based detection is fragile — it's a matter of when, not if, a query is phrased in a way that slips past it.

**What was built:** full replacement with `sqlglot`-based AST parsing. The entire parsed query tree is walked for write/destructive nodes, not just the top-level statement type.

**Two real gaps found during design, before they became production bugs:**
- **Writable CTEs**: `WITH x AS (DELETE FROM users RETURNING id) SELECT * FROM x` parses with a top-level `SELECT`, so a naive "check the top-level statement type" approach would misclassify a delete as a safe read. Fixed by walking the full tree.
- **Stacked/multi-statement queries** needed the same destructive-action check applied on the write path, not just the read path.

**Verified, not assumed:** sqlglot's actual class names for TRUNCATE/DROP (`TruncateTable`, `Drop`) were confirmed against the installed library version rather than hardcoded from memory or documentation.

**Known, documented limitation:** tautological WHERE clauses (`WHERE 1=1`) are not caught, since that requires semantic evaluation of the predicate, not just AST structure. This is a deliberate, accepted scope boundary — not an oversight.

**Test coverage:** an 11-case test suite (13 after MySQL support) covers both SQL dialects, including the CTE and stacked-query edge cases the old regex approach would have missed. All passing.

---

### 3. Schema retrieval to reduce prompt size and LLM dependency

**Problem:** every SQL-generation request sends the *entire* database schema to Gemini, regardless of relevance. On a wide schema, this wastes tokens and can dilute the model's focus with irrelevant tables.

**Goal:** rank tables by relevance to the user's question and send only the relevant subset (padded with foreign-key-connected neighbor tables), falling back to the full schema when signal is weak or the schema is small enough that it doesn't matter.

**Iteration, in order — including the approaches that failed and why:**

| Approach | Result |
|---|---|
| TF-IDF similarity | Only worked when the user's question contained literal table/column names — failed completely on natural phrasing like "who spent the most money" |
| Swap to local sentence embeddings (`all-MiniLM-L6-v2`) | Verified via raw cosine-similarity scores that the model was functioning correctly, but bare identifier lists (`id, name, email`) gave it too little real language to work with |
| Add hand-written natural-language table descriptions | Meaningfully closed the gap — enabled correct semantic matches like "arrived" → shipments table, "reviewed" → reviews table |
| Fixed similarity threshold | Simple, but a single global cutoff can't fit every query's score distribution — occasionally dropped a relevant table sitting just below the line |
| Fixed top-k selection | Broke on genuine long join chains — a hardcoded `k=3` cannot fit a query that legitimately needs 4+ tables |
| Relative margin (score within X% of the top match) | Best-performing scorer; adapts to each query's confidence distribution rather than one global number |

**The structural discovery:** none of the three scoring strategies could reliably tell "a narrow query that needs 3 tables" apart from "a vague query that coincidentally scores moderately across 3 tables" — both produce the same statistical shape to a similarity function. This caused every scoring approach to fail identically on broad requests like *"show me everything in the database."*

**The fix:** rather than continuing to tune a scoring mechanism against a problem it structurally can't solve, a lightweight keyword pre-filter now catches broad-intent phrasing ("everything," "summarize," "overview") and routes straight to the full schema before similarity scoring ever runs — combined with the margin-based scorer and a graph-neighbor padding step for join chains.

**Final evaluation result: 100% recall, ~66% precision across a 16-case hand-written test set** covering single-table queries, multi-table joins, FK chains, deliberately vague queries, and an adversarial case designed to trigger a keyword collision (a query using the word "status," which also happens to be a column name in an unrelated table).

**Verified live** against a real MySQL-backed test database with seeded data — confirmed correct table narrowing on specific queries, correct full-schema fallback on vague ones, and a correctly executed multi-table JOIN with real returned rows.

**Measured efficiency gain:** on the 9-table evaluation schema, for the 12 of 16 cases where retrieval genuinely narrowed the schema (the remaining 4 correctly triggered full-schema fallback for broad/ambiguous queries), the schema text sent to Gemini was reduced by an average of **58.5%**. Averaged across all 16 cases including intentional fallbacks, the blended reduction was **43.9%**. These numbers were measured on a 9-table test schema only — actual reduction on a real user's database will depend on its size and structure, and was not separately benchmarked at larger scale. A reasonable expectation is that the percentage improves on wider schemas, since the relevant-table set stays small while the total table count grows, but this is an untested hypothesis, not a measured result.

**Known open gap, intentionally deferred:** a genuinely broad query (e.g. "show me everything") now correctly receives the full schema, but a single SQL `SELECT` statement structurally cannot represent the contents of 9+ unrelated tables at once — this is a generation/UX-level problem, not a retrieval problem, and is tracked separately rather than folded into this feature's scope.

**Known limitation, found downstream of retrieval, not caused by it:** schema-statistics questions that require aggregate reasoning across every table (e.g. "count how many tables have more than 2 columns") are unreliable regardless of dialect, even when retrieval correctly supplies the full schema. This traced back to Gemini attempting multi-step counting via free-text reasoning rather than delegating the count to SQL's own aggregation (e.g. an `information_schema` `GROUP BY`/`HAVING` query) — a known LLM reasoning weakness, not a bug in the retrieval or validation layers. Deliberately not chased further given low real-world frequency of this query type; the correct fix (prompting Gemini to generate an aggregate SQL query instead of reasoning manually) is understood but deferred.

---

### 4. Multi-database support (PostgreSQL + MySQL)

Dialect-aware schema introspection, SQL generation prompting, and `sqlglot` validation, driven off a stored `db_type` per connection. Caught and fixed along the way: a cursor row-shape mismatch (tuples vs. dicts) between drivers, and a schema-introspection bug where MySQL's `information_schema.tables` itself was incorrectly appearing as a queryable user table. Verified end-to-end by asking Quera to create a table via natural language, approving the generated DDL, and independently confirming the result in DBeaver — a separate tool, to rule out the app reporting a false success.

---

## Safety architecture

- **Casual messages** → conversational reply, no SQL touches the database
- **Read queries** → auto-execute after passing sqlglot's read-safety check
- **Write/DDL queries** → require explicit Approve/Reject before execution
- **Destructive actions** (DROP, TRUNCATE, unscoped DELETE) → require typing a confirmation word before Approve becomes clickable, enforced server-side, not just in the UI
- **Ownership checks**: every connection-scoped endpoint verifies the authenticated user actually owns the referenced `conn_id` server-side (defense against IDOR), independent of any client-supplied state
- **Encryption at rest**: saved connection strings are encrypted with Fernet before storage
- **Defense-in-depth on auth**: Supabase RLS policies plus explicit `user_id` filters in every query — the backend does not rely on RLS alone, since the service-role key used server-side bypasses RLS by design

---

## Tech stack

- **Backend:** FastAPI (Python), port 8001
- **Frontend:** Next.js (App Router), Tailwind CSS
- **AI:** Google Gemini (Flash) for SQL generation and natural-language responses
- **ML:** scikit-learn (TF-IDF + Calibrated LinearSVC) for local intent classification; sentence-transformers for schema retrieval
- **SQL safety:** sqlglot (AST-based parsing across Postgres/MySQL dialects)
- **Auth:** Supabase Auth (Google OAuth), Row-Level Security + explicit backend filters
- **Databases supported:** PostgreSQL/Supabase, MySQL (via PyMySQL)
- **Security:** Fernet encryption for stored connection strings
- **Infra:** Docker Compose (local dev), Vercel (frontend), Render (backend)

---

## Running locally

```bash
git clone https://github.com/LokeshNehete119/Quera.git
cd Quera
docker-compose --env-file frontend/.env.local up --build
```

Backend runs on `http://localhost:8001`, frontend on `http://localhost:3000`. See `.env.example` files in `backend/` and `frontend/` for required environment variables (Gemini API key, Supabase project credentials, Fernet encryption key).

---

## Roadmap

- Low-privilege database role for the bot's own connections (defense-in-depth beyond application-level checks)
- Mobile responsiveness
- Handling for genuinely broad "show me everything" queries at the generation/UX level
- Custom domain (currently blocked by `vercel.app` being a shared domain, not required for OAuth's current non-sensitive scopes)