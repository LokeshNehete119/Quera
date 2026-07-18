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
import datetime
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import joblib
import pymysql
from urllib.parse import urlparse
import sqlglot
from sqlglot import exp

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from google import genai
from google.genai import types

from supabase import create_client, Client

load_dotenv()

SCHEMA_RETRIEVAL_THRESHOLD = 0.25
SCHEMA_RETRIEVAL_MIN_TABLES = 8
SCHEMA_RETRIEVAL_MARGIN = 0.30

SCHEMA_BROAD_INTENT_KEYWORDS = [
    "everything", 
    "all data", 
    "entire database", 
    "summarize", 
    "overview"
]

SCHEMA_DESCRIPTIONS = {
    "users_rich": "Stores registered customers including their names, emails, and signup information.",
    "products_rich": "Catalog of goods and items available for sale, containing names and prices.",
    "orders_rich": "Records of purchase transactions made by customers and when they occurred.",
    "order_items_rich": "Line items detailing the specific products and quantities purchased within a transaction.",
    "reviews_rich": "Customer feedback, ratings, and written comments left for specific goods.",
    "suppliers_rich": "External vendors and partners who provide or manufacture goods for the business.",
    "categories_rich": "Taxonomy and hierarchical classification used to organize the catalog of goods.",
    "warehouses_rich": "Physical storage sites, distribution centers, and facilities where inventory is kept.",
    "shipments_rich": "Logistics and tracking information for delivering orders to customers, including current delivery state."
}

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

# Global variable for the ML intent classifier
ml_classifier = None
schema_retrieval_model = None
schema_graphs_cache = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ml_classifier
    model_path = os.path.join(os.path.dirname(__file__), "ml", "classifier.joblib")
    try:
        ml_classifier = joblib.load(model_path)
        print(f"Successfully loaded ML classifier from {model_path}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load ML classifier from {model_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
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
                data_json JSONB,
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
            
            # Phase 12: Add data_json column for tabular data
            cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='messages' AND column_name='data_json') THEN
                    ALTER TABLE messages ADD COLUMN data_json JSONB;
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
# Enable CORS
allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_connection_ownership(conn_id: str, user_id: str, app_conn) -> None:
    if not conn_id:
        raise HTTPException(status_code=400, detail="Missing X-Connection-Id header")
    with app_conn.cursor() as cur:
        cur.execute("SELECT id FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Connection not found or access denied")
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

