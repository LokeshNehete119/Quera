# Quera Project (Phase 0 Scaffold)

This repository contains the scaffold for a full-stack Quera application.

## Folder Structure

- `backend/`: FastAPI Python application.
- `frontend/`: Next.js frontend application (App Router) with Tailwind CSS.

## Getting Started

### 1. Backend (FastAPI)

Prerequisites: Python 3.8+

```bash
# Navigate to the backend folder
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the development server
uvicorn main:app --reload --port 8001
```
The backend will be running at `http://localhost:8001`.

**Endpoints to test:**
- `curl http://localhost:8001/health`
- `curl -X POST http://localhost:8001/db/test-connection -H "Content-Type: application/json" -d '{"connection_string": "your_test_postgres_url"}'` (Note: for Windows Command Prompt, escape the inner quotes: `-d "{\"connection_string\": \"your_test_postgres_url\"}"`)

### 2. Frontend (Next.js)

Prerequisites: Node.js 18+

```bash
# Navigate to the frontend folder
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```
The frontend will be running at `http://localhost:3000`.

---

## 🚀 Running with Docker (Recommended)

You can run the entire application (both frontend and backend) simultaneously with a single command using Docker Compose. This automatically builds a production-ready Next.js bundle and a containerized Python backend.

**Prerequisites:** Docker and Docker Compose installed and running.

```bash
# Navigate to the project root directory
cd quera

# Start the application in detached mode, safely passing the build args from your env file
docker-compose --env-file frontend/.env.local up --build -d
```

### Useful Docker Commands:
- **Stop the containers:** `docker-compose down`
- **View backend logs:** `docker-compose logs -f backend`
- **View frontend logs:** `docker-compose logs -f frontend`
- **Rebuild after making code changes:** `docker-compose --env-file frontend/.env.local up --build -d`

*Note: The traditional two-terminal manual workflow (running `uvicorn` and `npm run dev` separately) is still fully supported if you prefer hot-reloading for rapid UI development.*
