# Quera - AI Database Assistant

**Talk to your database in plain English — safely.**

Quera is a full-stack AI chatbot that connects to your PostgreSQL/Supabase or MySQL database and allows you to query, update, and modify it through natural conversation. It features a custom local ML intent classifier, semantic schema retrieval, and robust AST-based SQL safety validation to ensure that no destructive action touches your data without explicit human approval.

**Live App:** [https://quera-nine.vercel.app](https://quera-nine.vercel.app) | **Repository:** [GitHub](https://github.com/LokeshNehete119/Quera)

![Next.js](https://img.shields.io/badge/Next.js-black?style=for-the-badge&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-005C84?style=for-the-badge&logo=mysql&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)

---

## 🚀 Key Engineering Achievements

Unlike standard "wrapper" AI apps, Quera is engineered with performance, safety, and efficiency at its core:

* **Local ML Intent Classification:** Replaced slow and expensive LLM calls for intent detection with a local `scikit-learn` pipeline (TF-IDF + Calibrated LinearSVC). Achieved **94.74% accuracy** and <20ms latency on production data, eliminating the need for an LLM fallback.
* **AST-Based SQL Safety Validation:** Replaced fragile Regex rules with full Abstract Syntax Tree (AST) parsing using `sqlglot`. The backend traverses the entire query tree to detect destructive operations (e.g., hidden `DELETE` inside a CTE or stacked queries) before execution.
* **Semantic Schema Retrieval (RAG):** Implemented `sentence-transformers` to rank and inject only relevant database tables into the LLM prompt. Reduced the context payload sent to the LLM by an average of **58.5%**, significantly reducing costs and improving LLM focus.
* **Human-in-the-Loop Execution:** Built a robust permission system where read queries execute automatically, but any write/destructive DDL actions are paused, presented to the user for review, and require explicit confirmation (e.g., typing "CONFIRM" for `DROP` operations).
* **Multi-Database Support:** Dynamically handles dialect-specific schema introspection and AST validation across PostgreSQL and MySQL databases.
* **Secure Architecture:** Database connection strings are encrypted at rest using `Fernet` symmetric encryption. Strict Row-Level Security (RLS) and ownership checks prevent IDOR attacks.

---

## 🏗️ Architecture

```text
User (Browser)
      │
      ▼
Next.js Frontend (Vercel)
      │  Google OAuth via Supabase Auth
      ▼
FastAPI Backend (Render)
      │
      ├─ Local ML Classifier (Casual / Read / Write intent)
      ├─ Schema Retrieval (Embeddings + FK Graph filtering)
      ├─ Gemini 3.5 Flash (SQL Generation & NL Responses)
      ├─ SQLGlot AST Validation (Safety checks)
      └─ Human-in-the-Loop Approval Queue
      │
      ▼
User's External Database (PostgreSQL / MySQL)
```

---

## 🛠️ Tech Stack

* **Frontend:** Next.js (App Router), React, Tailwind CSS
* **Backend:** FastAPI (Python), Uvicorn
* **AI / ML:** Google Gemini 3.5 Flash, `scikit-learn`, `sentence-transformers`
* **Database & Auth:** Supabase (PostgreSQL), PyMySQL, Google OAuth
* **Infrastructure:** Docker Compose, Vercel, Render

---

## 💻 Running Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/LokeshNehete119/Quera.git
   cd Quera
   ```

2. **Set up environment variables:**
   Review `.env.example` in both the `backend/` and `frontend/` directories and create your local `.env` files (requires Gemini API key, Supabase credentials, and a Fernet key).

3. **Run with Docker Compose:**
   ```bash
   docker-compose --env-file frontend/.env.local up --build
   ```

4. **Access the application:**
   * Frontend: `http://localhost:3000`
   * Backend API: `http://localhost:8001`

---

## 🗺️ Roadmap
* Implement role-based database connections with lower privileges for the AI agent.
* Optimize mobile responsiveness across the entire UI.
* Handle genuinely broad "show me everything" queries via pagination or aggregations.