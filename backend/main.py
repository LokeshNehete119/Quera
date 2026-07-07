from fastapi import FastAPI, HTTPException, Response, Request, Cookie, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import os
import json
import re
import time
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from cryptography.fernet import Fernet

from google import genai
from google.genai import types

from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "https://yupxousqgvyrqndgcqys.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "sb_publishable_C-CTdBX1IoTjmQFZ2-rxEA_G6D8sQPe")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

ENCRYPTION_KEY = os.environ.get("CONNECTION_STRING_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    print("CRITICAL ERROR: CONNECTION_STRING_ENCRYPTION_KEY is missing.", file=sys.stderr)
    sys.exit(1)
cipher_suite = Fernet(ENCRYPTION_KEY.encode('utf-8'))

def encrypt_conn(conn_str: str) -> str:
    return cipher_suite.encrypt(conn_str.encode('utf-8')).decode('utf-8')

def decrypt_conn(enc_str: str) -> str:
    return cipher_suite.decrypt(enc_str.encode('utf-8')).decode('utf-8')

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_db_url = os.environ.get("APP_DB_URL")
    if not app_db_url:
        print("CRITICAL ERROR: APP_DB_URL environment variable is missing. Failed to start.", file=sys.stderr)
        sys.exit(1)
        
    try:
        conn = psycopg2.connect(app_db_url)
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'ai', 'system')),
                content TEXT NOT NULL,
                sql TEXT,
                action_id TEXT,
                summary TEXT,
                is_destructive BOOLEAN,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """)
            
            # Auth & RLS Phase 8 setup
            # Ensure user_id column exists
            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chats' AND column_name='user_id') THEN
                    TRUNCATE chats CASCADE;
                    ALTER TABLE chats ADD COLUMN user_id UUID NOT NULL;
                END IF;
            END
            $$;
            """)
            
            # Phase 10: Persist db_connections
            cur.execute("""
            CREATE TABLE IF NOT EXISTS db_connections (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                name TEXT NOT NULL,
                encrypted_connection_string TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """)
            
            cur.execute("""
            ALTER TABLE chats ADD COLUMN IF NOT EXISTS db_connection_id UUID REFERENCES db_connections(id) ON DELETE CASCADE;
            """)
            
            cur.execute("ALTER TABLE chats ENABLE ROW LEVEL SECURITY;")
            cur.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;")
            cur.execute("ALTER TABLE db_connections ENABLE ROW LEVEL SECURITY;")
            
            cur.execute("""
            DROP POLICY IF EXISTS "Users manage own chats" ON chats;
            CREATE POLICY "Users manage own chats" ON chats
                FOR ALL
                USING (user_id = auth.uid())
                WITH CHECK (user_id = auth.uid());
                
            DROP POLICY IF EXISTS "Users manage own messages" ON messages;
            CREATE POLICY "Users manage own messages" ON messages
                FOR ALL
                USING (EXISTS (SELECT 1 FROM chats WHERE chats.id = messages.chat_id AND chats.user_id = auth.uid()))
                WITH CHECK (EXISTS (SELECT 1 FROM chats WHERE chats.id = messages.chat_id AND chats.user_id = auth.uid()));
                
            DROP POLICY IF EXISTS "Users manage own db connections" ON db_connections;
            CREATE POLICY "Users manage own db connections" ON db_connections
                FOR ALL
                USING (user_id = auth.uid())
                WITH CHECK (user_id = auth.uid());
            """)
            
        conn.commit()
        conn.close()
        print("Connected to APP_DB_URL and verified internal tables with RLS.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect or initialize APP_DB_URL: {e}", file=sys.stderr)
        sys.exit(1)
        
    yield
app = FastAPI(
    lifespan=lifespan,
    title="Quera API",
    description="Quera backend API"
)
# Enable CORS for the frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory dictionary to store session_id -> db_connection_id
sessions: dict[str, str] = {}
# In-memory dictionary to store pending write actions
pending_actions: dict[str, dict] = {}
# In-memory set of cancelled frontend message IDs
cancelled_messages: set[str] = set()