def get_active_db_connection_string(conn_id: str, user_id: str):
    app_conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, app_conn)
    
    with app_conn.cursor() as cur:
        cur.execute("SELECT encrypted_connection_string, db_type FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
        row = cur.fetchone()
    app_conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Selected database connection no longer exists.")
        
    return decrypt_conn(row[0]), row[1]

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

def save_message(conn, chat_id, role, content, sql=None, action_id=None, summary=None, is_destructive=None, data_json=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO messages (chat_id, role, content, sql, action_id, summary, is_destructive, data_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """, (chat_id, role, content, sql, action_id, summary, is_destructive, json.dumps(data_json) if data_json else None))
        msg_id = cur.fetchone()[0]
        cur.execute("UPDATE chats SET updated_at = NOW() WHERE id = %s", (chat_id,))
    conn.commit()
    return msg_id

def check_and_save_message(frontend_msg_id, conn, chat_id, role, content, sql=None, action_id=None, summary=None, is_destructive=None, data_json=None):
    if frontend_msg_id and frontend_msg_id in cancelled_messages:
        cancelled_messages.remove(frontend_msg_id)
        print(f"[AUDIT] Dropped saving response for cancelled frontend_msg_id: {frontend_msg_id}")
        return None
    return save_message(conn, chat_id, role, content, sql, action_id, summary, is_destructive, data_json)

def serialize_for_json(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Decimal':
        return float(obj)
    return obj

def cleanup_old_db(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS app_messages;")
            cur.execute("DROP TABLE IF EXISTS app_chats;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Note: Could not drop old app_ tables (might not exist or no permission): {e}")

def get_db_schema(conn, db_type: str) -> str:
    if db_type == "postgres":
        schema_query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """
    elif db_type == "mysql":
        schema_query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            ORDER BY table_name, ordinal_position;
        """
    else:
        return ""

    rows = []
    for _ in range(3):
        with conn.cursor() as cur:
            cur.execute(schema_query)
            rows = cur.fetchall()
        if rows:
            break
        time.sleep(0.5)
    
    tables = {}
    for row in rows:
        if isinstance(row, dict):
            t_name, c_name, d_type = list(row.values())
        else:
            t_name, c_name, d_type = row
            
        if t_name not in tables:
            tables[t_name] = []
        tables[t_name].append(f"{c_name} ({d_type})")
        
    schema_str = ""
    for table, columns in tables.items():
        schema_str += f"Table: {table}\nColumns: {', '.join(columns)}\n\n"
        
    return schema_str

def build_schema_graph(conn, db_type: str) -> dict:
    graph = {}
    
    if db_type == "postgres":
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
        fk_query = """
            SELECT
                tc.table_name,
                ccu.table_name AS foreign_table_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public';
        """
    elif db_type == "mysql":
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE';"
        fk_query = """
            SELECT
                TABLE_NAME,
                REFERENCED_TABLE_NAME
            FROM
                information_schema.KEY_COLUMN_USAGE
            WHERE
                REFERENCED_TABLE_NAME IS NOT NULL
                AND TABLE_SCHEMA = DATABASE();
        """
    else:
        return {}

    with conn.cursor() as cur:
        # Get all tables
        cur.execute(tables_query)
        tables = cur.fetchall()
        for row in tables:
            t_name = list(row.values())[0] if isinstance(row, dict) else row[0]
            graph[t_name] = set()

        # Get foreign keys
        cur.execute(fk_query)
        fks = cur.fetchall()
        for row in fks:
            if isinstance(row, dict):
                src = row['table_name'] if 'table_name' in row else row.get('TABLE_NAME')
                dst = row['foreign_table_name'] if 'foreign_table_name' in row else row.get('REFERENCED_TABLE_NAME')
            else:
                src, dst = row[0], row[1]
            
            if src in graph and dst in graph:
                graph[src].add(dst)
                graph[dst].add(src)
                
    return graph

def get_neighbor_tables(schema_graph: dict, table_names: set, hops: int = 1) -> set:
    if not schema_graph:
        return set()
        
    visited = set(table_names)
    current_frontier = set(table_names)
    
    for _ in range(hops):
        next_frontier = set()
        for node in current_frontier:
            if node in schema_graph:
                for neighbor in schema_graph[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
        current_frontier = next_frontier
        
    return visited

def get_relevant_schema(user_query: str, full_schema: str, schema_graph: dict, db_type: str) -> str:
    # Keyword pre-filter guard: if query indicates a broad intent, return full schema immediately
    query_lower = user_query.lower()
    if any(kw in query_lower for kw in SCHEMA_BROAD_INTENT_KEYWORDS):
        print(f"[SCHEMA RETRIEVAL] Fallback: Broad intent keyword detected in query. Returning full schema.")
        return full_schema
        
    # Parse full_schema
    tables_data = {}
    current_table = None
    for line in full_schema.split('\n'):
        line = line.strip()
        if line.startswith("Table: "):
            current_table = line[7:]
            tables_data[current_table] = {"name": current_table, "columns": "", "block": line + "\n"}
        elif line.startswith("Columns: ") and current_table:
            tables_data[current_table]["columns"] = line[9:]
            tables_data[current_table]["block"] += line + "\n\n"
            current_table = None
            
    # Fallback check 1: table count
    if len(tables_data) <= SCHEMA_RETRIEVAL_MIN_TABLES:
        print(f"[SCHEMA RETRIEVAL] Fallback: Total tables ({len(tables_data)}) <= {SCHEMA_RETRIEVAL_MIN_TABLES}. Returning full schema.")
        return full_schema
        
    # Build documents
    table_names = list(tables_data.keys())
    documents = []
    for t in table_names:
        desc = SCHEMA_DESCRIPTIONS.get(t, "")
        doc_str = f"{t} - {desc} - {tables_data[t]['columns']}"
        documents.append(doc_str)
    
    # Generate Embeddings
    global schema_retrieval_model
    if schema_retrieval_model is None:
        schema_retrieval_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    try:
        doc_embeddings = schema_retrieval_model.encode(documents)
        query_embedding = schema_retrieval_model.encode([user_query])
    except Exception as e:
        print(f"[SCHEMA RETRIEVAL] Fallback: Embeddings failed ({e}). Returning full schema.")
        return full_schema
        
    sims = cosine_similarity(query_embedding, doc_embeddings).flatten()
    
    seed_set = set()
    max_sim = max(sims) if len(sims) > 0 else 0
    if max_sim < SCHEMA_RETRIEVAL_THRESHOLD:
        print(f"[SCHEMA RETRIEVAL] Fallback: Top score {max_sim:.4f} < {SCHEMA_RETRIEVAL_THRESHOLD}. Returning full schema.")
        return full_schema
        
    # Known limitation: A table scoring just outside the relative margin from the top score 
    # may occasionally be dropped even when relevant (e.g. observed in eval case 15).
    # This is a deliberate, accepted scope boundary for small-schema vector similarity, 
    # not a bug to be fixed via further threshold tuning.
    margin_threshold = max_sim * (1.0 - SCHEMA_RETRIEVAL_MARGIN)
    for idx, sim in enumerate(sims):
        if sim >= margin_threshold:
            seed_set.add(table_names[idx])
            
    # Pad with neighbors
    final_tables = get_neighbor_tables(schema_graph, seed_set, hops=1)
    
    print(f"[SCHEMA RETRIEVAL] Activated: Seed set {seed_set} expanded to {final_tables}")
    
    # Rebuild schema string
    filtered_schema = ""
    for t in table_names:
        if t in final_tables:
            filtered_schema += tables_data[t]["block"]
            
    return filtered_schema

def is_safe_select_query(query: str, db_type: str = "postgres") -> bool:
    try:
        parsed = sqlglot.parse(query, read=db_type)
    except Exception:
        return False
        
    if len(parsed) != 1 or parsed[0] is None:
        return False
        
    stmt = parsed[0]
    if not isinstance(stmt, exp.Select):
        return False
        
    # Writable CTE / Nested Statement Check
    # Walk the tree and look for any destructive nodes, even if nested in CTEs
    destructive_nodes = list(stmt.find_all(
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.TruncateTable
    ))
    if destructive_nodes:
        return False
        
    return True

# Known limitation: tautological WHERE clauses (e.g. WHERE 1=1) are not detected as
# destructive, since this requires evaluating logical equivalence of arbitrary
# expressions, which is out of scope for this pass. WHERE-clause presence is
# checked syntactically, not semantically.
def is_highly_destructive(sql: str, db_type: str = "postgres") -> bool:
    try:
        parsed = sqlglot.parse(sql, read=db_type)
    except Exception:
        # Fail closed on parse errors
        return True
        
    # Multi-statement check: a generated write action should never be a stacked query
    if len(parsed) > 1:
        return True
        
    if not parsed or parsed[0] is None:
        return True
        
    stmt = parsed[0]
    
    if isinstance(stmt, (exp.Drop, exp.TruncateTable)):
        print(f"[SQL PARSER] AST type: {type(stmt).__name__}, Destructive: True")
        return True
        
    if isinstance(stmt, (exp.Delete, exp.Update)):
        if stmt.args.get("where") is None:
            print(f"[SQL PARSER] AST type: {type(stmt).__name__}, Destructive: True (no WHERE)")
            return True
            
    print(f"[SQL PARSER] AST type: {type(stmt).__name__}, Destructive: False")
    return False

@app.get("/health")
def health_check():
    return {"status": "ok"}

def detect_db_type(connection_string: str) -> str:
    if connection_string.startswith("postgres://") or connection_string.startswith("postgresql://"):
        return "postgres"
    if connection_string.startswith("mysql://") or connection_string.startswith("mysql+pymysql://"):
        return "mysql"
    raise ValueError("Unrecognized or unsupported connection string scheme.")

def get_db_connection(connection_string: str, db_type: str):
    if db_type == "postgres":
        return psycopg2.connect(connection_string)
    elif db_type == "mysql":
        parsed = urlparse(connection_string)
        port = parsed.port if parsed.port else 3306
        return pymysql.connect(
            host=parsed.hostname,
            port=port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            cursorclass=pymysql.cursors.DictCursor
        )
    else:
        raise ValueError("Unsupported database type")

@app.post("/db/test-connection")
def test_db_connection(req: ConnectionRequest, user_id: str = Depends(get_current_user)):
    try:
        db_type = detect_db_type(req.connection_string)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    try:
        conn = get_db_connection(req.connection_string, db_type)
        if db_type == "postgres":
            cleanup_old_db(conn) # Cleanup old internal tables from user DB
        conn.close()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

@app.get("/db/connections")
def list_db_connections(user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, name, db_type, created_at FROM db_connections WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        connections = cur.fetchall()
    conn.close()
    return connections

@app.post("/db/connections")
def create_db_connection(req: CreateDbConnectionReq, user_id: str = Depends(get_current_user)):
    try:
        db_type = detect_db_type(req.connection_string)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    try:
        # Test it first
        test_conn = get_db_connection(req.connection_string, db_type)
        if db_type == "postgres":
            cleanup_old_db(test_conn)
        test_conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")
        
    encrypted = encrypt_conn(req.connection_string)
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO db_connections (user_id, name, encrypted_connection_string, db_type) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, req.name, encrypted, db_type)
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    
    return {"id": new_id, "name": req.name}

@app.post("/db/connections/{conn_id}/select")
def select_db_connection(conn_id: str, user_id: str = Depends(get_current_user)):
    # Verify ownership implicitly through RLS and explicitly through WHERE clause
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
        row = cur.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    return {"success": True, "conn_id": conn_id}

@app.delete("/db/connections/{conn_id}")
def delete_db_connection(conn_id: str, user_id: str = Depends(get_current_user)):
    conn = get_app_db_conn_rls(user_id)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM db_connections WHERE id = %s AND user_id = %s", (conn_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/db/disconnect")
def disconnect_db():
    return {"success": True}

@app.get("/db/status")
def db_status(request: Request, user_id: str = Depends(get_current_user)):
    conn_id = request.headers.get("X-Connection-Id")
    if not conn_id:
        return {"connected": False}
        
    app_conn = get_app_db_conn_rls(user_id)
    try:
        verify_connection_ownership(conn_id, user_id, app_conn)
        return {"connected": True}
    except HTTPException:
        return {"connected": False}
    finally:
        app_conn.close()

# --- CHAT CRUD ENDPOINTS ---

@app.get("/chats")
def get_chats(request: Request, user_id: str = Depends(get_current_user)):
    conn_id = request.headers.get("X-Connection-Id")
    app_conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, app_conn)

    with app_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, title, created_at, updated_at FROM chats WHERE user_id = %s AND (db_connection_id = %s OR db_connection_id IS NULL) ORDER BY updated_at DESC", (user_id, conn_id))
        chats = cur.fetchall()
    app_conn.close()
    return chats

@app.post("/chats")
def create_chat(req: CreateChatReq, request: Request, user_id: str = Depends(get_current_user)):
    conn_id = request.headers.get("X-Connection-Id")
    conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, conn)

    with conn.cursor() as cur:
        cur.execute("INSERT INTO chats (title, user_id, db_connection_id) VALUES (%s, %s, %s) RETURNING id", (req.title, user_id, conn_id))
        chat_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": chat_id, "title": req.title}

@app.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str, request: Request, user_id: str = Depends(get_current_user)):
    conn_id = request.headers.get("X-Connection-Id")
    conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, conn)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT m.id, m.role, m.content, m.sql, m.action_id, m.summary, m.is_destructive, m.data_json, m.created_at 
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
    conn_id = request.headers.get("X-Connection-Id")
    app_conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, app_conn)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")

    conn_string, db_type = get_active_db_connection_string(conn_id, user_id)
    user_conn = get_db_connection(conn_string, db_type)
    
    chat_id = req.chat_id
    if not chat_id:
        with app_conn.cursor() as cur:
            cur.execute("INSERT INTO chats (title, user_id, db_connection_id) VALUES ('New Chat', %s, %s) RETURNING id", (user_id, conn_id))
            chat_id = cur.fetchone()[0]
        app_conn.commit()
    else:
        # Verify ownership of the requested chat and its association with the active connection
        with app_conn.cursor() as cur:
            cur.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s AND (db_connection_id = %s OR db_connection_id IS NULL)", (chat_id, user_id, conn_id))
            if not cur.fetchone():
                app_conn.close()
                user_conn.close()
                raise HTTPException(status_code=403, detail="Not authorized for this chat or it belongs to a different database")
        
    save_message(app_conn, chat_id, 'user', req.message)

    try:
        client = genai.Client(api_key=api_key)
        
        # Local ML Classification
        t0 = time.time()
        predicted_labels = ml_classifier.predict([req.message])
        category = predicted_labels[0]
        t1 = time.time()
        
        print(f"[TIMING] Local ML Classification took {t1 - t0:.4f} seconds")
        print(f"[INTENT CLASSIFIER] Message: '{req.message}' -> Predicted Category: {category} (Source: Local ML)")
        
        if category == "casual":
            casual_prompt = f"The user said: {req.message}\nProvide a friendly, conversational reply as an AI assistant."
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=casual_prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            reply = response.text.strip()
            chat_res = {"category": "casual", "reply": reply, "chat_id": chat_id}
            
            check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply)
            app_conn.close()
            user_conn.close()
            return chat_res
            
        full_schema_str = get_db_schema(user_conn, db_type)
        
        global schema_graphs_cache
        if conn_id not in schema_graphs_cache:
            schema_graphs_cache[conn_id] = build_schema_graph(user_conn, db_type)
            print(f"[SCHEMA CACHE] Built and cached schema graph for connection {conn_id}")
            
        schema_graph = schema_graphs_cache[conn_id]
        schema_str = get_relevant_schema(req.message, full_schema_str, schema_graph, db_type)
            
        if category == "read":
            if db_type == "postgres":
                sql_instruct = f"""You are an expert SQL generator for a PostgreSQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
You may query the tables listed in the schema, or standard PostgreSQL system catalogs (like information_schema) if the user asks metadata questions about the database itself.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""
            elif db_type == "mysql":
                sql_instruct = f"""You are an expert SQL generator for a MySQL database.
Here is the database schema:
{schema_str}

Generate a single valid SELECT query that answers the user's question. 
CRITICAL MYSQL RULES:
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
If the question is completely unrelated to databases or the schema, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;"""
            
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
                
            if not is_safe_select_query(raw_sql, db_type):
                reply = "Security Error: The generated query contained unsafe keywords or attempted to modify data. Only SELECT is allowed."
                check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply, sql=raw_sql)
                app_conn.close()
                user_conn.close()
                return {"category": "read", "reply": reply, "sql": raw_sql, "chat_id": chat_id}
                
            with user_conn.cursor() as cur:
                cur.execute(raw_sql)
                results = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
            
            data_json = None
            if len(results) > 1 or len(columns) > 1:
                truncated = len(results) > 50
                results_for_data = results[:50]
                
                serialized_rows = []
                for row in results_for_data:
                    # Safely handle both standard tuples (psycopg2 default) and dictionaries (pymysql DictCursor)
                    if isinstance(row, dict):
                        serialized_rows.append([serialize_for_json(val) for val in row.values()])
                    else:
                        serialized_rows.append([serialize_for_json(val) for val in row])
                
                data_json = {
                    "columns": columns,
                    "rows": serialized_rows,
                    "truncated": truncated
                }
            
            if len(results) > 100:
                 results = results[:100]
                 results.append("... (results truncated to 100 rows)")
                 
            nl_instruct = """You are an AI database assistant. You just ran a SQL query to answer the user's question.
Given the original question, the executed SQL, the column names, and the raw results, provide a clear, concise, natural-language answer to the user. Do not explain the SQL, just answer the question.
CRITICAL: If the results contain multiple rows, do NOT generate a markdown table or list them out. The application will render a data table separately. Instead, just provide a short single-sentence summary like 'I found X matching records.' or 'Here are the results you requested.' For single-value results (like COUNT or SUM), answer naturally in a sentence."""
            
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
            check_and_save_message(req.frontend_msg_id, app_conn, chat_id, 'ai', reply, sql=raw_sql, data_json=data_json)
            app_conn.close()
            user_conn.close()
            return {"category": "read", "reply": reply, "sql": raw_sql, "chat_id": chat_id, "data_json": data_json}

        elif category == "write":
            if db_type == "postgres":
                sql_instruct = f"""You are an expert SQL generator for PostgreSQL.
Here is the database schema:
{schema_str}

Generate a single valid SQL query that performs the write/schema-change the user requested. Also provide a plain-language, one-line summary of what this SQL will do.
If the question is impossible to answer from this schema and doesn't relate to standard database operations, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;
"""
            elif db_type == "mysql":
                sql_instruct = f"""You are an expert SQL generator for MySQL.
Here is the database schema:
{schema_str}

Generate a single valid SQL query that performs the write/schema-change the user requested. Also provide a plain-language, one-line summary of what this SQL will do.
CRITICAL MYSQL RULES:
- Use AUTO_INCREMENT for primary keys, NOT SERIAL.
- Quote string literals with single quotes ('). Do not use double quotes.
- Quote identifiers (tables/columns) with backticks (`), NOT double quotes.
- Do not use PostgreSQL-specific syntax or functions.
If the question is impossible to answer from this schema and doesn't relate to standard database operations, generate exactly: SELECT 'IMPOSSIBLE' AS STATUS;
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
                
            is_destructive = is_highly_destructive(raw_sql, db_type)
            action_id = str(uuid.uuid4())
            
            pending_actions[action_id] = {
                "conn_id": conn_id,
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
        app_conn.close()
        user_conn.close()
        raise HTTPException(status_code=500, detail="An error occurred while executing the query or contacting the AI API.")

@app.post("/chat/approve-action")
def approve_action(req: ActionDecisionRequest, request: Request, user_id: str = Depends(get_current_user)):
    conn_id = request.headers.get("X-Connection-Id")
    app_conn = get_app_db_conn_rls(user_id)
    verify_connection_ownership(conn_id, user_id, app_conn)
        
    if req.action_id not in pending_actions:
        app_conn.close()
        raise HTTPException(status_code=404, detail="Pending action not found or expired.")
        
    action = pending_actions[req.action_id]
    
    if action["conn_id"] != conn_id:
        app_conn.close()
        raise HTTPException(status_code=403, detail="Connection mismatch for this action.")
        
    if req.decision == "reject":
        del pending_actions[req.action_id]
        save_message(app_conn, action["chat_id"], 'system', "🚫 Action cancelled successfully.")
        app_conn.close()
        return {"status": "cancelled", "reply": "Action cancelled successfully."}
        
    if req.decision == "approve":
        if action["is_destructive"]:
            if not req.confirm_text or req.confirm_text.strip() != "CONFIRM":
                app_conn.close()
                raise HTTPException(status_code=400, detail="This action is highly destructive. You must type exactly 'CONFIRM' (case-sensitive).")
                
        conn_string, db_type = get_active_db_connection_string(conn_id, user_id)
        user_conn = get_db_connection(conn_string, db_type)
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
