from dotenv import load_dotenv
import os
import psycopg2
import json
load_dotenv()
conn = psycopg2.connect(os.environ.get('APP_DB_URL'))
with conn.cursor() as cur:
    cur.execute("SET LOCAL ROLE authenticated;")
    claim_json = json.dumps({"sub": '11111111-1111-1111-1111-111111111111', "role": "authenticated"})
    cur.execute("SET LOCAL request.jwt.claims = %s;", (claim_json,))
    try:
        cur.execute("SELECT auth.uid();")
        print("UID from auth.uid():", cur.fetchone())
    except Exception as e:
        print("Error:", e)
