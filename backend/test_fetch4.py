from dotenv import load_dotenv
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi.encoders import jsonable_encoder
import json
load_dotenv()

def get_app_db_conn_rls(user_id: str):
    conn = psycopg2.connect(os.environ.get("APP_DB_URL"))
    with conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE authenticated;")
        claim_json = json.dumps({"sub": user_id, "role": "authenticated"})
        cur.execute("SET LOCAL request.jwt.claims = %s;", (claim_json,))
    return conn

user_id = '60a9761a-f96f-4fe1-b1f9-8fb5aa82e23e'
conn = get_app_db_conn_rls(user_id)
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("SELECT id, name, created_at FROM db_connections WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    connections = cur.fetchall()
    
    try:
        print("jsonable:", jsonable_encoder(connections))
    except Exception as e:
        print("ERROR:", str(e))
conn.close()
