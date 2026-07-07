from dotenv import load_dotenv
import os
import psycopg2
import json
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
with conn.cursor() as cur:
    cur.execute("SET LOCAL ROLE authenticated;")
    # use the real user_id from the DB dump
    claim_json = json.dumps({"sub": '60a9761a-f96f-4fe1-b1f9-8fb5aa82e23e', "role": "authenticated"})
    cur.execute("SET LOCAL request.jwt.claims = %s;", (claim_json,))
    
    cur.execute("SELECT id, user_id FROM db_connections;")
    print("Rows visible to real user 1:", len(cur.fetchall()))
    
    cur.execute("SET LOCAL ROLE postgres;")
    cur.execute("SELECT id, user_id FROM db_connections;")
    print("Rows visible to postgres:", len(cur.fetchall()))