def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        user_res = supabase_client.auth.get_user(token)
        if not user_res or not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_res.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

def get_app_db_conn_rls(user_id: str):
    conn = psycopg2.connect(os.environ.get("APP_DB_URL"))
    with conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE authenticated;")
        claim_json = json.dumps({"sub": user_id, "role": "authenticated"})
        cur.execute("SET LOCAL request.jwt.claims = %s;", (claim_json,))
    return conn

def get_active_db_connection_string(session_id: str, user_id: str) -> str:
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required. Please reconnect.")
        
    conn_id = sessions[session_id]
    app_conn = get_app_db_conn_rls(user_id)
    with app_conn.cursor() as cur:
        cur.execute("SELECT encrypted_connection_string FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
        row = cur.fetchone()
    app_conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Selected database connection no longer exists.")
        
    return decrypt_conn(row[0])

class ConnectionRequest(BaseModel):
    connection_string: str

class ChatMessageRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    frontend_msg_id: Optional[str] = None

class ChatResponse(BaseModel):
    category: str
    reply: str
    sql: Optional[str] = None
    action_id: Optional[str] = None
    summary: Optional[str] = None
    is_destructive: Optional[bool] = None
    chat_id: Optional[str] = None

class SqlResponse(BaseModel):
    sql: str

class WriteSqlResponse(BaseModel):
    sql: str
    summary: str

class ActionDecisionRequest(BaseModel):
    action_id: str
    decision: str
    confirm_text: Optional[str] = None

class CreateChatReq(BaseModel):
    title: str = "New Chat"

class ChatUpdate(BaseModel):
    title: str

class CancelRequest(BaseModel):
    message_id: str

class CreateDbConnectionReq(BaseModel):
    name: str
    connection_string: str

@app.post("/chat/cancel")
def cancel_chat(req: CancelRequest, user_id: str = Depends(get_current_user)):
    cancelled_messages.add(req.message_id)
    return {"success": True}

def save_message(conn, chat_id, role, content, sql=None, action_id=None, summary=None, is_destructive=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO messages (chat_id, role, content, sql, action_id, summary, is_destructive)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (chat_id, role, content, sql, action_id, summary, is_destructive))
        msg_id = cur.fetchone()[0]
        cur.execute("UPDATE chats SET updated_at = NOW() WHERE id = %s", (chat_id,))
    conn.commit()
    return msg_id

def check_and_save_message(frontend_msg_id, conn, chat_id, role, content, sql=None, action_id=None, summary=None, is_destructive=None):
    if frontend_msg_id and frontend_msg_id in cancelled_messages:
        cancelled_messages.remove(frontend_msg_id)
        print(f"[AUDIT] Dropped saving response for cancelled frontend_msg_id: {frontend_msg_id}")
        return None
    return save_message(conn, chat_id, role, content, sql, action_id, summary, is_destructive)

def cleanup_old_db(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS app_messages;")
            cur.execute("DROP TABLE IF EXISTS app_chats;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Note: Could not drop old app_ tables (might not exist or no permission): {e}")

def get_db_schema(conn) -> str:
    schema_query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    with conn.cursor() as cur:
        cur.execute(schema_query)
        rows = cur.fetchall()
    
    tables = {}
    for table_name, column_name, data_type in rows:
        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].append(f"{column_name} ({data_type})")
        
    schema_str = ""
    for table, columns in tables.items():
        schema_str += f"Table: {table}\nColumns: {', '.join(columns)}\n\n"
        
    return schema_str

def is_safe_select_query(query: str) -> bool:
    if not query.strip().upper().startswith("SELECT"):
        return False
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", 
        "TRUNCATE", "CREATE", "GRANT", "REVOKE", "EXECUTE",
        "COMMIT", "ROLLBACK", "MERGE", "REPLACE"
    ]
    for kw in dangerous_keywords:
        if re.search(rf'\b{kw}\b', query, re.IGNORECASE):
            return False
    return True

def is_highly_destructive(sql: str) -> bool:
    upper_sql = sql.upper()
    if "DROP TABLE" in upper_sql or "TRUNCATE" in upper_sql:
        return True
    if "DELETE FROM" in upper_sql and "WHERE" not in upper_sql:
        return True
    return False

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/db/test-connection")
def test_db_connection(req: ConnectionRequest, user_id: str = Depends(get_current_user)):
    try:
        conn = psycopg2.connect(req.connection_string)
        cleanup_old_db(conn) # Cleanup old internal tables from user DB
        conn.close()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

@app.get("/db/connections")
def list_db_connections(user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, name, created_at FROM db_connections WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        connections = cur.fetchall()
    conn.close()
    return connections

@app.post("/db/connections")
def create_db_connection(req: CreateDbConnectionReq, user_id: str = Depends(get_current_user)):
    try:
        # Test it first
        test_conn = psycopg2.connect(req.connection_string)
        cleanup_old_db(test_conn)
        test_conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")
        
    encrypted = encrypt_conn(req.connection_string)
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO db_connections (user_id, name, encrypted_connection_string) VALUES (%s, %s, %s) RETURNING id",
            (user_id, req.name, encrypted)
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    
    return {"id": new_id, "name": req.name}

@app.post("/db/connections/{conn_id}/select")
def select_db_connection(conn_id: str, response: Response, user_id: str = Depends(get_current_user)):
    # Verify ownership implicitly through RLS and explicitly through WHERE clause
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
        row = cur.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    session_id = str(uuid.uuid4())
    sessions[session_id] = conn_id
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400  # 1 day
    )
    return {"success": True}

@app.delete("/db/connections/{conn_id}")
def delete_db_connection(conn_id: str, user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/db/disconnect")
def disconnect_db(response: Response):
    response.delete_cookie("session_id")
    return {"success": True}

@app.get("/db/status")
def db_status(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return {"connected": True}
    return {"connected": False}

# --- CHAT CRUD ENDPOINTS ---

@app.get("/chats")
def get_chats(request: Request, user_id: str = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required")
    conn_id = sessions[session_id]

    conn = get_app_db_conn_rls(user_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, title, created_at, updated_at FROM chats WHERE user_id = %s AND (db_connection_id = %s OR db_connection_id IS NULL) ORDER BY updated_at DESC", (user_id, conn_id))
        chats = cur.fetchall()
    conn.close()
    return chats

@app.post("/chats")
def create_chat(req: CreateChatReq, request: Request, user_id: str = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required")
    conn_id = sessions[session_id]

    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO chats (title, user_id, db_connection_id) VALUES (%s, %s, %s) RETURNING id", (req.title, user_id, conn_id))
        chat_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": chat_id, "title": req.title}

@app.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str, request: Request, user_id: str = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required")
    conn_id = sessions[session_id]

    conn = get_app_db_conn_rls(user_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT m.id, m.role, m.content, m.sql, m.action_id, m.summary, m.is_destructive, m.created_at 
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.chat_id = %s AND c.user_id = %s AND (c.db_connection_id = %s OR c.db_connection_id IS NULL)
            ORDER BY m.created_at ASC
        """, (chat_id, user_id, conn_id))
        messages = cur.fetchall()
    conn.close()
    return messages

@app.patch("/chats/{chat_id}")
def update_chat(chat_id: str, req: ChatUpdate, user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("UPDATE chats SET title = %s, updated_at = NOW() WHERE id = %s AND user_id = %s", (req.title, chat_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chats WHERE id = %s AND user_id = %s", (chat_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

# --- END CHAT CRUD ENDPOINTS ---

@app.post("/chat")
def chat_endpoint(req: ChatMessageRequest, request: Request, user_id: str = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required. Please reconnect.")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")

    app_conn = get_app_db_conn_rls(user_id)
    
    conn_string = get_active_db_connection_string(session_id, user_id)
    user_conn = psycopg2.connect(conn_string)
    
    chat_id = req.chat_id
    if not chat_id:
        conn_id = sessions[session_id]
        with app_conn.cursor() as cur:
            cur.execute("INSERT INTO chats (title, user_id, db_connection_id) VALUES ('New Chat', %s, %s) RETURNING id", (user_id, conn_id))
            chat_id = cur.fetchone()[0]
        app_conn.commit()
    else:
        # Verify ownership of the requested chat and its association with the active connection
        conn_id = sessions[session_id]
        with app_conn.cursor() as cur:
            cur.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s AND (db_connection_id = %s OR db_connection_id IS NULL)", (chat_id, user_id, conn_id))
            if not cur.fetchone():
                app_conn.close()
                user_conn.close()
                raise HTTPException(status_code=403, detail="Not authorized for this chat or it belongs to a different database")
        
    save_message(app_conn, chat_id, 'user', req.message)

    try:
        client = genai.Client(api_key=api_key)
        
        sys_instruct = """You are an AI database assistant. Classify the user's intent into exactly one of three categories: 'casual', 'read', or 'write'.
- 'casual': greetings, small talk, general questions not about the database. For this, provide a natural response in 'reply'.
- 'read': asking to view, count, query, or select existing data. For this, return exactly '[Detected: READ request]' as 'reply'.
- 'write': asking to create, alter, drop tables, or insert, update, delete data. For this, return exactly '[Detected: WRITE request]' as 'reply'."""

        t0 = time.time()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=req.message,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ChatResponse,
                system_instruction=sys_instruct,
                temperature=0.0
            ),
        )
        t1 = time.time()
        print(f"[TIMING] Gemini API call (Classification) took {t1 - t0:.2f} seconds")
        
        chat_res = json.loads(response.text)
        category = chat_res.get("category")
        
        if category == "casual":
            check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', chat_res.get("reply", ""))
            chat_res["chat_id"] = chat_id
            app_conn.close()
            user_conn.close()
            return chat_res
            
        schema_str = get_db_schema(user_conn)
            
        if category == "read":
            sql_instruct = f"""You are an expert SQL generator for a PostgreSQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
If the question is completely unrelated to the schema or asks for columns/tables that do not exist, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""
            
            t0 = time.time()
            sql_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=req.message,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SqlResponse,
                    system_instruction=sql_instruct,
                    temperature=0.0
                ),
            )
            t1 = time.time()
            print(f"[TIMING] Gemini API call (SQL Read Generation) took {t1 - t0:.2f} seconds")
            
            sql_data = json.loads(sql_response.text)
            raw_sql = sql_data.get("sql", "")
            
            if raw_sql.strip().upper() == "SELECT 'IMPOSSIBLE' AS STATUS;":
                reply = "I couldn't find a table or column matching your request in the database schema."
                check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply)
                app_conn.close()
                user_conn.close()
                return {"category": "read", "reply": reply, "sql": None, "chat_id": chat_id}
                
            if not is_safe_select_query(raw_sql):
                reply = "Security Error: The generated query contained unsafe keywords or attempted to modify data. Only SELECT is allowed."
                check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply, sql=raw_sql)
                app_conn.close()
                user_conn.close()
                return {"category": "read", "reply": reply, "sql": raw_sql, "chat_id": chat_id}
                
            with user_conn.cursor() as cur:
                cur.execute(raw_sql)
                results = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
            
            if len(results) > 100:
                 results = results[:100]
                 results.append("... (results truncated to 100 rows)")
                 
            nl_instruct = """You are an AI database assistant. You just ran a SQL query to answer the user's question.
Given the original question, the executed SQL, the column names, and the raw results, provide a clear, concise, natural-language answer to the user. Do not explain the SQL, just answer the question."""
            
            nl_prompt = f"User Question: {req.message}\nSQL Query: {raw_sql}\nColumns: {columns}\nResults: {results}"
            t0 = time.time()
            nl_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=nl_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=nl_instruct,
                    temperature=0.0
                ),
            )
            t1 = time.time()
            print(f"[TIMING] Gemini API call (Read NL formatting) took {t1 - t0:.2f} seconds")
            
            reply = nl_response.text.strip()
            check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply, sql=raw_sql)
            app_conn.close()
            user_conn.close()
            return {"category": "read", "reply": reply, "sql": raw_sql, "chat_id": chat_id}

        elif category == "write":
            sql_instruct = f"""You are an expert SQL generator for PostgreSQL.
Here is the database schema:
{schema_str}

Generate a single valid SQL query that performs the write/schema-change the user requested. Also provide a plain-language, one-line summary of what this SQL will do.
If the question is impossible to answer from this schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;
"""
            t0 = time.time()
            sql_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=req.message,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=WriteSqlResponse,
                    system_instruction=sql_instruct,
                    temperature=0.0
                ),
            )
            t1 = time.time()
            print(f"[TIMING] Gemini API call (SQL Write Generation) took {t1 - t0:.2f} seconds")
            
            sql_data = json.loads(sql_response.text)
            raw_sql = sql_data.get("sql", "")
            summary = sql_data.get("summary", "")
            
            if raw_sql.strip().upper() == "SELECT 'IMPOSSIBLE' AS STATUS;":
                reply = "I couldn't determine how to perform that operation based on the database schema."
                check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply)
                app_conn.close()
                user_conn.close()
                return {"category": "write", "reply": reply, "chat_id": chat_id}
                
            is_destructive = is_highly_destructive(raw_sql)
            action_id = str(uuid.uuid4())
            
            pending_actions[action_id] = {
                "session_id": session_id,
                "sql": raw_sql,
                "summary": summary,
                "is_destructive": is_destructive,
                "created_at": time.time(),
                "chat_id": chat_id
            }
            
            reply = "I've prepared the query for your approval."
            check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply, sql=raw_sql, action_id=action_id, summary=summary, is_destructive=is_destructive)
            app_conn.close()
            user_conn.close()
            return {
                "category": "write",
                "reply": reply,
                "sql": raw_sql,
                "action_id": action_id,
                "summary": summary,
                "is_destructive": is_destructive,
                "chat_id": chat_id
            }

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        sql_to_return = locals().get("raw_sql", None)
        reply = "An error occurred while executing the query or contacting the AI API."
        check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'system', reply, sql=sql_to_return)
        app_conn.close()
        user_conn.close()
        return {
             "category": chat_res.get("category", "unknown") if 'chat_res' in locals() else "unknown",
             "reply": reply,
             "sql": sql_to_return,
             "chat_id": chat_id
        }

@app.post("/chat/approve-action")
def approve_action(req: ActionDecisionRequest, request: Request, user_id: str = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Active database session required.")
        
    if req.action_id not in pending_actions:
        raise HTTPException(status_code=404, detail="Pending action not found or expired.")
        
    action = pending_actions[req.action_id]
    
    if action["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")
        
    if req.decision == "reject":
        del pending_actions[req.action_id]
        app_conn = get_app_db_conn_rls(user_id)
        save_message(app_conn, action["chat_id"], 'system', "🚫 Action cancelled successfully.")
        app_conn.close()
        return {"status": "cancelled", "reply": "Action cancelled successfully."}
        
    if req.decision == "approve":
        if action["is_destructive"]:
            if not req.confirm_text or req.confirm_text.strip() != "CONFIRM":
                raise HTTPException(status_code=400, detail="This action is highly destructive. You must type exactly 'CONFIRM' (case-sensitive).")
                
        conn_string = get_active_db_connection_string(session_id, user_id)
        user_conn = psycopg2.connect(conn_string)
        try:
            with user_conn.cursor() as cur:
                cur.execute(action["sql"])
            user_conn.commit()
            
            print(f"[AUDIT - {time.ctime()}] Executed write SQL: {action['sql']}")
            
            app_conn = get_app_db_conn_rls(user_id)
            save_message(app_conn, action["chat_id"], 'system', "✅ Action executed successfully.")
            app_conn.close()
            user_conn.close()
            
            del pending_actions[req.action_id]
            return {"status": "success", "reply": "Action executed successfully."}
            
        except Exception as e:
            app_conn = get_app_db_conn_rls(user_id)
            save_message(app_conn, action["chat_id"], 'system', f"Error: Database error: {str(e)}")
            app_conn.close()
            user_conn.close()
            return {"status": "error", "reply": f"Database error: {str(e)}"}
            
    raise HTTPException(status_code=400, detail="Invalid decision.")
